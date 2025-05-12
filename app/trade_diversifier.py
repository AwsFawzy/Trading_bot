"""
نظام التنويع الإلزامي للصفقات
يضمن التداول على عملات مختلفة ويمنع تركيز المخاطر على عملة واحدة
"""

import logging
import time
from typing import List, Dict, Tuple, Set
from datetime import datetime
import json
import os

# إعداد التسجيل
logger = logging.getLogger(__name__)

# السماح بصفقة واحدة فقط لكل عملة (إلزامي)
MAX_TRADES_PER_COIN = 1

# أقصى عدد للصفقات المفتوحة في نفس الوقت
MAX_TOTAL_OPEN_TRADES = 5

def load_active_trades() -> List[Dict]:
    """
    تحميل الصفقات النشطة
    """
    try:
        if os.path.exists('active_trades.json'):
            with open('active_trades.json', 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات النشطة: {e}")
        return []

def get_open_trades() -> List[Dict]:
    """
    الحصول على قائمة بجميع الصفقات المفتوحة
    """
    trades = load_active_trades()
    return [t for t in trades if t.get('status') == 'OPEN']

def get_open_trades_per_coin() -> Dict[str, int]:
    """
    حساب عدد الصفقات المفتوحة لكل عملة
    """
    open_trades = get_open_trades()
    counts = {}
    
    for trade in open_trades:
        symbol = trade.get('symbol', '')
        if symbol:
            counts[symbol] = counts.get(symbol, 0) + 1
    
    return counts

def get_unique_traded_coins() -> Set[str]:
    """
    الحصول على مجموعة العملات المتداولة حاليًا
    """
    open_trades = get_open_trades()
    return set(t.get('symbol', '') for t in open_trades if t.get('symbol'))

def is_trade_allowed(symbol: str) -> Tuple[bool, str]:
    """
    التحقق الصارم مما إذا كان مسموحًا بفتح صفقة جديدة على العملة
    منع بشكل صارم تمامًا فتح أي صفقات متعددة على نفس العملة
    
    :param symbol: رمز العملة
    :return: (مسموح, السبب)
    """
    if not symbol:
        return False, "رمز العملة غير محدد"
    
    # التنفيذ الأكثر صرامة - فحص مباشر لقاعدة البيانات
    try:
        # 1. الفحص المباشر لملف قاعدة البيانات
        with open('active_trades.json', 'r') as f:
            all_trades = json.load(f)
            
        # فحص وجود أي صفقة مفتوحة لهذه العملة بالضبط
        symbol_trades = [t for t in all_trades if t.get('symbol') == symbol and t.get('status') == 'OPEN']
        
        if len(symbol_trades) > 0:
            logger.error(f"⛔ منع إلزامي وحاسم! - يوجد بالفعل {len(symbol_trades)} صفقة مفتوحة على {symbol}")
            return False, f"منع تداول نفس العملة: يوجد بالفعل صفقة مفتوحة على {symbol}"
    except Exception as e:
        logger.error(f"خطأ في التحقق المباشر من الصفقات المفتوحة: {e}")
        # في حالة الخطأ، نمنع التداول ليكون آمنًا
        return False, f"خطأ في التحقق من الصفقات: {e}"
    
    # 2. التحقق من إجمالي الصفقات المفتوحة
    try:
        open_trades = [t for t in all_trades if t.get('status') == 'OPEN']
        if len(open_trades) >= MAX_TOTAL_OPEN_TRADES:
            return False, f"تم الوصول للحد الأقصى من الصفقات ({MAX_TOTAL_OPEN_TRADES})"
    except Exception:
        # استخدام الطريقة الاحتياطية
        open_trades = get_open_trades()
        if len(open_trades) >= MAX_TOTAL_OPEN_TRADES:
            return False, f"تم الوصول للحد الأقصى من الصفقات ({MAX_TOTAL_OPEN_TRADES})"
    
    # 3. إجراء فحص ثالث كإجراء أمان إضافي
    try:
        # فحص من خلال قراءة الملف مرة أخرى لضمان أحدث البيانات
        with open('active_trades.json', 'r') as f:
            latest_trades = json.load(f)
        
        latest_symbols = set([t.get('symbol') for t in latest_trades if t.get('status') == 'OPEN'])
        
        if symbol in latest_symbols:
            logger.error(f"⛔ فحص أخير: يوجد بالفعل صفقة مفتوحة على {symbol}")
            return False, f"منع نهائي: يوجد بالفعل صفقة مفتوحة على {symbol}"
    except Exception as e:
        logger.error(f"خطأ في الفحص النهائي: {e}")
    
    return True, "مسموح بفتح صفقة جديدة"

def enforce_diversity(candidates: List[str]) -> List[str]:
    """
    فرض التنويع الصارم والإلزامي على قائمة العملات المرشحة للتداول
    
    :param candidates: قائمة برموز العملات المرشحة
    :return: قائمة بالعملات المسموح التداول عليها بعد تطبيق قواعد التنويع
    """
    if not candidates:
        return []
    
    # 1. جمع العملات المتداولة من عدة مصادر للتأكد من دقة البيانات
    
    # قراءة مباشرة من ملف الصفقات (أكثر دقة)
    currently_traded_symbols = set()
    try:
        with open('active_trades.json', 'r') as f:
            trades = json.load(f)
            for trade in trades:
                # تحقق صارم للصفقات المفتوحة
                if trade.get('status') == 'OPEN' and trade.get('symbol'):
                    symbol = trade.get('symbol')
                    currently_traded_symbols.add(symbol)
                    logger.warning(f"⛔ يوجد صفقة مفتوحة حالياً على {symbol}")
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الصفقات مباشرة: {e}")
    
    # استخدام الطريقة المعتادة كنسخة احتياطية
    traded_coins_backup = get_unique_traded_coins()
    
    # دمج النتائج من مختلف المصادر لضمان تغطية شاملة
    all_traded_coins = currently_traded_symbols.union(traded_coins_backup)
    
    # 2. سجلات مفصلة للتوضيح والتصحيح
    logger.error(f"⚠️ العملات المتداولة من القراءة المباشرة: {currently_traded_symbols}")
    logger.error(f"⚠️ العملات المتداولة من الطريقة الاحتياطية: {traded_coins_backup}")
    logger.error(f"⚠️ إجمالي العملات المتداولة بعد الدمج: {all_traded_coins}")
    logger.error(f"⚠️ العملات المرشحة قبل التصفية: {candidates}")
    
    # 3. استبعاد صارم للعملات المتداولة حالياً
    allowed_coins = []
    for candidate in candidates:
        if candidate in all_traded_coins:
            logger.error(f"⛔ استبعاد {candidate} - لديها صفقة مفتوحة بالفعل!")
        else:
            allowed_coins.append(candidate)
    
    # 4. إضافة فحص إضافي صارم لكل عملة
    final_allowed_coins = []
    for coin in allowed_coins:
        # فحص مباشر مرة أخرى للتأكد 
        try:
            with open('active_trades.json', 'r') as f:
                trades = json.load(f)
                open_for_symbol = sum(1 for t in trades if t.get('status') == 'OPEN' and t.get('symbol') == coin)
                
                if open_for_symbol > 0:
                    logger.error(f"⛔⛔⛔ فحص نهائي: استبعاد {coin} - وجدنا {open_for_symbol} صفقة مفتوحة عليها!")
                else:
                    final_allowed_coins.append(coin)
        except Exception as e:
            logger.error(f"خطأ في الفحص النهائي: {e}")
            
    # 5. سجل النتائج النهائية
    logger.error(f"⚠️ العملات المسموح بها بعد تطبيق التنويع: {final_allowed_coins} (من أصل {len(candidates)} مرشح)")
    
    return final_allowed_coins

def get_trade_diversity_metrics() -> Dict:
    """
    الحصول على مقاييس التنويع الحالية
    
    :return: قاموس بمقاييس التنويع
    """
    open_trades = get_open_trades()
    trades_per_coin = get_open_trades_per_coin()
    
    return {
        'total_open_trades': len(open_trades),
        'unique_coins': len(trades_per_coin),
        'coins_distribution': trades_per_coin,
        'max_trades_per_coin': MAX_TRADES_PER_COIN,
        'max_total_trades': MAX_TOTAL_OPEN_TRADES,
        'diversity_achieved': len(trades_per_coin) == len(open_trades) if open_trades else True
    }