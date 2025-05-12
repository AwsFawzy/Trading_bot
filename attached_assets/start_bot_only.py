"""
ملف لتشغيل بوت التداول فقط بدون واجهة الويب
"""
import logging
import time
import os
import sys
from app.trading_bot import start_auto_trader, stop_auto_trader, get_auto_trader_status
from app.watchdog import start_watchdog

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """تشغيل البوت في الخلفية والانتظار"""
    logger.info("بدء تشغيل البوت في وضع الخلفية...")
    
    # بدء نظام المراقبة
    start_watchdog()
    
    # بدء بوت التداول
    start_result = start_auto_trader()
    if not start_result:
        logger.error("فشل بدء تشغيل البوت!")
        return False
    
    logger.info("تم بدء البوت بنجاح!")
    
    try:
        # الانتظار مع عرض معلومات كل دقيقة
        i = 0
        while True:
            # عرض معلومات الحالة كل 60 ثانية
            if i % 60 == 0:
                status = get_auto_trader_status()
                uptime = status.get('uptime', 'غير متاح')
                logger.info(f"البوت يعمل ✅ | وقت التشغيل: {uptime}")
            
            time.sleep(1)
            i += 1
            
    except KeyboardInterrupt:
        logger.info("تم استلام إشارة إيقاف...")
    except Exception as e:
        logger.error(f"حدث خطأ: {str(e)}")
    finally:
        # محاولة إيقاف البوت بشكل نظيف
        logger.info("إيقاف البوت...")
        stop_auto_trader()
        logger.info("تم إيقاف البوت بنجاح.")
    
    return True

if __name__ == "__main__":
    main()