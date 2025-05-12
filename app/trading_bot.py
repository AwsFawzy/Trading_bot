"""
بوت التداول الرئيسي - يتحكم في تشغيل دورات التداول بشكل مستمر
يجمع بين المكونات المختلفة للنظام في واجهة موحدة
"""
import logging
import threading
import time
from typing import Dict, Any

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trading_bot')

# استيراد نظام التداول
from app.trading_system import (
    clean_fake_trades,
    check_and_sell_trades,
    diversify_portfolio,
    manage_trades,
    force_sell_all,
    run_trade_cycle
)

# استيراد نظام مراقبة السوق
try:
    from app.market_scanner import scan_market
except ImportError:
    # دالة بديلة في حالة عدم وجود وحدة market_scanner
    def scan_market() -> Dict[str, Any]:
        """دالة بديلة لفحص السوق في حالة عدم وجود الوحدة الأصلية"""
        logger.warning("❌ تم استدعاء الدالة البديلة لـ scan_market لأن الوحدة الأصلية غير موجودة")
        return {"opportunities": [], "timestamp": int(time.time())}

# حالة البوت
BOT_STATUS = {
    'running': False,
    'thread': None,
    'last_run': 0,
    'cycle_count': 0,
    'stats': {}
}

def trading_loop():
    """
    حلقة التداول الرئيسية للبوت
    تعمل في خيط منفصل وتدير عمليات التداول بشكل مستمر
    """
    try:
        logger.info("🚀 بدء تشغيل حلقة التداول")
        
        BOT_STATUS['running'] = True
        BOT_STATUS['cycle_count'] = 0
        
        # تنظيف الصفقات الوهمية عند بدء التشغيل
        logger.info("🧹 تنظيف الصفقات الوهمية عند بدء التشغيل")
        clean_result = clean_fake_trades()
        logger.info(f"🧹 نتيجة التنظيف: {clean_result}")
        
        # سجل لتتبع العملات التي تم تداولها مؤخراً
        recent_trades = set()
        
        # استمرار الحلقة طالما البوت يعمل
        while BOT_STATUS['running']:
            try:
                cycle_start_time = time.time()
                BOT_STATUS['last_run'] = cycle_start_time
                BOT_STATUS['cycle_count'] += 1
                
                logger.info(f"📊 دورة التداول رقم {BOT_STATUS['cycle_count']}")
                
                # 1. تشغيل دورة التداول الكاملة (بيع الصفقات المؤهلة وفتح صفقات جديدة)
                stats = run_trade_cycle()
                BOT_STATUS['stats'] = stats
                
                # 2. فحص السوق للحصول على فرص جديدة
                scan_result = scan_market()
                
                # حساب الوقت المستغرق في الدورة
                cycle_duration = time.time() - cycle_start_time
                logger.info(f"⏱️ استغرقت دورة التداول {cycle_duration:.1f} ثانية")
                
                # انتظار 15 دقيقة (900 ثانية) بين الدورات
                # أو أقل إذا كانت الدورة استغرقت وقتاً طويلاً
                sleep_time = max(60, 900 - cycle_duration)  # ننتظر على الأقل دقيقة واحدة
                logger.info(f"💤 انتظار {sleep_time:.0f} ثانية قبل الدورة التالية")
                
                # تقسيم وقت الانتظار لإتاحة التوقف السريع
                wait_intervals = 6  # نتحقق كل 10 ثوانٍ
                interval_time = sleep_time / wait_intervals
                
                for _ in range(wait_intervals):
                    if not BOT_STATUS['running']:
                        break
                    time.sleep(interval_time)
                
            except Exception as cycle_error:
                logger.error(f"❌ خطأ في دورة التداول: {cycle_error}")
                # ننتظر قليلاً ثم نستمر
                time.sleep(60)
        
        logger.info("🛑 انتهت حلقة التداول")
    except Exception as e:
        logger.error(f"❌❌ خطأ كارثي في حلقة التداول: {e}")
        BOT_STATUS['running'] = False

def start_bot() -> bool:
    """
    بدء تشغيل البوت
    
    :return: نجاح العملية
    """
    try:
        if BOT_STATUS['running']:
            logger.warning("البوت يعمل بالفعل")
            return False
            
        # إنشاء خيط جديد لحلقة التداول
        BOT_STATUS['thread'] = threading.Thread(target=trading_loop)
        BOT_STATUS['thread'].daemon = True
        BOT_STATUS['thread'].start()
        
        logger.info("🚀 تم بدء تشغيل البوت بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في بدء تشغيل البوت: {e}")
        BOT_STATUS['running'] = False
        return False

def stop_bot() -> bool:
    """
    إيقاف تشغيل البوت
    
    :return: نجاح العملية
    """
    try:
        if not BOT_STATUS['running']:
            logger.warning("البوت متوقف بالفعل")
            return False
            
        # إيقاف الحلقة
        BOT_STATUS['running'] = False
        
        # انتظار انتهاء الخيط (بحد أقصى 5 ثوانٍ)
        if BOT_STATUS['thread'] and BOT_STATUS['thread'].is_alive():
            BOT_STATUS['thread'].join(5)
            
        logger.info("🛑 تم إيقاف البوت بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في إيقاف البوت: {e}")
        return False

def get_bot_status() -> Dict[str, Any]:
    """
    الحصول على حالة البوت
    
    :return: معلومات حالة البوت
    """
    return {
        'running': BOT_STATUS['running'],
        'last_run': BOT_STATUS['last_run'],
        'cycle_count': BOT_STATUS['cycle_count'],
        'stats': BOT_STATUS['stats']
    }

def execute_manual_trade_cycle() -> Dict[str, Any]:
    """
    تنفيذ دورة تداول يدوية
    
    :return: نتائج الدورة
    """
    try:
        logger.info("🔄 تنفيذ دورة تداول يدوية")
        stats = run_trade_cycle()
        logger.info(f"📊 نتائج دورة التداول اليدوية: {stats}")
        return stats
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ دورة التداول اليدوية: {e}")
        return {'error': str(e)}

def clean_all_fake_trades() -> Dict[str, Any]:
    """
    تنظيف جميع الصفقات الوهمية
    
    :return: نتائج التنظيف
    """
    try:
        logger.info("🧹 تنظيف الصفقات الوهمية")
        result = clean_fake_trades()
        logger.info(f"🧹 نتائج التنظيف: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف الصفقات الوهمية: {e}")
        return {'error': str(e)}

def sell_all_trades() -> int:
    """
    بيع جميع الصفقات المفتوحة
    
    :return: عدد الصفقات التي تم بيعها
    """
    try:
        logger.info("💰 بيع جميع الصفقات المفتوحة")
        sold_count = force_sell_all()
        logger.info(f"💰 تم بيع {sold_count} صفقة")
        return sold_count
    except Exception as e:
        logger.error(f"❌ خطأ في بيع جميع الصفقات: {e}")
        return 0

def scan_and_update() -> Dict[str, Any]:
    """
    فحص السوق وتحديث قائمة الفرص
    
    :return: نتائج الفحص
    """
    try:
        logger.info("🔍 فحص السوق")
        scan_result = scan_market()
        logger.info(f"🔍 تم فحص السوق وإيجاد {len(scan_result.get('opportunities', []))} فرصة")
        return scan_result
    except Exception as e:
        logger.error(f"❌ خطأ في فحص السوق: {e}")
        return {'error': str(e)}

def check_bot_health() -> Dict[str, Any]:
    """
    التحقق من صحة البوت وإعادة تشغيله إذا لزم الأمر
    
    :return: حالة البوت
    """
    try:
        logger.info("🩺 فحص صحة البوت")
        bot_status = get_bot_status()
        
        # إذا كان البوت متوقفًا، نحاول إعادة تشغيله
        if not bot_status.get('running', False):
            logger.warning("⚠️ البوت متوقف، محاولة إعادة تشغيله")
            start_bot()
            # التحقق من حالة البوت بعد محاولة إعادة التشغيل
            new_status = get_bot_status()
            logger.info(f"🩺 حالة البوت بعد محاولة إعادة التشغيل: {new_status}")
            return new_status
        
        logger.info("✅ البوت يعمل بشكل صحيح")
        return bot_status
    except Exception as e:
        logger.error(f"❌ خطأ في فحص صحة البوت: {e}")
        return {'error': str(e), 'running': False}