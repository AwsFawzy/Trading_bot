"""
سكريبت لإصلاح الصفقات الحالية وإضافة التنويع الفوري

هذا السكريبت:
1. يحاول إغلاق أي صفقات مفتوحة حالياً
2. يفتح 5 صفقات جديدة على عملات مختلفة
3. يضمن تنويع المحفظة بشكل فوري
"""

import os
import json
import time
import logging
import sys

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# قائمة العملات المفضلة للتنويع
PREFERRED_COINS = [
    'BTCUSDT',     # بيتكوين
    'ETHUSDT',     # إيثريوم
    'DOGEUSDT',    # دوج كوين
    'SOLUSDT',     # سولانا
    'BNBUSDT',     # بينانس كوين
    'MATICUSDT',   # بوليجون
    'AVAXUSDT',    # أفالانش
    'LINKUSDT',    # تشينلينك - لدينا صفقة بالفعل على هذه العملة
    'TRXUSDT',     # ترون
    'LTCUSDT',     # لايتكوين
]

# إعدادات النظام
SETTINGS = {
    'total_capital': 30.0,      # رأس المال الإجمالي
    'max_trades': 5,            # الحد الأقصى لعدد الصفقات
    'blacklisted_symbols': ['XRPUSDT']  # العملات المحظورة
}

def create_backup(filename='active_trades.json'):
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        if not os.path.exists(filename):
            return
            
        timestamp = int(time.time())
        backup_file = f"{filename}.backup.{timestamp}"
        os.system(f"cp {filename} {backup_file}")
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_file}")
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")

def load_trades(filename='active_trades.json'):
    """تحميل الصفقات من الملف"""
    try:
        if not os.path.exists(filename):
            return {'open': [], 'closed': []}
            
        with open(filename, 'r') as f:
            data = json.load(f)
            
        # تحويل البيانات إلى التنسيق الصحيح إذا لزم الأمر
        if isinstance(data, dict) and 'open' in data and 'closed' in data:
            return data
        elif isinstance(data, list):
            return {
                'open': [t for t in data if t.get('status') == 'OPEN'],
                'closed': [t for t in data if t.get('status') != 'OPEN']
            }
        else:
            logger.warning(f"صيغة غير متوقعة لملف الصفقات: {type(data)}")
            return {'open': [], 'closed': []}
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {'open': [], 'closed': []}

def save_trades(data, filename='active_trades.json'):
    """حفظ الصفقات في الملف"""
    try:
        # إنشاء نسخة احتياطية
        create_backup(filename)
        
        # حفظ البيانات
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"تم حفظ {len(data.get('open', []))} صفقة مفتوحة و {len(data.get('closed', []))} صفقة مغلقة")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def close_all_trades():
    """إغلاق جميع الصفقات المفتوحة"""
    try:
        # محاولة استيراد دالة البيع من وحدة التداول
        try:
            from app.trade_logic import close_trade
            from app.mexc_api import place_order
            
            # تحميل الصفقات
            data = load_trades()
            open_trades = data.get('open', [])
            closed_trades = data.get('closed', [])
            
            if not open_trades:
                logger.info("لا توجد صفقات مفتوحة للإغلاق")
                return 0
                
            closed_count = 0
            
            # محاولة بيع كل صفقة مفتوحة
            for trade in list(open_trades):
                symbol = trade.get('symbol')
                quantity = trade.get('quantity')
                
                if not symbol or not quantity:
                    logger.warning(f"تجاهل صفقة بدون رمز أو كمية: {trade}")
                    continue
                
                logger.info(f"محاولة بيع {symbol} بكمية {quantity}")
                
                # تنفيذ أمر البيع
                try:
                    result = place_order(symbol, "SELL", quantity, None, "MARKET")
                    
                    if result and isinstance(result, dict) and 'orderId' in result:
                        # تحديث حالة الصفقة
                        trade['status'] = 'closed'
                        trade['exit_time'] = int(time.time() * 1000)
                        trade['exit_reason'] = 'forced_close'
                        trade['order_result'] = result
                        
                        # نقل الصفقة من المفتوحة إلى المغلقة
                        open_trades.remove(trade)
                        closed_trades.append(trade)
                        
                        closed_count += 1
                        logger.info(f"✅ تم بيع {symbol} بنجاح: {result}")
                    else:
                        logger.error(f"❌ فشل بيع {symbol}: {result}")
                except Exception as e:
                    logger.error(f"❌ خطأ في بيع {symbol}: {e}")
            
            # حفظ التغييرات
            if closed_count > 0:
                data['open'] = open_trades
                data['closed'] = closed_trades
                save_trades(data)
                
            return closed_count
        except ImportError:
            # إذا فشل استيراد وحدة التداول، استخدام الإغلاق المحلي فقط
            logger.warning("تعذر استيراد وحدة التداول، سيتم إغلاق الصفقات محلياً فقط")
            return close_trades_locally()
    except Exception as e:
        logger.error(f"خطأ في إغلاق الصفقات: {e}")
        return 0

def close_trades_locally():
    """إغلاق الصفقات في الملف المحلي فقط"""
    try:
        # تحميل الصفقات
        data = load_trades()
        open_trades = data.get('open', [])
        closed_trades = data.get('closed', [])
        
        if not open_trades:
            logger.info("لا توجد صفقات مفتوحة للإغلاق")
            return 0
            
        # تعديل حالة الصفقات
        for trade in open_trades:
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_reason'] = 'forced_close_local'
            
        # نقل الصفقات من المفتوحة إلى المغلقة
        closed_trades.extend(open_trades)
        data['open'] = []
        data['closed'] = closed_trades
        
        # حفظ التغييرات
        save_trades(data)
        
        logger.info(f"تم إغلاق {len(open_trades)} صفقة محلياً")
        return len(open_trades)
    except Exception as e:
        logger.error(f"خطأ في إغلاق الصفقات محلياً: {e}")
        return 0

def open_diverse_trades():
    """فتح صفقات متنوعة حقيقية فقط عبر API"""
    try:
        # استيراد الدوال اللازمة
        from app.auto_trade import execute_buy, get_active_symbols
        
        # تحميل الصفقات الحالية
        active_symbols = get_active_symbols()
        logger.info(f"العملات المتداولة حالياً: {active_symbols}")
        
        # إذا كان عدد العملات المتداولة وصل للحد الأقصى
        max_trades = SETTINGS['max_trades']
        if len(active_symbols) >= max_trades:
            logger.info(f"تم الوصول للحد الأقصى من العملات المتداولة: {len(active_symbols)}/{max_trades}")
            return 0
            
        # حساب عدد الصفقات التي يمكن فتحها
        trades_to_open = max_trades - len(active_symbols)
        
        # اختيار عملات لم يتم تداولها بالفعل
        selected_coins = []
        for coin in PREFERRED_COINS:
            if coin not in active_symbols and coin not in SETTINGS['blacklisted_symbols'] and len(selected_coins) < trades_to_open:
                selected_coins.append(coin)
        
        # حساب المبلغ لكل صفقة
        per_trade_amount = SETTINGS['total_capital'] / max_trades
        
        # فتح صفقات جديدة
        opened_count = 0
        for coin in selected_coins:
            # تنفيذ الشراء
            logger.info(f"محاولة شراء {coin} بمبلغ {per_trade_amount} دولار")
            
            # محاولة الشراء 3 مرات في حالة الفشل
            for attempt in range(3):
                try:
                    success, result = execute_buy(coin, per_trade_amount)
                    
                    if success:
                        opened_count += 1
                        logger.info(f"✅ تم شراء {coin} بنجاح: {result}")
                        break
                    else:
                        logger.warning(f"❌ فشل شراء {coin} (المحاولة {attempt+1}/3): {result}")
                        if attempt < 2:  # انتظار قبل المحاولة التالية
                            time.sleep(2)
                except Exception as e:
                    logger.error(f"خطأ في محاولة شراء {coin} (المحاولة {attempt+1}/3): {e}")
                    if attempt < 2:  # انتظار قبل المحاولة التالية
                        time.sleep(2)
        
        return opened_count
    except Exception as e:
        logger.error(f"خطأ في فتح الصفقات: {e}")
        return 0

def fix_trades_file():
    """إصلاح ملف الصفقات والتحويل إلى الصيغة الجديدة"""
    try:
        # تحميل الصفقات
        if not os.path.exists('active_trades.json'):
            logger.info("ملف الصفقات غير موجود، سيتم إنشاء ملف جديد")
            save_trades({'open': [], 'closed': []})
            return True
            
        with open('active_trades.json', 'r') as f:
            data = json.load(f)
            
        # تحويل البيانات إلى التنسيق الصحيح إذا لزم الأمر
        if isinstance(data, dict) and 'open' in data and 'closed' in data:
            logger.info("ملف الصفقات بالصيغة الصحيحة بالفعل")
            return True
        elif isinstance(data, list):
            # تحويل من القائمة إلى القاموس
            new_data = {
                'open': [t for t in data if t.get('status') == 'OPEN'],
                'closed': [t for t in data if t.get('status') != 'OPEN']
            }
            
            # حفظ البيانات بالصيغة الجديدة
            save_trades(new_data)
            logger.info(f"تم تحويل ملف الصفقات من قائمة إلى قاموس: {len(new_data['open'])} مفتوحة، {len(new_data['closed'])} مغلقة")
            return True
        else:
            logger.error(f"صيغة غير متوقعة لملف الصفقات: {type(data)}")
            return False
    except Exception as e:
        logger.error(f"خطأ في إصلاح ملف الصفقات: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    logger.info("بدء إصلاح وتنويع الصفقات")
    
    # إصلاح ملف الصفقات أولاً
    if not fix_trades_file():
        logger.error("فشل إصلاح ملف الصفقات، إلغاء العملية")
        return False
    
    # إغلاق الصفقات المفتوحة حالياً
    closed_count = close_all_trades()
    logger.info(f"تم إغلاق {closed_count} صفقة")
    
    # فتح صفقات متنوعة
    opened_count = open_diverse_trades()
    logger.info(f"تم فتح {opened_count} صفقة متنوعة")
    
    return True

if __name__ == "__main__":
    try:
        result = main()
        print("نجاح" if result else "فشل")
    except Exception as e:
        logger.error(f"خطأ في تنفيذ البرنامج: {e}")
        print(f"خطأ: {e}")
        sys.exit(1)