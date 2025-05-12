"""
ملف واجهة لربط آلية منع تكرار الصفقات مع نظام التداول الآلي.
يتم استدعاء هذا الملف من app/auto_trader.py و app/trade_executor.py
"""

import os
import json
import time
import logging
import subprocess
from typing import Tuple, Set, List, Dict, Any

logger = logging.getLogger(__name__)

# العملات الممنوعة بشكل دائم
BANNED_SYMBOLS = ['XRPUSDT']

def enforce_diversity() -> int:
    """
    تنفيذ التنويع الإلزامي للصفقات
    
    :return: عدد الصفقات المغلقة
    """
    try:
        # محاولة تنفيذ السكريبت الخارجي
        result = subprocess.run(['python', 'run_before_trade.py'], 
                               capture_output=True, text=True)
        logger.info(f"تم تنفيذ سكريبت التنويع: {result.stdout}")
        
        # استخراج عدد الصفقات المغلقة من النتيجة
        import re
        match = re.search(r'تم إغلاق (\d+) صفقة مكررة', result.stdout)
        if match:
            return int(match.group(1))
        
        return 0
    except Exception as e:
        logger.error(f"خطأ في تنفيذ التنويع: {e}")
        
        # محاولة التنفيذ الداخلي للتنويع
        return _internal_enforce_diversity()

def _internal_enforce_diversity() -> int:
    """
    تنفيذ التنويع داخلياً إذا فشل السكريبت الخارجي
    
    :return: عدد الصفقات المغلقة
    """
    try:
        # تحميل الصفقات
        trades_data = _load_trades()
        
        # تطبيق قواعد التنويع
        return _apply_diversity_rules(trades_data)
    except Exception as e:
        logger.error(f"خطأ في التنفيذ الداخلي للتنويع: {e}")
        return 0

def _load_trades() -> Dict[str, List[Dict[str, Any]]]:
    """
    تحميل الصفقات من الملف
    
    :return: بيانات الصفقات
    """
    try:
        if os.path.exists('active_trades.json'):
            with open('active_trades.json', 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'open' in data and 'closed' in data:
                    return data
                # تحويل التنسيق القديم (قائمة) إلى التنسيق الجديد (قاموس)
                return {
                    'open': [t for t in data if t.get('status') == 'OPEN'],
                    'closed': [t for t in data if t.get('status') != 'OPEN']
                }
        return {'open': [], 'closed': []}
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {'open': [], 'closed': []}
        
def _save_trades(trades_data: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    حفظ الصفقات في الملف
    
    :param trades_data: بيانات الصفقات
    :return: نجاح العملية
    """
    try:
        # إنشاء نسخة احتياطية
        backup_name = f"active_trades.json.backup.{int(time.time())}"
        os.system(f"cp active_trades.json {backup_name}")
        
        # حفظ البيانات
        with open('active_trades.json', 'w') as f:
            json.dump(trades_data, f, indent=2)
            
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def _apply_diversity_rules(trades_data: Dict[str, List[Dict[str, Any]]]) -> int:
    """
    تطبيق قواعد التنويع على الصفقات
    
    :param trades_data: بيانات الصفقات
    :return: عدد الصفقات المغلقة
    """
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    # للمعالجة
    processed_symbols = set()
    filtered_trades = []
    trades_to_close = []
    
    # فرز الصفقات حسب التاريخ (الأحدث أولاً)
    open_trades.sort(key=lambda x: x.get('enter_time', 0), reverse=True)
    
    for trade in open_trades:
        symbol = trade.get('symbol', '').upper()
        if not symbol:
            filtered_trades.append(trade)
            continue
            
        # منع العملات المحظورة
        if symbol in BANNED_SYMBOLS:
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_reason'] = 'banned_symbol'
            trade['enforced_close'] = True
            trades_to_close.append(trade)
            logger.warning(f"🚫 إغلاق صفقة على عملة محظورة: {symbol}")
            continue
            
        # إذا كانت العملة لم تتم معالجتها
        if symbol not in processed_symbols:
            processed_symbols.add(symbol)
            filtered_trades.append(trade)
        # إذا كانت العملة قد تمت معالجتها
        else:
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_reason'] = 'enforce_diversity'
            trade['enforced_close'] = True
            trades_to_close.append(trade)
            logger.warning(f"🔄 إغلاق صفقة مكررة: {symbol}")
    
    # تحديث القوائم
    trades_data['open'] = filtered_trades
    trades_data['closed'].extend(trades_to_close)
    
    # حفظ التغييرات
    _save_trades(trades_data)
    
    return len(trades_to_close)

def get_traded_symbols() -> Set[str]:
    """
    الحصول على العملات المتداولة حالياً
    
    :return: مجموعة من العملات المتداولة
    """
    try:
        trades_data = _load_trades()
        open_trades = trades_data.get('open', [])
        
        # استخراج العملات
        symbols = set()
        for trade in open_trades:
            symbol = trade.get('symbol', '').upper()
            if symbol:
                symbols.add(symbol)
                
        # إضافة العملات المحظورة
        for symbol in BANNED_SYMBOLS:
            symbols.add(symbol)
            
        return symbols
    except Exception as e:
        logger.error(f"خطأ في الحصول على العملات المتداولة: {e}")
        return set()

def is_symbol_allowed(symbol: str) -> Tuple[bool, str]:
    """
    التحقق ما إذا كان مسموحاً بتداول عملة معينة
    
    :param symbol: رمز العملة
    :return: (مسموح، السبب)
    """
    if not symbol:
        return False, "الرمز غير محدد"
        
    # منع العملات المحظورة
    if symbol.upper() in BANNED_SYMBOLS:
        return False, f"العملة {symbol} محظورة"
        
    # تنفيذ التنويع أولاً
    enforce_diversity()
    
    # الحصول على العملات المتداولة
    traded_symbols = get_traded_symbols()
    
    # التحقق من التداول
    if symbol.upper() in traded_symbols:
        return False, f"العملة {symbol} قيد التداول بالفعل"
        
    return True, "مسموح بالتداول"

def is_trade_allowed(symbol: str) -> bool:
    """
    للتوافق مع الواجهة القديمة - التحقق ما إذا كان مسموحاً بتداول عملة معينة
    
    :param symbol: رمز العملة
    :return: مسموح بالتداول
    """
    if not symbol:
        return False
        
    # إضافة الصلابة للتعامل مع الأنواع غير المتوقعة
    try:
        symbol_str = str(symbol).upper()
    except:
        return False
        
    allowed, _ = is_symbol_allowed(symbol_str)
    return allowed