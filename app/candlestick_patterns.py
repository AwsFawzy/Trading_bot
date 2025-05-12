"""
وحدة تحليل أنماط الشموع اليابانية للتعرف على فرص التداول
"""
import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_doji(open_price: float, close_price: float, high: float, low: float) -> bool:
    """
    تحديد ما إذا كانت الشمعة من نوع دوجي (Doji) - جسم صغير وظلال طويلة
    
    :param open_price: سعر افتتاح الشمعة
    :param close_price: سعر إغلاق الشمعة
    :param high: أعلى سعر
    :param low: أدنى سعر
    :return: True إذا كانت الشمعة دوجي، False خلاف ذلك
    """
    body_size = abs(close_price - open_price)
    range_size = high - low
    
    # إذا كان حجم الجسم صغيراً جداً بالنسبة للمدى الكلي
    if range_size > 0:
        return body_size / range_size < 0.1
    return False

def is_hammer(open_price: float, close_price: float, high: float, low: float) -> bool:
    """
    تحديد ما إذا كانت الشمعة على شكل مطرقة (Hammer) - جسم صغير وظل سفلي طويل
    
    :param open_price: سعر افتتاح الشمعة
    :param close_price: سعر إغلاق الشمعة
    :param high: أعلى سعر
    :param low: أدنى سعر
    :return: True إذا كانت الشمعة مطرقة، False خلاف ذلك
    """
    body_size = abs(close_price - open_price)
    range_size = high - low
    
    # تحديد الظل العلوي والسفلي
    upper_shadow = high - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low
    
    # الشرط: الظل السفلي طويل (أكثر من ضعف حجم الجسم) والظل العلوي قصير
    if range_size > 0 and body_size > 0:
        return (lower_shadow / body_size >= 2.0 and 
                upper_shadow / body_size <= 0.5 and
                lower_shadow / range_size >= 0.6)
    return False

def is_shooting_star(open_price: float, close_price: float, high: float, low: float) -> bool:
    """
    تحديد ما إذا كانت الشمعة على شكل نجمة هابطة (Shooting Star) - جسم صغير وظل علوي طويل
    
    :param open_price: سعر افتتاح الشمعة
    :param close_price: سعر إغلاق الشمعة
    :param high: أعلى سعر
    :param low: أدنى سعر
    :return: True إذا كانت الشمعة نجمة هابطة، False خلاف ذلك
    """
    body_size = abs(close_price - open_price)
    range_size = high - low
    
    # تحديد الظل العلوي والسفلي
    upper_shadow = high - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low
    
    # الشرط: الظل العلوي طويل (أكثر من ضعف حجم الجسم) والظل السفلي قصير
    if range_size > 0 and body_size > 0:
        return (upper_shadow / body_size >= 2.0 and 
                lower_shadow / body_size <= 0.5 and
                upper_shadow / range_size >= 0.6)
    return False

def is_engulfing_bullish(current_open: float, current_close: float, 
                        prev_open: float, prev_close: float) -> bool:
    """
    تحديد ما إذا كانت شمعة الابتلاع الصاعدة (Bullish Engulfing)
    
    :param current_open: سعر افتتاح الشمعة الحالية
    :param current_close: سعر إغلاق الشمعة الحالية
    :param prev_open: سعر افتتاح الشمعة السابقة
    :param prev_close: سعر إغلاق الشمعة السابقة
    :return: True إذا كان هناك ابتلاع صاعد، False خلاف ذلك
    """
    # الشمعة السابقة هابطة (أحمر) والشمعة الحالية صاعدة (أخضر)
    if prev_close < prev_open and current_close > current_open:
        # يجب أن يحتوي إغلاق الشمعة الحالية على افتتاح وإغلاق الشمعة السابقة
        return (current_open <= prev_close and 
                current_close >= prev_open)
    return False

def is_engulfing_bearish(current_open: float, current_close: float, 
                         prev_open: float, prev_close: float) -> bool:
    """
    تحديد ما إذا كانت شمعة الابتلاع الهابطة (Bearish Engulfing)
    
    :param current_open: سعر افتتاح الشمعة الحالية
    :param current_close: سعر إغلاق الشمعة الحالية
    :param prev_open: سعر افتتاح الشمعة السابقة
    :param prev_close: سعر إغلاق الشمعة السابقة
    :return: True إذا كان هناك ابتلاع هابط، False خلاف ذلك
    """
    # الشمعة السابقة صاعدة (أخضر) والشمعة الحالية هابطة (أحمر)
    if prev_close > prev_open and current_close < current_open:
        # يجب أن يحتوي افتتاح الشمعة الحالية على افتتاح وإغلاق الشمعة السابقة
        return (current_open >= prev_close and 
                current_close <= prev_open)
    return False

def is_pin_bar(open_price: float, close_price: float, high: float, low: float) -> bool:
    """
    تحديد ما إذا كانت الشمعة على شكل بن بار (Pin Bar)
    
    :param open_price: سعر افتتاح الشمعة
    :param close_price: سعر إغلاق الشمعة
    :param high: أعلى سعر
    :param low: أدنى سعر
    :return: True إذا كانت الشمعة بن بار، False خلاف ذلك
    """
    # Pin Bar هو نموذج مشابه للمطرقة والنجمة الهابطة
    return is_hammer(open_price, close_price, high, low) or is_shooting_star(open_price, close_price, high, low)

def is_three_white_soldiers(klines: List[Dict[str, Any]]) -> bool:
    """
    تحديد ما إذا كان هناك نموذج ثلاث جنود بيض (Three White Soldiers)
    
    :param klines: بيانات الشموع (يجب أن يكون هناك على الأقل 3 شموع)
    :return: True إذا كان النموذج موجود، False خلاف ذلك
    """
    if len(klines) < 3:
        return False
    
    # الثلاث شموع الأخيرة
    candle1 = klines[-3]
    candle2 = klines[-2]
    candle3 = klines[-1]
    
    # تحقق من أن جميع الشموع صاعدة (خضراء)
    if not (float(candle1['close']) > float(candle1['open']) and
            float(candle2['close']) > float(candle2['open']) and
            float(candle3['close']) > float(candle3['open'])):
        return False
    
    # تحقق من أن سعر الإغلاق يزداد في كل شمعة
    if not (float(candle3['close']) > float(candle2['close']) > float(candle1['close'])):
        return False
    
    # تحقق من أن كل شمعة تفتح ضمن نطاق الشمعة السابقة وتغلق فوقها
    if not (float(candle2['open']) >= float(candle1['open']) and
            float(candle3['open']) >= float(candle2['open'])):
        return False
    
    return True

def is_three_black_crows(klines: List[Dict[str, Any]]) -> bool:
    """
    تحديد ما إذا كان هناك نموذج ثلاث غربان سود (Three Black Crows)
    
    :param klines: بيانات الشموع (يجب أن يكون هناك على الأقل 3 شموع)
    :return: True إذا كان النموذج موجود، False خلاف ذلك
    """
    if len(klines) < 3:
        return False
    
    # الثلاث شموع الأخيرة
    candle1 = klines[-3]
    candle2 = klines[-2]
    candle3 = klines[-1]
    
    # تحقق من أن جميع الشموع هابطة (حمراء)
    if not (float(candle1['close']) < float(candle1['open']) and
            float(candle2['close']) < float(candle2['open']) and
            float(candle3['close']) < float(candle3['open'])):
        return False
    
    # تحقق من أن سعر الإغلاق ينخفض في كل شمعة
    if not (float(candle3['close']) < float(candle2['close']) < float(candle1['close'])):
        return False
    
    # تحقق من أن كل شمعة تفتح ضمن نطاق الشمعة السابقة وتغلق تحتها
    if not (float(candle2['open']) <= float(candle1['open']) and
            float(candle3['open']) <= float(candle2['open'])):
        return False
    
    return True

def is_morning_star(klines: List[Dict[str, Any]]) -> bool:
    """
    تحديد ما إذا كان هناك نموذج نجمة الصباح (Morning Star)
    
    :param klines: بيانات الشموع (يجب أن يكون هناك على الأقل 3 شموع)
    :return: True إذا كان النموذج موجود، False خلاف ذلك
    """
    if len(klines) < 3:
        return False
    
    # الثلاث شموع الأخيرة
    candle1 = klines[-3]  # الشمعة الأولى (هابطة)
    candle2 = klines[-2]  # الشمعة الوسطى (دوجي أو صغيرة)
    candle3 = klines[-1]  # الشمعة الثالثة (صاعدة)
    
    # الشمعة الأولى هابطة (حمراء) والشمعة الثالثة صاعدة (خضراء)
    if not (float(candle1['close']) < float(candle1['open']) and
            float(candle3['close']) > float(candle3['open'])):
        return False
    
    # حجم الشمعة الوسطى صغير نسبياً
    middle_body_size = abs(float(candle2['close']) - float(candle2['open']))
    first_body_size = abs(float(candle1['close']) - float(candle1['open']))
    third_body_size = abs(float(candle3['close']) - float(candle3['open']))
    
    if not middle_body_size < 0.5 * min(first_body_size, third_body_size):
        return False
    
    # الشمعة الثالثة يجب أن تغلق فوق منتصف الشمعة الأولى
    first_mid_point = (float(candle1['open']) + float(candle1['close'])) / 2
    if not float(candle3['close']) > first_mid_point:
        return False
    
    return True

def is_evening_star(klines: List[Dict[str, Any]]) -> bool:
    """
    تحديد ما إذا كان هناك نموذج نجمة المساء (Evening Star)
    
    :param klines: بيانات الشموع (يجب أن يكون هناك على الأقل 3 شموع)
    :return: True إذا كان النموذج موجود، False خلاف ذلك
    """
    if len(klines) < 3:
        return False
    
    # الثلاث شموع الأخيرة
    candle1 = klines[-3]  # الشمعة الأولى (صاعدة)
    candle2 = klines[-2]  # الشمعة الوسطى (دوجي أو صغيرة)
    candle3 = klines[-1]  # الشمعة الثالثة (هابطة)
    
    # الشمعة الأولى صاعدة (خضراء) والشمعة الثالثة هابطة (حمراء)
    if not (float(candle1['close']) > float(candle1['open']) and
            float(candle3['close']) < float(candle3['open'])):
        return False
    
    # حجم الشمعة الوسطى صغير نسبياً
    middle_body_size = abs(float(candle2['close']) - float(candle2['open']))
    first_body_size = abs(float(candle1['close']) - float(candle1['open']))
    third_body_size = abs(float(candle3['close']) - float(candle3['open']))
    
    if not middle_body_size < 0.5 * min(first_body_size, third_body_size):
        return False
    
    # الشمعة الثالثة يجب أن تغلق تحت منتصف الشمعة الأولى
    first_mid_point = (float(candle1['open']) + float(candle1['close'])) / 2
    if not float(candle3['close']) < first_mid_point:
        return False
    
    return True

def detect_candlestick_patterns(klines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    اكتشاف أنماط الشموع اليابانية في بيانات الشموع
    
    :param klines: بيانات الشموع
    :return: قاموس يحتوي على الأنماط المكتشفة والاتجاه المحتمل
    """
    if not klines or len(klines) < 3:
        return {"patterns": [], "trend": "neutral", "strength": 0}
    
    patterns = []
    trend = "neutral"
    strength = 0  # قوة الإشارة (0-1)
    
    # استخراج البيانات للشمعة الحالية والسابقة
    current_candle = klines[-1]
    prev_candle = klines[-2]
    
    current_open = float(current_candle['open'])
    current_close = float(current_candle['close'])
    current_high = float(current_candle['high'])
    current_low = float(current_candle['low'])
    
    prev_open = float(prev_candle['open'])
    prev_close = float(prev_candle['close'])
    
    # اكتشاف الأنماط
    
    # 1. نموذج دوجي
    if is_doji(current_open, current_close, current_high, current_low):
        patterns.append("doji")
        # دوجي لوحده لا يعطي اتجاه واضح، لكن يمكن أن يشير إلى تردد السوق
    
    # 2. نموذج المطرقة (صاعد)
    if is_hammer(current_open, current_close, current_high, current_low):
        patterns.append("hammer")
        trend = "up"
        strength += 0.5
    
    # 3. نموذج النجمة الهابطة (هابط)
    if is_shooting_star(current_open, current_close, current_high, current_low):
        patterns.append("shooting_star")
        trend = "down"
        strength += 0.5
    
    # 4. نموذج الابتلاع الصاعد
    if is_engulfing_bullish(current_open, current_close, prev_open, prev_close):
        patterns.append("bullish_engulfing")
        trend = "up"
        strength += 0.7
    
    # 5. نموذج الابتلاع الهابط
    if is_engulfing_bearish(current_open, current_close, prev_open, prev_close):
        patterns.append("bearish_engulfing")
        trend = "down"
        strength += 0.7
    
    # 6. نموذج البن بار
    if is_pin_bar(current_open, current_close, current_high, current_low):
        patterns.append("pin_bar")
        # تحديد الاتجاه بناءً على شكل البن بار
        if current_close > current_open:  # شمعة صاعدة
            trend = "up"
            strength += 0.5
        else:  # شمعة هابطة
            trend = "down"
            strength += 0.5
    
    # 7. نموذج ثلاث جنود بيض (صاعد قوي)
    if is_three_white_soldiers(klines):
        patterns.append("three_white_soldiers")
        trend = "up"
        strength += 0.9
    
    # 8. نموذج ثلاث غربان سود (هابط قوي)
    if is_three_black_crows(klines):
        patterns.append("three_black_crows")
        trend = "down"
        strength += 0.9
    
    # 9. نموذج نجمة الصباح (صاعد)
    if is_morning_star(klines):
        patterns.append("morning_star")
        trend = "up"
        strength += 0.8
    
    # 10. نموذج نجمة المساء (هابط)
    if is_evening_star(klines):
        patterns.append("evening_star")
        trend = "down"
        strength += 0.8
    
    # تقييد قوة الإشارة بين 0 و 1
    strength = min(strength, 1.0)
    
    return {
        "patterns": patterns,
        "trend": trend,
        "strength": strength
    }

def get_entry_signal(klines_1h, klines_15m, klines_5m) -> Tuple[bool, str, float, Dict[str, Any]]:
    """
    تحليل شامل للإطارات الزمنية المتعددة (1 ساعة، 15 دقيقة، 5 دقائق) ليقرر إشارة دخول
    
    :param klines_1h: بيانات شموع الإطار الزمني 1 ساعة
    :param klines_15m: بيانات شموع الإطار الزمني 15 دقيقة
    :param klines_5m: بيانات شموع الإطار الزمني 5 دقائق
    :return: (هل توجد إشارة دخول، الاتجاه، قوة الإشارة، معلومات إضافية)
    """
    # 1. تحليل الإطار الزمني 1 ساعة للاتجاه العام
    patterns_1h = detect_candlestick_patterns(klines_1h)
    trend_1h = patterns_1h['trend']
    strength_1h = patterns_1h['strength']
    
    # 2. تحليل الإطار الزمني 15 دقيقة للتأكيد
    patterns_15m = detect_candlestick_patterns(klines_15m)
    trend_15m = patterns_15m['trend']
    strength_15m = patterns_15m['strength']
    
    # 3. تحليل الإطار الزمني 5 دقائق لنقطة الدخول
    patterns_5m = detect_candlestick_patterns(klines_5m)
    trend_5m = patterns_5m['trend']
    strength_5m = patterns_5m['strength']
    
    # اتخاذ القرار:
    # إشارة قوية: يجب أن يكون الاتجاه متوافقًا في جميع الإطارات الزمنية
    if trend_1h == trend_15m == trend_5m and trend_1h != "neutral":
        signal = True
        trend = trend_1h
        # الوزن: 50% للإطار الزمني 1h، 30% للإطار الزمني 15m، 20% للإطار الزمني 5m
        strength = (strength_1h * 0.5) + (strength_15m * 0.3) + (strength_5m * 0.2)
    
    # إشارة متوسطة: الاتجاه متوافق بين 1h و15m، مع إشارة دخول قوية في 5m
    elif trend_1h == trend_15m and trend_1h != "neutral" and strength_5m >= 0.7:
        signal = True
        trend = trend_1h
        # الوزن: 40% للإطار الزمني 1h، 40% للإطار الزمني 15m، 20% للإطار الزمني 5m
        strength = (strength_1h * 0.4) + (strength_15m * 0.4) + (strength_5m * 0.2)
    
    # إشارة ضعيفة: نمط قوي جدًا في 5m يتوافق مع اتجاه 1h
    elif trend_1h == trend_5m and trend_1h != "neutral" and strength_5m >= 0.9:
        signal = True
        trend = trend_1h
        # الوزن: 60% للإطار الزمني 1h، 10% للإطار الزمني 15m، 30% للإطار الزمني 5m
        strength = (strength_1h * 0.6) + (strength_15m * 0.1) + (strength_5m * 0.3)
    
    # لا توجد إشارة واضحة
    else:
        signal = False
        trend = "neutral"
        strength = 0.0
    
    additional_info = {
        "1h": {
            "patterns": patterns_1h["patterns"],
            "trend": trend_1h,
            "strength": strength_1h
        },
        "15m": {
            "patterns": patterns_15m["patterns"],
            "trend": trend_15m,
            "strength": strength_15m
        },
        "5m": {
            "patterns": patterns_5m["patterns"],
            "trend": trend_5m,
            "strength": strength_5m
        }
    }
    
    return signal, trend, strength, additional_info

def calculate_take_profit_stop_loss(entry_price: float, trend: str, 
                                   klines_1h, risk_reward_ratio=2.0) -> Tuple[float, float]:
    """
    حساب مستويات أخذ الربح ووقف الخسارة بناءً على حركة السعر والاتجاه
    
    :param entry_price: سعر الدخول
    :param trend: الاتجاه المتوقع (up/down)
    :param klines_1h: بيانات شموع الإطار الزمني 1 ساعة لتحديد مستويات الدعم/المقاومة
    :param risk_reward_ratio: نسبة المكافأة إلى المخاطرة (الافتراضي: 2، بمعنى الربح المستهدف ضعف الخسارة المحتملة)
    :return: (مستوى أخذ الربح، مستوى وقف الخسارة)
    """
    # تحديد مستويات الدعم والمقاومة
    supports, resistances = find_support_resistance_levels(klines_1h)
    
    if trend == "up":
        # للصفقات الشرائية:
        # وقف الخسارة: تحت آخر مستوى دعم
        # أخذ الربح: عند مستوى المقاومة التالي
        
        # تحديد مستوى الدعم الأقرب تحت سعر الدخول
        closest_support = entry_price * 0.99  # قيمة افتراضية (1% تحت سعر الدخول)
        for support in sorted(supports, reverse=True):
            if support < entry_price:
                closest_support = support
                break
        
        # تحديد مستوى المقاومة الأقرب فوق سعر الدخول
        closest_resistance = entry_price * 1.03  # قيمة افتراضية (3% فوق سعر الدخول)
        for resistance in sorted(resistances):
            if resistance > entry_price:
                closest_resistance = resistance
                break
        
        # حساب المسافة إلى وقف الخسارة
        stop_loss_distance = entry_price - closest_support
        
        # تعديل مستوى أخذ الربح وفقًا لنسبة المكافأة/المخاطرة إذا كان مستوى المقاومة غير مناسب
        calculated_take_profit = entry_price + (stop_loss_distance * risk_reward_ratio)
        
        # استخدام القيمة الأعلى بين المستوى المحسوب ومستوى المقاومة المحدد
        take_profit = max(calculated_take_profit, closest_resistance)
        stop_loss = closest_support
        
    elif trend == "down":
        # للصفقات البيعية (وهذا نادر في استراتيجيتنا ولكن نضيفه للاكتمال):
        # وقف الخسارة: فوق آخر مستوى مقاومة
        # أخذ الربح: عند مستوى الدعم التالي
        
        # تحديد مستوى المقاومة الأقرب فوق سعر الدخول
        closest_resistance = entry_price * 1.01  # قيمة افتراضية (1% فوق سعر الدخول)
        for resistance in sorted(resistances):
            if resistance > entry_price:
                closest_resistance = resistance
                break
        
        # تحديد مستوى الدعم الأقرب تحت سعر الدخول
        closest_support = entry_price * 0.97  # قيمة افتراضية (3% تحت سعر الدخول)
        for support in sorted(supports, reverse=True):
            if support < entry_price:
                closest_support = support
                break
        
        # حساب المسافة إلى وقف الخسارة
        stop_loss_distance = closest_resistance - entry_price
        
        # تعديل مستوى أخذ الربح وفقًا لنسبة المكافأة/المخاطرة
        calculated_take_profit = entry_price - (stop_loss_distance * risk_reward_ratio)
        
        # استخدام القيمة الأدنى بين المستوى المحسوب ومستوى الدعم المحدد
        take_profit = min(calculated_take_profit, closest_support)
        stop_loss = closest_resistance
        
    else:
        # في حالة عدم وجود اتجاه واضح، نستخدم قيم افتراضية
        take_profit = entry_price * 1.03  # 3% ربح
        stop_loss = entry_price * 0.99  # 1% خسارة
    
    # تقريب القيم للحصول على أرقام أنظف
    take_profit = round(take_profit, 8)
    stop_loss = round(stop_loss, 8)
    
    return take_profit, stop_loss

def find_support_resistance_levels(klines, num_levels=5) -> Tuple[List[float], List[float]]:
    """
    تحديد مستويات الدعم والمقاومة من بيانات الشموع
    
    :param klines: بيانات الشموع
    :param num_levels: عدد المستويات المراد إرجاعها
    :return: قائمتان بمستويات الدعم والمقاومة
    """
    if not klines or len(klines) < 10:
        return [], []
    
    # استخراج القمم والقيعان
    highs = [float(k['high']) for k in klines]
    lows = [float(k['low']) for k in klines]
    
    # تحديد القمم المحلية
    local_maxima = []
    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            local_maxima.append(highs[i])
    
    # تحديد القيعان المحلية
    local_minima = []
    for i in range(1, len(lows) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            local_minima.append(lows[i])
    
    # دمج القمم والقيعان المتقاربة
    def merge_levels(levels, tolerance=0.005):
        if not levels:
            return []
        
        # فرز المستويات
        sorted_levels = sorted(levels)
        merged = []
        current_level = sorted_levels[0]
        current_count = 1
        
        for i in range(1, len(sorted_levels)):
            # حساب الفرق النسبي
            relative_diff = abs(sorted_levels[i] - current_level) / current_level
            
            if relative_diff <= tolerance:
                # دمج المستويات المتقاربة عن طريق حساب المتوسط
                current_level = ((current_level * current_count) + sorted_levels[i]) / (current_count + 1)
                current_count += 1
            else:
                merged.append(current_level)
                current_level = sorted_levels[i]
                current_count = 1
        
        merged.append(current_level)
        return merged
    
    # دمج المستويات المتقاربة
    resistance_levels = merge_levels(local_maxima)
    support_levels = merge_levels(local_minima)
    
    # ترتيب المستويات وأخذ أكثرها أهمية
    resistance_levels.sort(reverse=True)
    support_levels.sort()
    
    return support_levels[:num_levels], resistance_levels[:num_levels]