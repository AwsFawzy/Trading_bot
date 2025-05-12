"""
سكريبت لتشغيل مدير الصفقات المحسن
"""

import logging
import time
import sys
from app.enhanced_trade_manager import manage_all_trades, get_traded_symbols, force_sell_stale_trades

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    الدالة الرئيسية لتشغيل مدير الصفقات
    """
    logger.info("بدء تشغيل مدير الصفقات المحسن")
    
    # عرض العملات المتداولة حالياً
    traded_symbols = get_traded_symbols()
    logger.info(f"العملات المتداولة حالياً: {traded_symbols}")
    
    # إدارة جميع الصفقات
    stats = manage_all_trades()
    
    logger.info("نتائج إدارة الصفقات:")
    logger.info(f"تم بيع {stats['stale_trades_sold']} صفقة قديمة")
    logger.info(f"تم بيع {stats['profitable_trades_sold']} صفقة مربحة")
    logger.info(f"تم فتح {stats['new_trades_opened']} صفقة جديدة متنوعة")
    
    # عرض العملات المتداولة بعد التحديث
    traded_symbols = get_traded_symbols()
    logger.info(f"العملات المتداولة بعد التحديث: {traded_symbols}")
    
    return stats

def forced_sell_old_trades(max_hours=8):
    """
    بيع الصفقات القديمة بشكل قسري
    
    :param max_hours: الحد الأقصى للساعات قبل البيع القسري
    """
    logger.info(f"بدء البيع القسري للصفقات الأقدم من {max_hours} ساعات")
    
    # عرض العملات المتداولة قبل البيع
    traded_symbols = get_traded_symbols()
    logger.info(f"العملات المتداولة قبل البيع: {traded_symbols}")
    
    # بيع الصفقات القديمة
    sold_count = force_sell_stale_trades(max_hours)
    
    # عرض العملات المتداولة بعد البيع
    traded_symbols = get_traded_symbols()
    logger.info(f"العملات المتداولة بعد البيع: {traded_symbols}")
    
    logger.info(f"تم بيع {sold_count} صفقة قديمة")
    
    return sold_count

if __name__ == "__main__":
    # تحديد العملية المطلوبة حسب المعاملات
    if len(sys.argv) > 1:
        # معالجة المعاملات
        if sys.argv[1] == "sell_old" and len(sys.argv) > 2:
            try:
                hours = int(sys.argv[2])
                forced_sell_old_trades(hours)
            except ValueError:
                logger.error(f"قيمة غير صالحة للساعات: {sys.argv[2]}")
                print(f"قيمة غير صالحة للساعات: {sys.argv[2]}")
        else:
            print("استخدام غير صحيح. أمثلة:")
            print("python run_trade_manager.py")
            print("python run_trade_manager.py sell_old 8")
    else:
        # تشغيل الإدارة الشاملة للصفقات
        main()