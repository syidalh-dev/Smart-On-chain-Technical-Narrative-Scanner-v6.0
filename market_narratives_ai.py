import requests
from datetime import datetime
from main import send_telegram_message

def analyze_market_narratives_ai():
    """
    تحليل سرديات السوق باستخدام مصادر موثوقة
    (CoinMarketCap + CoinGecko + CoinMarketCal)
    دون الحاجة إلى مفاتيح API.
    """
    try:
        sources = {"cmc": [], "coingecko": [], "coinmarketcal": []}
        insights = []

        # --- CoinMarketCap ---
        try:
            cmc = requests.get(
                "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/trending",
                timeout=10
            ).json()
            cmc_coins = [c["name"].lower() for c in cmc.get("data", {}).get("coins", [])]
            sources["cmc"] = cmc_coins
        except Exception as e:
            print(f"⚠️ CoinMarketCap error: {e}")

        # --- CoinGecko ---
        try:
            cg = requests.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=10
            ).json()
            cg_coins = [c["item"]["name"].lower() for c in cg.get("coins", [])]
            sources["coingecko"] = cg_coins
        except Exception as e:
            print(f"⚠️ CoinGecko error: {e}")

        # --- CoinMarketCal (بديل آمن لـ CoinMarketCall) ---
        try:
            cmcal = requests.get(
                "https://api.coinmarketcal.com/v1/events?max=10",
                headers={"Accept": "application/json"},
                timeout=10
            ).json()
            events = cmcal.get("body") or cmcal.get("data") or []
            cal_events = [e.get("title", "").lower() for e in events if isinstance(e, dict)]
            sources["coinmarketcal"] = cal_events
        except Exception as e:
            print(f"⚠️ CoinMarketCal error: {e}")

        # جمع وتحليل السرديات
        all_text = " ".join(sum(sources.values(), []))
        keywords = ["ai", "defi", "rwa", "gaming", "layer2", "meme", "social", "infrastructure"]

        scores = {k: all_text.count(k) for k in keywords}
        top_narratives = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]

        insights = [f"{k.upper()} 🔥 ({v} mentions)" for k, v in top_narratives if v > 0]

        # إرسال تلغرام إذا وُجدت نتائج
        if insights:
            message = "🧠 <b>تحليل السرديات الذكي</b>\n" + "\n".join(insights)
            print(message)
            send_telegram_message(message)
        else:
            print("⚙️ لا توجد سرديات نشطة حالياً.")

        return insights

    except Exception as e:
        print("⚠️ Narrative AI analysis error:", e)
        return []
