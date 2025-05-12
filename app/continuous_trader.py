"""
نظام التداول المستمر المحسن
يعمل في الخلفية كخدمة مستمرة تراقب وتدير الصفقات
يحل مشكلتي البيع وتنويع العملات بشكل جذري
"""

import os
import time
import logging
import threading
import signal
import sys
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("continuous_trader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# متغير للإشارة إلى استمرار التشغيل
running = False
trader_thread = None

def handle_exit(signum, frame):
    """
    معالج إشارات الخروج
    """
    global running
    logger.info("استلام إشارة خروج، إيقاف الخدمة")
    running = False

def run_trading_cycle():
    """
    تشغيل دورة تداول
    """
    try:
        from app.auto_trade import run_trade_cycle, get_active_symbols, force_sell_all
        
        stats = run_trade_cycle()
        logger.info(f"نتائج دورة التداول: {stats}")
        
        # عرض العملات المتداولة بعد الدورة
        active_symbols = get_active_symbols()
        logger.info(f"العملات المتداولة الحالية: {active_symbols}")
        
        return stats
    except Exception as e:
        logger.error(f"خطأ في تشغيل دورة التداول: {e}")
        return {'sold_trades': 0, 'opened_trades': 0}

def trader_service():
    """
    خدمة التداول الرئيسية - تعمل في الخلفية
    """
    global running
    
    logger.info("بدء خدمة التداول المستمر")
    
    # مدة الانتظار بين الدورات (بالثواني)
    cycle_interval = 300  # 5 دقائق
    
    # عدد الدورات قبل دورة البيع الإلزامي
    cycles_before_force_sell = 12  # كل ساعة إذا كانت المدة 5 دقائق
    
    cycle_count = 0
    
    while running:
        try:
            cycle_start = time.time()
            
            logger.info(f"بدء دورة التداول رقم {cycle_count+1}")
            
            # دورة بيع إلزامي كل عدة دورات
            if cycle_count % cycles_before_force_sell == 0 and cycle_count > 0:
                from app.auto_trade import force_sell_all
                logger.info("تشغيل دورة بيع إلزامي للتأكد من تحقيق الأرباح")
                sold_count = force_sell_all()
                logger.info(f"تم بيع {sold_count} صفقة بشكل إلزامي")
            
            # تشغيل دورة تداول عادية
            stats = run_trading_cycle()
            
            # عرض الوقت المستغرق
            cycle_time = time.time() - cycle_start
            logger.info(f"استغرقت الدورة {cycle_time:.2f} ثانية")
            
            # زيادة عداد الدورات
            cycle_count += 1
            
            # انتظار قبل الدورة التالية، مع مراعاة الوقت المستغرق
            wait_time = max(1, cycle_interval - cycle_time)
            logger.info(f"انتظار {wait_time:.2f} ثانية قبل الدورة التالية")
            
            # انتظار مع فحص متكرر لحالة التشغيل
            end_time = time.time() + wait_time
            while time.time() < end_time and running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("تم إيقاف الخدمة بواسطة المستخدم")
            running = False
            break
        except Exception as e:
            logger.error(f"خطأ في دورة التداول: {e}")
            # انتظار قبل المحاولة مرة أخرى
            time.sleep(60)
    
    logger.info("انتهت خدمة التداول المستمر")

def start_trader():
    """
    بدء تشغيل خدمة التداول
    """
    global running, trader_thread
    
    if running and trader_thread and trader_thread.is_alive():
        logger.warning("خدمة التداول قيد التشغيل بالفعل")
        return False
    
    # تسجيل معالجات الإشارات
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    running = True
    
    # إنشاء وتشغيل خيط التداول
    trader_thread = threading.Thread(target=trader_service)
    trader_thread.daemon = True
    trader_thread.start()
    
    logger.info("تم بدء تشغيل خدمة التداول")
    return True

def stop_trader():
    """
    إيقاف خدمة التداول
    """
    global running, trader_thread
    
    if not running or not trader_thread:
        logger.warning("خدمة التداول ليست قيد التشغيل")
        return False
    
    logger.info("إيقاف خدمة التداول")
    running = False
    
    # انتظار انتهاء الخيط (بحد أقصى 10 ثواني)
    if trader_thread.is_alive():
        trader_thread.join(10)
    
    logger.info("تم إيقاف خدمة التداول")
    return True

def get_trader_status():
    """
    الحصول على حالة خدمة التداول
    """
    global running, trader_thread
    
    if running and trader_thread and trader_thread.is_alive():
        return {"status": "running", "thread_alive": True}
    else:
        return {"status": "stopped", "thread_alive": trader_thread and trader_thread.is_alive()}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "start":
            start_trader()
            # إبقاء البرنامج قيد التشغيل
            while running:
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    stop_trader()
                    break
        elif command == "stop":
            stop_trader()
        elif command == "status":
            status = get_trader_status()
            print(f"حالة خدمة التداول: {status['status']}")
        else:
            print("أمر غير صالح. الأوامر المتاحة: start, stop, status")
    else:
        print("الاستخدام:")
        print("  python continuous_trader.py start   # بدء تشغيل خدمة التداول")
        print("  python continuous_trader.py stop    # إيقاف خدمة التداول")
        print("  python continuous_trader.py status  # عرض حالة خدمة التداول")