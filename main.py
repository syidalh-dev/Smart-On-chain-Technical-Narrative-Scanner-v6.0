# -*- coding: utf-8 -*-
"""
Smart AI Scanner v8.5 — Hybrid (CEX + DeFi) + Smart Picks (send on strong opportunities)
- Uses: CoinMarketCap (primary), Binance klines (4h), DEX Screener, DeFiLlama
- Sends Telegram alerts ONLY when strong opportunities / picks detected
- Keeps lightweight limits for Render Free Plan
"""

import os
import time
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, UTC, timedelta

# ----------------------------- #
# Config / Env                  #
# ----------------------------- #
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CMC_API_KEY = os.getenv("CMC_API_KEY", "")

MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", "50000000"))
MIN_VOLUME_USD = float(os.getenv("MIN_VOLUME_USD", "2000"))
SLEEP_MINUTES = float(os.getenv("SLEEP_MINUTES", "30"))

MARKET_FILE = "market_data.json"
WATCHLIST_FILE = "watchlist.json"
SIGNALS_FILE = "signals_history.json"

# Scoring / thresholds
TOP_K = 5
STRONG_THRESHOLD = 0.80  # >= this => strong opportunity -> send immediately

# Narrative keywords (can be extended)
NARRATIVE_KEYWORDS = {
    "AI": ["ai", "artificial intelligence", "machine learning", "llm", "genai", "ai-token", "ai-"],
    "DeFi": ["defi", "liquidity", "staking", "lending", "dex", "swap", "yield"],
    "Gaming": ["game", "gaming", "gamefi", "metaverse", "nft", "play"],
    "RWA": ["real-world", "real world", "rwa", "tokenization"],
    "Infra": ["infrastructure", "node", "protocol", "rpc"],
    "Layer2": ["layer2", "rollup", "zk", "optimism", "arbitrum"],
    "Meme": ["meme", "dog", "shib", "woof"]
}

# ----------------------------- #
# Utilities                     #
# ----------------------------- #
def now_ts():
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

def http_get(url, params=None, headers=None, timeout=15):
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
    except Exception:
        pass

def load_json(filename):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(now_ts(), "⚠️ Telegram keys missing")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(now_ts(), "⚠️ Telegram exception:", e)
        return False

# ----------------------------- #
# Technical helpers             #
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
# Narrative scoring             #
# ----------------------------- #
def narrative_score_from_text(name, description=""):
    txt = (name + " " + (description or "")).lower()
    score = 0.0
    matches = []
    for cat, keys in NARRATIVE_KEYWORDS.items():
        for k in keys:
            if k in txt:
                score += 1.0
                matches.append(cat)
                break
    maxc = max(1, len(NARRATIVE_KEYWORDS))
    return min(1.0, score / maxc), list(set(matches))

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
    # normalize
    df["symbol"] = df["symbol"].astype(str).str.upper()
    # for description: sometimes CMC response includes 'description' only in detail endpoint;
    # here we'll use name as primary text for narratives (keeps light)
    df["name"] = df.get("name", "")
    df["price"] = df["quote"].apply(lambda q: q.get("USD", {}).get("price", 0) if isinstance(q, dict) else 0)
    df["market_cap"] = df["quote"].apply(lambda q: q.get("USD", {}).get("market_cap", 0) if isinstance(q, dict) else 0)
    df["volume_24h"] = df["quote"].apply(lambda q: q.get("USD", {}).get("volume_24h", 0) if isinstance(q, dict) else 0)
    return df

def fetch_binance_klines(symbol="BTCUSDT", interval="4h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    j = http_get(url, params=params)
    if not j or not isinstance(j, list):
        return None
    df = pd.DataFrame(j, columns=["t","o","h","l","c","v","_1","_2","_3","_4","_5","_6"])
    df["c"] = pd.to_numeric(df["c"], errors="coerce")
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    return df

def fetch_dexscreener_data(limit_pairs=30):
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
            # priceChange fields vary; attempt safe extraction
            price_change = None
            if "priceChange" in p and isinstance(p["priceChange"], dict):
                price_change = float(p["priceChange"].get("h24", 0) or 0)
            else:
                # fallback: some endpoints provide 'priceUsd' old/new - not used here
                price_change = 0.0
            out.append({
                "symbol": symbol,
                "volume_24h": vol,
                "price_change_24h": price_change,
                "pair": p.get("pairName", ""),
                "dex": p.get("dexId", "")
            })
        except Exception:
            continue
    return out

def fetch_defillama_data(limit_protocols=30):
    url = "https://api.llama.fi/protocols"
    j = http_get(url)
    out = []
    if not j:
        return out
    for p in j[:limit_protocols]:
        try:
            name = p.get("name", "")
            symbol = p.get("symbol") or ""
            tvl = float(p.get("tvl") or 0)
            # note: the official /protocols endpoint doesn't include daily % change consistently, so we use presence only
            out.append({"name": name, "symbol": symbol, "tvl": tvl})
        except Exception:
            continue
    return out

# ----------------------------- #
# Scoring & Selection           #
# ----------------------------- #
def score_coin(row, kl_df, dex_map, defillama_map):
    """
    row: a row from CMC df
    kl_df: binance klines df or None
    """
    tech = 0.0
    onchain = 0.0
    social = 0.0
    vol_comp = 0.0

    # narrative score (from name)
    narrative, narrative_tags = narrative_score_from_text(str(row.get("name","")), "")
    social = narrative  # 0..1

    # presence in DEX screener / DeFiLlama
    symbol = str(row.get("symbol","")).upper()
    if symbol in dex_map:
        onchain += 0.5
    if symbol in defillama_map:
        onchain += 0.3

    # technicals from klines (4h)
    if kl_df is not None and not kl_df.empty:
        ser = kl_df["c"].astype(float)
        if len(ser) >= 50:
            rsi_val = compute_rsi(ser, period=14).iloc[-1]
            ema50 = ema(ser, 50).iloc[-1]
            ema100 = ema(ser, 100).iloc[-1]
            macd_line, macd_signal, macd_hist = compute_macd(ser)
            macd_hist_latest = macd_hist.iloc[-1]
            trend = 1.0 if (ema50 > ema100 and macd_hist_latest > 0) else 0.0
            tech += 0.6 * trend
            tech += 0.4 * (1.0 if rsi_val > 55 else (0.5 if rsi_val > 48 else 0.0))
            # volume measure
            vol = kl_df["v"].astype(float)
            avg_vol = vol.rolling(30).mean().iloc[-1] if len(vol) >= 30 else vol.mean()
            last_vol = vol.iloc[-1]
            if avg_vol and last_vol / max(1, avg_vol) > 1.5:
                vol_comp = 1.0
            else:
                vol_comp = min(1.0, (last_vol / max(1, avg_vol))) if avg_vol else 0.0
    else:
        # no klines -> be conservative
        tech += 0.0
        vol_comp = 0.0

    # weights
    total_score = 0.45 * tech + 0.30 * social + 0.15 * onchain + 0.10 * vol_comp
    total_score = max(0.0, min(1.0, total_score))

    return {
        "symbol": symbol,
        "name": row.get("name", ""),
        "price": float(row.get("price", 0) or 0),
        "market_cap": float(row.get("market_cap", 0) or 0),
        "volume_24h": float(row.get("volume_24h", 0) or 0),
        "tech": round(tech, 3),
        "social": round(social, 3),
        "onchain": round(onchain, 3),
        "vol_comp": round(vol_comp, 3),
        "score": round(total_score, 3),
    }

# ----------------------------- #
# Main scanner / flow           #
# ----------------------------- #
def run_scan():
    print(now_ts(), "🚀 Running smart scan (v8.5)")
    # load persisted
    watchlist = load_json(WATCHLIST_FILE)
    signals_history = load_json(SIGNALS_FILE)

    # fetch market list from CMC (light)
    cmc_df = fetch_cmc_listings(limit=100)
    if cmc_df.empty:
        print(now_ts(), "⚠️ No CMC data (check API key).")
        return []

    # fetch DEX & DeFi lists (light)
    dex_pairs = fetch_dexscreener_data(limit_pairs=30)
    dex_map = {d["symbol"].upper(): d for d in dex_pairs if d.get("symbol")}
    defillama = fetch_defillama_data(limit_protocols=30)
    defillama_map = {d["symbol"].upper(): d for d in defillama if d.get("symbol")}

    scored = []
    # iterate coins (light: only top 100 from CMC)
    for _, row in cmc_df.iterrows():
        symbol = str(row.get("symbol","")).upper()
        # try to fetch 4h klines from Binance
        kl = fetch_binance_klines(f"{symbol}USDT", interval="4h", limit=200)
        s = score_coin(row, kl, dex_map, defillama_map)
        scored.append(s)

    # sort by score desc
    scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)

    # pick strong opportunities (above threshold) or top K if none above threshold but still good
    strong = [c for c in scored_sorted if c["score"] >= STRONG_THRESHOLD]
    picks = []
    if strong:
        picks = strong[:TOP_K]
    else:
        # fallback: choose top K with score >= 0.65 to avoid useless picks
        picks = [c for c in scored_sorted if c["score"] >= 0.65][:TOP_K]

    # update watchlist and signals history
    if picks:
        for p in picks:
            if p["symbol"] not in [w.get("symbol") for w in watchlist]:
                w = {"symbol": p["symbol"], "added_at": now_ts(), "score": p["score"]}
                watchlist.append(w)

        # persist signals (append)
        try:
            signals_history.extend(picks)
        except Exception:
            signals_history = signals_history + picks

        save_json(WATCHLIST_FILE, watchlist)
        save_json(SIGNALS_FILE, signals_history)

    # also save last market snapshot (light)
    save_json(MARKET_FILE, cmc_df.to_dict(orient="records"))

    return picks, dex_pairs, defillama

# ----------------------------- #
# Build Telegram message        #
# ----------------------------- #
def build_and_send_picks(picks, dex_pairs, defillama):
    if not picks:
        return False
    msg = "*💎 Smart Investment Picks (7–14 days — Strong Opportunities)*\n"
    for p in picks:
        # find narrative tags quickly
        narrative, tags = narrative_score_from_text(p["name"], "")
        tag_txt = ", ".join(tags) if tags else "General"
        msg += (f"• *{p['symbol']}* — ${p['price']:.6f} | Score: {p['score']*100:.0f}% | {tag_txt}\n")
        msg += (f"  (tech:{p['tech']}, social:{p['social']}, onchain:{p['onchain']})\n")
    # optional: append short DEX/DeFi highlights
    if dex_pairs:
        # show up to 3 hot dex tokens (light)
        hot = [d for d in dex_pairs if d.get("volume_24h",0) > 50000][:3]
        if hot:
            msg += "\n*🧩 DEX Hot Tokens (sample):*\n"
            for h in hot:
                msg += f"• {h.get('symbol')} — +{h.get('price_change_24h',0)}% / ${int(h.get('volume_24h',0))} vol\n"
    if defillama:
        sample = defillama[:3]
        if sample:
            msg += "\n*💧 DeFi Flow (sample):*\n"
            for d in sample:
                msg += f"• {d.get('name')} ({d.get('symbol')}) — TVL ${int(d.get('tvl',0))}\n"

    sent = send_telegram_message(msg)
    if sent:
        print(now_ts(), f"📢 Sent {len(picks)} Smart Picks to Telegram.")
    else:
        print(now_ts(), "⚠️ Failed to send picks to Telegram.")
    return sent

# ----------------------------- #
# Runner (single cycle)         #
# ----------------------------- #
def main_loop():
    print(now_ts(), "🚀 Smart AI Scanner v8.5 — started")
    while True:
        try:
            picks, dex_pairs, defillama = run_scan()
            # send ONLY if there are picks (strong opportunities) — user requested instant send on strong
            if picks:
                build_and_send_picks(picks, dex_pairs, defillama)
            else:
                print(now_ts(), "ℹ️ No strong picks this cycle.")
        except Exception as e:
            print(now_ts(), "⚠️ scan error:", e)

        print(now_ts(), f"⏳ Sleeping {SLEEP_MINUTES} minutes...")
        time.sleep(SLEEP_MINUTES * 60)

if __name__ == "__main__":
    main_loop()
