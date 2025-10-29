import os
import time
import json
import requests
import traceback
from datetime import datetime, timedelta
from smart_insights import detect_smart_money_flow, has_recent_partnerships, get_holders_growth

# ==============================
# الإعدادات العامة
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
API_KEY = os.getenv("API_KEY", "YOUR_API_KEY")
SAVE_FILE = "smart_signals.json"

last_sentiment_update = datetime.utcnow() - timedelta(hours=6)

# ==============================
# تحليل الاتجاه العام للسوق
# ==============================
def get_market_sentiment():
    """تحليل الاتجاه العام للسوق من CoinMarketCap و CoinMarketCall"""
    sentiment_score = 0
    try:
        # من CoinMarketCap
        cmc_news = requests.get("https://api.coinmarketcap.com/content/v3/news", timeout=10).json()
        headlines = " ".join([n["meta"]["title"] for n in cmc_news.get("data", [])[:20]])

        # من CoinMarketCall
        cmc_call = requests.get("https://api.coinmarketcall.com/v1/analysis/latest", timeout=10).json()
        calls = " ".join([c.get("title", "") for c in cmc_call.get("data", [])[:20]])

        combined_text = headlines + " " + calls
        positive_words = ["bullish", "buy", "positive", "uptrend", "growth"]
        negative_words = ["bearish", "sell", "negative", "downtrend", "fear"]

        pos_count = sum(word in combined_text.lower() for word in positive_words)
        neg_count = sum(word in combined_text.lower() for word in negative_words)

        if pos_count > neg_count:
            sentiment_score = 0.2
            sentiment = "🟢 الاتجاه العام إيجابي"
        elif neg_count > pos_count:
            sentiment_score = -0.2
            sentiment = "🔴 الاتجاه العام سلبي"
        else:
            sentiment_score = 0.0
            sentiment = "⚪ الاتجاه العام محايد"

        print(f"📰 Market Sentiment Score: {sentiment_score} | {sentiment}")
        return sentiment_score, sentiment
    except Exception as e:
        print(f"⚠️ Market Sentiment error: {e}")
        return 0, "⚠️ تعذر تحديد الاتجاه العام للسوق"

# ==============================
# دوال مساعدة
# ==============================
def save_smart_signal(symbol, score, reason):
    """يحفظ الإشارات الذكية في ملف JSON"""
    data = []
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []

    entry = {
        "symbol": symbol,
        "score": round(score, 2),
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    }
    data.append(entry)
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_telegram_message(text):
    """إرسال رسالة إلى تيليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

def get_klines(symbol="BTCUSDT", interval="1h", limit=100):
    """جلب بيانات الشموع من Binance"""
    try:
        url = f"https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return [{
            "t": float(i[0]),
            "o": float(i[1]),
            "h": float(i[2]),
            "l": float(i[3]),
            "c": float(i[4]),
            "v": float(i[5])
        } for i in data]
    except Exception as e:
        print(f"⚠️ Binance error: {e}")
        return []

# ==============================
# دالة التقييم الرئيسية
# ==============================
def score_coin_light(symbol="BTCUSDT"):
    global last_sentiment_update
    try:
        kl = get_klines(symbol)
        if not kl:
            print(f"⚠️ لا توجد بيانات للرمز {symbol}")
            return None

        kl_df = {k: [i[k] for i in kl] for k in kl[0].keys()}
        tech_score = 0
        social_score = 0
        onchain_score = 0

        # 🔍 تحديث الاتجاه العام للسوق كل 6 ساعات فقط
        if (datetime.utcnow() - last_sentiment_update).total_seconds() > 6 * 3600:
            market_sentiment_score, sentiment_text = get_market_sentiment()
            send_telegram_message(f"🧭 <b>تحديث الاتجاه العام للسوق</b>\n{sentiment_text}")
            last_sentiment_update = datetime.utcnow()
        else:
            market_sentiment_score, _ = get_market_sentiment()

        if market_sentiment_score > 0:
            social_score += 0.1
        elif market_sentiment_score < 0:
            social_score -= 0.1

        # 🔍 Smart Insights
        try:
            vol_series = kl_df["v"]
            close_series = kl_df["c"]
            volume_now = float(vol_series[-1])
            volume_week_ago = float(vol_series[-24]) if len(vol_series) > 24 else 0.0
            price_7d_change = ((close_series[-1] - close_series[-24]) / max(1, close_series[-24])) * 100 if len(close_series) > 24 else 0.0

            if detect_smart_money_flow(volume_now, volume_week_ago, price_7d_change):
                tech_score += 0.2
                save_smart_signal(symbol, tech_score, "🧠 تدفق أموال ذكي")

            if has_recent_partnerships(symbol):
                social_score += 0.2
                save_smart_signal(symbol, social_score, "🤝 شراكات جديدة")

            holders_growth = get_holders_growth("0x0000000000000000000000000000000000000000")
            if holders_growth and holders_growth > 1000:
                onchain_score += 0.2
                save_smart_signal(symbol, onchain_score, "👥 نمو الحاملين")

        except Exception as e:
            print(f"⚠️ smart_insights integration error for {symbol}: {e}")

        # 📈 التحليل الفني القوي
        closes = kl_df["c"]
        if len(closes) >= 50:
            ma20 = sum(closes[-20:]) / 20
            ma50 = sum(closes[-50:]) / 50
            if ma20 > ma50:
                tech_score += 0.15

            gains = [closes[i+1] - closes[i] for i in range(len(closes)-1) if closes[i+1] > closes[i]]
            losses = [closes[i] - closes[i+1] for i in range(len(closes)-1) if closes[i+1] < closes[i]]
            avg_gain = sum(gains[-14:]) / max(1, len(gains[-14:]))
            avg_loss = sum(losses[-14:]) / max(1, len(losses[-14:]))
            rsi = 100 - (100 / (1 + (avg_gain / max(1e-6, avg_loss))))
            if rsi > 55:
                tech_score += 0.15
            elif rsi < 40:
                tech_score -= 0.1

        total_score = tech_score + social_score + onchain_score
        total_score = max(0, min(total_score, 1.0))

        # 🔖 تصنيف الفرصة + المدة المقترحة
        if total_score >= 0.7:
            label = "🚀 قوية جدًا (استثمار 1–2 أسبوع)"
            suggested_holding = "احتفظ من 7 إلى 14 يوم"
        elif total_score >= 0.4:
            label = "📈 متوسطة (فرصة محتملة)"
            suggested_holding = "احتفظ من 3 إلى 7 أيام"
        else:
            label = "⚠️ ضعيفة (للمراقبة فقط)"
            suggested_holding = "راقب فقط، لا تدخل الآن"

        print(f"✅ {symbol} => Score: {round(total_score, 2)} | {label} | {suggested_holding}")

        send_telegram_message(
            f"{label}\n"
            f"رمز: {symbol}\n"
            f"النتيجة: {round(total_score,2)}\n"
            f"⏳ <b>{suggested_holding}</b>"
        )

        save_smart_signal(symbol, total_score, f"{label} - {suggested_holding}")
        return total_score

    except Exception as e:
        print(f"❌ خطأ في تقييم {symbol}: {e}")
        traceback.print_exc()
        return None

# ==============================
# التشغيل الرئيسي
# ==============================
if __name__ == "__main__":
    print("🔔 تم تشغيل النظام بنجاح 👁️‍🗨️✅ Smart AI Scanner يعمل الآن ويبدأ بمراقبة الفرص.")
    while True:
        try:
            score_coin_light("BTCUSDT")
            score_coin_light("ETHUSDT")
            time.sleep(60 * 10)
        except KeyboardInterrupt:
            print("⏹️ تم إيقاف النظام يدويًا.")
            break
        except Exception as e:
            print("⚠️ خطأ في الدورة:", e)
            time.sleep(30)
