import requests
from main import send_telegram_message

def analyze_market_narratives_ai():
    """
    تحليل السرديات الشائعة في السوق بشكل خفيف وذكي
    عبر عدة مصادر مجانية.
    """
    try:
        sources = {}

        # 🔹 CoinGecko
        try:
            cg = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
            cg_coins = [c["item"]["name"].lower() for c in cg.get("coins", [])]
            sources["coingecko"] = cg_coins
        except Exception:
            sources["coingecko"] = []

        # 🔹 CoinPaprika (بديل CoinMarketCal)
        try:
            paprika = requests.get("https://api.coinpaprika.com/v1/coins", timeout=10).json()
            paprika_coins = [c["name"].lower() for c in paprika[:50]]
            sources["coinpaprika"] = paprika_coins
        except Exception:
            sources["coinpaprika"] = []

        all_text = " ".join(sum(sources.values(), []))
        keywords = ["ai", "defi", "rwa", "gaming", "layer2", "meme", "social", "infrastructure"]
        scores = {k: all_text.count(k) for k in keywords}
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]

        insights = [f"{k.upper()} 🔥 ({v} mentions)" for k, v in top if v > 0]

        if insights:
            message = "🧠 <b>السرديات النشطة</b>\n" + "\n".join(insights)
            send_telegram_message(message)
        return insights

    except Exception as e:
        print("⚠️ narrative_ai error:", e)
        return []
