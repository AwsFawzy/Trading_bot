"""
ملف خاص لبدء تشغيل التطبيق على منصة Render
يقوم بتشغيل خادم الويب وبوت التداول معًا
"""
import os
import threading
import logging
from main import app, start_all_background_tasks
import gunicorn.app.base

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_bot_thread():
    """تشغيل البوت في خيط منفصل"""
    logger.info("بدء تشغيل بوت التداول...")
    start_all_background_tasks()

class StandaloneApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            if hasattr(self.cfg, "settings") and key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)
            else:
                # Fallback for older versions of gunicorn
                setattr(self.cfg, key.lower(), value)

    def load(self):
        return self.application

if __name__ == "__main__":
    # الحصول على رقم المنفذ من متغيرات البيئة أو استخدام 5000 كقيمة افتراضية
    port = int(os.environ.get("PORT", 5000))
    
    # بدء تشغيل بوت التداول في خيط منفصل
    bot_thread = threading.Thread(target=start_bot_thread)
    bot_thread.daemon = True  # جعل الخيط daemon لإيقافه عند توقف البرنامج الرئيسي
    bot_thread.start()
    
    logger.info(f"بدء تشغيل خادم الويب على المنفذ {port}...")
    
    # تكوين خيارات Gunicorn
    options = {
        'bind': f'0.0.0.0:{port}',
        'workers': 1,
        'reuse_port': True,
        'timeout': 120
    }
    
    # تشغيل خادم الويب
    StandaloneApplication(app, options).run()