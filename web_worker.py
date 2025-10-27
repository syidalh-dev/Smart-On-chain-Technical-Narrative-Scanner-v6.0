# web_worker.py
import os
import threading
import time
from flask import Flask, jsonify
from datetime import datetime, timezone

# import scanner (main.py)
try:
    import main as scanner
except Exception as e:
    scanner = None
    print("⚠️ Failed to import main.py:", e)

app = Flask(__name__)

@app.route("/_healthz")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "scanner_loaded": bool(scanner is not None)
    })

def run_scanner():
    if scanner is None:
        print("⚠️ scanner module not available; skipping background run.")
        return
    # Prefer explicit start_worker_loop if exists
    if hasattr(scanner, "start_worker_loop"):
        try:
            scanner.start_worker_loop()
            return
        except Exception as e:
            print("⚠️ start_worker_loop failed:", e)
    # Fallback (safe): call analyze_and_score repeatedly
    SLEEP = getattr(scanner, "SLEEP_MINUTES", 30.0)
    TOP_K = getattr(scanner, "TOP_K", 8)
    while True:
        try:
            signals = []
            if hasattr(scanner, "analyze_and_score"):
                signals = scanner.analyze_and_score(top_k=TOP_K)
            if signals and hasattr(scanner, "build_message") and hasattr(scanner, "send_telegram_message"):
                msg = scanner.build_message(signals)
                scanner.send_telegram_message(msg)
                if hasattr(scanner, "save_results_to_file"):
                    try:
                        scanner.save_results_to_file(signals)
                    except Exception as e:
                        print("⚠️ save_results error:", e)
            else:
                print("📉 No signals in this cycle.")
        except Exception as e:
            print("⚠️ Error in fallback scanner loop:", e)
        time.sleep(float(SLEEP) * 60)

if __name__ == "__main__":
    # launch scanner thread
    t = threading.Thread(target=run_scanner, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
