import os
import time
import json
import requests
import traceback
import zoneinfo
from datetime import datetime, timedelta
from smart_insights import detect_smart_money_flow, has_recent_partnerships, get_holders_growth
from narrative_ai import analyze_market_narratives_ai  # ← إضافة السرديات

# ==============================
# الإعدادات العامة
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
SAVE_FILE = "smart_signals.json"
WATCHLIST_FILE = "watchlist.json"

LOCAL_TZ = zoneinfo.ZoneInfo("Africa/Tripoli")
LAST_SENTIMENT_UPDATE = datetime.utcnow() - timedelta(hours=6)
LAST_DAILY_SEND = None

MONITOR_DAYS = 3
DAILY_SEND_HOUR = 6

# ==============================
# أدوات مساعدة
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

def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("⚠️ Telegram error:", e)

# ==============================
# تحليل السوق
# ==============================
def get_market_sentiment():
    try:
        news = requests.get("https://api.coinmarketcap.com/content/v3/news", timeout=10).json()
        headlines = " ".join([n["meta"]["title"] for n in news.get("data", [])[:20]])

        try:
            cmcal = requests.get("https://developers.coinpaprika.com/v1/events", timeout=10).json()
            calls = " ".join([c.get("title", "") for c in cmcal[:20]])
        except Exception as e:
            print(f"⚠️ CoinPaprika fallback: {e}")
            calls = ""

        combined = (headlines + " " + calls).lower()
        pos = sum(w in combined for w in ["bullish", "buy", "positive", "uptrend"])
        neg = sum(w in combined for w in ["bearish", "sell", "negative", "downtrend"])

        if pos > neg:
            return 0.2, "🟢 الاتجاه العام إيجابي"
        elif neg > pos:
            return -0.2, "🔴 الاتجاه العام سلبي"
        return 0.0, "⚪ الاتجاه العام محايد"
    except Exception as e:
        print("⚠️ Market Sentiment error:", e)
        return 0, "⚠️ تعذر تحليل السوق"

# ==============================
# إرسال تقرير صباحي مرة واحدة
# ==============================
def maybe_send_daily_summary():
    global LAST_DAILY_SEND
    now = now_local()
    today = now.date().isoformat()
    if now.hour >= DAILY_SEND_HOUR and LAST_DAILY_SEND != today:
        signals = load_json(SAVE_FILE)
        day_ago = (now - timedelta(days=1)).isoformat()
        recent = [s for s in signals if s.get("timestamp", "") >= day_ago]

        msg = "📰 <b>ملخص اليوم</b>\n\n"
        if not recent:
            msg += "لا توجد إشارات جديدة خلال 24 ساعة.\n"
        else:
            for r in sorted(recent, key=lambda x: x.get("score", 0), reverse=True)[:10]:
                label = "🚀" if r["score"] >= 0.7 else "📈" if r["score"] >= 0.4 else "⚠️"
                msg += f"{label} {r['symbol']} | درجة: {r['score']*100:.0f}%\n"

        # إضافة السرديات اليومية
        narratives = analyze_market_narratives_ai()
        if narratives:
            msg += "\n🧠 <b>أهم السرديات:</b>\n" + "\n".join(narratives)

        send_telegram_message(msg)
        LAST_DAILY_SEND = today
        print("✅ تم إرسال التقرير الصباحي.")

# ==============================
# الحلقة الرئيسية
# ==============================
def main_loop():
    print("🚀 Smart AI Scanner يعمل (تحليل كل 6 ساعات)")

    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"]
    while True:
        try:
            for sym in symbols:
                print(f"تحليل {sym} ...")
                time.sleep(3)

            maybe_send_daily_summary()
            print("🕕 الانتظار 6 ساعات قبل الدورة القادمة...")
            time.sleep(6 * 3600)

        except Exception as e:
            print("⚠️ main_loop error:", e)
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    main_loop()
