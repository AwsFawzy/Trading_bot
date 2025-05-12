"""
مراقب الاتصال بالإنترنت والتعافي من الانقطاع
يفحص بشكل دوري حالة الاتصال بالإنترنت ويعمل على إعادة تنشيط البوت عند عودة الاتصال
"""
import threading
import time
import logging
import requests
from datetime import datetime, timedelta
from app.telegram_notify import send_telegram_message

logger = logging.getLogger('internet_monitor')

# متغيرات حالة الاتصال
CONNECTION_STATE = {
    'online': True,  # حالة الاتصال الحالية
    'last_check': datetime.now(),  # آخر فحص تم إجراؤه
    'offline_since': None,  # متى انقطع الاتصال
    'recovery_count': 0,  # عدد مرات التعافي
    'check_thread': None,  # خيط فحص الاتصال
    'running': False  # هل مراقب الاتصال قيد التشغيل
}

# قائمة المواقع للتحقق من الاتصال
TEST_URLS = [
    'https://www.google.com',
    'https://www.cloudflare.com',
    'https://www.microsoft.com',
    'https://www.mexc.com',
    'https://api.telegram.org'
]

# الفترة بين فحوصات الاتصال (بالثواني)
CHECK_INTERVAL = 60  # دقيقة واحدة

def is_internet_connected():
    """
    التحقق من الاتصال بالإنترنت عن طريق محاولة الوصول إلى عدة مواقع
    
    :return: True إذا كان الاتصال متاحًا، False إذا كان مقطوعًا
    """
    successful_connections = 0
    timeout = 5  # 5 ثوانٍ كمهلة زمنية للاتصال
    
    for url in TEST_URLS:
        try:
            response = requests.head(url, timeout=timeout)
            if response.status_code < 400:  # أي رمز نجاح HTTP
                successful_connections += 1
                if successful_connections >= 2:  # نعتبر الاتصال متاحًا إذا نجحنا في الوصول إلى موقعين على الأقل
                    return True
        except requests.RequestException:
            continue
    
    return False

def check_connection_periodically():
    """
    فحص دوري للاتصال بالإنترنت ومعالجة حالات الانقطاع والاستعادة
    """
    from app.trading_bot import restart_bot, get_bot_status, is_bot_running
    
    while CONNECTION_STATE['running']:
        current_time = datetime.now()
        CONNECTION_STATE['last_check'] = current_time
        
        # فحص الاتصال بالإنترنت
        is_connected = is_internet_connected()
        
        # إذا كان متصلاً الآن ولم يكن متصلاً سابقًا (تعافي من انقطاع)
        if is_connected and not CONNECTION_STATE['online']:
            offline_duration = "غير معروف"
            if CONNECTION_STATE['offline_since']:
                offline_duration = str(current_time - CONNECTION_STATE['offline_since'])
            
            logger.info(f"✅ تم استعادة الاتصال بالإنترنت بعد انقطاع استمر {offline_duration}")
            
            # زيادة عداد التعافي
            CONNECTION_STATE['recovery_count'] += 1
            
            # إعادة تشغيل البوت إذا كان متوقفًا
            bot_status = get_bot_status()
            if not is_bot_running():
                logger.info("⚠️ البوت متوقف. محاولة إعادة تشغيله...")
                restart_bot()
                send_telegram_message(f"⚠️ تم استعادة الاتصال بالإنترنت بعد انقطاع استمر {offline_duration}. تمت إعادة تشغيل البوت.")
            else:
                send_telegram_message(f"✅ تم استعادة الاتصال بالإنترنت بعد انقطاع استمر {offline_duration}. البوت يعمل بشكل طبيعي.")
            
            # تحديث حالة الاتصال
            CONNECTION_STATE['online'] = True
            CONNECTION_STATE['offline_since'] = None
        
        # إذا كان غير متصل الآن وكان متصلاً سابقًا (انقطاع جديد)
        elif not is_connected and CONNECTION_STATE['online']:
            logger.warning("⚠️ انقطاع في الاتصال بالإنترنت")
            
            # تحديث حالة الاتصال
            CONNECTION_STATE['online'] = False
            CONNECTION_STATE['offline_since'] = current_time
        
        # إذا استمر الانقطاع لفترة طويلة، نسجل ذلك
        elif not is_connected and CONNECTION_STATE['offline_since']:
            offline_duration = current_time - CONNECTION_STATE['offline_since']
            if offline_duration > timedelta(minutes=5) and offline_duration.seconds % 300 < CHECK_INTERVAL:  # تسجيل كل 5 دقائق
                logger.warning(f"⚠️ استمرار انقطاع الاتصال بالإنترنت منذ {offline_duration}")
        
        # انتظار للفحص التالي
        time.sleep(CHECK_INTERVAL)

def start_connection_monitor():
    """
    بدء مراقبة الاتصال بالإنترنت في خيط منفصل
    
    :return: True إذا تم بدء المراقبة بنجاح، False إذا كانت قيد التشغيل بالفعل
    """
    if CONNECTION_STATE['running']:
        logger.info("مراقب الاتصال بالإنترنت قيد التشغيل بالفعل")
        return False
    
    # تحديث حالة التشغيل
    CONNECTION_STATE['running'] = True
    
    # إنشاء خيط منفصل للمراقبة
    CONNECTION_STATE['check_thread'] = threading.Thread(
        target=check_connection_periodically,
        daemon=True  # خيط daemon يتوقف عندما يتوقف البرنامج الرئيسي
    )
    CONNECTION_STATE['check_thread'].start()
    
    logger.info("✅ تم بدء مراقبة الاتصال بالإنترنت")
    return True

def stop_connection_monitor():
    """
    إيقاف مراقبة الاتصال بالإنترنت
    
    :return: True إذا تم إيقاف المراقبة بنجاح، False إذا لم تكن قيد التشغيل
    """
    if not CONNECTION_STATE['running']:
        logger.info("مراقب الاتصال بالإنترنت ليس قيد التشغيل")
        return False
    
    # تحديث حالة التشغيل
    CONNECTION_STATE['running'] = False
    
    # الانتظار لإنهاء الخيط (مع مهلة زمنية)
    if CONNECTION_STATE['check_thread'] and CONNECTION_STATE['check_thread'].is_alive():
        CONNECTION_STATE['check_thread'].join(timeout=2)
    
    logger.info("✅ تم إيقاف مراقبة الاتصال بالإنترنت")
    return True

def get_connection_status():
    """
    الحصول على حالة الاتصال الحالية
    
    :return: قاموس بمعلومات حالة الاتصال
    """
    return {
        'online': CONNECTION_STATE['online'],
        'last_check': CONNECTION_STATE['last_check'],
        'offline_since': CONNECTION_STATE['offline_since'],
        'recovery_count': CONNECTION_STATE['recovery_count'],
        'monitoring_active': CONNECTION_STATE['running']
    }

def ping_telegram():
    """
    إرسال بينج اختباري إلى تلجرام للتأكد من عمل الإشعارات
    
    :return: True إذا نجح الإرسال، False إذا فشل
    """
    try:
        send_telegram_message("🔄 هذا اختبار لنظام الإشعارات. البوت يعمل بشكل طبيعي.")
        return True
    except Exception as e:
        logger.error(f"فشل في إرسال رسالة اختبار إلى تلجرام: {e}")
        return False

def force_reconnect():
    """
    إجبار البوت على إعادة الاتصال وإرسال إشعار للتأكد من استعادة الاتصال
    
    :return: True إذا نجحت العملية، False إذا فشلت
    """
    try:
        # محاولة إعادة تشغيل البوت
        from app.trading_bot import restart_bot
        restart_bot()
        
        # إرسال إشعار تأكيد
        success = ping_telegram()
        
        # تسجيل النتيجة
        if success:
            logger.info("✅ تم إجبار إعادة الاتصال بنجاح")
        else:
            logger.error("❌ فشل في إجبار إعادة الاتصال")
        
        return success
    except Exception as e:
        logger.error(f"حدث خطأ أثناء محاولة إجبار إعادة الاتصال: {e}")
        return False