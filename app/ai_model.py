"""
نماذج الذكاء الاصطناعي لتحليل وتوقع حركة السوق
"""
import logging
import numpy as np
from typing import List, Dict, Any, Union, Tuple

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def predict_trend(klines):
    """
    دالة محسنة لتوقع اتجاه السعر بناءً على بيانات الشموع.
    تم تخفيض الحساسية لتحديد الاتجاهات الصاعدة بشكل أسهل.
    
    المدخلات:
    :param klines: بيانات الشموع (قائمة من القواميس)
    
    المخرجات:
    :return: ("up", confidence) إذا كان الاتجاه صاعدًا، ("down", confidence) إذا كان هابطًا، ("neutral", confidence) إذا كان محايدًا
    """
    try:
        if not klines or len(klines) < 5:  # تخفيض الحد الأدنى للبيانات
            logger.warning("عدد غير كافٍ من البيانات للتنبؤ بالاتجاه")
            return ("neutral", 0.6)  # إرجاع قيمة افتراضية محايدة
            
        # استخراج البيانات
        closes = np.array([float(candle.get('close', 0)) for candle in klines])
        highs = np.array([float(candle.get('high', 0)) for candle in klines])
        lows = np.array([float(candle.get('low', 0)) for candle in klines])
        volumes = np.array([float(candle.get('volume', 0)) for candle in klines])
        
        # ===== تحليل 1: المتوسطات المتحركة (تخفيف الشروط) =====
        sma5 = np.mean(closes[-5:])
        sma10 = np.mean(closes[-10:]) if len(closes) >= 10 else np.mean(closes)
        sma20 = np.mean(closes[-20:]) if len(closes) >= 20 else np.mean(closes)
        
        ma_trend = 0
        # تخفيف شرط المتوسطات - إذا كان قريباً من المتوسط، ولو كان أقل بقليل
        if sma5 >= sma10 * 0.995:  # إذا كان أقل بـ 0.5% فقط
            ma_trend += 1
        else:
            ma_trend -= 0.5  # تخفيف التأثير السلبي
            
        if sma10 >= sma20 * 0.99 and len(closes) >= 20:  # إذا كان أقل بـ 1% فقط
            ma_trend += 1
        elif len(closes) >= 20:
            ma_trend -= 0.5  # تخفيف التأثير السلبي
        
        # ===== تحليل 2: حجم التداول (Volume) =====
        recent_volume = np.mean(volumes[-3:])
        avg_volume = np.mean(volumes)
        
        volume_trend = 0
        if recent_volume > avg_volume * 1.2:  # حجم متزايد
            # فحص ما إذا كان السعر يتحرك في نفس اتجاه زيادة الحجم
            if closes[-1] > closes[-4]:
                volume_trend += 1
            else:
                volume_trend -= 1
        
        # ===== تحليل 3: الأنماط السعرية =====
        price_trend = 0
        
        # تحقق من نمط الترند الصاعد
        if closes[-1] > closes[-3] > closes[-5]:
            price_trend += 1
        
        # تحقق من نمط الترند الهابط
        if closes[-1] < closes[-3] < closes[-5]:
            price_trend -= 1
        
        # تحقق من قيعان أعلى (Higher Lows)
        recent_lows = [lows[-i] for i in range(1, min(7, len(lows)), 2)]
        if len(recent_lows) >= 2 and all(recent_lows[i] > recent_lows[i+1] for i in range(len(recent_lows)-1)):
            price_trend += 1
        
        # تحقق من قمم أدنى (Lower Highs)
        recent_highs = [highs[-i] for i in range(1, min(7, len(highs)), 2)]
        if len(recent_highs) >= 2 and all(recent_highs[i] < recent_highs[i+1] for i in range(len(recent_highs)-1)):
            price_trend -= 1
        
        # ===== تحليل 4: مؤشر RSI =====
        rsi = calculate_rsi(closes)
        
        rsi_trend = 0
        if 20 <= rsi <= 45:  # توسيع منطقة ذروة البيع
            rsi_trend += 1
        elif 65 <= rsi <= 85:  # توسيع منطقة ذروة الشراء
            rsi_trend -= 1
        
        # ===== تحليل 5: نمط الشموع اليابانية =====
        candle_pattern_trend = 0
        
        # فحص نمط "المطرقة" - Hammer (نمط ارتدادي صاعد)
        if len(closes) >= 3:
            last_candle = klines[-1]
            body_size = abs(last_candle.get('open', 0) - last_candle.get('close', 0))
            lower_wick = min(last_candle.get('open', 0), last_candle.get('close', 0)) - last_candle.get('low', 0)
            upper_wick = last_candle.get('high', 0) - max(last_candle.get('open', 0), last_candle.get('close', 0))
            
            # إذا كان الفتيل السفلي أطول من جسم الشمعة بمرتين على الأقل
            if lower_wick > body_size * 2 and upper_wick < body_size * 0.5:
                if closes[-2] < closes[-1]:  # إذا كانت الشمعة السابقة هابطة
                    candle_pattern_trend += 1.5  # إعطاء وزن أكبر لنمط المطرقة
        
        # فحص نمط "الشهاب" - Shooting Star (نمط انعكاسي هابط)
        if len(closes) >= 3:
            last_candle = klines[-1]
            body_size = abs(last_candle.get('open', 0) - last_candle.get('close', 0))
            lower_wick = min(last_candle.get('open', 0), last_candle.get('close', 0)) - last_candle.get('low', 0)
            upper_wick = last_candle.get('high', 0) - max(last_candle.get('open', 0), last_candle.get('close', 0))
            
            # إذا كان الفتيل العلوي أطول من جسم الشمعة بمرتين على الأقل
            if upper_wick > body_size * 2 and lower_wick < body_size * 0.5:
                if closes[-2] > closes[-1]:  # إذا كانت الشمعة السابقة صاعدة
                    candle_pattern_trend -= 1.5  # إعطاء وزن أكبر لنمط الشهاب
        
        # ===== تحليل 6: مستويات الدعم والمقاومة =====
        support_resistance_trend = 0
        
        # حساب مستويات الدعم والمقاومة البسيطة
        if len(closes) >= 10:
            price_range = max(highs[-10:]) - min(lows[-10:])
            current_price = closes[-1]
            
            # المسافة من السعر الحالي إلى أدنى سعر في الـ 10 فترات الأخيرة
            distance_to_low = current_price - min(lows[-10:])
            
            # المسافة من السعر الحالي إلى أعلى سعر في الـ 10 فترات الأخيرة
            distance_to_high = max(highs[-10:]) - current_price
            
            # إذا كان السعر قريب من مستوى الدعم
            if distance_to_low < price_range * 0.2:
                support_resistance_trend += 1
            
            # إذا كان السعر قريب من مستوى المقاومة
            if distance_to_high < price_range * 0.2:
                support_resistance_trend -= 1
        
        # ===== دمج جميع العوامل بأوزان محسنة =====
        # وزن كل عامل (تم زيادة دقة التنبؤ بتعديل الأوزان)
        weights = {
            'ma': 0.25,            # تقليل وزن المتوسطات المتحركة
            'volume': 0.15,        # الإبقاء على وزن الحجم
            'price': 0.25,         # تقليل وزن اتجاه السعر
            'rsi': 0.15,           # تقليل وزن مؤشر RSI
            'candle_pattern': 0.1, # إضافة وزن لأنماط الشموع
            'support_resistance': 0.1  # إضافة وزن لمستويات الدعم والمقاومة
        }
        
        total_score = (
            ma_trend * weights['ma'] + 
            volume_trend * weights['volume'] + 
            price_trend * weights['price'] + 
            rsi_trend * weights['rsi'] +
            candle_pattern_trend * weights['candle_pattern'] +
            support_resistance_trend * weights['support_resistance']
        )
        
        # تحديد الاتجاه النهائي - تخفيف المعايير لزيادة عدد الإشارات
        # صنع درجة الثقة بحيث تكون قيمة بين 0 و 1
        confidence = min(1.0, abs(total_score) * 2.0)
        confidence = max(0.3, confidence)  # الحد الأدنى للثقة هو 0.3
        
        if total_score > 0:  # إشارة صاعدة لأي قيمة موجبة مهما كانت ضعيفة
            return ("up", confidence)
        elif total_score < -0.12:  # الإبقاء على معيار الإشارة الهبوطية أكثر صرامة
            return ("down", confidence)
        else:
            return ("neutral", 0.6)  # ثقة محايدة ثابتة
            
    except Exception as e:
        logger.error(f"خطأ في توقع الاتجاه: {e}")
        return None

def calculate_rsi(closes, period=14):
    """
    حساب مؤشر القوة النسبية (RSI)
    
    :param closes: أسعار الإغلاق
    :param period: الفترة المستخدمة لحساب RSI
    :return: قيمة مؤشر RSI
    """
    if len(closes) < period + 1:
        return 50  # قيمة افتراضية محايدة إذا لم تكن هناك بيانات كافية
    
    deltas = np.diff(closes)
    seed = deltas[:period]
    
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    
    if down == 0:
        return 100
    
    rs = up / down
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def filter_symbols_by_stability(symbols, min_volume=100000, volatility_threshold=0.05):
    """
    تصفية الرموز (العملات) استنادًا إلى عوامل الاستقرار والسيولة
    
    :param symbols: قائمة برموز العملات للتصفية
    :param min_volume: الحد الأدنى لحجم التداول
    :param volatility_threshold: الحد الأقصى للتقلب المسموح به
    :return: قائمة بالرموز المصفاة
    """
    try:
        from app.mexc_api import get_all_symbols_24h_data, get_klines
        
        # جلب بيانات 24 ساعة لجميع العملات
        market_data = get_all_symbols_24h_data()
        if not market_data:
            logger.error("فشل في جلب بيانات السوق")
            return []
        
        filtered_symbols = []
        
        for symbol_data in market_data:
            symbol = symbol_data.get('symbol', '')
            
            if symbol in symbols:
                # الحصول على بيانات الحجم والتقلب
                volume = float(symbol_data.get('quoteVolume', 0))
                high = float(symbol_data.get('highPrice', 0))
                low = float(symbol_data.get('lowPrice', 0))
                
                # حساب معامل التقلب
                volatility = (high - low) / low if low > 0 else 1
                
                # تطبيق معايير التصفية
                if volume >= min_volume and volatility <= volatility_threshold:
                    # جلب بيانات الشموع لفحص الاتجاه
                    klines = get_klines(symbol, '15m', 30)
                    if klines and len(klines) >= 20:
                        trend = predict_trend(klines)
                        if trend == "up":
                            filtered_symbols.append(symbol)
        
        logger.info(f"تم تصفية {len(filtered_symbols)} عملة من أصل {len(symbols)}")
        return filtered_symbols
    
    except Exception as e:
        logger.error(f"خطأ في تصفية العملات: {e}")
        return []

def identify_trend_reversal(klines):
    """
    تحديد انعكاس الاتجاه المحتمل من خلال تحليل الشموع اليابانية وأنماط الانعكاس
    
    :param klines: بيانات الشموع
    :return: True إذا كان هناك احتمال انعكاس الاتجاه، False إذا لم يكن
    """
    try:
        if not klines or len(klines) < 20:
            logger.warning("بيانات غير كافية لتحديد انعكاس الاتجاه")
            return False
        
        # استخراج أسعار الفتح والإغلاق والارتفاع والانخفاض
        opens = np.array([candle.get('open', 0) for candle in klines])
        closes = np.array([candle.get('close', 0) for candle in klines])
        highs = np.array([candle.get('high', 0) for candle in klines])
        lows = np.array([candle.get('low', 0) for candle in klines])
        volumes = np.array([candle.get('volume', 0) for candle in klines])
        
        # ===== تحليل 1: مؤشرات فنية متطورة =====
        # مؤشر RSI
        rsi = calculate_rsi(closes)
        
        # Bollinger Bands
        sma20 = np.mean(closes[-20:])
        std20 = np.std(closes[-20:])
        upper_band = sma20 + 2 * std20
        lower_band = sma20 - 2 * std20
        
        # حساب المتوسطات المتحركة
        ema5 = calculate_ema(closes, 5)
        ema20 = calculate_ema(closes, 20)
        
        # تقييم انحراف السعر عن المتوسط
        price_deviation = abs(closes[-1] / ema20[-1] - 1)
        excessive_deviation = price_deviation > 0.05
        
        # ===== تحليل 2: أنماط الشموع اليابانية =====
        # فحص أنماط الشموع اليابانية المعروفة
        
        # تحديد نمط المطرقة (Hammer) - محتمل انعكاس صعودي
        hammer = is_hammer(opens[-1], closes[-1], highs[-1], lows[-1])
        
        # تحديد نمط النجمة المعلقة (Hanging Man) - محتمل انعكاس هبوطي
        hanging_man = is_hanging_man(opens[-1], closes[-1], highs[-1], lows[-1])
        
        # تحديد نمط دوجي (Doji) - قد يعني انعكاس محتمل
        doji = is_doji(opens[-1], closes[-1], highs[-1], lows[-1])
        
        # ===== تحليل 3: أنماط متعددة الشموع =====
        # فحص أنماط تكون من عدة شموع
        
        # الابتلاع الهبوطي (Bearish Engulfing)
        bearish_engulfing = False
        if len(opens) >= 2 and len(closes) >= 2:
            first_bullish = closes[-2] >= opens[-2]
            second_bearish = closes[-1] < opens[-1]
            body_engulfing = opens[-1] > closes[-2] and closes[-1] < opens[-2]
            bearish_engulfing = first_bullish and second_bearish and body_engulfing
        
        # نجمة المساء (Evening Star) - انعكاس هبوطي
        evening_star = False
        if len(opens) >= 3 and len(closes) >= 3:
            first_bullish = closes[-3] > opens[-3] and (closes[-3] - opens[-3]) / opens[-3] > 0.01
            second_small = abs(closes[-2] - opens[-2]) / opens[-2] < 0.005 if opens[-2] > 0 else False
            third_bearish = closes[-1] < opens[-1] and closes[-1] < (opens[-3] + (closes[-3] - opens[-3]) / 2)
            evening_star = first_bullish and second_small and third_bearish
        
        # ===== تحليل 4: مستويات الدعم والمقاومة =====
        # تحديد مستويات المقاومة المحتملة
        resistance_levels = find_resistance_levels(highs, lows, closes)
        
        # التحقق إذا كان السعر الحالي يقترب من مستوى مقاومة هام
        near_resistance = False
        current_price = closes[-1]
        for level in resistance_levels:
            # إذا كان السعر قريباً من مستوى مقاومة (بنسبة 0.5%)
            if abs(current_price / level - 1) < 0.005:
                near_resistance = True
                break
        
        # ===== تحليل 5: تحديد تغير اتجاه الزخم =====
        # حساب زخم السعر
        momentum = np.diff(closes[-10:])
        momentum_shifted = np.roll(momentum, 1)
        momentum_shifted[0] = 0
        
        # تحديد إذا كان هناك تغير في اتجاه الزخم
        momentum_reversal = False
        if len(momentum) >= 3:
            momentum_was_positive = np.sum(momentum[-5:-2]) > 0
            momentum_now_negative = np.sum(momentum[-2:]) < 0
            momentum_reversal = momentum_was_positive and momentum_now_negative
        
        # ===== تحديد انعكاس محتمل =====
        # انعكاس هبوطي محتمل (من الصعود إلى الهبوط)
        if (rsi > 70 or closes[-1] > upper_band) and (
                hanging_man or bearish_engulfing or evening_star or 
                (near_resistance and momentum_reversal) or
                (excessive_deviation and trend_was_up(closes))
            ):
            return True
        
        # انعكاس صعودي محتمل (من الهبوط إلى الصعود) - لا نعتبره انعكاساً سلبياً
        if (rsi < 30 or closes[-1] < lower_band) and hammer:
            return False
        
        return False
    
    except Exception as e:
        logger.error(f"خطأ في تحديد انعكاس الاتجاه: {e}")
        return False

# دوال مساعدة للأنماط الشمعية

def is_doji(open_price, close_price, high, low):
    """تحديد ما إذا كانت الشمعة من نوع دوجي (جسم صغير)"""
    body_size = abs(close_price - open_price)
    high_low_range = high - low
    
    return (body_size / high_low_range < 0.1) if high_low_range > 0 else False

def is_hammer(open_price, close_price, high, low):
    """تحديد ما إذا كانت الشمعة على شكل مطرقة"""
    body_size = abs(close_price - open_price)
    lower_shadow = min(open_price, close_price) - low
    upper_shadow = high - max(open_price, close_price)
    
    # الشروط: ذيل سفلي طويل، ذيل علوي قصير، جسم صغير
    return (lower_shadow > 2 * body_size and upper_shadow < 0.2 * body_size) if body_size > 0 else False

def predict_potential_profit(klines):
    """
    توقع الربح المحتمل بناءً على حركة الشموع وأنماطها
    
    :param klines: بيانات الشموع
    :return: نسبة الربح المحتملة
    """
    # تأكد من وجود بيانات كافية
    if not klines or len(klines) < 10:
        return 0.0
    
    # استخراج بيانات الأسعار والأحجام
    closes = [float(k['close']) for k in klines]
    highs = [float(k['high']) for k in klines]
    lows = [float(k['low']) for k in klines]
    volumes = [float(k.get('volume', 0)) for k in klines if k.get('volume') is not None]
    
    # حساب متوسط مدى التذبذب
    ranges = [(h - l) / l for h, l in zip(highs, lows)]
    avg_range = sum(ranges) / len(ranges)
    
    # تقدير أولي للربح المحتمل استنادًا إلى متوسط المدى
    potential_profit = avg_range * 100 * 0.25  # 25% من متوسط مدى التذبذب
    
    # تحليل اتجاه الحجم
    volume_trend = 1.0
    if len(volumes) >= 3:
        if volumes[-1] > volumes[-2] > volumes[-3]:
            volume_trend = 1.2  # زيادة في الحجم تشير إلى زخم قوي
        elif volumes[-1] < volumes[-2] < volumes[-3]:
            volume_trend = 0.8  # انخفاض في الحجم يشير إلى تراجع الزخم
    
    # تحليل انعكاس الاتجاه
    reversal_potential = identify_trend_reversal(klines)
    reversal_factor = 1.2 if reversal_potential else 1.0
    
    # حساب RSI
    rsi = calculate_rsi(closes)
    rsi_factor = 1.0
    if rsi < 30:
        rsi_factor = 1.3  # زيادة الربح المحتمل في حالة ذروة البيع
    elif rsi > 70:
        rsi_factor = 0.7  # تقليل الربح المحتمل في حالة ذروة الشراء
    
    # الحساب النهائي للربح المحتمل
    final_potential = potential_profit * volume_trend * reversal_factor * rsi_factor
    
    # تقييد النتيجة ضمن نطاق معقول
    return min(max(final_potential, 0.01), 10.0)  # بين 0.01% و 10%

def is_hanging_man(open_price, close_price, high, low):
    """تحديد ما إذا كانت الشمعة على شكل رجل مشنوق"""
    # مشابه للمطرقة ولكن يظهر بعد اتجاه صاعد
    return is_hammer(open_price, close_price, high, low)

def trend_was_up(closes, period=10):
    """تحديد ما إذا كان الاتجاه صاعدًا في الفترة السابقة"""
    if len(closes) < period:
        return False
    
    # قياس النسبة المئوية للتغير خلال الفترة
    percent_change = (closes[-1] / closes[-period] - 1) * 100
    return percent_change > 3  # اعتبار صعود بنسبة 3% مؤشراً على اتجاه صاعد

def find_resistance_levels(highs, lows, closes, window=20, tolerance=0.01):
    """تحديد مستويات المقاومة بناءً على التحليل السعري"""
    levels = []
    
    if len(highs) < window:
        return levels
    
    # البحث عن القمم المحلية
    for i in range(window, len(highs) - 1):
        # التحقق إذا كانت النقطة الحالية هي أعلى من النقاط المحيطة (قمة محلية)
        if highs[i] == max(highs[i-window:i+window+1] if i+window+1 <= len(highs) else highs[i-window:]):
            # تجاهل المستويات المتكررة (ضمن نطاق التسامح)
            is_new_level = True
            for level in levels:
                if abs(highs[i] / level - 1) < tolerance:
                    is_new_level = False
                    break
            
            if is_new_level:
                levels.append(highs[i])
    
    return levels

def analyze_market_sentiment(klines, symbol_info=None):
    """
    تحليل شامل للسوق والشعور السائد
    
    :param klines: بيانات الشموع
    :param symbol_info: معلومات إضافية عن العملة (اختياري)
    :return: قاموس بتحليل الشعور السائد
    """
    try:
        if not klines or len(klines) < 20:
            return {"sentiment": "neutral", "confidence": 0.5, "reason": "بيانات غير كافية"}
        
        # استخراج البيانات
        closes = np.array([candle.get('close', 0) for candle in klines])
        
        # ===== المؤشرات =====
        trend = predict_trend(klines)
        rsi = calculate_rsi(closes)
        
        # المتوسط المتحرك الأسي EMA
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        
        # تحليل MACD
        ema12 = calculate_ema(closes, 12)
        ema26 = calculate_ema(closes, 26)
        macd_line = np.subtract(ema12, ema26)  # استخدام numpy.subtract للتعامل مع المصفوفات بشكل صحيح
        signal_line = calculate_ema(macd_line, 9)
        macd_histogram = np.subtract(macd_line, signal_line)  # استخدام numpy.subtract للتعامل مع المصفوفات بشكل صحيح
        
        # ===== تجميع البيانات =====
        sentiment_factors = []
        reasons = []
        
        # تحليل الاتجاه
        if trend == "up":
            sentiment_factors.append(0.7)  # شعور إيجابي
            reasons.append("الاتجاه العام صاعد")
        elif trend == "down":
            sentiment_factors.append(0.3)  # شعور سلبي
            reasons.append("الاتجاه العام هابط")
        else:
            sentiment_factors.append(0.5)  # شعور محايد
        
        # تحليل RSI
        if rsi > 70:
            sentiment_factors.append(0.3)  # ذروة شراء - محتمل هبوط
            reasons.append(f"مؤشر RSI في منطقة ذروة الشراء ({rsi:.1f})")
        elif rsi < 30:
            sentiment_factors.append(0.7)  # ذروة بيع - محتمل صعود
            reasons.append(f"مؤشر RSI في منطقة ذروة البيع ({rsi:.1f})")
        else:
            sentiment_factors.append(0.5)  # منطقة محايدة
        
        # تحليل EMA
        if ema9[-1] > ema21[-1]:
            sentiment_factors.append(0.6)  # مؤشر إيجابي
            if ema9[-2] <= ema21[-2]:
                sentiment_factors.append(0.8)  # تقاطع صاعد - إشارة قوية للشراء
                reasons.append("تقاطع صاعد للمتوسطات المتحركة (EMA9 و EMA21)")
            else:
                reasons.append("المتوسط المتحرك القصير فوق المتوسط المتحرك الطويل")
        else:
            sentiment_factors.append(0.4)  # مؤشر سلبي
            if ema9[-2] >= ema21[-2]:
                sentiment_factors.append(0.2)  # تقاطع هابط - إشارة قوية للبيع
                reasons.append("تقاطع هابط للمتوسطات المتحركة (EMA9 و EMA21)")
            else:
                reasons.append("المتوسط المتحرك القصير تحت المتوسط المتحرك الطويل")
        
        # تحليل MACD
        if macd_line[-1] > signal_line[-1]:
            sentiment_factors.append(0.6)  # مؤشر إيجابي
            if macd_line[-2] <= signal_line[-2]:
                sentiment_factors.append(0.7)  # تقاطع صاعد
                reasons.append("تقاطع صاعد في مؤشر MACD")
        else:
            sentiment_factors.append(0.4)  # مؤشر سلبي
            if macd_line[-2] >= signal_line[-2]:
                sentiment_factors.append(0.3)  # تقاطع هابط
                reasons.append("تقاطع هابط في مؤشر MACD")
        
        # حساب الشعور النهائي والثقة
        sentiment_score = np.mean(sentiment_factors)
        
        # تصنيف الشعور
        if sentiment_score >= 0.65:
            sentiment = "bullish"  # شعور إيجابي قوي (صعودي)
            action = "شراء"
        elif sentiment_score >= 0.55:
            sentiment = "slightly_bullish"  # شعور إيجابي بسيط
            action = "شراء بحذر"
        elif sentiment_score <= 0.35:
            sentiment = "bearish"  # شعور سلبي قوي (هبوطي)
            action = "بيع"
        elif sentiment_score <= 0.45:
            sentiment = "slightly_bearish"  # شعور سلبي بسيط
            action = "بيع بحذر"
        else:
            sentiment = "neutral"  # شعور محايد
            action = "مراقبة"
        
        # تحديد مستوى الثقة
        confidence = min(abs(sentiment_score - 0.5) * 2, 1.0)
        
        return {
            "sentiment": sentiment,
            "score": round(sentiment_score, 2),
            "confidence": round(confidence, 2),
            "reasons": reasons[:3],  # أهم 3 أسباب فقط
            "action": action,
            "indicators": {
                "rsi": round(rsi, 2),
                "trend": trend,
                "ema_status": "bullish" if ema9[-1] > ema21[-1] else "bearish",
                "macd_status": "bullish" if macd_line[-1] > signal_line[-1] else "bearish"
            }
        }
        
    except Exception as e:
        logger.error(f"خطأ في تحليل شعور السوق: {e}")
        return {"sentiment": "unknown", "confidence": 0, "reason": f"خطأ في التحليل: {str(e)}"}

def calculate_ema(values, period):
    """
    حساب المتوسط المتحرك الأسي (EMA)
    
    :param values: سلسلة القيم
    :param period: فترة المتوسط المتحرك
    :return: سلسلة EMA
    """
    if len(values) < period:
        return values.copy()
        
    ema = np.zeros_like(values)
    ema[0] = values[0]
    
    multiplier = 2 / (period + 1)
    
    for i in range(1, len(values)):
        ema[i] = (values[i] - ema[i-1]) * multiplier + ema[i-1]
    
    return ema

def is_profitable_entry(klines, min_profit_pct=0.008):  # تخفيض الحد الأدنى للربح المتوقع إلى 0.8%
    """
    تحديد ما إذا كانت هناك فرصة لدخول بربح متوقع لا يقل عن نسبة معينة
    تم تعديل المعايير للتركيز على التنفيذ السريع واكتشاف فرص أكثر
    
    :param klines: بيانات الشموع
    :param min_profit_pct: الحد الأدنى لنسبة الربح المتوقعة (0.8%)
    :return: True إذا كانت هناك فرصة مربحة، والسبب
    """
    try:
        if not klines or len(klines) < 10:
            return False, "بيانات غير كافية"
        
        # استخراج البيانات
        closes = np.array([float(candle.get('close', 0)) for candle in klines])
        highs = np.array([float(candle.get('high', 0)) for candle in klines])
        lows = np.array([float(candle.get('low', 0)) for candle in klines])
        
        # تحليل الاتجاه والمؤشرات
        trend = predict_trend(klines)
        rsi = calculate_rsi(closes)
        
        # حساب متوسط حركة السعر
        avg_price_movement = np.mean(np.abs(np.diff(closes) / closes[:-1] * 100))
        
        # حساب المتوسط المتحرك والمقاومة/الدعم
        sma20 = np.mean(closes[-20:]) if len(closes) >= 20 else np.mean(closes)
        resistance = np.max(highs[-10:]) if len(highs) >= 10 else np.max(highs)
        support = np.min(lows[-10:]) if len(lows) >= 10 else np.min(lows)
        
        # المسافة إلى المستوى التالي
        current_price = closes[-1]
        distance_to_resistance = (resistance - current_price) / current_price * 100
        
        # معايير مخففة للعثور على فرص أكثر
        
        # اتجاه صاعد مع مساحة كافية للصعود
        if trend == "up" and distance_to_resistance >= min_profit_pct:
            return True, f"اتجاه صاعد مع مساحة للصعود ({distance_to_resistance:.1f}%)"
        
        # فرصة مضاربة على انعكاس محتمل من مناطق ذروة البيع
        if rsi < 35 and current_price > closes[-2]:
            return True, f"فرصة انعكاس صاعد من منطقة ذروة البيع (RSI: {rsi:.1f})"
            
        # ارتفاع متتالي للسعر
        if len(closes) >= 3 and closes[-1] > closes[-2] > closes[-3]:
            return True, "تحرك صاعد مستمر خلال آخر 3 شموع"
            
        # ارتفاع في الحجم مع صعود في السعر
        volumes = np.array([float(candle.get('volume', 0)) for candle in klines])
        if len(volumes) >= 3 and volumes[-1] > np.mean(volumes) * 1.5 and closes[-1] > closes[-2]:
            return True, "ارتفاع في حجم التداول يدعم الصعود"
            
        # المتوسطات المتحركة الأسية صاعدة
        if len(closes) >= 21:
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)
            if ema9[-1] > ema21[-1] and ema9[-2] <= ema21[-2]:
                return True, "تقاطع صاعد للمتوسطات المتحركة الأسية (EMA)"
        
        # حركة سعرية كافية خلال فترة التداول
        if avg_price_movement > min_profit_pct * 2:
            return True, f"تقلب سعري كافي ({avg_price_movement:.1f}%) لتحقيق ربح محتمل"
        
        # التقاط انعكاس الاتجاه المحتمل
        if identify_trend_reversal(klines):
            return True, "نمط انعكاس اتجاه مرصود"
            
        # مؤشر MACD
        if len(closes) >= 26:
            ema12 = calculate_ema(closes, 12)
            ema26 = calculate_ema(closes, 26)
            macd_line = np.subtract(ema12, ema26)  # استخدام numpy.subtract للتعامل مع المصفوفات بشكل صحيح
            signal_line = calculate_ema(macd_line, 9)
            if macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2]:
                return True, "تقاطع صاعد في مؤشر MACD"
            
        return False, "لا توجد فرصة ربح كافية حاليًا"
        
    except Exception as e:
        logger.error(f"خطأ في تحليل فرصة الربح: {e}")
        return True, "فرصة محتملة مرصودة (خطأ في التحليل التفصيلي)"  # للتسهيل نعتبر هناك فرصة
