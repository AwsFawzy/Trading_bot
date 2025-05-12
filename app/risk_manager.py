import logging
import time
from datetime import datetime, timedelta

# إعداد المسجل
logger = logging.getLogger(__name__)

# مخزن مؤقت لقياس التقلب
volatility_cache = {}

def get_volatility(symbol, period=24):
    """
    حساب تقلب العملة خلال الفترة المحددة (بالساعات)
    
    :param symbol: رمز العملة
    :param period: الفترة الزمنية (بالساعات) للحساب
    :return: قيمة التقلب (نسبة مئوية)
    """
    # التحقق من الذاكرة المؤقتة أولاً (صالحة لمدة 15 دقيقة)
    cache_key = f"{symbol}_{period}"
    if cache_key in volatility_cache:
        cache_time, cache_value = volatility_cache[cache_key]
        if time.time() - cache_time < 900:  # 15 دقيقة = 900 ثانية
            return cache_value
    
    try:
        # استدعاء API للحصول على البيانات التاريخية
        from app.exchange_manager import get_historical_klines
        
        # الحصول على الإطار الزمني المناسب (1h لفترة 24 ساعة أو أقل)
        timeframe = "1h"
        
        # الحصول على عدد الساعات + 1 للتأكد من وجود بيانات كافية
        klines = get_historical_klines(symbol, timeframe, limit=period+1)
        
        if not klines or len(klines) < 2:
            logger.warning(f"بيانات غير كافية لحساب تقلب {symbol}")
            return None
        
        # استخراج أسعار الإغلاق
        prices = [float(k[4]) for k in klines]  # عمود رقم 4 هو سعر الإغلاق
        
        # حساب التغييرات النسبية
        price_changes = []
        for i in range(1, len(prices)):
            change = abs(prices[i] - prices[i-1]) / prices[i-1]
            price_changes.append(change)
        
        # حساب متوسط التغيير المطلق
        volatility = sum(price_changes) / len(price_changes)
        
        # تخزين في الذاكرة المؤقتة
        volatility_cache[cache_key] = (time.time(), volatility)
        
        return volatility
    except Exception as e:
        logger.error(f"خطأ في حساب التقلب: {e}")
        return None

def adjust_position_size(symbol, base_position_size):
    """
    تعديل حجم المركز بناءً على تقييم المخاطر المتقدم
    
    :param symbol: رمز العملة
    :param base_position_size: حجم المركز الأساسي
    :return: حجم المركز المعدل
    """
    # قراءة الإعدادات من ملف التكوين
    from app.config import RISK_LEVEL, MAX_POSITION_SIZE_PERCENT, MIN_TRADE_AMOUNT
    
    # البدء بحجم المركز الأساسي
    adjusted_size = base_position_size
    
    # الحصول على مستوى التقلب
    volatility = get_volatility(symbol)
    
    # الحصول على السعر الحالي للعملة
    from app.exchange_manager import get_current_price
    current_price = get_current_price(symbol)
    
    if not current_price:
        return 0
    
    # تعديل حجم المركز بناءً على مستوى التقلب بشكل تدريجي أكثر
    if volatility:
        # معايرة أكثر دقة للتقلبات مع مستويات متعددة
        if volatility > 0.07:  # تقلب مرتفع جداً
            adjusted_size = base_position_size * 0.3  # تخفيض كبير
        elif volatility > 0.05:  # تقلب مرتفع
            adjusted_size = base_position_size * 0.5
        elif volatility > 0.03:  # تقلب متوسط
            adjusted_size = base_position_size * 0.7
        elif volatility > 0.02:  # تقلب منخفض
            adjusted_size = base_position_size * 0.9
        # تقلب منخفض جداً - استخدام الحجم الأساسي بالكامل
    
    # فحص أداء العملة في آخر 24 ساعة
    from app.market_analyzer import get_price_change_24h
    change_24h = get_price_change_24h(symbol)
    
    # تعديل إضافي بناءً على أداء 24 ساعة
    if change_24h is not None:
        if change_24h < -10:  # هبوط كبير
            adjusted_size = adjusted_size * 0.5  # تخفيض حجم المركز بنسبة 50% إضافية
        elif change_24h < -5:  # هبوط متوسط
            adjusted_size = adjusted_size * 0.7  # تخفيض حجم المركز بنسبة 30% إضافية
        elif change_24h > 20:  # ارتفاع كبير
            adjusted_size = adjusted_size * 0.6  # الحذر من الارتفاعات الكبيرة أيضاً
    
    # فحص حالة السوق العامة
    from app.market_analyzer import get_market_sentiment
    market_sentiment = 0  # قيمة افتراضية
    try:
        from app.market_analyzer import get_market_sentiment
        sentiment = get_market_sentiment()
        if sentiment is not None:
            market_sentiment = sentiment
    except (ImportError, AttributeError):
        # إذا لم تكن الدالة موجودة، نستخدم القيمة الافتراضية
        pass
    
    # تعديل إضافي بناءً على حالة السوق
    if market_sentiment < -0.5:  # سوق هابط
        adjusted_size = adjusted_size * 0.8  # تخفيض إضافي
    
    # التحقق من أن حجم المركز لا يتجاوز الحد المسموح به
    from app.capital_manager import get_available_balance
    max_position_size = get_available_balance() * MAX_POSITION_SIZE_PERCENT
    if adjusted_size > max_position_size:
        adjusted_size = max_position_size
    
    # التأكد من أن قيمة الصفقة لا تقل عن الحد الأدنى
    try:
        trade_value = float(current_price) * adjusted_size
        if trade_value < MIN_TRADE_AMOUNT:
            # زيادة حجم المركز ليحقق الحد الأدنى (بحد أقصى 80% من الرصيد المتاح)
            min_quantity = MIN_TRADE_AMOUNT / float(current_price)
            if min_quantity * float(current_price) <= 0.8 * get_available_balance():
                adjusted_size = min_quantity
            else:
                # إذا كان الحد الأدنى أكبر من 80% من الرصيد، نرفض الصفقة
                return 0
    except Exception as e:
        logger.error(f"خطأ في حساب قيمة الصفقة: {e}")
        return 0
    
    return adjusted_size

def is_night_time():
    """
    التحقق مما إذا كان الوقت الحالي ضمن وقت الليل (من الساعة 12 منتصف الليل إلى 5 صباحًا)
    قد يكون مفيدًا لتقليل التداول في الأوقات التي تكون فيها حركة السوق أقل نشاطًا
    
    :return: True إذا كان الوقت ليلًا، False خلاف ذلك
    """
    current_hour = datetime.now().hour
    return 0 <= current_hour < 5  # من منتصف الليل حتى الساعة 5 صباحًا

def check_day_trading_risk():
    """
    التحقق من مخاطر التداول اليومي والعودة بعامل تعديل المخاطر
    
    :return: عامل تعديل المخاطر (1.0 = عادي، أقل من 1.0 = خفض المخاطر)
    """
    # التحقق من أداء الصفقات السابقة اليوم
    from app.utils import load_json_data
    trades = load_json_data('active_trades.json', [])
    
    # الحصول على بداية اليوم الحالي
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_timestamp = int(today_start.timestamp() * 1000)
    
    # حساب عدد الصفقات المغلقة اليوم
    today_trades = [t for t in trades if t.get('close_timestamp', 0) >= today_timestamp and t.get('status') == 'CLOSED']
    
    # حساب نسبة الربح/الخسارة لليوم
    profit_trades = 0
    loss_trades = 0
    
    for trade in today_trades:
        profit_percent = trade.get('profit_percent', 0)
        if profit_percent > 0:
            profit_trades += 1
        elif profit_percent < 0:
            loss_trades += 1
    
    # إذا كان عدد الصفقات كافيًا للتقييم
    if len(today_trades) >= 5:
        win_rate = profit_trades / len(today_trades) if len(today_trades) > 0 else 0
        
        # تعديل المخاطر بناءً على معدل الربح اليومي
        if win_rate < 0.3:  # معدل ربح منخفض جدًا
            return 0.3  # تخفيض كبير للمخاطر
        elif win_rate < 0.5:  # معدل ربح منخفض
            return 0.7  # تخفيض معتدل للمخاطر
    
    # الوضع الافتراضي: بدون تعديل
    return 1.0

def calculate_position_risk(symbol, base_position_size):
    """
    حساب مخاطر المركز الشاملة وإرجاع حجم المركز المعدل مع تقرير المخاطر
    
    :param symbol: رمز العملة
    :param base_position_size: حجم المركز الأساسي
    :return: (حجم المركز المعدل، تقرير المخاطر)
    """
    # عوامل الخطر المختلفة
    volatility_factor = 1.0
    market_condition_factor = 1.0
    day_trading_factor = check_day_trading_risk()
    
    # تعديل حجم المركز الأساسي
    adjusted_size = adjust_position_size(symbol, base_position_size)
    
    # الحصول على مستوى التقلب
    volatility = get_volatility(symbol)
    if volatility:
        volatility_rating = "منخفض"
        if volatility > 0.07:
            volatility_rating = "مرتفع جداً"
            volatility_factor = 0.3
        elif volatility > 0.05:
            volatility_rating = "مرتفع"
            volatility_factor = 0.5
        elif volatility > 0.03:
            volatility_rating = "متوسط"
            volatility_factor = 0.7
        
        volatility_percentage = volatility * 100
    else:
        volatility_rating = "غير معروف"
        volatility_percentage = 0
    
    # تقرير المخاطر
    risk_report = {
        "symbol": symbol,
        "base_size": base_position_size,
        "adjusted_size": adjusted_size,
        "volatility": volatility_percentage,
        "volatility_rating": volatility_rating,
        "market_factor": market_condition_factor,
        "day_trading_factor": day_trading_factor,
        "total_risk_factor": volatility_factor * market_condition_factor * day_trading_factor
    }
    
    return adjusted_size, risk_report

def get_max_open_positions():
    """
    تحديد العدد الأقصى للمراكز المفتوحة بناءً على حالة السوق وأداء التداول
    
    :return: العدد الأقصى للمراكز المفتوحة
    """
    from app.config import MAX_ACTIVE_TRADES
    
    # البدء بالحد الأقصى من الإعدادات
    max_positions = MAX_ACTIVE_TRADES
    
    # تعديل بناءً على أداء التداول
    day_factor = check_day_trading_risk()
    if day_factor < 0.7:  # أداء ضعيف اليوم
        max_positions = max(1, int(MAX_ACTIVE_TRADES * 0.5))  # تخفيض الحد الأقصى بمقدار النصف
    
    # التحقق من وقت الليل
    if is_night_time():
        max_positions = max(1, int(max_positions * 0.7))  # تخفيض الحد الأقصى خلال الليل
    
    return max_positions