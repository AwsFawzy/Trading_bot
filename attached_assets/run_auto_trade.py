"""
سكريبت تشغيل نظام التداول الآلي المحسن
يعالج مشكلتي البيع وتنويع العملات بشكل جذري
"""

import logging
import time
import sys
import argparse

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auto_trade.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    الدالة الرئيسية لتشغيل النظام
    """
    # إعداد محلل المعاملات
    parser = argparse.ArgumentParser(description='نظام التداول الآلي المحسن')
    parser.add_argument('--sell-all', action='store_true', help='بيع جميع الصفقات المفتوحة')
    parser.add_argument('--cycle', action='store_true', help='تشغيل دورة تداول كاملة')
    parser.add_argument('--check', action='store_true', help='التحقق من العملات المتداولة حالياً')
    parser.add_argument('--diversify', action='store_true', help='تنويع المحفظة')
    
    args = parser.parse_args()
    
    # استيراد النظام
    try:
        from app.auto_trade import force_sell_all, run_trade_cycle, get_active_symbols, diversify_portfolio
    except ImportError as e:
        logger.error(f"خطأ في استيراد النظام: {e}")
        print(f"خطأ في استيراد النظام: {e}")
        return False
        
    # تنفيذ العملية المطلوبة
    if args.sell_all:
        # بيع جميع الصفقات المفتوحة
        logger.info("بدء بيع جميع الصفقات المفتوحة")
        sold_count = force_sell_all()
        logger.info(f"تم بيع {sold_count} صفقة بنجاح")
        print(f"تم بيع {sold_count} صفقة بنجاح")
        
    elif args.cycle:
        # تشغيل دورة تداول كاملة
        logger.info("بدء دورة تداول كاملة")
        stats = run_trade_cycle()
        logger.info(f"نتائج الدورة: {stats}")
        print(f"نتائج الدورة: تم بيع {stats['sold_trades']} صفقة وفتح {stats['opened_trades']} صفقة جديدة")
        
    elif args.check:
        # التحقق من العملات المتداولة حالياً
        active_symbols = get_active_symbols()
        logger.info(f"العملات المتداولة حالياً: {active_symbols}")
        print(f"العملات المتداولة حالياً: {active_symbols}")
        print(f"عدد العملات المتداولة: {len(active_symbols)}")
        
    elif args.diversify:
        # تنويع المحفظة
        logger.info("بدء تنويع المحفظة")
        opened_count = diversify_portfolio()
        logger.info(f"تم فتح {opened_count} صفقة جديدة")
        print(f"تم فتح {opened_count} صفقة جديدة")
        
        # عرض العملات المتداولة بعد التنويع
        active_symbols = get_active_symbols()
        logger.info(f"العملات المتداولة بعد التنويع: {active_symbols}")
        print(f"العملات المتداولة بعد التنويع: {active_symbols}")
        
    else:
        # عرض الاستخدام
        print("الاستخدام:")
        print("  python run_auto_trade.py --sell-all    # بيع جميع الصفقات المفتوحة")
        print("  python run_auto_trade.py --cycle       # تشغيل دورة تداول كاملة")
        print("  python run_auto_trade.py --check       # التحقق من العملات المتداولة حالياً")
        print("  python run_auto_trade.py --diversify   # تنويع المحفظة")
        
    return True
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nتم إلغاء التشغيل")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطأ في تشغيل النظام: {e}")
        print(f"خطأ في تشغيل النظام: {e}")
        sys.exit(1)