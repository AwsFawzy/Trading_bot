"""
سكريبت لإيقاف البوت مباشرة من خلال استدعاء وظيفة stop_bot
"""
import sys
import logging
import os

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# استيراد وظيفة إيقاف البوت
try:
    from app.trading_bot import stop_bot, get_bot_status
    
    logger.info("حالة البوت قبل محاولة الإيقاف:")
    status = get_bot_status()
    logger.info(f"Bot running: {status.get('running', False)}")
    
    # محاولة إيقاف البوت
    result = stop_bot()
    
    logger.info(f"نتيجة محاولة إيقاف البوت: {result}")
    
    # التحقق من حالة البوت بعد الإيقاف
    status_after = get_bot_status()
    logger.info(f"حالة البوت بعد محاولة الإيقاف: {status_after.get('running', False)}")
    
except Exception as e:
    logger.error(f"حدث خطأ أثناء محاولة إيقاف البوت: {e}")
    sys.exit(1)