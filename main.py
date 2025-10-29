# -*- coding: utf-8 -*-
"""
main.py — Smart AI Scanner v7.3 (narrative_strength + light TF boost)
تحسينات:
- أضفنا narrative_strength وخفضنا استهلاك الموارد
- تقوية التحليل الفني بخوارزميات EMA/MACD خفيفة
- دمج آمن مع smart_insights (اختياري)
- لا تغير في المنطق العام (قوائم، حفظ، إرسال تلغرام)
"""

import os
import time
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, UTC

# ----------------------------- #
# إعدادات / متغيرات            #
# ----------------------------- #
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
CMC_API_KEY = os.getenv("CMC_API_KEY", "")

MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", "50000000"))
MIN_VOLUME_USD = float(os.getenv("MIN_VOLUME_USD", "2000"))
SLEEP_MINUTES = float(os.getenv("SLEEP_MINUTES", "30"))

MARKET_FILE = "market_data.json"
WATCHLIST_FILE = "watchlist.json"
SIGNALS_FILE = "signals_history.json"
SMART_SIGNALS_FILE = "smart_signals.json"

TOP_K = 5
STRONG_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.70

DEX_PAIR_LIMIT = 40
DEFILLAMA_LIMIT = 40
DEX_MIN_VOL_FOR_REAL = 50000
DEFI_TVL_MIN_FOR_REAL = 1_000_000

# Narrative keywords (موسعة قليلاً)
NARRATIVE_KEYWORDS = {
    "AI": ["ai", "artificial intelligence", "machine learning", "llm", "genai", "render", "fet"],
    "DeFi": ["defi", "liquidity", "staking", "lending", "dex", "swap", "yield"],
    "Gaming": ["game", "gaming", "gamefi", "metaverse"],
    "RWA": ["real-world", "real world", "rwa"],
    "Layer2": ["layer2", "rollup", "zk", "optimism", "arbitrum"],
    "Meme": ["meme", "dog", "shib", "woof"]
}

# Try to import optional smart_insights helpers (if provided)
try:
    from smart_insights import detect_smart_money_flow, has_recent_partnerships, get_holders_growth
    SMART_INSIGHTS_AVAILABLE = True
except Exception:
    SMART_INSIGHTS_AVAILABLE = False

# ----------------------------- #
# Utilities                     #
# ----------------------------- #
def now_ts():
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

def http_get(url, params=None, headers=None, timeout=12):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(now_ts(), "⚠️ Error saving", filename, e)

def load_json(filename):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def send_telegram_message_ar(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(now_ts(), "⚠️ Telegram keys missing")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(now_ts(), "⚠️ Telegram exception:", e)
        return False

# ----------------------------- #
# Technical indicators (light)  #
# ----------------------------- #
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.rolling(window=period, min_periods=period).mean()
    ma_down = down.rolling(window=period, min_periods=period).mean()
    rs = ma_up / (ma_down.replace(0, 1e-10))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def compute_macd(series, fast=12, slow=26, signal=9):
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

# ----------------------------- #
# Fetchers                      #
# ----------------------------- #
def fetch_cmc_listings(limit=100):
    if not CMC_API_KEY:
        return pd.DataFrame()
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"limit": limit, "convert": "USD"}
    j = http_get(url, params=params, headers=headers)
    if not j:
        return pd.DataFrame()
    df = pd.DataFrame(j.get("data", []))
    df["symbol"] = df["symbol"].astype(str).str.upper()
    # normalize columns used later
    def q_get(q, k, default=0):
        try:
            return q.get("USD", {}).get(k, default) if isinstance(q, dict) else default
        except Exception:
            return default
    df["price"] = df["quote"].apply(lambda q: q_get(q, "price", 0))
    df["market_cap"] = df["quote"].apply(lambda q: q_get(q, "market_cap", 0))
    df["volume_24h"] = df["quote"].apply(lambda q: q_get(q, "volume_24h", 0))
    df["name"] = df.get("name", "")
    return df

def fetch_binance_klines(symbol="BTCUSDT", interval="4h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    j = http_get(url, params=params)
    if not j or not isinstance(j, list):
        return None
    cols = ["t","o","h","l","c","v","_1","_2","_3","_4","_5","_6"]
    df = pd.DataFrame(j, columns=cols)
    df["c"] = pd.to_numeric(df["c"], errors="coerce")
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    return df

def fetch_dexscreener_pairs(limit_pairs=DEX_PAIR_LIMIT):
    url = "https://api.dexscreener.com/latest/dex/tokens"
    j = http_get(url)
    out = []
    if not j or "pairs" not in j:
        return out
    for p in j["pairs"][:limit_pairs]:
        try:
            base = p.get("baseToken", {}) or {}
            symbol = (base.get("symbol") or "").upper()
            vol = float(p.get("volume", {}).get("h24", 0) or 0)
            price_change = 0.0
            if isinstance(p.get("priceChange"), dict):
                price_change = float(p["priceChange"].get("h24", 0) or 0)
            out.append({
                "symbol": symbol,
                "volume_24h": vol,
                "price_change_24h": price_change,
                "pairName": p.get("pairName",""),
                "dex": p.get("dexId","")
            })
        except Exception:
            continue
    return out

def fetch_defillama_protocols(limit_protocols=DEFILLAMA_LIMIT):
    url = "https://api.llama.fi/protocols"
    j = http_get(url)
    out = []
    if not j:
        return out
    for p in j[:limit_protocols]:
        try:
            out.append({
                "name": p.get("name",""),
                "symbol": (p.get("symbol") or "").upper(),
                "tvl": float(p.get("tvl") or 0)
            })
        except Exception:
            continue
    return out

# ----------------------------- #
# Narrative scoring (خفيف)      #
# ----------------------------- #
def narrative_strength(name, description="", dex_map=None, defillama_map=None):
    """
    compute a lightweight narrative strength between 0.0 - 1.0
    - counts matching narrative keywords in name/desc
    - boost if many coins in same narrative present on DEX or DeFi maps
    """
    txt = (str(name) + " " + str(description)).lower()
    tags = []
    for label, keys in NARRATIVE_KEYWORDS.items():
        for k in keys:
            if k in txt:
                tags.append(label)
                break
    base = min(1.0, 0.25 * len(tags))  # each tag small base boost

    # lightweight market-level boost: if many dex entries match narrative tags, raise strength
    boost = 0.0
    if dex_map:
        # count dex symbols that contain any narrative key (cheap heuristic)
        count = 0
        for sym, d in dex_map.items():
            for keys in NARRATIVE_KEYWORDS.values():
                for k in keys:
                    if k in (sym or "").lower():
                        count += 1
                        break
                if count > 30:
                    break
        if count >= 8:
            boost += 0.15
        elif count >= 3:
            boost += 0.07

    if defillama_map:
        # if many protocols present for a narrative, small boost
        if len(defillama_map) >= 5:
            boost += 0.03

    return min(1.0, base + boost), tags

# ----------------------------- #
# Scoring light per coin        #
# ----------------------------- #
def score_coin_light(row, kl_df, dex_map, defillama_map):
    symbol = str(row.get("symbol","")).upper()
    name = row.get("name","") or ""
    price = float(row.get("price") or 0)
    market_cap = float(row.get("market_cap") or 0)
    vol24 = float(row.get("volume_24h") or 0)

    # onchain presence (DEX/DeFi)
    onchain_score = 0.0
    dex_entry = dex_map.get(symbol) if dex_map else None
    def_entry = defillama_map.get(symbol) if defillama_map else None
    if dex_entry:
        v = float(dex_entry.get("volume_24h", 0) or 0)
        onchain_score += 0.65 if v >= DEX_MIN_VOL_FOR_REAL else 0.35
    if def_entry:
        tvl = float(def_entry.get("tvl", 0) or 0)
        onchain_score += 0.45 if tvl >= DEFI_TVL_MIN_FOR_REAL else 0.2

    # narrative
    narr_strength, tags = narrative_strength(name, "", dex_map, defillama_map)

    # technical (light)
    tech_score = 0.0
    vol_comp = 0.0
    if kl_df is not None and not kl_df.empty:
        ser = kl_df["c"].astype(float)
        if len(ser) >= 50:
            # trend using EMA50 vs EMA200 (light)
            ema50 = ema(ser, 50).iloc[-1]
            ema200 = ema(ser, 200).iloc[-1] if len(ser) >= 200 else ema(ser, 100).iloc[-1]
            trend = 1.0 if ema50 > ema200 else 0.0

            # macd hist
            macd_line, macd_signal, macd_hist = compute_macd(ser)
            macd_boost = 1.0 if (macd_hist.iloc[-1] > 0 and macd_hist.iloc[-1] > macd_hist.iloc[-2]) else 0.0

            # rsi
            rsi_val = compute_rsi(ser).iloc[-1]
            rsi_boost = 1.0 if rsi_val > 55 else (0.5 if rsi_val > 48 else 0.0)

            tech_score = 0.5 * trend + 0.3 * macd_boost + 0.2 * rsi_boost

            vol = kl_df["v"].astype(float)
            avg_vol = vol.rolling(50).mean().iloc[-1] if len(vol) >= 50 else vol.mean()
            last_vol = vol.iloc[-1]
            if avg_vol and last_vol / max(1, avg_vol) > 1.5:
                vol_comp = 1.0
            else:
                vol_comp = min(1.0, last_vol / max(1, avg_vol)) if avg_vol else 0.0

    # optional smart_insights integration (cheap checks)
    smart_bonus = 0.0
    if SMART_INSIGHTS_AVAILABLE:
        try:
            # compute small metrics safely
            volume_now = float(kl_df["v"].iloc[-1]) if kl_df is not None and not kl_df.empty else 0.0
            volume_week_ago = float(kl_df["v"].iloc[-24]) if kl_df is not None and len(kl_df) > 24 else 0.0
            price_7d_change = ((kl_df["c"].iloc[-1] - kl_df["c"].iloc[-24]) / max(1, kl_df["c"].iloc[-24])) * 100 if kl_df is not None and len(kl_df) > 24 else 0.0

            if detect_smart_money_flow(volume_now, volume_week_ago, price_7d_change):
                smart_bonus += 0.08
                save_smart_signal_safe(symbol, 0.0, "smart_money_flow")
            if has_recent_partnerships(symbol):
                smart_bonus += 0.06
                save_smart_signal_safe(symbol, 0.0, "partnerships")
            holders_growth = get_holders_growth(symbol) if callable(get_holders_growth) else None
            if holders_growth and holders_growth >= 300:  # threshold conservative
                smart_bonus += 0.05
                save_smart_signal_safe(symbol, 0.0, "holders_growth")
        except Exception:
            pass

    # final aggregation — المحافظة على المنطق العام لكن نضيف narrative_strength
    final_score = (
        0.35 * tech_score +
        0.20 * onchain_score +
        0.15 * vol_comp +
        0.15 * narr_strength +
        0.15 * smart_bonus  # small additive from smart insights
    )
    final_score = max(0.0, min(1.0, final_score))

    return {
        "symbol": symbol,
        "name": name,
        "price": price,
        "market_cap": market_cap,
        "volume_24h": vol24,
        "tech": round(tech_score, 3),
        "onchain": round(onchain_score, 3),
        "vol_comp": round(vol_comp, 3),
        "narrative": round(narr_strength, 3),
        "smart_bonus": round(smart_bonus, 3),
        "score": round(final_score, 3),
        "narrative_tags": tags
    }

# safe saver for smart signals (non-intrusive)
def save_smart_signal_safe(symbol, score, reason):
    try:
        data = load_json(SMART_SIGNALS_FILE) if os.path.exists(SMART_SIGNALS_FILE) else []
        entry = {"symbol": symbol, "score": score, "reason": reason, "timestamp": now_ts()}
        # allow duplicates — it's diagnostic
        data.append(entry)
        save_json(SMART_SIGNALS_FILE, data)
    except Exception:
        pass

# ----------------------------- #
# Single scan (one iteration)   #
# ----------------------------- #
def run_scan_once():
    print(now_ts(), "🚀 بدء المسح (scan once)")
    watchlist = load_json(WATCHLIST_FILE)
    signals_history = load_json(SIGNALS_FILE)

    cmc_df = fetch_cmc_listings(limit=100)
    if cmc_df.empty:
        print(now_ts(), "⚠️ no CMC data")
        return [], [], []

    dex_pairs = fetch_dexscreener_pairs(limit_pairs=DEX_PAIR_LIMIT)
    dex_map = {d["symbol"].upper(): d for d in dex_pairs if d.get("symbol")}
    defillama = fetch_defillama_protocols(limit_protocols=DEFILLAMA_LIMIT)
    defillama_map = {d["symbol"].upper(): d for d in defillama if d.get("symbol")}

    scored = []
    for _, row in cmc_df.iterrows():
        sym = str(row.get("symbol","")).upper()
        # try fetch kline; if fails, we still compute narrative/onchain scores
        kl = None
        try:
            kl = fetch_binance_klines(f"{sym}USDT", interval="4h", limit=200)
        except Exception:
            kl = None
        s = score_coin_light(row, kl, dex_map, defillama_map)
        scored.append(s)

    scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)

    strong = [c for c in scored_sorted if c["score"] >= STRONG_THRESHOLD]
    medium = [c for c in scored_sorted if MEDIUM_THRESHOLD <= c["score"] < STRONG_THRESHOLD]

    picks_to_send = []
    if strong:
        picks_to_send = strong[:TOP_K]
    else:
        for m in medium:
            sym = m["symbol"]
            dex_entry = dex_map.get(sym)
            def_entry = defillama_map.get(sym)
            is_real = False
            if dex_entry and (dex_entry.get("volume_24h",0) or 0) >= DEX_MIN_VOL_FOR_REAL:
                is_real = True
            if def_entry and (def_entry.get("tvl",0) or 0) >= DEFI_TVL_MIN_FOR_REAL:
                is_real = True
            if is_real:
                picks_to_send.append(m)
            if len(picks_to_send) >= TOP_K:
                break

    # update watchlist & save signals (light)
    if picks_to_send:
        for p in picks_to_send:
            if p["symbol"] not in [w.get("symbol") for w in watchlist]:
                watchlist.append({"symbol": p["symbol"], "added_at": now_ts(), "score": p["score"]})
        signals_history.extend(picks_to_send)
        save_json(WATCHLIST_FILE, watchlist)
        save_json(SIGNALS_FILE, signals_history)

    # save snapshot of market (cheap)
    try:
        save_json(MARKET_FILE, cmc_df.to_dict(orient="records"))
    except Exception:
        pass

    return picks_to_send, dex_pairs, defillama

# ----------------------------- #
# Build & send message (Arabic) #
# ----------------------------- #
def build_and_send_top3_ar(picks, dex_pairs, defillama):
    if not picks:
        return False
    msg = "*🏆 أفضل فرص (Top picks)*\n"
    for p in picks[:3]:
        tags = p.get("narrative_tags", []) or []
        tag_txt = ", ".join(tags) if tags else "عام"
        pct = int(p["score"] * 100)
        msg += f"• *{p['symbol']}* — ${p['price']:.6f} | درجة: {pct}% | سرد: {tag_txt}\n"
        msg += f"  (تقني: {p['tech']}, سلاسل: {p['onchain']}, سرد: {p['narrative']})\n"
    # sample dex/dev
    hot_dex = [d for d in dex_pairs if d.get("volume_24h",0) >= 50000][:3]
    if hot_dex:
        msg += "\n*🧩 عينات DEX:*\n"
        for h in hot_dex:
            msg += f"• {h.get('symbol')} — +{h.get('price_change_24h',0)}% / ${int(h.get('volume_24h',0))}\n"
    if defillama:
        sample = defillama[:2]
        if sample:
            msg += "\n*💧 عينات DeFi:*\n"
            for d in sample:
                msg += f"• {d.get('name')} ({d.get('symbol')}) — TVL ${int(d.get('tvl',0))}\n"

    sent = send_telegram_message_ar(msg)
    if sent:
        print(now_ts(), "📢 sent Top picks")
    else:
        print(now_ts(), "⚠️ failed to send Top picks")
    return sent

# ----------------------------- #
# Main loop                     #
# ----------------------------- #
def main_loop():
    print(now_ts(), "🚀 Smart AI Scanner — loop started")
    while True:
        try:
            picks, dex_pairs, defillama = run_scan_once()
            if picks:
                build_and_send_top3_ar(picks, dex_pairs, defillama)
            else:
                print(now_ts(), "ℹ️ no qualified picks this cycle")
        except Exception as e:
            print(now_ts(), "⚠️ main loop error:", e)
        print(now_ts(), f"⏳ sleeping {SLEEP_MINUTES} minutes")
        time.sleep(SLEEP_MINUTES * 60)

if __name__ == "__main__":
    main_loop()
