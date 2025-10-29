# smart_insights.py
# أدوات "الذكاء" الخفيف — يستدعى من main.py عند الحاجة فقط.
import os, time, requests, json
from datetime import datetime, timedelta

# مفاتيح (اختيارية) — ضعها في إعدادات Render
ETHERSCAN_KEY = os.getenv("ETHERSCAN_API_KEY", "")
GLASSNODE_KEY = os.getenv("GLASSNODE_API_KEY", "")
COINMARKETCAL_KEY = os.getenv("COINMARKETCAL_KEY", "")

SAVE_FILE = "smart_signals.json"

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def load_signals():
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_signals(data):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("⚠️ smart_insights.save_signals error:", e)

def save_smart_signal(symbol, score, reason):
    # يضيف إشارة ذكية إذا غيرت الحالة أو أول مرّة
    data = load_signals()
    now = now_iso()
    entry = {"symbol": symbol, "score": round(float(score),3), "reason": reason, "ts": now}
    # تجنّب التكرار: إذا نفس الرمز موجود مع نفس السبب لا نكرر
    for x in data:
        if x.get("symbol")==symbol and x.get("reason")==reason:
            return True
    data.append(entry)
    save_signals(data)
    print("💾 smart_insights saved:", symbol, reason)
    return True

# ---------- خوارزميات خفيفة (بدون تحميل كبير) ----------
def detect_smart_money_flow(volume_now, volume_past, price_7d_change_pct, vol_ratio_threshold=3.0, price_cap=50.0):
    """
    منطق خفيف: إذا زاد الحجم الحالي على الماضي بنسبة كبيرة (ex: > vol_ratio_threshold)
    مع زيادة متواضعة في السعر (لا نريد ارتفاع سعر كبير ليكون Pump فقط).
    """
    try:
        if volume_past <= 0:
            return False
        ratio = (volume_now / max(1.0, volume_past))
        if ratio >= vol_ratio_threshold and abs(price_7d_change_pct) < price_cap:
            return True
    except Exception:
        pass
    return False

def has_recent_partnerships(symbol):
    """
    تحقق خفيف: استخدم CoinMarketCal أو صفحات الأخبار — إذا لم تتوفر API، نرجع False.
    (يمكن توسيعها لاحقاً). هنا نعمل استدعاء بسيط على CoinMarketCal إن وُجد مفتاح.
    """
    if not COINMARKETCAL_KEY:
        return False
    try:
        # مثال مبسّط: نتحقق عن أحداث مرتبطة بالرمز خلال 30 يوم
        url = "https://developers.coinmarketcal.com/v1/events"  # لاحظ: مثال — قد يحتاج ضبط
        params = {"coinId": symbol, "lang":"en"}
        headers = {"x-api-key": COINMARKETCAL_KEY}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        if r.status_code == 200:
            j = r.json()
            if j and len(j.get("body", []))>0:
                return True
    except Exception:
        pass
    return False

def get_holders_growth(address_or_contract):
    """
    دالة وهمية/خفة الوزن: في حال وجود ETHERSCAN_KEY يمكن طلب holders (قد يتطلب عمل على السلسلة).
    هنا نُرجع None إذا لا يتوفر مفتاح — أو قيمة عددية تقريبية إن امكن.
    """
    if not ETHERSCAN_KEY:
        return None
    try:
        # ملاحظة: استخراج "عدد الحاملين" من Ethplorer/Etherscan قد يحتاج endpoint مدفوع — لذا هذه مجرد محاولة خفيفة
        url = "https://api.etherscan.io/api"
        params = {"module":"token","action":"tokenholderlist","contractaddress":address_or_contract,"page":1,"offset":1,"apikey":ETHERSCAN_KEY}
        r = requests.get(url, params=params, timeout=8)
        if r.status_code==200:
            # صيغة الاستجابة قد تختلف — رجّع قيمة تخمينية
            j = r.json()
            # إذا لم توفر Etherscan هذا، نعيد None
            return None
    except Exception:
        pass
    return None
