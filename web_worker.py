# web_worker.py
from flask import Flask
import threading
import main  # <-- هذا يستدعي كودك الأساسي

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Smart AI Scanner is running (Render Free Plan Mode)."

# تشغيل الكود الرئيسي في خيط منفصل
def background_worker():
    main.main_loop()  # سنضيف هذه الدالة في main.py بعد قليل

threading.Thread(target=background_worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
    
