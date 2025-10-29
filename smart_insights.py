import time
import requests
import statistics

# ==============================
# كشف تدفق الأموال الذكية (Smart Money Flow)
# ==============================
def detect_smart_money_flow(volume_now, volume_week_ago, price_7d_change, vol_ratio_threshold=2.5, price_limit=20.0):
    """
    تتحقق مما إذا كانت هناك زيادة كبيرة في حجم التداول
    دون ارتفاع مفرط في السعر (تجميع ذكي أو دخول مؤسسات).
    """
    try:
        if volume_week_ago <= 0:
            return False

        ratio = volume_now / max(1, volume_week_ago)
        # 📊 معيار التدفق الذكي:
        # ارتفاع الحجم >= 2.5x بينما السعر لم يرتفع أكثر من 20%
        if ratio >= vol_ratio_threshold and abs(price_7d_change) <= price_limit:
            return True
    except Exception:
        return False
    return False


# ==============================
# فحص وجود شراكات أو إدراجات حديثة (Partnerships)
# ==============================
def has_recent_partnerships(symbol):
    """
    يستخدم CoinGecko لاكتشاف أخبار الإدراج أو الشراكات الحديثة.
    """
    try:
        cg_url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower().replace('usdt','')}"
        data = requests.get(cg_url, timeout=10).json()

        last_update = data.get("last_updated", "")
        if not last_update:
            return False

        # إذا تم تحديث المشروع خلال الأيام الأخيرة => نشاط أو شراكة محتملة
        from datetime import datetime, timezone
        update_time = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
        days_since_update = (datetime.now(timezone.utc) - update_time).days

        if days_since_update <= 7:
            return True
    except Exception as e:
        print(f"⚠️ has_recent_partnerships error: {e}")
    return False


# ==============================
# نمو عدد الحاملين (Holders Growth)
# ==============================
_cache_holders = {}

def get_holders_growth(address_or_symbol):
    """
    تجمع تقدير عدد الحاملين من CoinGecko وDexTools وDeFiLlama
    وتحسب متوسط نمو تقريبي، مع تخزين مؤقت لتقليل الطلبات.
    """
    now = time.time()
    if address_or_symbol in _cache_holders:
        cached = _cache_holders[address_or_symbol]
        if now - cached["time"] < 3600:  # أقل من ساعة
            return cached["value"]

    growth_values = []

    # 🔹 DexTools API (تقدير مباشر للحاملين)
    try:
        dex_url = f"https://www.dextools.io/shared/data/pair-info?address={address_or_symbol}"
        dex_data = requests.get(dex_url, timeout=10).json()
        holders = dex_data.get("holders") or dex_data.get("data", {}).get("holders")
        if holders and isinstance(holders, (int, float)):
            growth_values.append(holders)
    except Exception as e:
        print(f"⚠️ DexTools holders fetch failed: {e}")

    # 🔹 CoinGecko (بيانات اجتماعية)
    try:
        cg_url = f"https://api.coingecko.com/api/v3/coins/{address_or_symbol.lower().replace('usdt','')}"
        cg_data = requests.get(cg_url, timeout=10).json()
        community = cg_data.get("community_data", {}).get("twitter_followers", 0)
        if community:
            growth_values.append(community)
    except Exception as e:
        print(f"⚠️ CoinGecko fetch failed: {e}")

    # 🔹 DeFiLlama (نمو المشاريع النشطة)
    try:
        defi_url = "https://api.llama.fi/protocols"
        defi_data = requests.get(defi_url, timeout=10).json()
        for protocol in defi_data:
            if address_or_symbol.lower().replace("usdt","") in str(protocol).lower():
                tvl = protocol.get("tvl", 0)
                if tvl:
                    growth_values.append(tvl)
                break
    except Exception as e:
        print(f"⚠️ DeFiLlama fetch failed: {e}")

    # 🧮 حساب متوسط ذكي للنتائج
    if len(growth_values) >= 2:
        avg_growth = statistics.mean(growth_values)
    elif growth_values:
        avg_growth = growth_values[0]
    else:
        avg_growth = 0

    _cache_holders[address_or_symbol] = {"value": avg_growth, "time": now}
    return avg_growth
