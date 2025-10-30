import os
import time
import json
import requests
import traceback
import zoneinfo
from datetime import datetime, timedelta
from smart_insights import detect_smart_money_flow, has_recent_partnerships, get_holders_growth

# ==============================
# الإعدادات العامة
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
SAVE_FILE = "smart_signals.json"
WATCHLIST_FILE = "watchlist.json"

LOCAL_TZ = zoneinfo.ZoneInfo("Africa/Tripoli")
last_sentiment_update = datetime.utcnow() - timedelta(hours=6)
LAST_DAILY_SEND = None

MONITOR_DAYS = 3
DAILY_SEND_HOUR = 6

# ==============================
# أدوات مساعدة للتوقيت والتخزين
# ==============================
def now_local():
    return datetime.now(LOCAL_TZ)

def load_json(path):
    if os.path.exists(path):
        try:
            return json.load(open(path, "r", encoding="utf-8"))
        except Exception:
            return []
    return []

def save_json(path, data):
    try:
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        print("⚠️ save_json error:", e)

# ==============================
# دوال مساعدة عامة
# ==============================
def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("⚠️ Telegram error:", e)

def get_klines(symbol="BTCUSDT", interval="1h", limit=100):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return [{"t": float(i[0]), "o": float(i[1]), "h": float(i[2]),
                 "l": float(i[3]), "c": float(i[4]), "v": float(i[5])} for i in data]
    except Exception as e:
        print(f"⚠️ Binance error: {e}")
        return []

# ==============================
# تحليل الاتجاه العام للسوق
# ==============================
def get_market_sentiment():
    sentiment_score = 0
    try:
        cmc_news = requests.get("https://api.coinmarketcap.com/content/v3/news", timeout=10).json()
        headlines = " ".join([n["meta"]["title"] for n in cmc_news.get("data", [])[:20]])
        try:
            cmc_call = requests.get("https://api.coinmarketcall.com/v1/analysis/latest", timeout=10).json()
            calls = " ".join([c.get("title", "") for c in cmc_call.get("data", [])[:20]])
        except Exception as e:
            print(f"⚠️ CoinMarketCall error fallback: {e}")
            calls = ""
        combined_text = (headlines + " " + calls).lower()
        pos_words = ["bullish", "buy", "positive", "uptrend", "growth"]
        neg_words = ["bearish", "sell", "negative", "downtrend", "fear"]
        pos = sum(w in combined_text for w in pos_words)
        neg = sum(w in combined_text for w in neg_words)
        if pos > neg:
            sentiment_score, sentiment = 0.2, "🟢 الاتجاه العام إيجابي"
        elif neg > pos:
            sentiment_score, sentiment = -0.2, "🔴 الاتجاه العام سلبي"
        else:
            sentiment_score, sentiment = 0.0, "⚪ الاتجاه العام محايد"
        print(f"📰 Market Sentiment: {sentiment_score} | {sentiment}")
        return sentiment_score, sentiment
    except Exception as e:
        print("⚠️ Market Sentiment error:", e)
        return 0, "⚠️ تعذر تحليل السوق"

# ==============================
# إدارة المراقبة Watchlist
# ==============================
def add_to_watchlist(symbol, score, investment_duration):
    w = load_json(WATCHLIST_FILE)
    for x in w:
        if x["symbol"] == symbol:
            x["last_score"] = score
            x["investment_duration"] = investment_duration
            x["monitor_cycles"] = x.get("monitor_cycles", 0) + 1
            x["last_seen"] = now_local().isoformat()
            save_json(WATCHLIST_FILE, w)
            return
    w.append({
        "symbol": symbol,
        "added_at": now_local().isoformat(),
        "monitor_cycles": 1,
        "last_score": score,
        "investment_duration": investment_duration,
        "last_seen": now_local().isoformat()
    })
    save_json(WATCHLIST_FILE, w)

def prune_watchlist():
    w = load_json(WATCHLIST_FILE)
    new_w, now_t = [], now_local()
    for x in w:
        added = datetime.fromisoformat(x["added_at"])
        if (now_t - added).days >= MONITOR_DAYS and x.get("last_score", 0) < 0.5:
            print(f"🧹 إزالة {x['symbol']} بعد {MONITOR_DAYS} أيام دون تحسن.")
            continue
        new_w.append(x)
    save_json(WATCHLIST_FILE, new_w)

# ==============================
# إرسال تقرير صباحي الساعة 6
# ==============================
def maybe_send_daily_summary():
    global LAST_DAILY_SEND
    now = now_local()
    today = now.date().isoformat()
    if now.hour >= DAILY_SEND_HOUR and LAST_DAILY_SEND != today:
        signals = load_json(SAVE_FILE)
        day_ago = (now - timedelta(days=1)).isoformat()
        recent = [s for s in signals if s.get("timestamp", "") >= day_ago]
        if not recent:
            msg = "📰 ملخص اليوم: لا توجد إشارات جديدة خلال الـ24 ساعة الماضية."
        else:
            msg = "📰 <b>ملخص اليوم</b>\n\n"
            for r in sorted(recent, key=lambda x: x.get("score", 0), reverse=True)[:10]:
                label = "🚀" if r["score"] >= 0.7 else "📈" if r["score"] >= 0.4 else "⚠️"
                duration = "7–14 يوم" if r["score"] >= 0.7 else "3–7 أيام" if r["score"] >= 0.4 else "مراقبة"
                msg += f"{label} {r['symbol']} | درجة: {r['score']*100:.0f}% | مدة الاستثمار: {duration}\n"
        send_telegram_message(msg)
        LAST_DAILY_SEND = today
        print("✅ تم إرسال تقرير صباحي.")

# ==============================
# التحليل الفني والذكاء الاصطناعي
# ==============================
def score_coin_light(symbol="BTCUSDT"):
    global last_sentiment_update
    try:
        kl = get_klines(symbol)
        if not kl:
            print(f"⚠️ لا توجد بيانات للرمز {symbol}")
            return None

        kl_df = {k: [i[k] for i in kl] for k in kl[0].keys()}
        tech_score, social_score, onchain_score = 0, 0, 0

        if (datetime.utcnow() - last_sentiment_update).total_seconds() > 6 * 3600:
            market_score, sentiment_text = get_market_sentiment()
            send_telegram_message(f"🧭 <b>تحديث السوق</b>\n{sentiment_text}")
            last_sentiment_update = datetime.utcnow()
        else:
            market_score, _ = get_market_sentiment()

        if market_score > 0:
            social_score += 0.1
        elif market_score < 0:
            social_score -= 0.1

        vol = kl_df["v"]
        closes = kl_df["c"]
        if len(closes) < 50:
            return None

        v_now = float(vol[-1])
        v_prev = float(vol[-24]) if len(vol) > 24 else 0.0
        p_change = ((closes[-1] - closes[-24]) / max(1, closes[-24])) * 100

        if detect_smart_money_flow(v_now, v_prev, p_change):
            tech_score += 0.2
        if has_recent_partnerships(symbol):
            social_score += 0.2
        holders_growth = get_holders_growth(symbol)
        if holders_growth and holders_growth > 1000:
            onchain_score += 0.2

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

        total = max(0, min(tech_score + social_score + onchain_score, 1.0))

        if total >= 0.7:
            label, hold = "🚀 قوية جدًا (استثمار 1–2 أسبوع)", "7–14 يوم"
        elif total >= 0.4:
            label, hold = "📈 متوسطة (فرصة محتملة)", "3–7 أيام"
        else:
            label, hold = "⚠️ ضعيفة (للمراقبة فقط)", "مراقبة"

        add_to_watchlist(symbol, total, hold)

        msg = f"{label}\nرمز: {symbol}\nالنتيجة: {total:.2f}\n⏳ <b>مدة الاستثمار:</b> {hold}"
        print(f"✅ {symbol} | {total:.2f} | {label}")

        if total >= 0.7:
            send_telegram_message(msg)

        data = load_json(SAVE_FILE)
        data.append({"symbol": symbol, "score": round(total, 2),
                     "timestamp": datetime.utcnow().isoformat(),
                     "investment_duration": hold})
        save_json(SAVE_FILE, data)
        return total

    except Exception as e:
        print("❌ خطأ:", e)
        traceback.print_exc()
        return None

# ==============================
# الحلقة الرئيسية
# ==============================
def main_loop():
    print("🔔 Smart AI Scanner يعمل الآن ✅")
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT"]
    while True:
        try:
            for sym in symbols:
                score_coin_light(sym)
                time.sleep(5)
            prune_watchlist()
            maybe_send_daily_summary()
            time.sleep(6 * 3600)  # ⏰ كل 6 ساعات تحليل جديد
        except KeyboardInterrupt:
            print("⏹️ تم إيقاف النظام يدويًا.")
            break
        except Exception as e:
            print("⚠️ خطأ في الدورة:", e)
            time.sleep(30)

if __name__ == "__main__":
    main_loop()
