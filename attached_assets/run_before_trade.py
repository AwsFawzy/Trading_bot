"""
سكريبت موحد وبسيط لتنفيذه قبل كل صفقة تداول
يتضمن كل عمليات التحقق والتنويع في ملف واحد
"""

import os
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# العملات الممنوعة تماماً
BANNED_SYMBOLS = ['XRPUSDT']  # منع تداول XRPUSDT نهائياً

def get_active_trades():
    """تحميل الصفقات النشطة"""
    try:
        if os.path.exists('active_trades.json'):
            with open('active_trades.json', 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                else:
                    # تحويل التنسيق القديم إلى الجديد
                    return {'open': [t for t in data if t.get('status') == 'OPEN'], 
                            'closed': [t for t in data if t.get('status') != 'OPEN']}
        return {'open': [], 'closed': []}
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {'open': [], 'closed': []}

def create_backup():
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        backup_name = f"active_trades.json.backup.{int(time.time())}"
        os.system(f"cp active_trades.json {backup_name}")
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")

def save_active_trades(data):
    """حفظ الصفقات النشطة"""
    try:
        create_backup()
        with open('active_trades.json', 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"تم حفظ {len(data['open'])} صفقة مفتوحة و {len(data['closed'])} صفقة مغلقة")
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")

def enforce_diversity():
    """تطبيق قواعد التنويع بإبقاء صفقة واحدة فقط لكل عملة"""
    trades_data = get_active_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    # العملات التي تمت معالجتها
    processed_symbols = set()
    # الصفقات بعد التنويع
    filtered_trades = []
    # الصفقات التي سيتم إغلاقها
    to_close = []
    
    # فرز الصفقات حسب التاريخ (الأحدث أولاً) لإبقاء أحدث صفقة
    open_trades.sort(key=lambda x: x.get('enter_time', 0), reverse=True)
    
    for trade in open_trades:
        symbol = trade.get('symbol', '').upper()
        if not symbol:
            filtered_trades.append(trade)
            continue
            
        # منع تداول العملات المحظورة
        if symbol in BANNED_SYMBOLS:
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_reason'] = 'banned_symbol'
            to_close.append(trade)
            logger.warning(f"إغلاق صفقة على عملة محظورة: {symbol}")
            continue
        
        # إذا كانت العملة لم تتم معالجتها بعد
        if symbol not in processed_symbols:
            processed_symbols.add(symbol)
            filtered_trades.append(trade)
        # إذا كانت العملة قد تمت معالجتها
        else:
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_reason'] = 'duplicate'
            to_close.append(trade)
            logger.warning(f"إغلاق صفقة مكررة: {symbol}")
    
    # تحديث القوائم
    trades_data['open'] = filtered_trades
    trades_data['closed'].extend(to_close)
    
    # حفظ التغييرات
    save_active_trades(trades_data)
    
    return len(to_close)

def is_symbol_allowed(symbol):
    """التحقق ما إذا كان مسموحاً بتداول عملة معينة"""
    # منع العملات المحظورة تماماً
    if symbol.upper() in BANNED_SYMBOLS:
        logger.warning(f"العملة {symbol} محظورة نهائياً")
        return False
    
    # التحقق من عدم وجود الرمز في الصفقات المفتوحة
    trades_data = get_active_trades()
    open_trades = trades_data.get('open', [])
    
    traded_symbols = set(t.get('symbol', '').upper() for t in open_trades if t.get('symbol'))
    
    if symbol.upper() in traded_symbols:
        logger.warning(f"العملة {symbol} قيد التداول بالفعل")
        return False
    
    return True

def get_active_symbols():
    """الحصول على مجموعة العملات المتداولة حالياً"""
    trades_data = get_active_trades()
    open_trades = trades_data.get('open', [])
    
    return set(t.get('symbol', '').upper() for t in open_trades if t.get('symbol'))

def main():
    """الدالة الرئيسية"""
    # تطبيق قواعد التنويع
    closed_count = enforce_diversity()
    print(f"تم إغلاق {closed_count} صفقة مكررة")
    
    # عرض العملات النشطة بعد التنويع
    active_symbols = get_active_symbols()
    print(f"العملات المتداولة حالياً: {active_symbols}")
    
    return True

if __name__ == "__main__":
    main()