import logging
import time
import numpy as np
from datetime import datetime, timedelta

# إعداد المسجل
logger = logging.getLogger(__name__)

# مخزن مؤقت للبيانات
price_change_cache = {}
sentiment_cache = {}

def get_price_change_24h(symbol):
    """
    الحصول على نسبة تغير سعر العملة خلال الـ 24 ساعة الماضية
    
    :param symbol: رمز العملة
    :return: نسبة التغير (نسبة مئوية)
    """
    # التحقق من الذاكرة المؤقتة أولاً (صالحة لمدة 15 دقيقة)
    if symbol in price_change_cache:
        cache_time, cache_value = price_change_cache[symbol]
        if time.time() - cache_time < 900:  # 15 دقيقة = 900 ثانية
            return cache_value
    
    try:
        # استدعاء API للحصول على بيانات تغير السعر
        from app.exchange_manager import get_ticker
        ticker = get_ticker(symbol)
        
        if not ticker:
            logger.warning(f"فشل في الحصول على معلومات تغير السعر لـ {symbol}")
            return None
        
        # استخراج نسبة التغير من البيانات
        price_change = float(ticker.get('priceChangePercent', 0))
        
        # تخزين في الذاكرة المؤقتة
        price_change_cache[symbol] = (time.time(), price_change)
        
        return price_change
    except Exception as e:
        logger.error(f"خطأ في الحصول على نسبة تغير السعر: {e}")
        return None

def get_market_sentiment():
    """
    تحليل حالة السوق العامة بناء على أداء العملات الرئيسية
    النتيجة تكون بين -1 (سوق هابط بشدة) و 1 (سوق صاعد بقوة)
    
    :return: قيمة المشاعر السوقية (-1 إلى 1)
    """
    # التحقق من الذاكرة المؤقتة أولاً (صالحة لمدة 30 دقيقة)
    if 'market' in sentiment_cache:
        cache_time, cache_value = sentiment_cache['market']
        if time.time() - cache_time < 1800:  # 30 دقيقة = 1800 ثانية
            return cache_value
    
    try:
        # العملات الرئيسية للمؤشر
        key_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT']
        
        price_changes = []
        for symbol in key_symbols:
            change = get_price_change_24h(symbol)
            if change is not None:
                price_changes.append(change)
        
        if not price_changes:
            logger.warning("لا توجد بيانات كافية لتحليل حالة السوق")
            return 0
        
        # حساب متوسط التغير
        avg_change = sum(price_changes) / len(price_changes)
        
        # تحويل المتوسط إلى قيمة بين -1 و 1
        # التغير بنسبة 10% أو أكثر يعتبر 1، والتغير بنسبة -10% أو أقل يعتبر -1
        sentiment = avg_change / 10 if abs(avg_change) < 10 else (1 if avg_change > 0 else -1)
        
        # تخزين في الذاكرة المؤقتة
        sentiment_cache['market'] = (time.time(), sentiment)
        
        return sentiment
    except Exception as e:
        logger.error(f"خطأ في تحليل حالة السوق: {e}")
        return 0

def analyze_market_cycles():
    """
    تحليل دورات السوق وإرجاع مؤشر الموقع في دورة السوق
    
    :return: نتيجة التحليل (dict)
    """
    try:
        # تحليل دورة BTC كمؤشر رئيسي للسوق
        btc_change_24h = get_price_change_24h('BTCUSDT')
        btc_change_7d = get_relative_price_change('BTCUSDT', days=7)
        btc_change_30d = get_relative_price_change('BTCUSDT', days=30)
        
        # تحديد موقع الدورة السوقية
        market_phase = "غير محدد"
        if btc_change_24h is not None and btc_change_7d is not None and btc_change_30d is not None:
            if btc_change_24h > 0 and btc_change_7d > 0 and btc_change_30d > 0:
                market_phase = "اتجاه صاعد قوي"
            elif btc_change_24h > 0 and btc_change_7d > 0 and btc_change_30d < 0:
                market_phase = "بداية اتجاه صاعد"
            elif btc_change_24h < 0 and btc_change_7d < 0 and btc_change_30d < 0:
                market_phase = "اتجاه هابط قوي"
            elif btc_change_24h < 0 and btc_change_7d < 0 and btc_change_30d > 0:
                market_phase = "بداية اتجاه هابط"
            elif btc_change_24h > 0 and btc_change_7d < 0:
                market_phase = "ارتداد في اتجاه هابط"
            elif btc_change_24h < 0 and btc_change_7d > 0:
                market_phase = "تصحيح في اتجاه صاعد"
            else:
                market_phase = "ترند جانبي"
        
        result = {
            "market_phase": market_phase,
            "btc_change_24h": btc_change_24h,
            "btc_change_7d": btc_change_7d,
            "btc_change_30d": btc_change_30d,
            "market_sentiment": get_market_sentiment()
        }
        
        return result
    except Exception as e:
        logger.error(f"خطأ في تحليل دورات السوق: {e}")
        return {"market_phase": "غير محدد", "error": str(e)}

def get_relative_price_change(symbol, days=7):
    """
    حساب نسبة تغير سعر العملة خلال عدد محدد من الأيام
    
    :param symbol: رمز العملة
    :param days: عدد الأيام للمقارنة
    :return: نسبة التغير (نسبة مئوية)
    """
    try:
        # استدعاء API للحصول على البيانات التاريخية
        from app.exchange_manager import get_historical_klines
        
        # حساب عدد الساعات
        hours = days * 24
        
        # اختيار الإطار الزمني المناسب
        timeframe = "1d" if days > 7 else "1h"
        
        # الحصول على البيانات
        klines = get_historical_klines(symbol, timeframe, limit=hours if timeframe == "1h" else days+1)
        
        if not klines or len(klines) < 2:
            logger.warning(f"بيانات غير كافية لحساب تغير السعر لـ {symbol} خلال {days} يوم")
            return None
        
        # استخراج سعر الإغلاق الحالي والقديم
        current_price = float(klines[0][4])  # أحدث سعر إغلاق
        old_price = float(klines[-1][4])  # أقدم سعر إغلاق
        
        # حساب نسبة التغير
        price_change = ((current_price - old_price) / old_price) * 100
        
        return price_change
    except Exception as e:
        logger.error(f"خطأ في حساب تغير السعر النسبي: {e}")
        return None

def identify_trending_coins(limit=10):
    """
    تحديد العملات الرائجة بناءً على حجم التداول والأداء
    
    :param limit: عدد العملات للإرجاع
    :return: قائمة العملات الرائجة
    """
    try:
        from app.exchange_manager import get_top_symbols
        
        # الحصول على أفضل العملات من حيث حجم التداول
        top_volume_symbols = get_top_symbols(limit=limit*2)  # نأخذ ضعف العدد للتصفية
        
        if not top_volume_symbols:
            logger.warning("لم يتم العثور على عملات رائجة")
            return []
        
        # تحليل كل عملة
        trending_coins = []
        for symbol in top_volume_symbols:
            # الحصول على نسبة تغير السعر
            price_change = get_price_change_24h(symbol)
            
            if price_change is not None:
                trending_coins.append({
                    "symbol": symbol,
                    "price_change_24h": price_change,
                })
        
        # ترتيب العملات حسب نسبة التغير
        trending_coins = sorted(trending_coins, key=lambda x: abs(x.get('price_change_24h', 0)), reverse=True)
        
        # إرجاع أفضل 'limit' عملات
        return trending_coins[:limit]
    except Exception as e:
        logger.error(f"خطأ في تحديد العملات الرائجة: {e}")
        return []

def predict_next_move(symbol, timeframe="15m"):
    """
    التنبؤ بالحركة المحتملة التالية للعملة بناءً على المؤشرات الفنية
    
    :param symbol: رمز العملة
    :param timeframe: الإطار الزمني للتحليل
    :return: التنبؤ (dict)
    """
    try:
        from app.exchange_manager import get_historical_klines
        
        # الحصول على البيانات التاريخية
        klines = get_historical_klines(symbol, timeframe, limit=100)
        
        if not klines or len(klines) < 50:
            logger.warning(f"بيانات غير كافية للتنبؤ بحركة {symbol}")
            return {"direction": "غير محدد", "confidence": 0}
        
        # استخراج أسعار الإغلاق
        close_prices = np.array([float(k[4]) for k in klines])
        
        # حساب المتوسطات المتحركة
        ma_short = np.mean(close_prices[-10:])  # متوسط 10 فترات
        ma_medium = np.mean(close_prices[-20:])  # متوسط 20 فترة
        ma_long = np.mean(close_prices[-50:])  # متوسط 50 فترة
        
        current_price = close_prices[-1]
        
        # تحليل وضع المتوسطات والسعر
        above_short = current_price > ma_short
        above_medium = current_price > ma_medium
        above_long = current_price > ma_long
        
        # تحديد الاتجاه المحتمل
        # المزيد من المؤشرات فوق المتوسطات = احتمال أكبر للارتفاع
        bullish_indicators = sum([above_short, above_medium, above_long])
        bearish_indicators = 3 - bullish_indicators
        
        confidence = 0
        direction = "غير محدد"
        
        if bullish_indicators > bearish_indicators:
            direction = "صعود"
            confidence = bullish_indicators / 3.0
        elif bearish_indicators > bullish_indicators:
            direction = "هبوط"
            confidence = bearish_indicators / 3.0
        else:
            direction = "ترند جانبي"
            # حساب ضيق النطاق للترند الجانبي
            price_range = (max(close_prices[-10:]) - min(close_prices[-10:])) / current_price
            confidence = 1 - min(price_range * 10, 1)  # نطاق أضيق = ثقة أعلى في الترند الجانبي
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "confidence": confidence,
            "current_price": current_price,
            "ma_short": ma_short,
            "ma_medium": ma_medium,
            "ma_long": ma_long
        }
    except Exception as e:
        logger.error(f"خطأ في التنبؤ بالحركة التالية: {e}")
        return {"direction": "غير محدد", "confidence": 0, "error": str(e)}