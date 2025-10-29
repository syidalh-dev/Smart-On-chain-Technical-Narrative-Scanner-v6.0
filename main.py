import os
import time
import json
import requests
import traceback
from datetime import datetime
from smart_insights import detect_smart_money_flow, has_recent_partnerships, get_holders_growth

# ==============================
# الإعدادات العامة
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
API_KEY = os.getenv("API_KEY", "YOUR_API_KEY")
SAVE_FILE = "smart_signals.json"

# ==============================
# الدوال المساعدة
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
    try:
        kl = get_klines(symbol)
        if not kl:
            print(f"⚠️ لا توجد بيانات للرمز {symbol}")
            return None

        kl_df = {k: [i[k] for i in kl] for k in kl[0].keys()}
        tech_score = 0
        social_score = 0
        onchain_score = 0

        # ---------------------------------------------
        # 🔍 Smart Insights Integration (تحليل ذكي إضافي)
        # ---------------------------------------------
        try:
            vol_series = kl_df["v"]
            close_series = kl_df["c"]

            volume_now = float(vol_series[-1]) if len(vol_series) > 0 else 0.0
            volume_week_ago = float(vol_series[-24]) if len(vol_series) > 24 else 0.0
            price_7d_change = ((close_series[-1] - close_series[-24]) / max(1, close_series[-24])) * 100 if len(close_series) > 24 else 0.0

            # تدفق الأموال الذكي
            if detect_smart_money_flow(volume_now, volume_week_ago, price_7d_change):
                tech_score += 0.2
                save_smart_signal(symbol, tech_score, "🧠 تدفق أموال ذكي")
                print(f"🧠 Smart money flow detected for {symbol}")

            # الشراكات الحديثة
            if has_recent_partnerships(symbol):
                social_score += 0.2
                save_smart_signal(symbol, social_score, "🤝 شراكات جديدة")
                print(f"🤝 New partnerships detected for {symbol}")

            # نمو عدد الحاملين
            holders_growth = get_holders_growth("0x0000000000000000000000000000000000000000")
            if holders_growth and holders_growth > 1000:
                onchain_score += 0.2
                save_smart_signal(symbol, onchain_score, "👥 نمو الحاملين")
                print(f"👥 Holders growth signal for {symbol}")

        except Exception as e:
            print(f"⚠️ smart_insights integration error for {symbol}: {e}")

        # ---------------------------------------------
        # 📈 تحليل فني بسيط (تأكيد إضافي)
        # ---------------------------------------------
        closes = kl_df["c"]
        if len(closes) >= 50:
            ma20 = sum(closes[-20:]) / 20
            ma50 = sum(closes[-50:]) / 50
            if ma20 > ma50:
                tech_score += 0.1
            rsi = 55  # مثال ثابت مؤقتاً
            if rsi > 55:
                tech_score += 0.1

        # مجموع النقاط
        total_score = tech_score + social_score + onchain_score
        print(f"✅ {symbol} => Score: {round(total_score, 2)}")

        # إرسال الفرص القوية فقط
        if total_score >= 0.5:
            send_telegram_message(f"🚀 فرصة قوية: {symbol}\nالنتيجة: {round(total_score,2)}")
            save_smart_signal(symbol, total_score, "🚀 فرصة قوية")

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
            time.sleep(60 * 10)  # فحص كل 10 دقائق
        except KeyboardInterrupt:
            print("⏹️ تم إيقاف النظام يدويًا.")
            break
        except Exception as e:
            print("⚠️ خطأ في الدورة:", e)
            time.sleep(30)
