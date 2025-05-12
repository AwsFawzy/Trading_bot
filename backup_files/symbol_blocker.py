"""
نظام بسيط لمنع تكرار التداول على نفس العملات
يعمل كوظيفة مساعدة للبوت الرئيسي
يتم تشغيله قبل كل تداول جديد
"""

import json
import os
import time
import logging

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# العملات المحظورة نهائياً
PERMANENTLY_BLOCKED = ['XRPUSDT']

def create_backup():
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        timestamp = int(time.time())
        os.system(f"cp active_trades.json active_trades.json.backup.{timestamp}")
        logger.info(f"تم إنشاء نسخة احتياطية: active_trades.json.backup.{timestamp}")
    except Exception as e:
        logger.error(f"خطأ في إنشاء النسخة الاحتياطية: {e}")

def load_active_trades():
    """تحميل الصفقات النشطة من الملف"""
    try:
        if os.path.exists('active_trades.json'):
            with open('active_trades.json', 'r') as f:
                return json.load(f)
        return {"open": [], "closed": []}
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {"open": [], "closed": []}

def save_active_trades(trades_data):
    """حفظ الصفقات النشطة في الملف"""
    try:
        create_backup()
        with open('active_trades.json', 'w') as f:
            json.dump(trades_data, f, indent=2)
        logger.info(f"تم حفظ {len(trades_data.get('open', []))} صفقات مفتوحة و {len(trades_data.get('closed', []))} صفقات مغلقة")
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")

def get_active_symbols():
    """الحصول على العملات التي يتم تداولها حالياً"""
    trades_data = load_active_trades()
    open_trades = trades_data.get('open', [])
    symbols = set()
    
    for trade in open_trades:
        symbol = trade.get('symbol', '').upper()
        if symbol:
            symbols.add(symbol)
    
    return symbols

def is_trade_allowed(symbol):
    """التحقق ما إذا كان مسموحاً بتداول هذه العملة"""
    # 1. منع العملات المحظورة نهائياً
    if symbol.upper() in PERMANENTLY_BLOCKED:
        logger.warning(f"العملة {symbol} محظورة نهائياً")
        return False
    
    # 2. منع العملات التي يتم تداولها حالياً
    active_symbols = get_active_symbols()
    if symbol.upper() in active_symbols:
        logger.warning(f"العملة {symbol} قيد التداول بالفعل")
        return False
    
    return True

def enforce_diversification():
    """
    فرض التنويع بإبقاء صفقة واحدة فقط لكل عملة
    """
    trades_data = load_active_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    # تخزين العملات المتداولة بالفعل
    processed_symbols = set()
    # الصفقات الجديدة بعد التصفية
    new_open_trades = []
    # الصفقات التي سيتم إغلاقها
    trades_to_close = []
    
    # فرز الصفقات حسب التاريخ (الأحدث أولاً)
    open_trades.sort(key=lambda x: x.get('enter_time', 0), reverse=True)
    
    for trade in open_trades:
        symbol = trade.get('symbol', '').upper()
        if not symbol:
            new_open_trades.append(trade)
            continue
            
        # إذا كانت العملة لم يتم التعامل معها بعد، نضيفها للقائمة
        if symbol not in processed_symbols:
            processed_symbols.add(symbol)
            new_open_trades.append(trade)
        # إذا كانت العملة قد تمت معالجتها، نغلق الصفقة
        else:
            # تحديث حالة الصفقة وإغلاقها
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_reason'] = 'duplicate_removed'
            trades_to_close.append(trade)
            logger.warning(f"إغلاق صفقة مكررة على {symbol}")
    
    # تحديث قوائم الصفقات
    trades_data['open'] = new_open_trades
    trades_data['closed'].extend(trades_to_close)
    
    # حفظ التغييرات
    save_active_trades(trades_data)
    
    # إعادة عدد الصفقات المغلقة
    return len(trades_to_close)

if __name__ == "__main__":
    # تنفيذ التنويع عند تشغيل السكريبت
    closed_count = enforce_diversification()
    print(f"تم إغلاق {closed_count} صفقة مكررة")
    
    # طباعة العملات النشطة حالياً
    active_symbols = get_active_symbols()
    print(f"العملات المتداولة حالياً: {active_symbols}")