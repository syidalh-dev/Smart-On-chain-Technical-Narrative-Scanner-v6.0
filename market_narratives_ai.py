import requests
from datetime import datetime
from main import send_telegram_message

def analyze_market_sentiment_ai():
    """
    🧠 تحليل ذكي يجمع بين:
    - السرديات النشطة (CoinGecko + CryptoPanic)
    - الزخم الفني البسيط (تحليل الاتجاهات السعرية)
    - توصية نهائية للاستثمار متوسط المدى
    """
    try:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        narratives = {}
        tracked_coins = set()
        insights = []
        tech_data = {}
        recommendation = ""

        # ==============================
        # 🟢 1. السرديات من CoinGecko
        # ==============================
        try:
            cg_events = requests.get("https://api.coingecko.com/api/v3/events", timeout=15).json()
            for e in cg_events.get("data", []):
                title = (e.get("title") or "").lower()
                desc = (e.get("description") or "").lower()
                for key in ["ai", "defi", "rwa", "gaming", "layer2", "meme", "social", "infra"]:
                    if key in title or key in desc:
                        narratives[key] = narratives.get(key, 0) + 1
        except Exception as e:
            print("⚠️ CoinGecko events fetch failed:", e)

        # ==============================
        # 🟣 2. الأخبار من CryptoPanic
        # ==============================
        try:
            panic = requests.get("https://cryptopanic.com/api/v1/posts/?filter=important", timeout=15).json()
            for news in panic.get("results", []):
                title = (news.get("title") or "").lower()
                for key in ["ai", "defi", "rwa", "layer2", "meme"]:
                    if key in title:
                        narratives[key] = narratives.get(key, 0) + 1
        except Exception as e:
            print("⚠️ CryptoPanic fetch failed:", e)

        if not narratives:
            print("⚙️ لا توجد سرديات نشطة حالياً.")
            return []

        # ==============================
        # 📊 3. ترتيب قوة السرديات
        # ==============================
        sorted_narr = sorted(narratives.items(), key=lambda x: x[1], reverse=True)
        strong_narrs = [k for k, v in sorted_narr if v >= 3]
        insights.append("🧠 <b>تحليل السرديات الذكي</b>")
        for k, v in sorted_narr:
            power = "🔥 قوي" if v >= 5 else "📈 متوسط" if v >= 3 else "💤 ضعيف"
            insights.append(f"• {k.upper()} — {power} ({v} mentions)")

        # ==============================
        # 🪙 4. تتبع العملات المرتبطة بالسرديات
        # ==============================
        try:
            cg_trending = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
            for coin in cg_trending.get("coins", []):
                name = coin["item"]["name"].lower()
                for narr in strong_narrs:
                    if narr in name or narr in (coin["item"].get("symbol", "").lower()):
                        tracked_coins.add(coin["item"]["id"])
        except Exception as e:
            print("⚠️ CoinGecko trending fetch failed:", e)

        # ==============================
        # 💹 5. التحليل الفني البسيط (CoinGecko Market Data)
        # ==============================
        for coin_id in list(tracked_coins)[:5]:
            try:
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true"
                data = requests.get(url, timeout=10).json()
                md = data.get("market_data", {})
                price_change_24h = md.get("price_change_percentage_24h", 0)
                price_change_7d = md.get("price_change_percentage_7d", 0)
                vol_change = md.get("total_volume", {}).get("usd", 0)
                tech_data[coin_id] = {
                    "price_24h": price_change_24h,
                    "price_7d": price_change_7d,
                    "volume": vol_change
                }
            except Exception as e:
                print(f"⚠️ Technical fetch failed for {coin_id}:", e)

        # ==============================
        # 📈 6. التوصية الذكية
        # ==============================
        avg_24h = sum([v["price_24h"] for v in tech_data.values()]) / max(1, len(tech_data))
        avg_7d = sum([v["price_7d"] for v in tech_data.values()]) / max(1, len(tech_data))

        if len(strong_narrs) >= 3 and avg_7d > 5:
            recommendation = "🟢 <b>شراء مبدئي</b> — زخم قوي وسرديات متناسقة."
        elif len(strong_narrs) >= 1 and avg_24h > 0:
            recommendation = "🟡 <b>راقب</b> — السرديات بدأت بالتحرك والسوق يتحسن تدريجياً."
        else:
            recommendation = "🔴 <b>انتظر</b> — لا توجد إشارات واضحة حالياً."

        # ==============================
        # 🕵️ 7. التقرير النهائي
        # ==============================
        message = f"""
📅 <b>تقرير السوق الذكي</b>
🕒 {now}

{"\n".join(insights)}

<b>📊 عملات مرتبطة بالسرديات النشطة:</b>
{', '.join([c.upper() for c in list(tracked_coins)[:10]]) or 'لا توجد حالياً'}

💹 <b>تحليل فني عام:</b>
📊 24h: {avg_24h:.2f}% | 7d: {avg_7d:.2f}%

💡 <b>التوصية:</b> {recommendation}
"""
        send_telegram_message(message)
        print(message)
        return insights

    except Exception as e:
        print("⚠️ analyze_market_sentiment_ai error:", e)
        return []
