# worker.py — continuous monitor for v6.0
import os
import time
import json
from datetime import datetime, timedelta
from main import scan_once, build_message, send_telegram_message

HISTORY_FILE = os.getenv("HISTORY_FILE", "history_v6.json")
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "300"))  # 5 minutes default
NO_REPEAT_HOURS = int(os.getenv("NO_REPEAT_HOURS", "24"))

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_history(h):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("⚠️ save_history error:", e)

def should_send(symbol, history):
    last = history.get(symbol)
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        return (datetime.utcnow() - last_dt) > timedelta(hours=NO_REPEAT_HOURS)
    except Exception:
        return True

def main_loop():
    history = load_history()
    print("Worker v6.0 started — interval:", SLEEP_SECONDS, "sec —", datetime.utcnow().isoformat())
    while True:
        try:
            signals = scan_once()
            if not signals:
                print(datetime.utcnow().isoformat(), "— no signals")
            else:
                # filter by history
                new = []
                for s in signals:
                    sym = s.get("symbol")
                    if sym and should_send(sym, history):
                        new.append(s)
                if new:
                    msg = build_message(new)
                    ok = send_telegram_message(msg)
                    if ok:
                        for s in new:
                            history[s["symbol"]] = datetime.utcnow().isoformat()
                        save_history(history)
                        print(datetime.utcnow().isoformat(), f"— sent {len(new)} signals")
                    else:
                        print(datetime.utcnow().isoformat(), "— telegram send failed")
                else:
                    print(datetime.utcnow().isoformat(), "— no NEW signals after history filter")
        except Exception as e:
            print("Worker exception:", e)
        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main_loop()
