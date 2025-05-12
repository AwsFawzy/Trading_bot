"""
ملف اختبار لإشعارات تلجرام
"""
from app.telegram_notify import send_telegram_message, notify_bot_status
import logging

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_telegram')

def test_send_telegram():
    """اختبار إرسال رسالة تلجرام مباشرة"""
    logger.info("بدء اختبار إرسال رسالة تلجرام...")
    result = send_telegram_message("🔄 هذه رسالة اختبار من بوت التداول - تم إعادة توصيل الإشعارات بنجاح!")
    logger.info(f"نتيجة إرسال الرسالة: {result}")
    return result

def test_bot_status_notification():
    """اختبار إرسال إشعار حالة البوت"""
    logger.info("بدء اختبار إرسال إشعار حالة البوت...")
    notify_bot_status("info", "تم إعادة تشغيل نظام الإشعارات واستعادة الاتصال بتلجرام")
    logger.info("تم إرسال إشعار حالة البوت")
    return True

if __name__ == "__main__":
    test_send_telegram()
    test_bot_status_notification()