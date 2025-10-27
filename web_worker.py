# web_worker.py
import os
import threading
from flask import Flask, jsonify
import main  # يفترض أن main.py في نفس المجلد ويحتوي start_worker_loop() + watched_tokens

app = Flask(__name__)

@app.route("/_healthz")
def health():
    try:
        count = len(main.watched_tokens)
    except Exception:
        count = 0
    return jsonify({"status":"ok","watch_count": count})

# start the scanner loop in background
threading.Thread(target=main.start_worker_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
    
