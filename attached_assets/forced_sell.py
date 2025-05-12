"""
سكريبت لتنفيذ البيع القسري لجميع الصفقات المفتوحة
يستخدم عندما يكون هناك مشكلة في النظام الرئيسي للبيع
"""

import os
import json
import time
import logging
import sys

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_backup():
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        timestamp = int(time.time())
        backup_name = f"active_trades.json.backup.{timestamp}"
        if os.path.exists('active_trades.json'):
            os.system(f"cp active_trades.json {backup_name}")
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")

def load_trades():
    """تحميل الصفقات من الملف"""
    try:
        if os.path.exists('active_trades.json'):
            with open('active_trades.json', 'r') as f:
                data = json.load(f)
            # التحقق من الصيغة وتحويلها إذا لزم الأمر
            if isinstance(data, dict) and 'open' in data and 'closed' in data:
                return data
            elif isinstance(data, list):
                # التحويل من الصيغة القديمة
                return {
                    'open': [t for t in data if t.get('status') == 'OPEN'],
                    'closed': [t for t in data if t.get('status') != 'OPEN']
                }
            else:
                return {'open': [], 'closed': []}
        return {'open': [], 'closed': []}
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {'open': [], 'closed': []}

def save_trades(data):
    """حفظ الصفقات في الملف"""
    try:
        create_backup()
        with open('active_trades.json', 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"تم حفظ {len(data.get('open', []))} صفقة مفتوحة و {len(data.get('closed', []))} صفقة مغلقة")
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")

def execute_market_sell(symbol, quantity):
    """تنفيذ أمر بيع مباشر من خلال واجهة البرمجة"""
    try:
        # استدعاء وظيفة البيع من خلال API
        from app.mexc_api import place_order
        
        result = place_order(symbol, "SELL", quantity, None, "MARKET")
        if result and isinstance(result, dict) and 'orderId' in result:
            logger.info(f"✅ تم تنفيذ أمر البيع بنجاح لـ {symbol}: {result}")
            return True, result
        else:
            logger.error(f"❌ فشل تنفيذ أمر البيع لـ {symbol}: {result}")
            return False, result
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ أمر البيع لـ {symbol}: {e}")
        return False, str(e)

def sell_all_open_trades():
    """بيع جميع الصفقات المفتوحة بشكل قسري"""
    data = load_trades()
    open_trades = data.get('open', [])
    closed_trades = data.get('closed', [])
    
    logger.info(f"تم العثور على {len(open_trades)} صفقة مفتوحة")
    
    # إذا لم تكن هناك صفقات مفتوحة
    if not open_trades:
        logger.info("لا توجد صفقات مفتوحة للبيع")
        return
    
    # محاولة بيع كل صفقة مفتوحة
    success_count = 0
    failed_count = 0
    
    for trade in open_trades[:]:  # نسخة من القائمة لتجنب مشاكل التعديل أثناء التكرار
        symbol = trade.get('symbol')
        quantity = trade.get('quantity', 0)
        
        if not symbol or not quantity:
            logger.warning(f"تجاهل صفقة بدون رمز أو كمية: {trade}")
            continue
        
        logger.info(f"محاولة بيع {symbol} بكمية {quantity}")
        
        # تنفيذ أمر البيع
        success, result = execute_market_sell(symbol, quantity)
        
        if success:
            # تحديث حالة الصفقة
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_price'] = float(result.get('price', 0))
            trade['exit_reason'] = 'forced_sell'
            
            # نقل الصفقة من قائمة المفتوحة إلى المغلقة
            open_trades.remove(trade)
            closed_trades.append(trade)
            
            success_count += 1
            logger.info(f"✅ تم بيع {symbol} بنجاح")
        else:
            failed_count += 1
            logger.error(f"❌ فشل بيع {symbol}: {result}")
    
    # حفظ التغييرات
    data['open'] = open_trades
    data['closed'] = closed_trades
    save_trades(data)
    
    logger.info(f"تم بيع {success_count} صفقة بنجاح، وفشل بيع {failed_count} صفقة")
    return success_count, failed_count

def force_close_trades_in_file():
    """إغلاق الصفقات في الملف فقط دون تنفيذ أوامر بيع فعلية"""
    data = load_trades()
    open_trades = data.get('open', [])
    closed_trades = data.get('closed', [])
    
    logger.info(f"تم العثور على {len(open_trades)} صفقة مفتوحة")
    
    # إذا لم تكن هناك صفقات مفتوحة
    if not open_trades:
        logger.info("لا توجد صفقات مفتوحة للإغلاق")
        return 0
    
    # إغلاق جميع الصفقات بدون تنفيذ أوامر بيع
    for trade in open_trades:
        trade['status'] = 'closed'
        trade['exit_time'] = int(time.time() * 1000)
        trade['exit_reason'] = 'forced_close'
        
    # نقل جميع الصفقات المفتوحة إلى قائمة المغلقة
    closed_trades.extend(open_trades)
    data['open'] = []
    data['closed'] = closed_trades
    
    # حفظ التغييرات
    save_trades(data)
    
    return len(open_trades)

def main():
    """الدالة الرئيسية"""
    print("اختر العملية المطلوبة:")
    print("1. بيع جميع الصفقات المفتوحة (تنفيذ أوامر بيع فعلية)")
    print("2. إغلاق الصفقات في الملف فقط (بدون تنفيذ أوامر بيع)")
    
    try:
        choice = input("اختيارك (1 أو 2): ")
        
        if choice == '1':
            success_count, failed_count = sell_all_open_trades()
            print(f"تم بيع {success_count} صفقة بنجاح، وفشل بيع {failed_count} صفقة")
        elif choice == '2':
            closed_count = force_close_trades_in_file()
            print(f"تم إغلاق {closed_count} صفقة في الملف")
        else:
            print("اختيار غير صالح")
            
    except KeyboardInterrupt:
        print("\nتم إلغاء العملية")
        sys.exit(1)

if __name__ == "__main__":
    main()