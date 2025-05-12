"""
ملف اختبار مباشر للتلجرام لتشخيص المشكلة
"""
import os
import requests
import logging

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_telegram_direct')

def test_direct():
    """اختبار مباشر لإرسال رسالة تلجرام باستخدام بيانات الاعتماد من متغيرات البيئة فقط"""
    
    # الحصول على بيانات الاعتماد من متغيرات البيئة مباشرة
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    if token:
        logger.info(f"TELEGRAM_BOT_TOKEN مأخوذ من متغيرات البيئة: {token[:4]}...{token[-4:]}")
    else:
        logger.error("TELEGRAM_BOT_TOKEN غير موجود في متغيرات البيئة!")
    logger.info(f"TELEGRAM_CHAT_ID مأخوذ من متغيرات البيئة: {chat_id}")
    
    # إنشاء رسالة للاختبار
    message = "🔄 رسالة مباشرة من اختبار التلجرام - تم إرسالها بواسطة test_telegram_direct.py"
    
    # إرسال الرسالة باستخدام طلب HTTP مباشر
    try:
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        params = {
            'chat_id': chat_id,
            'text': message
        }
        
        logger.info(f"إرسال طلب إلى: {url}")
        response = requests.get(url, params=params)
        
        logger.info(f"رمز الاستجابة: {response.status_code}")
        logger.info(f"محتوى الاستجابة: {response.text}")
        
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")
        return False

if __name__ == "__main__":
    result = test_direct()
    print(f"نتيجة الاختبار المباشر: {result}")