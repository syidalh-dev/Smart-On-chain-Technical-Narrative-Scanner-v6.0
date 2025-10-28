# -*- coding: utf-8 -*-
"""
Smart AI Scanner v7.2 — Hybrid (CEX + DeFi) + Top3 Weekly Picks (Arabic)
تحسينات مضافة:
- دمج DEX Screener (أخذ عينات من Uniswap/Pancake/Raydium عبر API العام)
- دمج DeFiLlama (TVL) للتحقق من وجود سيولة/مصداقية البروتوكول
- تحليل سردي مُحسّن باستخدام اسم العملة (CoinGecko اختياري)
- إرسال فوري للفرص القوية (>=0.85) — والفرص المتوسطة (>=0.7) فقط إذا كان لديها سيولة/وجود حقيقي
- رسائل Telegram باللغة العربية
- بقيت البنية الأساسية كما هي وخفيفة للـ Render Free Plan
"""

import os
import time
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, UTC

# ----------------------------- #
# الإعدادات والمتغيرات         #
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

TOP_K = 5
STRONG_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.7

# خُذ عينات محدودة لتقليل الضغط (خطة مجانية)
DEX_PAIR_LIMIT = 40
DEFILLAMA_LIMIT = 40

# DEX Screener يدعم العديد من السلاسل؛ نحن نأخذ عينات عامة (يشمل Uniswap, Pancake, Raydium...)
DEX_MIN_VOL_FOR_REAL = 50000  # دولار/24h لتعتبر "وجود حقيقي"
DEFI_TVL_MIN_FOR_REAL = 1_000_000  # TVL بالدولار ليُعتبر وجود حقيقي

# كلمات سردية مبسطة
NARRATIVE_KEYWORDS = {
    "الذكاء الاصطناعي": ["ai", "artificial intelligence", "machine learning", "llm", "genai", "render", "fet"],
    "DeFi": ["defi", "liquidity", "staking", "lending", "dex", "swap", "yield"],
    "الألعاب": ["game", "gaming", "gamefi", "metaverse", "mana", "play"],
    "RWA": ["real-world", "real world", "rwa", "tokenization"],
    "البنية التحتية": ["infrastructure", "node", "protocol", "rpc"],
    "Layer2": ["layer2", "rollup", "zk", "optimism", "arbitrum"],
    "ميم": ["meme", "dog", "shib", "woof"]
}

# ----------------------------- #
# وظائف مساعدة                 #
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
        print(now_ts(), "⚠️ خطأ في الحفظ:", filename, e)

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
        print(now_ts(), "⚠️ مفاتيح Telegram غير مضبوطة")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(now_ts(), "⚠️ استثناء Telegram:", e)
        return False

# ----------------------------- #
# مؤشرات تقنية                 #
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
# جلب بيانات من CMC وBinance    #
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

# ----------------------------- #
# DEX Screener (عينات خفيفة)    #
# ----------------------------- #
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

# ----------------------------- #
# DeFiLlama (TVL)               #
# ----------------------------- #
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
# تحليل سردي بسيط               #
# ----------------------------- #
def narrative_from_text(name, description=""):
    txt = (name + " " + (description or "")).lower()
    tags = []
    for label, keys in NARRATIVE_KEYWORDS.items():
        for k in keys:
            if k in txt:
                tags.append(label)
                break
    return list(dict.fromkeys(tags))  # remove duplicates preserve order

# ----------------------------- #
# دالة تقييم كل عملة            #
# ----------------------------- #
def score_coin_light(row, kl_df, dex_map, defillama_map):
    symbol = str(row.get("symbol","")).upper()
    name = row.get("name","")
    # narrative
    tags = narrative_from_text(name, "")
    social_score = min(1.0, 0.2 * len(tags))  # كل tag يعطي وزن بسيط (حتى 1.0)

    # onchain presence
    onchain_score = 0.0
    dex_entry = dex_map.get(symbol)
    def_entry = defillama_map.get(symbol)
    if dex_entry:
        # نقيم حسب حجم الـ DEX
        vol = dex_entry.get("volume_24h", 0) or 0
        if vol >= DEX_MIN_VOL_FOR_REAL:
            onchain_score += 0.7
        else:
            onchain_score += 0.4
    if def_entry:
        tvl = def_entry.get("tvl", 0) or 0
        if tvl >= DEFI_TVL_MIN_FOR_REAL:
            onchain_score += 0.5
        else:
            onchain_score += 0.2

    # technicals
    tech_score = 0.0
    vol_comp = 0.0
    if kl_df is not None and not kl_df.empty:
        ser = kl_df["c"].astype(float)
        if len(ser) >= 50:
            rsi_val = compute_rsi(ser).iloc[-1]
            ema50 = ema(ser, 50).iloc[-1]
            ema100 = ema(ser, 100).iloc[-1]
            macd_line, macd_signal, macd_hist = compute_macd(ser)
            hist_last = macd_hist.iloc[-1]
            trend = 1.0 if (ema50 > ema100 and hist_last > 0) else 0.0
            tech_score += 0.6 * trend
            tech_score += 0.4 * (1.0 if rsi_val > 55 else (0.5 if rsi_val > 48 else 0.0))
            # volume spike
            vol = kl_df["v"].astype(float)
            avg_vol = vol.rolling(30).mean().iloc[-1] if len(vol) >= 30 else vol.mean()
            last_vol = vol.iloc[-1]
            if avg_vol and last_vol / max(1, avg_vol) > 1.5:
                vol_comp = 1.0
            else:
                vol_comp = min(1.0, (last_vol / max(1, avg_vol))) if avg_vol else 0.0

    # تجميع الدرجات مع أوزان
    total = 0.5 * tech_score + 0.25 * social_score + 0.15 * onchain_score + 0.10 * vol_comp
    total = max(0.0, min(1.0, total))
    return {
        "symbol": symbol,
        "name": name,
        "price": float(row.get("price") or 0),
        "market_cap": float(row.get("market_cap") or 0),
        "volume_24h": float(row.get("volume_24h") or 0),
        "tech": round(tech_score,3),
        "social": round(social_score,3),
        "onchain": round(onchain_score,3),
        "vol_comp": round(vol_comp,3),
        "score": round(total,3),
        "narrative_tags": tags
    }

# ----------------------------- #
# تنفيذ مسح واحد (دورة واحدة)  #
# ----------------------------- #
def run_scan_once():
    print(now_ts(), "🚀 بدء المسح الذكي v7.2")
    # تحميل محفوظات / قوائم
    watchlist = load_json(WATCHLIST_FILE)
    signals_history = load_json(SIGNALS_FILE)

    # جلب قوائم السوق من CMC
    cmc_df = fetch_cmc_listings(limit=100)
    if cmc_df.empty:
        print(now_ts(), "⚠️ لم يُسترجع بيانات CMC — تأكد من مفتاح API أو اتصال الشبكة.")
        return [], [], []

    # جلب بيانات DEX وDeFi (عينات خفيفة)
    dex_pairs = fetch_dexscreener_pairs(limit_pairs=DEX_PAIR_LIMIT)
    dex_map = {d["symbol"].upper(): d for d in dex_pairs if d.get("symbol")}
    defillama = fetch_defillama_protocols(limit_protocols=DEFILLAMA_LIMIT)
    defillama_map = {d["symbol"].upper(): d for d in defillama if d.get("symbol")}

    scored = []
    for _, row in cmc_df.iterrows():
        sym = str(row.get("symbol","")).upper()
        # جرب جلب بيانات من Binance (4h) — إن لم تتوفر تجاهل التقنية للحفاظ على الموارد
        kl = fetch_binance_klines(f"{sym}USDT", interval="4h", limit=200)
        s = score_coin_light(row, kl, dex_map, defillama_map)
        scored.append(s)

    scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)

    # فصل القوي والمتوسط
    strong = [c for c in scored_sorted if c["score"] >= STRONG_THRESHOLD]
    medium = [c for c in scored_sorted if MEDIUM_THRESHOLD <= c["score"] < STRONG_THRESHOLD]

    # قرارات الإرسال: قوي => أرسل, متوسط => أرسل فقط لو لديه وجود حقيقي (DEX vol أو DeFi TVL)
    picks_to_send = []
    # نأخذ حتى TOP_K من القوي أولاً
    if strong:
        picks_to_send = strong[:TOP_K]
    else:
        # لنفحص المتوسطة ونقبلها فقط إذا متوفرة شروط "الحقيقة" (liquidity/presence)
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

    # تحديث القوائم والحفظ خفيف
    if picks_to_send:
        for p in picks_to_send:
            if p["symbol"] not in [w.get("symbol") for w in watchlist]:
                watchlist.append({"symbol": p["symbol"], "added_at": now_ts(), "score": p["score"]})
        try:
            signals_history.extend(picks_to_send)
        except Exception:
            signals_history = signals_history + picks_to_send
        save_json(WATCHLIST_FILE, watchlist)
        save_json(SIGNALS_FILE, signals_history)

    # حفظ لقطة السوق
    save_json(MARKET_FILE, cmc_df.to_dict(orient="records"))

    return picks_to_send, dex_pairs, defillama

# ----------------------------- #
# بناء رسالة تليغرام بالعربية  #
# ----------------------------- #
def build_and_send_top3_ar(picks, dex_pairs, defillama):
    if not picks:
        return False
    # رسالة مُفصّلة بالعربية للـ Top picks
    msg = "*🏆 أفضل 3 فرص استثمارية هذا الأسبوع*\n"
    for p in picks[:3]:
        tags = p.get("narrative_tags") or []
        tag_txt = ", ".join(tags) if tags else "عام"
        pct = int(p["score"]*100)
        msg += f"• *{p['symbol']}* — سعر ${p['price']:.6f} | درجة: {pct}% | {tag_txt}\n"
        msg += f"  (التحليل الفني: {p['tech']}, السرد: {p['social']}, الوجود على السلاسل: {p['onchain']})\n"
    # أمثلة سريعة من DEX/DeFi
    hot_dex = [d for d in dex_pairs if d.get("volume_24h",0) >= 50000][:3]
    if hot_dex:
        msg += "\n*🧩 عينات من DEX (حار):*\n"
        for h in hot_dex:
            msg += f"• {h.get('symbol')} — +{h.get('price_change_24h',0)}% / ${int(h.get('volume_24h',0))} vol\n"
    if defillama:
        sample = defillama[:2]
        if sample:
            msg += "\n*💧 عينات DeFi (TVL):*\n"
            for d in sample:
                msg += f"• {d.get('name')} ({d.get('symbol')}) — TVL ${int(d.get('tvl',0))}\n"

    sent = send_telegram_message_ar(msg)
    if sent:
        print(now_ts(), f"📢 أرسلت رسالة Top picks بعدد {min(len(picks),3)}")
    else:
        print(now_ts(), "⚠️ فشل إرسال Top picks")
    return sent

# ----------------------------- #
# الحلقة الرئيسية (Loop)        #
# ----------------------------- #
def main_loop():
    print(now_ts(), "🚀 Smart AI Scanner v7.2 — بدأ التشغيل")
    while True:
        try:
            picks, dex_pairs, defillama = run_scan_once()
            if picks:
                # نرسِل رسالة مستقلة للـ Top 3 (قوية أو متوسطة مع وجود حقيقي)
                build_and_send_top3_ar(picks, dex_pairs, defillama)
            else:
                print(now_ts(), "ℹ️ لا توجد فرص قوية/مؤهلة في هذه الدورة.")
        except Exception as e:
            print(now_ts(), "⚠️ خطأ أثناء المسح:", e)

        print(now_ts(), f"⏳ النوم {SLEEP_MINUTES} دقيقة...")
        time.sleep(SLEEP_MINUTES * 60)

if __name__ == "__main__":
    main_loop()
import requests
import os

# 📩 دالة إرسال الرسائل إلى تليجرام (مطلوبة من web_worker)
def send_telegram_message(message):
    try:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            print("⚠️ لم يتم ضبط TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID في الإعدادات البيئية.")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        r = requests.post(url, data=data)
        if r.status_code == 200:
            print("📨 تم إرسال الرسالة إلى تليجرام بنجاح.")
        else:
            print("⚠️ فشل الإرسال إلى تليجرام:", r.text)
    except Exception as e:
        print("⚠️ خطأ أثناء إرسال رسالة تليجرام:", e)
