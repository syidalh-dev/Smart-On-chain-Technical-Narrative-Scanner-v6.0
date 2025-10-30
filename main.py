import time
import json
import requests
import statistics
from datetime import datetime, timedelta, timezone
from market_sentiment_ai import analyze_market_sentiment_ai
from smart_money import detect_smart_money_flow, get_holders_growth, has_recent_partnerships

# ==============================
# إعدادات عامة
# ==============================
WATCHLIST_FILE = "watchlist.json"
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

# ==============================
# أدوات مساعدة
# ==============================
def now_local():
    return datetime.now(timezone.utc)

def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("⚠️ Telegram send error:", e)

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==============================
# التحليل الفني الذكي
# ==============================
def analyze_coin(coin_id):
    """
    تحليل فني أساسي (CoinGecko) + مؤشرات نمو + تدفق الأموال
    """
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true"
        data = requests.get(url, timeout=10).json()
        md = data.get("market_data", {})
        price = md.get("current_price", {}).get("usd", 0)
        vol_now = md.get("total_volume", {}).get("usd", 0)
        price_7d = md.get("price_change_percentage_7d", 0)
        price_24h = md.get("price_change_percentage_24h", 0)

        # تحليل الذكاء الاصطناعي الذكي للسلوك السعري
        vol_prev = vol_now / 3 if vol_now else 0
        smart_flow = detect_smart_money_flow(vol_now, vol_prev, price_7d)
        holders_growth = get_holders_growth(coin_id)
        partnership = has_recent_partnerships(coin_id)

        score = 0
        if smart_flow: score += 2
        if holders_growth > 0: score += 1
        if partnership: score += 1
        if price_7d > 5: score += 1
        if price_24h > 0: score += 0.5

        duration = "قصيرة (3-5 أيام)" if price_7d > 10 else \
                   "متوسطة (7-14 يوم)" if smart_flow else \
                   "طويلة (15-30 يوم)"

        return {
            "coin": coin_id,
            "price": price,
            "score": round(score, 2),
            "duration": duration,
            "holders_growth": round(holders_growth, 2),
            "smart_flow": smart_flow,
            "partnership": partnership,
            "price_7d": price_7d,
            "price_24h": price_24h
        }
    except Exception as e:
        print(f"⚠️ analyze_coin error for {coin_id}: {e}")
        return None

# ==============================
# دورة التحليل الكاملة
# ==============================
def main_loop():
    print("🚀 بدء التحليل الذكي للسوق ...")
    watchlist = load_json(WATCHLIST_FILE)
    results = []

    # تحليل السرديات والأخبار العامة
    narratives = analyze_market_sentiment_ai()
    if not narratives:
        print("⚙️ لا توجد سرديات نشطة حالياً.")
        return

    # تحليل كل عملة في السرديات النشطة
    for narr in narratives:
        try:
            coins = ["bitcoin", "ethereum", "solana", "injective-protocol", "render-token", "celestia"]
            for c in coins:
                info = analyze_coin(c)
                if info and info["score"] >= 2.5:
                    results.append(info)
                    watchlist.append({
                        "coin": c,
                        "ts": now_local().isoformat(),
                        "score": info["score"],
                        "duration": info["duration"]
                    })
        except Exception as e:
            print("⚠️ Narrative coin scan error:", e)

    # حفظ النتائج
    save_json(WATCHLIST_FILE, watchlist)

    # إرسال النتائج
    if results:
        message = "📊 <b>نتائج التحليل الذكي (كل 6 ساعات)</b>\n\n"
        for r in results:
            message += f"• {r['coin'].upper()} — {r['duration']} 🕒\n"
            message += f"  💹 7d: {r['price_7d']}% | 24h: {r['price_24h']}%\n"
            message += f"  💧 Smart Flow: {r['smart_flow']} | Holders↑: {r['holders_growth']}\n\n"
        send_telegram_message(message)
        print(message)
    else:
        print("📭 لا توجد فرص واضحة حالياً.")

# ==============================
# جدولة العمل التلقائي
# ==============================
def scheduler():
    while True:
        now = datetime.now().time()

        # تحليل السوق كل 6 ساعات
        main_loop()

        # تقرير صباحي 6:00
        if now.hour == 6:
            send_telegram_message("🌅 <b>تقرير السوق الصباحي</b> تم توليده تلقائياً ✅")

        time.sleep(6 * 3600)  # كل 6 ساعات


if __name__ == "__main__":
    print("🤖 تشغيل Smart AI Market Scanner ...")
    scheduler()
