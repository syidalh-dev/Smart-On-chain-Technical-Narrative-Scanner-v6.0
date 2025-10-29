from flask import Flask, jsonify, render_template
import threading, os, time, requests
import main

app = Flask(__name__, template_folder="templates")

@app.route("/")
def home():
    try:
        watch = main.load_json(main.WATCHLIST_FILE)
        return render_template(
            "index.html",
            watch_count=len(watch),
            last_run=main.now_local().strftime("%Y-%m-%d %H:%M"),
        )
    except Exception:
        return "✅ Smart AI Scanner يعمل (Render Free Plan Mode)"

@app.route("/ping")
def ping():
    return jsonify({"status": "pong", "ts": main.now_local().isoformat()})

@app.route("/_healthz")
def health():
    count = len(main.load_json(main.WATCHLIST_FILE))
    return jsonify({"status": "ok", "watch_count": count})

def background_worker():
    """
    تشغيل الذكاء الاصطناعي كل 6 ساعات تلقائياً
    """
    while True:
        try:
            print("🚀 بدء تحليل جديد كل 6 ساعات ...")
            main.main_loop()
        except Exception as e:
            print("⚠️ background_worker error:", e)
        time.sleep(6 * 3600)  # كل 6 ساعات

# تشغيل الخيط الخلفي للتحليل التلقائي
threading.Thread(target=background_worker, daemon=True).start()

# 🔄 نظام Keep-Alive لإبقاء السيرفر نشطاً في Render
def keep_alive():
    while True:
        try:
            url = os.getenv("RENDER_EXTERNAL_URL", "https://smart-ai-scanner.onrender.com")
            requests.get(url + "/ping", timeout=10)
            print(f"💓 Keep-alive ping sent to {url}")
        except Exception as e:
            print("⚠️ Keep-alive error:", e)
        time.sleep(300)  # كل 5 دقائق

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    print("🚀 بدء تشغيل Smart AI Scanner Web Worker")
    app.run(host="0.0.0.0", port=port)
