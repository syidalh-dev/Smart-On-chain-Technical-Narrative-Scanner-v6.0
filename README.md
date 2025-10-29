# Smart-On-chain-Technical-Narrative-Scanner-v6.0
# 🧠 Smart AI Scanner

مشروع لتحليل السوق الذكي باستخدام البيانات على السلسلة والتحليل الفني والذكاء الاصطناعي.

### 🔍 الملفات
- `main.py` — الكود الأساسي للتحليل والتقارير اليومية
- `smart_insights.py` — تحليل تدفق الأموال الذكية والشراكات وعدد الحاملين
- `market_narratives_ai.py` — تحليل السرديات الذكية في السوق
- `web_worker.py` — خادم Flask لتشغيل الواجهة والحلقات الدورية
- `templates/index.html` — صفحة الحالة
- `requirements.txt` — مكتبات التشغيل

### ⚙️ الإعداد على Render
- أنشئ **Web Service** من هذا المستودع.
- أمر البناء: `pip install -r requirements.txt`
- أمر التشغيل: `python web_worker.py`
- أضف المتغيرات البيئية:
  - `TELEGRAM_TOKEN`
  - `TELEGRAM_CHAT_ID`
- يرسل التلغرام إشارات قوية تلقائياً + تقرير صباحي 6:00 بتوقيت ليبيا.
