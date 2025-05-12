"""
نظام تنوع العملات لضمان عدم تركيز التداول على عملة واحدة
يوفر آليات متقدمة لفرض التنوع في اختيار العملات وتفادي تركيز الصفقات
"""

import time
import logging
from typing import Dict, List, Set, Tuple
from app.utils import load_json_data, save_json_data
from app.config import ENFORCE_COIN_DIVERSITY, MAX_TRADES_PER_COIN, COOLDOWN_AFTER_TRADE

logger = logging.getLogger(__name__)

# قائمة العملات المستبعدة مؤقتًا (في فترة الراحة)
_coin_cooldown_periods = {}  # تخزين {symbol: وقت_آخر_بيع}


def get_trade_diversity_status() -> Dict:
    """
    تحليل تنوع الصفقات المفتوحة
    
    :return: إحصائيات حول تنوع العملات المتداولة
    """
    trades = load_json_data('active_trades.json', [])
    open_trades = [t for t in trades if t.get('status') == 'OPEN']
    
    # عدد الصفقات المفتوحة لكل عملة
    coin_counts = {}
    for trade in open_trades:
        symbol = trade.get('symbol', '')
        coin_counts[symbol] = coin_counts.get(symbol, 0) + 1
    
    # تحليل التنوع
    unique_coins = len(coin_counts)
    max_per_coin = max(coin_counts.values()) if coin_counts else 0
    
    return {
        'total_open_trades': len(open_trades),
        'unique_coins': unique_coins,
        'max_trades_per_coin': max_per_coin,
        'coin_distribution': coin_counts,
        'diversity_score': unique_coins / max(1, len(open_trades)) if open_trades else 1.0
    }


def is_coin_allowed(symbol: str) -> Tuple[bool, str]:
    """
    التحقق مما إذا كان مسموحًا بفتح صفقة جديدة لهذه العملة وفقًا لقواعد التنويع
    
    :param symbol: رمز العملة
    :return: (مسموح، السبب)
    """
    if not ENFORCE_COIN_DIVERSITY:
        return True, "آلية التنويع غير مفعلة"
    
    # فحص فترة الراحة الإلزامية
    cooldown_until = _coin_cooldown_periods.get(symbol, 0)
    current_time = time.time()
    
    if cooldown_until > current_time:
        remaining_time = int(cooldown_until - current_time)
        remaining_minutes = remaining_time // 60
        remaining_seconds = remaining_time % 60
        
        return False, f"العملة في فترة راحة إلزامية (متبقي {remaining_minutes}:{remaining_seconds:02d} دقيقة)"
    
    # فحص عدد الصفقات المفتوحة لهذه العملة
    trades = load_json_data('active_trades.json', [])
    open_trades = [t for t in trades if t.get('status') == 'OPEN']
    
    # عدد الصفقات المفتوحة لهذه العملة
    coin_count = sum(1 for t in open_trades if t.get('symbol') == symbol)
    
    if coin_count >= MAX_TRADES_PER_COIN:
        return False, f"وصلت للحد الأقصى من الصفقات المسموح بها لهذه العملة ({MAX_TRADES_PER_COIN})"
    
    # تحليل التنوع الحالي
    diversity_status = get_trade_diversity_status()
    
    # منع إضافة المزيد من الصفقات للعملات الأكثر تداولًا إذا كان لدينا على الأقل 3 صفقات مفتوحة
    if diversity_status['total_open_trades'] >= 3:
        most_traded_coins = sorted(diversity_status['coin_distribution'].items(), 
                                  key=lambda x: x[1], reverse=True)
        
        # إذا كانت العملة ضمن أكثر العملات تداولًا وتتجاوز الحد المسموح
        for coin, count in most_traded_coins:
            if coin == symbol and count >= MAX_TRADES_PER_COIN:
                return False, f"لتحقيق التنوع، يجب التداول على عملات أخرى بدلاً من {symbol}"
    
    return True, "مسموح بالتداول على هذه العملة"


def record_coin_sale(symbol: str) -> None:
    """
    تسجيل بيع عملة وإضافتها إلى قائمة فترة الراحة
    
    :param symbol: رمز العملة
    """
    if ENFORCE_COIN_DIVERSITY:
        current_time = time.time()
        _coin_cooldown_periods[symbol] = current_time + COOLDOWN_AFTER_TRADE
        logger.info(f"تم إضافة {symbol} إلى فترة الراحة الإلزامية لمدة {COOLDOWN_AFTER_TRADE//60} دقيقة")


def get_coin_cooldown_status() -> Dict:
    """
    الحصول على حالة العملات الموجودة في فترة الراحة
    
    :return: معلومات عن العملات في فترة الراحة
    """
    current_time = time.time()
    
    # تنظيف القائمة من العملات التي انتهت فترة راحتها
    expired_coins = []
    for symbol, end_time in _coin_cooldown_periods.items():
        if end_time <= current_time:
            expired_coins.append(symbol)
    
    for symbol in expired_coins:
        del _coin_cooldown_periods[symbol]
    
    # تحضير المعلومات الحالية
    cooldown_status = {}
    for symbol, end_time in _coin_cooldown_periods.items():
        remaining_time = max(0, int(end_time - current_time))
        cooldown_status[symbol] = {
            'end_time': end_time,
            'remaining_seconds': remaining_time,
            'remaining_minutes': remaining_time // 60
        }
    
    return cooldown_status


def get_diverse_watchlist(available_symbols: List[str], active_trades: List[Dict], max_count: int = 10) -> List[str]:
    """
    إنشاء قائمة مراقبة متنوعة استنادًا إلى العملات النشطة حاليًا
    
    :param available_symbols: قائمة الرموز المتاحة
    :param active_trades: قائمة الصفقات النشطة
    :param max_count: الحد الأقصى لعدد العملات
    :return: قائمة الرموز المتنوعة
    """
    # العملات المتداولة حاليًا (لتجنبها)
    active_symbols = {t.get('symbol') for t in active_trades if t.get('status') == 'OPEN'}
    
    # العملات في فترة الراحة (لتجنبها)
    current_time = time.time()
    cooldown_symbols = {symbol for symbol, end_time in _coin_cooldown_periods.items() 
                       if end_time > current_time}
    
    # العملات المتاحة (تستبعد العملات النشطة والعملات في فترة الراحة)
    available_diverse = [s for s in available_symbols 
                         if s not in active_symbols and s not in cooldown_symbols]
    
    # عدد العملات المطلوبة
    needed_count = max_count - len(active_symbols)
    
    if needed_count <= 0:
        # لدينا بالفعل عدد كافٍ من العملات النشطة
        return list(active_symbols)
    
    # تعبئة القائمة بالعملات المتنوعة
    diverse_list = list(active_symbols) + available_diverse[:needed_count]
    
    return diverse_list[:max_count]