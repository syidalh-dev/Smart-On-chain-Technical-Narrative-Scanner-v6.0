# smart_insights.py
import time
import requests
import statistics

_cache_holders = {}

def detect_smart_money_flow(volume_now, volume_week_ago, price_7d_change, vol_ratio_threshold=3.0, price_limit=20.0):
    try:
        if volume_week_ago <= 0:
            return False
        ratio = volume_now / max(1, volume_week_ago)
        if ratio >= vol_ratio_threshold and abs(price_7d_change) <= price_limit:
            return True
    except Exception:
        return False
    return False

def has_recent_partnerships(symbol):
    return False


def get_holders_growth(address_or_symbol):
    """
    🔹 يجلب نمو عدد الحاملين من عدة مصادر (خفيفة وآمنة):
    DexTools, CoinGecko, DeFiLlama, CoinMarketCap, Etherscan/BscScan.
    """
    now = time.time()
    if address_or_symbol in _cache_holders:
        cached = _cache_holders[address_or_symbol]
        if now - cached["time"] < 3600:  # أقل من ساعة
            return cached["value"]

    growth_values = []

    # 🔹 DexTools
    try:
        dex_url = f"https://www.dextools.io/shared/data/pair-info?address={address_or_symbol}"
        dex_data = requests.get(dex_url, timeout=10).json()
        holders = dex_data.get("holders") or dex_data.get("data", {}).get("holders")
        if holders and isinstance(holders, (int, float)):
            growth_values.append(holders)
    except Exception as e:
        print(f"⚠️ DexTools holders fetch failed: {e}")

    # 🔹 CoinGecko
    try:
        cg_url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{address_or_symbol}"
        cg_data = requests.get(cg_url, timeout=10).json()
        holders = cg_data.get("market_data", {}).get("holders", 0)
        if holders:
            growth_values.append(holders)
        else:
            community = cg_data.get("community_data", {}).get("twitter_followers", 0)
            if community:
                growth_values.append(community)
    except Exception as e:
        print(f"⚠️ CoinGecko fetch failed: {e}")

    # 🔹 DeFiLlama
    try:
        defi_url = "https://api.llama.fi/protocols"
        defi_data = requests.get(defi_url, timeout=10).json()
        for protocol in defi_data:
            if address_or_symbol.lower() in str(protocol).lower():
                tvl = protocol.get("tvl", 0)
                if tvl:
                    growth_values.append(tvl)
                break
    except Exception as e:
        print(f"⚠️ DeFiLlama fetch failed: {e}")

    # 🔹 CoinMarketCap (بيانات تقريبية عبر scraping بسيط)
    try:
        cmc_url = f"https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail?slug={address_or_symbol}"
        cmc_data = requests.get(cmc_url, timeout=10).json()
        holders = cmc_data.get("data", {}).get("statistics", {}).get("holderCount", 0)
        if holders:
            growth_values.append(holders)
    except Exception as e:
        print(f"⚠️ CoinMarketCap fetch failed: {e}")

    # 🔹 Etherscan / BscScan (تقديري)
    try:
        if address_or_symbol.startswith("0x"):
            chain_api = "https://api.etherscan.io/api"
            params = {
                "module": "token",
                "action": "tokenholderlist",
                "contractaddress": address_or_symbol,
                "page": 1,
                "offset": 1,
                "apikey": "YourApiKeyToken"
            }
            resp = requests.get(chain_api, params=params, timeout=10).json()
            if "result" in resp and isinstance(resp["result"], list):
                holders_count = len(resp["result"])
                if holders_count:
                    growth_values.append(holders_count)
    except Exception as e:
        print(f"⚠️ Etherscan holders fetch failed: {e}")

    # 🧮 حساب المتوسط الذكي
    if len(growth_values) >= 2:
        avg_growth = statistics.mean(growth_values)
    elif growth_values:
        avg_growth = growth_values[0]
    else:
        avg_growth = 0

    _cache_holders[address_or_symbol] = {"value": avg_growth, "time": now}
    return avg_growth
