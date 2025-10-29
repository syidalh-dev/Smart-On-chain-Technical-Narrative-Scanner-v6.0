import requests
from datetime import datetime
from main import send_telegram_message

def analyze_market_narratives_ai():
    """
    تحليل سرديات السوق باستخدام ذكاء اصطناعي خفيف مدمج
    دون استهلاك موارد خارجية أو واجهات مدفوعة.
    """
    try:
        sources = {}
        insights = []

        # --- CoinMarketCap ---
        try:
            cmc = requests.get(
                "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/trending",
                timeout=10
            ).json()
            cmc_coins = [c["name"].lower() for c in cmc["data"]["coins"]]
            sources["cmc"] = cmc_coins
        except Exception:
            sources["cmc"] = []

        # --- CoinGecko ---
        try:
            cg = requests.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=10
            ).json()
            cg_coins = [c["item"]["name"].lower() for c in cg.get("coins", [])]
            sources["coingecko"] = cg_coins
        except Exception:
            sources["coingecko"] = []

        # --- CoinMarketCal ---
        try:
            cmcal = requests.get(
                "https://developers.coinmarketcal.com/v1/events?max=10",
                timeout=10
            ).json()
            cal_events = [e["title"].lower() for e in cmcal.get("body", [])]
            sources["coinmarketcal"] = cal_events
        except Exception:
            sources["coinmarketcal"] = []

        # جمع وتحليل السرديات
        all_text = " ".join(sum(sources.values(), []))
        keywords = ["ai", "defi", "rwa", "gaming", "layer2", "meme", "social", "infrastructure"]

        scores = {k: all_text.count(k) for k in keywords}
        top_narratives = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]

        insights = [f"{k.upper()} 🔥 ({v} mentions)" for k, v in top_narratives if v > 0]

        # إرسال تلغرام
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
