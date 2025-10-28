# -*- coding: utf-8 -*-
"""
Smart AI Scanner v7.1 — Render Free Plan Compatible
- Auto Watchlist + Persistent Storage
- Market Change Comparison (Delta Alerts)
- Technical + Narrative + Volume + Trend Detection
"""

import os
import time
import json
import math
import requests
import pandas as pd
import numpy as np
from datetime import datetime, UTC

# ----------------------------- #
# Environment & Configurations  #
# ----------------------------- #
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CMC_API_KEY = os.getenv("CMC_API_KEY")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", "50000000"))
MIN_VOLUME_USD = float(os.getenv("MIN_VOLUME_USD", "2000"))
SLEEP_MINUTES = float(os.getenv("SLEEP_MINUTES", "30"))

MARKET_FILE = "market_data.json"
WATCHLIST_FILE = "watchlist.json"
SIGNALS_FILE = "signals_history.json"

# ----------------------------- #
# Utilities                     #
# ----------------------------- #
def now_ts():
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

def safe_get(dct, *keys, default=None):
    v = dct
    for k in keys:
        if isinstance(v, dict) and k in v:
            v = v[k]
        else:
            return default
    return v

def http_get(url, params=None, headers=None):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("⚠️ Error saving:", filename, e)

def load_json(filename):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# ----------------------------- #
# Technical Indicators          #
# ----------------------------- #
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.rolling(period).mean()
    ma_down = down.rolling(period).mean()
    rs = ma_up / (ma_down.replace(0, 1e-10))
    return 100 - (100 / (1 + rs))

def compute_macd(series):
    fast = series.ewm(span=12, adjust=False).mean()
    slow = series.ewm(span=26, adjust=False).mean()
    macd = fast - slow
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

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
    df["price"] = df["quote"].apply(lambda x: safe_get(x, "USD", "price", default=0))
    df["market_cap"] = df["quote"].apply(lambda x: safe_get(x, "USD", "market_cap", default=0))
    df["volume_24h"] = df["quote"].apply(lambda x: safe_get(x, "USD", "volume_24h", default=0))
    return df

def fetch_binance_klines(symbol="BTCUSDT", interval="1h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    j = http_get(url, params=params)
    if not j:
        return None
    df = pd.DataFrame(j, columns=["t", "o", "h", "l", "c", "v", "_1", "_2", "_3", "_4", "_5", "_6"])
    df["c"] = pd.to_numeric(df["c"])
    df["v"] = pd.to_numeric(df["v"])
    return df

# ----------------------------- #
# Watchlist Logic               #
# ----------------------------- #
def update_watchlist(watchlist, candidates):
    for coin in candidates:
        symbol = coin["symbol"]
        if symbol not in [w["symbol"] for w in watchlist]:
            coin["added_at"] = now_ts()
            watchlist.append(coin)
    return watchlist

# ----------------------------- #
# Telegram                      #
# ----------------------------- #
def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Missing Telegram keys")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass
        # اختبار إرسال رسالة يدوية إلى التلغرام
if __name__ == "__main__":
    send_telegram_message("✅ اختبار: Smart AI Scanner متصل الآن بنجاح 🚀")
    print("تم إرسال رسالة اختبار إلى التلغرام ✅")

# ----------------------------- #
# Core Analyzer                 #
# ----------------------------- #
def analyze_market():
    df = fetch_cmc_listings(limit=100)
    if df.empty:
        print("⚠️ No market data.")
        return []
    df = df[(df["market_cap"] <= MAX_MARKET_CAP) & (df["volume_24h"] >= MIN_VOLUME_USD)]
    signals = []

    for _, row in df.iterrows():
        symbol = row["symbol"]
        price = row["price"]
        kl = fetch_binance_klines(f"{symbol}USDT")
        if kl is None or kl.empty:
            continue
        close = kl["c"]
        vol = kl["v"]

        rsi = compute_rsi(close).iloc[-1]
        macd, signal, hist = compute_macd(close)
        ema20 = ema(close, 20).iloc[-1]
        ema50 = ema(close, 50).iloc[-1]
        trend_up = ema20 > ema50 and hist.iloc[-1] > 0
        vol_boost = vol.iloc[-1] > 1.5 * vol.rolling(20).mean().iloc[-1]

        score = 0
        if trend_up:
            score += 0.5
        if vol_boost:
            score += 0.3
        if rsi > 55:
            score += 0.2

        if score >= 0.8:
            signals.append({
                "symbol": symbol,
                "price": round(price, 6),
                "rsi": round(rsi, 2),
                "trend_up": trend_up,
                "volume_boost": vol_boost,
                "score": round(score, 2),
                "timestamp": now_ts()
            })
    return signals

# ----------------------------- #
# Delta Comparison               #
# ----------------------------- #
def compare_with_old(new_data, old_data):
    alerts = []
    old_map = {c["symbol"]: c for c in old_data}
    for coin in new_data:
        old = old_map.get(coin["symbol"])
        if not old:
            continue
        try:
            price_change = (coin["price"] - old["price"]) / max(1e-8, old["price"]) * 100
            rsi_change = coin["rsi"] - old.get("rsi", coin["rsi"])
            if price_change > 5 or rsi_change > 10 or (not old["trend_up"] and coin["trend_up"]):
                alerts.append({
                    "symbol": coin["symbol"],
                    "price_change": round(price_change, 2),
                    "rsi_change": round(rsi_change, 2),
                    "timestamp": now_ts()
                })
        except Exception:
            continue
    return alerts

# ----------------------------- #
# Main Loop                     #
# ----------------------------- #
def main_loop():
    print(now_ts(), "🚀 Smart AI Scanner v7.1 started (Render Mode)")
    old_market = load_json(MARKET_FILE)
    watchlist = load_json(WATCHLIST_FILE)
    signals_cache = load_json(SIGNALS_FILE)

    while True:
        new_data = analyze_market()
        if not new_data:
            print(now_ts(), "📉 No new signals found.")
        else:
            print(now_ts(), f"✅ {len(new_data)} signals analyzed.")
            watchlist = update_watchlist(watchlist, new_data)
            save_json(WATCHLIST_FILE, watchlist)

            changes = compare_with_old(new_data, old_market)
            if changes:
                msg = "*📈 Market Updates Detected:*\n"
                for c in changes:
                    msg += f"• *{c['symbol']}*: +{c['price_change']}% price, ΔRSI={c['rsi_change']}\n"
                send_telegram_message(msg)
                print(now_ts(), f"🔔 {len(changes)} market changes sent.")

            save_json(MARKET_FILE, new_data)
            save_json(SIGNALS_FILE, signals_cache + new_data)

        print(now_ts(), f"⏳ Sleeping {SLEEP_MINUTES} minutes...")
        time.sleep(SLEEP_MINUTES * 60)

if __name__ == "__main__":
    main_loop()
