from flask import Flask
import threading
import main

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Smart AI Scanner is running (Render Free Plan Mode)."

# Start the scanner in a background thread
threading.Thread(target=main.start_worker_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
  
