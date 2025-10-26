# -*- coding: utf-8 -*-
"""
Smart On-chain + Technical + Narrative Scanner v6.0 (Render-ready)
Primary: CoinMarketCap (CMC) -> Fallback: CoinGecko
Technical: RSI, EMA20/EMA50, MACD
Sources: CMC, CoinGecko, Binance (klines), DexScreener, DeFiLlama
Notifier: Telegram (instant send)
Designed for Render (persistent mode + memory-friendly)
"""

import os
import time
import math
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# -------------------------
# Config / Env
# -------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CMC_API_KEY = os.getenv("CMC_API_KEY")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

ENABLE_HF = os.getenv("ENABLE_HF", "false").lower() in ("1","true","yes")

# Tunables
MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", str(50_000_000)))  # focus <= $50M by default
MIN_VOLUME_USD = float(os.getenv("MIN_VOLUME_USD", "2000"))
TOP_K = int(os.getenv("TOP_K", "8"))

# Scan interval (seconds)
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "1800"))  # default: every 30 min

# Narrative keywords
NARRATIVE_KEYWORDS = {
    "AI": ["ai","artificial intelligence","machine learning","llm","genai"],
    "DeFi": ["defi","liquidity","yield","staking","lending","dex"],
    "Gaming": ["game","gaming","gamefi","metaverse"],
    "RWA": ["real-world","real world","rwa"]
}

# -------------------------
# Utilities
# -------------------------
def now_ts():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def http_get(url, params=None, headers=None, timeout=15):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def safe_get(dct, *keys, default=None):
    v = dct
    for k in keys:
        if isinstance(v, dict) and k in v:
            v = v[k]
        else:
            return default
    return v

# -------------------------
# Technical helpers
# -------------------------
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
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

# -------------------------
# Data fetchers
# -------------------------
def fetch_cmc_listings(limit=200):
    if not CMC_API_KEY:
        return pd.DataFrame()
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"limit": limit, "convert":"USD"}
    j = http_get(url, params=params, headers=headers)
    if not j:
        return pd.DataFrame()
    return pd.DataFrame(j.get("data", []))

def fetch_coingecko_markets(per_page=250, page=1):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    params = {"vs_currency":"usd","order":"market_cap_asc","per_page":per_page,"page":page,"sparkline":"false"}
    j = http_get(url, params=params, headers=headers)
    if not j:
        return pd.DataFrame()
    return pd.DataFrame(j)

def fetch_dexscreener_pairs():
    url = "https://api.dexscreener.com/latest/dex/tokens"
    j = http_get(url)
    if not j:
        return pd.DataFrame()
    pairs = j.get("pairs") if isinstance(j, dict) else []
    try:
        return pd.DataFrame(pairs)
    except Exception:
        return pd.DataFrame()

def fetch_defillama_protocols():
    url = "https://api.llama.fi/protocols"
    j = http_get(url)
    if not j:
        return pd.DataFrame()
    return pd.DataFrame(j)

def fetch_binance_klines(symbol, interval="1h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    j = http_get(url, params=params)
    if not j or not isinstance(j, list):
        return None
    cols = ["open_time","open","high","low","close","volume","close_time","qav","num_trades","tbqav","tqav","ignore"]
    df = pd.DataFrame(j, columns=cols)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    return df

# -------------------------
# Narrative scoring
# -------------------------
def keyword_narrative_score(name, description=""):
    txt = f"{name} {description}".lower()
    score = 0.0
    for cat, keys in NARRATIVE_KEYWORDS.items():
        for k in keys:
            if k in txt:
                score += 1.0
                break
    maxc = max(1, len(NARRATIVE_KEYWORDS))
    return min(1.0, score / maxc)

# -------------------------
# Core analysis
# -------------------------
def load_market_list():
    cmc = fetch_cmc_listings(limit=300)
    if not cmc.empty:
        df = cmc
        df["symbol"] = df["symbol"].astype(str).str.upper()
        df["price"] = df["quote"].apply(lambda q: safe_get(q,"USD","price", default=0) if isinstance(q,dict) else 0)
        df["market_cap"] = df["quote"].apply(lambda q: safe_get(q,"USD","market_cap", default=0) if isinstance(q,dict) else 0)
        df["volume_24h"] = df["quote"].apply(lambda q: safe_get(q,"USD","volume_24h", default=0) if isinstance(q,dict) else 0)
        return df
    cg = fetch_coingecko_markets(per_page=250, page=1)
    if cg.empty:
        return pd.DataFrame()
    cg["symbol"] = cg["symbol"].astype(str).str.upper()
    cg["price"] = cg["current_price"]
    cg["market_cap"] = cg["market_cap"]
    cg["volume_24h"] = cg["total_volume"]
    return cg

def analyze_and_score(top_k=TOP_K):
    markets = load_market_list()
    if markets.empty:
        print(now_ts(), "⚠️ no market data from CMC/CG")
        return []
    dex = fetch_dexscreener_pairs()
    llama = fetch_defillama_protocols()
    results = []

    for _, row in markets.iterrows():
        try:
            symbol = str(row.get("symbol","")).upper()
            name = row.get("name","")
            price = float(row.get("price") or 0)
            market_cap = float(row.get("market_cap") or 0)
            vol24 = float(row.get("volume_24h") or 0)
            if market_cap <= 0 or market_cap > MAX_MARKET_CAP: continue
            if vol24 < MIN_VOLUME_USD: continue

            narrative_score = keyword_narrative_score(name, "")
            dex_liq = dex_vol24 = 0.0
            try:
                if not dex.empty:
                    mask = dex.apply(lambda x: isinstance(x.get("baseToken"), dict) and x.get("baseToken").get("symbol","").upper()==symbol, axis=1)
                    matched = dex[mask]
                    if matched.empty:
                        mask2 = dex.apply(lambda x: isinstance(x.get("pairName"), str) and symbol in x.get("pairName","").upper(), axis=1)
                        matched = dex[mask2]
                    if not matched.empty:
                        dex_liq = matched.apply(lambda x: safe_get(x,"liquidity","usd", default=0), axis=1).max()
                        dex_vol24 = matched.apply(lambda x: safe_get(x,"volume","h24", default=0), axis=1).max()
            except Exception: pass

            onchain_presence = False
            try:
                if not llama.empty and "symbol" in llama.columns:
                    onchain_presence = any(llama["symbol"].dropna().astype(str).str.upper() == symbol)
            except Exception: pass

            bin_sym = f"{symbol}USDT"
            kdf = fetch_binance_klines(bin_sym, interval="1h", limit=120)
            rsi_val, ema20_over_50, macd_hit, vol_spike, bin_vol = 50.0, False, False, False, 0.0
            if kdf is not None and not kdf.empty:
                ser = kdf["close"].astype(float)
                if len(ser) >= 20:
                    rsi_val = float(compute_rsi(ser, 14).iloc[-1])
                    ema20 = ema(ser, 20).iloc[-1]
                    ema50 = ema(ser, 50).iloc[-1] if len(ser)>=50 else ema(ser, 50).iloc[-1]
                    ema20_over_50 = ema20 > ema50
                    macd_line, macd_signal, macd_hist = compute_macd(ser)
                    macd_hit = (macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0)
                bin_vol = float(kdf["volume"].astype(float).sum())
                try:
                    last_vol = float(kdf["volume"].astype(float).iloc[-1])
                    avg_vol = float(kdf["volume"].astype(float).tail(24).mean() or 1)
                    if last_vol / max(1, avg_vol) > 3.0: vol_spike = True
                except Exception: vol_spike = False

            tech_comp = 0.5*(1 if ema20_over_50 else 0) + 0.3*(1 if rsi_val>55 else (0.5 if rsi_val>45 else 0)) + 0.2*(1 if macd_hit else 0)
            social_comp = narrative_score
            onchain_comp = 0.6*(1 if dex_liq>100_000 else 0) + 0.4*(1 if onchain_presence else 0)
            vol_comp = 0.6*(1 if vol_spike else 0) + 0.4*min(1.0, bin_vol / max(1.0, vol24))
            total_score = max(0, min(1.0, 0.35*tech_comp + 0.3*social_comp + 0.25*onchain_comp + 0.1*vol_comp))

            if total_score >= 0.80:
                results.append({
                    "symbol": symbol, "name": name, "price": price, "market_cap": market_cap,
                    "total_volume": vol24, "dex_liquidity": int(dex_liq or 0),
                    "dex_volume_24h": int(dex_vol24 or 0), "binance_volume": int(bin_vol or 0),
                    "rsi": float(rsi_val), "ema20_over_50": bool(ema20_over_50),
                    "macd_hit": bool(macd_hit), "vol_spike": bool(vol_spike),
                    "narrative_score": float(narrative_score), "onchain_presence": bool(onchain_presence),
                    "total_score": float(total_score), "timestamp": now_ts()
                })
        except Exception:
            continue
    return sorted(results, key=lambda x: x["total_score"], reverse=True)[:top_k] if results else []

# -------------------------
# Telegram notifier
# -------------------------
def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(now_ts(), "⚠️ Telegram credentials missing")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode":"Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            return True
        else:
            print(now_ts(), "⚠️ Telegram error:", r.status_code, r.text)
            return False
    except Exception as e:
        print(now_ts(), "⚠️ Telegram exception:", e)
        return False

def build_message(signals):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    msg = f"*🚀 Smart AI v6.0 — Rare Opportunities Detected*\n🕒 {now}\n\n"
    for s in signals:
        msg += (f"*{s['symbol']}* — `${s['price']:.6f}` | *Score:* {int(s['total_score']*100)}%\n"
                f"RSI: {s['rsi']:.1f} | EMA20>50: {s['ema20_over_50']} | MACD up: {s['macd_hit']}\n"
                f"DexLiq: ${s['dex_liquidity']:,} | DexVol24: ${s['dex_volume_24h']:,} | BinVol: ${s['binance_volume']:,}\n"
                f"Narrative: {s['narrative_score']:.2f} | OnChain: {s['onchain_presence']}\n\n")
    msg += "_Note: Signals combine technical + on-chain + narrative layers._"
    return msg

def scan_once():
    return analyze_and_score(top_k=TOP_K)

# -------------------------
# Continuous Run Loop (Render-ready)
# -------------------------
if __name__ == "__main__":
    print(now_ts(), "🚀 Smart AI v6.0 — Continuous scanning started")
    while True:
        try:
            signals = scan_once()
            if signals:
                msg = build_message(signals)
                send_telegram_message(msg)
                print(now_ts(), f"✅ Sent {len(signals)} signals to Telegram.")
            else:
                print(now_ts(), "📉 No rare opportunities found.")
        except Exception as e:
            print(now_ts(), "⚠️ Exception in main loop:", e)
        print(now_ts(), f"⏳ Sleeping for {SCAN_INTERVAL/60:.1f} minutes...\n")
        time.sleep(SCAN_INTERVAL)
