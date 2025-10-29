# web_worker.py
import json
import os
from flask import render_template_string
from flask import Flask, jsonify
import threading
import main  # يفترض أن main.py في نفس المجلد ويحتوي على main_loop()
import time
import os
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Smart AI Scanner is running (Render Free Plan Mode)."

# simple ping endpoint for keep-alive
@app.route("/ping")
def ping():
    return jsonify({"status": "pong", "ts": __import__("datetime").datetime.utcnow().isoformat() + "Z"})

@app.route("/_healthz")
def health():
    try:
        count = len(main.load_json(main.WATCHLIST_FILE)) if hasattr(main, "WATCHLIST_FILE") else 0
    except Exception:
        count = 0
    return jsonify({"status": "ok", "watch_count": count})

# تشغيل الكود الرئيسي في خيط الخلفية
def background_worker():
    try:
        main.main_loop()
    except Exception as e:
        print("⚠️ background_worker error:", e)

# 🧠 Smart Keep-Alive system
def smart_keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://smart-on-chain-technical-narrative-7yj1.onrender.com")  # عدّل إذا تغير رابط تطبيقك
    last_state = "idle"

    while True:
        try:
            # نتحقق إن كان هناك نشاط أو إشارات نشطة في main
            active = getattr(main, "active_signals", [])
            if active and len(active) > 0:
                if last_state != "busy":
                    print("⚙️ نشاط مرتفع، إيقاف keep-alive مؤقتاً.")
                    last_state = "busy"
                # لا نرسل ping أثناء التحليل لتوفير الموارد
                time.sleep(60)
                continue
            else:
                if last_state != "idle":
                    print("✅ لا يوجد نشاط، استئناف keep-alive الذكي.")
                    last_state = "idle"

            # إرسال ping كل 10 دقائق فقط إذا لا يوجد نشاط
            requests.get(url + "/ping", timeout=10)
            print("💓 Smart keep-alive ping sent.")
            time.sleep(600)  # 10 دقائق
        except Exception as e:
            print("⚠️ Smart keep-alive error:", e)
            time.sleep(300)  # إعادة المحاولة بعد 5 دقائق
            # 📨 إرسال رسالة عند بدء التشغيل الناجح مع الوقت المحلي
def send_start_notification():
    try:
        import datetime
        import pytz

        # ضبط المنطقة الزمنية المحلية (ليبيا)
        tz = pytz.timezone("Africa/Tripoli")
        local_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"🔔 تم تشغيل النظام بنجاح 👁️‍🗨️\n"
            f"✅ Smart AI Scanner يعمل الآن ويبدأ بمراقبة الفرص.\n"
            f"🕒 التوقيت المحلي: {local_time}"
        )

        if hasattr(main, "send_telegram_message"):
            main.send_telegram_message(message)
            print("📩 تم إرسال إشعار بدء التشغيل إلى تليجرام.")
        else:
            print("⚠️ لم يتم العثور على دالة send_telegram_message في main.py.")
    except Exception as e:
        print("⚠️ فشل إرسال إشعار البدء:", e)

# تشغيل إشعار التشغيل لمرة واحدة
threading.Thread(target=send_start_notification, daemon=True).start()

# تشغيل كل من العامل الرئيسي ونظام keep-alive في الخلفية
threading.Thread(target=background_worker, daemon=True).start()
threading.Thread(target=smart_keep_alive, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
