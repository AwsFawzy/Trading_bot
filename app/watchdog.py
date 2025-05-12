"""
نظام مراقبة حالة البوت وإرسال إشعارات التوقف
"""
import os
import time
import requests
import logging
import threading
from datetime import datetime, timedelta

from app.telegram_notify import send_telegram_message
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.trading_bot import get_bot_status, BOT_STATE
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('watchdog')

# المتغيرات العالمية
WATCHDOG_INTERVAL = 300  # التحقق كل 5 دقائق
ALERT_INTERVAL = 1800  # لا ترسل تنبيهات متكررة في فترة أقل من 30 دقيقة
last_alert_time = 0  # وقت آخر تنبيه تم إرساله
watchdog_thread = None  # متغير لتخزين الثريد
is_watchdog_running = False

def check_bot_status():
    """
    التحقق من حالة البوت وإرسال إشعارات إذا كان متوقفاً - مع محاولة إعادة التشغيل التلقائية
    نظام مراقبة 24/7 للتأكد من عمل البوت باستمرار حتى عند إغلاق الهاتف أو انقطاع الإنترنت
    """
    global last_alert_time
    
    try:
        # التحقق من حالة البوت
        bot_status = get_bot_status()
        bot_running = bot_status.get('running', False)
        
        # حساب وقت التشغيل إذا كان البوت يعمل
        uptime_string = "غير متاح"
        start_time = BOT_STATE.get('start_time')
        if start_time and bot_running:
            uptime = datetime.now() - start_time
            hours, remainder = divmod(uptime.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_string = f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
        
        # تحقق من نشاط البوت (هل هو خامل؟)
        is_bot_active = False
        last_activity = BOT_STATE.get('last_activity_time')
        
        if last_activity:
            time_since_activity = (datetime.now() - last_activity).total_seconds()
            # إذا كان آخر نشاط في آخر 5 دقائق، فالبوت نشط
            is_bot_active = time_since_activity < 300  # 5 دقائق
        
        # تسجيل حالة البوت
        if bot_running:
            activity_status = "نشط ✅" if is_bot_active else "خامل ⚠️"
            logger.info(f"نظام المراقبة: البوت يعمل {activity_status} | وقت التشغيل: {uptime_string}")
            
            # إذا كان البوت خاملاً لفترة طويلة، حاول إعادة تنشيطه
            if not is_bot_active and last_activity:
                current_time = time.time()
                if current_time - last_alert_time > ALERT_INTERVAL:
                    # محاولة إعادة تشغيل البوت
                    from app.trading_bot import restart_bot
                    logger.warning(f"البوت خامل منذ {time_since_activity:.1f} ثوانٍ. محاولة إعادة تنشيطه...")
                    
                    # إعادة تشغيل البوت
                    restart_result = restart_bot()
                    
                    # إرسال إشعار عبر تيليجرام
                    alert_message = f"⚠️ تنبيه! تم اكتشاف أن البوت خامل.\n⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n✅ تمت محاولة إعادة تنشيطه تلقائيًا."
                    send_telegram_message(alert_message)
                    logger.info(f"تم إرسال إشعار عن إعادة تنشيط البوت عبر تيليجرام")
                    
                    # تحديث وقت آخر تنبيه
                    last_alert_time = current_time
        else:
            logger.error(f"نظام المراقبة: البوت متوقف ❌")
            
            # التحقق مما إذا كان يمكن إرسال تنبيه (لتجنب التنبيهات المتكررة)
            current_time = time.time()
            if current_time - last_alert_time > ALERT_INTERVAL:
                # محاولة إعادة تشغيل البوت أولاً
                from app.trading_bot import restart_bot
                logger.warning("البوت متوقف. محاولة إعادة تشغيله تلقائيًا...")
                restart_result = restart_bot()
                
                restart_status = "بنجاح ✅" if restart_result else "بفشل ❌"
                
                # إرسال إشعار عبر تيليجرام
                alert_message = f"⚠️ تنبيه! البوت كان متوقفًا عن العمل!\n⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🔄 تمت محاولة إعادة تشغيله تلقائيًا {restart_status}."
                send_telegram_message(alert_message)
                logger.info(f"تم إرسال إشعار توقف البوت وإعادة تشغيله عبر تيليجرام")
                
                # تحديث وقت آخر تنبيه
                last_alert_time = current_time
                
                # إذا فشلت إعادة التشغيل، حاول مرة أخرى بطريقة بديلة
                if not restart_result:
                    try:
                        # جرب تنفيذ إعادة التشغيل بطريقة بديلة
                        import os
                        # تنفيذ أمر إعادة التشغيل للبوت
                        os.system("python3 restart_bot_task.sh &")
                        logger.info("تم تنفيذ أمر إعادة التشغيل الاحتياطي")
                    except Exception as e:
                        logger.error(f"فشل في تنفيذ إعادة التشغيل الاحتياطية: {e}")
    except Exception as e:
        logger.error(f"حدث خطأ أثناء التحقق من حالة البوت: {e}")

def watchdog_loop():
    """
    حلقة المراقبة المستمرة
    """
    global is_watchdog_running
    
    logger.info("بدء نظام مراقبة البوت...")
    is_watchdog_running = True
    
    try:
        while is_watchdog_running:
            # التحقق من حالة البوت
            check_bot_status()
            
            # الانتظار للتحقق التالي
            time.sleep(WATCHDOG_INTERVAL)
    except Exception as e:
        logger.error(f"حدث خطأ في نظام المراقبة: {e}")
        is_watchdog_running = False
    
    logger.info("تم إيقاف نظام مراقبة البوت.")

def start_watchdog():
    """
    بدء نظام المراقبة في خيط منفصل
    """
    global watchdog_thread, is_watchdog_running
    
    # التحقق مما إذا كان نظام المراقبة يعمل بالفعل
    if watchdog_thread and watchdog_thread.is_alive():
        logger.info("نظام المراقبة يعمل بالفعل.")
        return False
    
    # إنشاء خيط جديد لنظام المراقبة
    watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
    watchdog_thread.start()
    
    logger.info("تم بدء نظام مراقبة البوت بنجاح.")
    return True

def stop_watchdog():
    """
    إيقاف نظام المراقبة
    """
    global is_watchdog_running
    
    is_watchdog_running = False
    logger.info("تم إرسال طلب إيقاف نظام المراقبة.")
    return True

def is_watchdog_active():
    """
    التحقق مما إذا كان نظام المراقبة نشطًا
    """
    global watchdog_thread, is_watchdog_running
    
    if watchdog_thread and watchdog_thread.is_alive() and is_watchdog_running:
        return True
    return False

def send_ping_to_prevent_sleep():
    """
    إرسال طلب HTTP إلى التطبيق نفسه لمنعه من الدخول في وضع السكون
    """
    try:
        # استخراج عنوان URL من متغيرات البيئة إذا كان متاحًا
        app_url = os.environ.get("REPLIT_DEPLOYMENT_URL")
        if not app_url:
            # في حالة عدم وجود متغير بيئة، يمكن استخدام 'localhost'
            app_url = "http://localhost:5000"
        
        # إرسال طلب GET إلى الصفحة الرئيسية
        response = requests.get(f"{app_url}/", timeout=10)
        if response.status_code == 200:
            logger.info(f"تم إرسال إشارة لمنع وضع السكون بنجاح. الاستجابة: {response.status_code}")
            return True
        else:
            logger.warning(f"فشل إرسال إشارة لمنع وضع السكون. الاستجابة: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"حدث خطأ أثناء محاولة منع وضع السكون: {e}")
        return False

# في حالة التشغيل المباشر لملف watchdog.py
if __name__ == "__main__":
    start_watchdog()