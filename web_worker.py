# web_worker.py
from flask import Flask, jsonify, render_template
import threading
import main  # يفترض أن main.py في نفس المجلد ويحتوي على main_loop()
import time
import os
import requests

app = Flask(__name__, template_folder="templates")

@app.route("/")
def home():
    # صفحة HTML خفيفة للعرض فقط
    try:
        watch = main.load_json(main.WATCHLIST_FILE) if hasattr(main, "WATCHLIST_FILE") else []
        return render_template("index.html", watch_count=len(watch), last_run=main.now_ts() if hasattr(main, "now_ts") else "")
    except Exception:
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
    return jsonify({"status":"ok","watch_count": count})

# تشغيل الكود الرئيسي في خيط الخلفية
def background_worker():
    try:
        main.main_loop()
    except Exception as e:
        print("⚠️ background_worker error:", e)

threading.Thread(target=background_worker, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
