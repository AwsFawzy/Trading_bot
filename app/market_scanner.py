import logging
import time
import threading
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

# مخزن مؤقت للبيانات
symbols_cache = {}
prices_cache = {}
patterns_cache = {}

# حالة المسح
SCANNER_STATE = {
    'running': False,
    'thread': None,
    'last_scan': None,
    'opportunities': [],
    'watched_symbols': [],
    'interval': 300  # فترة المسح الافتراضية بالثواني
}

def scan_market():
    """
    فحص السوق للبحث عن فرص تداول ممتازة باستخدام تحليل تقني متقدم
    
    :return: قائمة الفرص المتاحة
    """
    from app.exchange_manager import get_exchange_symbols, get_current_price, get_historical_klines
    from app.config import CACHE_EXPIRY
    
    # التحقق مما إذا كانت البيانات محفوظة مؤقتًا
    cache_key = 'all_symbols'
    if cache_key in symbols_cache:
        cache_time, symbols = symbols_cache[cache_key]
        if time.time() - cache_time < CACHE_EXPIRY:
            all_symbols = symbols
        else:
            # البيانات قديمة، إعادة استرداد
            all_symbols = get_exchange_symbols() or []
            # تخزين في ذاكرة التخزين المؤقت
            symbols_cache[cache_key] = (time.time(), all_symbols)
    else:
        # البيانات غير متوفرة، استرداد جديد
        all_symbols = get_exchange_symbols() or []
        # تخزين في ذاكرة التخزين المؤقت
        symbols_cache[cache_key] = (time.time(), all_symbols)
    
    # فلترة الرموز - استبعاد الرموز غير الصالحة أو غير المدعومة
    from app.config import API_UNSUPPORTED_SYMBOLS, HIGH_VOLUME_SYMBOLS
    from app.mexc_api import get_ticker_info
    
    # التركيز حصرياً على العملات ذات التداول المرتفع
    priority_symbols = [s for s in HIGH_VOLUME_SYMBOLS if s in all_symbols]
    
    # الحصول على معلومات حجم التداول لهذه العملات
    symbols_with_volume = []
    for symbol in priority_symbols:
        try:
            ticker_info = get_ticker_info(symbol)
            if ticker_info and 'volume' in ticker_info:
                volume = float(ticker_info['volume']) * float(ticker_info['lastPrice'])
                # تحديد حد أدنى لحجم التداول (بالدولار) - 500,000 دولار يومياً
                if volume > 500000:  # التأكد من حجم تداول كبير (بالدولار)
                    symbols_with_volume.append({
                        'symbol': symbol,
                        'volume': volume
                    })
        except Exception as e:
            logger.error(f"خطأ في الحصول على معلومات حجم التداول لـ {symbol}: {e}")
    
    # ترتيب العملات بناءً على حجم التداول (الأعلى أولاً)
    symbols_with_volume = sorted(symbols_with_volume, key=lambda x: x['volume'], reverse=True)
    
    # استخراج الرموز فقط من القائمة المرتبة
    filtered_symbols = [item['symbol'] for item in symbols_with_volume]
    
    # إذا لم نجد عملات ذات حجم تداول كافٍ، استخدم قائمة HIGH_VOLUME_SYMBOLS كاملة
    if not filtered_symbols:
        filtered_symbols = priority_symbols
        logger.warning("لم يتم العثور على عملات ذات حجم تداول كافٍ، استخدام قائمة العملات ذات الأولوية كاملة")
    
    # الحد من عدد الرموز للتحليل - أداء أفضل
    from app.config import LIMIT_COINS_SCAN
    filtered_symbols = filtered_symbols[:LIMIT_COINS_SCAN]
    
    logger.info(f"تم اختيار {len(filtered_symbols)} رمز للتحليل، منها {len(priority_symbols)} عملة ذات أولوية عالية")
    
    opportunities = []
    
    for symbol in filtered_symbols:
        try:
            # الحصول على السعر الحالي
            current_price = get_current_price(symbol)
            if not current_price:
                continue
            
            # الحصول على البيانات التاريخية
            klines = get_historical_klines(symbol, "15m", limit=50)
            if not klines or len(klines) < 20:
                continue
            
            # استخراج أسعار الإغلاق
            close_prices = np.array([float(k[4]) for k in klines])
            
            # حساب المتوسطات المتحركة
            ma7 = np.mean(close_prices[-7:])
            ma25 = np.mean(close_prices[-25:])
            
            # حساب النطاقات (Bollinger Bands)
            std20 = np.std(close_prices[-20:])
            upper_band = ma25 + (std20 * 2)
            lower_band = ma25 - (std20 * 2)
            
            # حساب مؤشر القوة النسبية (RSI)
            delta = np.diff(close_prices)
            gain = delta.copy()
            loss = delta.copy()
            gain[gain < 0] = 0
            loss[loss > 0] = 0
            loss = abs(loss)
            
            avg_gain = np.mean(gain[-14:]) if len(gain) >= 14 else 0
            avg_loss = np.mean(loss[-14:]) if len(loss) >= 14 else 0
            
            rs = avg_gain / avg_loss if avg_loss != 0 else 0
            rsi = 100 - (100 / (1 + rs))
            
            # تحليل الفرص باستخدام المؤشرات الفنية
            potential_profit = 0
            reason = ""
            signals = 0
            
            # 1. تحقق من تقاطع المتوسطات (golden cross)
            if close_prices[-2] < ma7 and close_prices[-1] >= ma7:
                potential_profit += 0.01  # زيادة الربح المحتمل بنسبة 1%
                signals += 1
                reason += "تقاطع إيجابي للمتوسطات، "
            
            # 2. تحقق من مؤشر القوة النسبية (RSI)
            if 30 <= rsi <= 40:  # منطقة ذروة البيع المتوسطة
                potential_profit += 0.005
                signals += 1
                reason += "RSI في منطقة ذروة البيع، "
            elif rsi < 30:  # منطقة ذروة البيع القوية
                potential_profit += 0.01
                signals += 1
                reason += "RSI في منطقة ذروة البيع القوية، "
            
            # 3. تحقق من نطاقات بولينجر
            if float(current_price) <= lower_band:
                potential_profit += 0.015
                signals += 1
                reason += "السعر عند/أسفل النطاق السفلي لبولينجر، "
            
            # 4. تحقق من أنماط الشموع اليابانية
            if detect_hammer_pattern(klines[-5:]):
                potential_profit += 0.01
                signals += 1
                reason += "نمط المطرقة مكتشف، "
            
            # 5. تحقق من دعم/مقاومة
            key_levels = find_support_resistance(close_prices)
            nearest_support = find_nearest_level(float(current_price), key_levels['support'])
            if nearest_support and (float(current_price) / nearest_support - 1) < 0.02:
                potential_profit += 0.01
                signals += 1
                reason += "السعر قريب من مستوى دعم، "
            
            # تعديل الربح المحتمل بناءً على عدد الإشارات
            if signals >= 3:
                potential_profit *= 1.5  # تعزيز الفرص المؤكدة بعدة إشارات
            
            # تطبيق عامل احتمالية
            confidence_factor = min(signals / 5.0, 1.0)  # الحد الأقصى 5 إشارات = 100% ثقة
            
            # التأكد من أن هناك إشارة واحدة على الأقل
            if signals > 0:
                # إزالة الفاصلة الأخيرة من الأسباب
                if reason.endswith(", "):
                    reason = reason[:-2]
                
                opportunities.append({
                    'symbol': symbol,
                    'current_price': current_price,
                    'potential_profit': round(potential_profit, 4),
                    'signals': signals,
                    'confidence': round(confidence_factor, 2),
                    'reason': reason
                })
        except Exception as e:
            logger.error(f"خطأ في فحص {symbol}: {e}")
    
    # ترتيب الفرص حسب الربح المحتمل
    opportunities = sorted(opportunities, key=lambda x: x['potential_profit'] * x['confidence'], reverse=True)
    
    return opportunities[:10]  # إرجاع أفضل 10 فرص

def detect_hammer_pattern(candles):
    """
    اكتشاف نمط المطرقة في الشموع اليابانية
    
    :param candles: قائمة الشموع (OHLCV)
    :return: True إذا تم اكتشاف النمط، False خلاف ذلك
    """
    if not candles or len(candles) < 3:
        return False
    
    # نمط المطرقة يظهر عادة في نهاية الترند الهابط
    # التحقق من وجود ترند هابط
    downtrend = True
    for i in range(len(candles) - 3):
        if float(candles[i][4]) <= float(candles[i+1][4]):  # مقارنة أسعار الإغلاق
            downtrend = False
            break
    
    if not downtrend:
        return False
    
    # التحقق من آخر شمعة للنمط
    last_candle = candles[-1]
    open_price = float(last_candle[1])
    high_price = float(last_candle[2])
    low_price = float(last_candle[3])
    close_price = float(last_candle[4])
    
    body_size = abs(open_price - close_price)
    total_range = high_price - low_price
    
    if total_range == 0:  # تجنب القسمة على صفر
        return False
    
    lower_shadow = min(open_price, close_price) - low_price
    upper_shadow = high_price - max(open_price, close_price)
    
    # شروط نمط المطرقة:
    # 1. الظل السفلي طويل (على الأقل ضعف حجم الجسم)
    # 2. الجسم صغير نسبياً
    # 3. الظل العلوي قصير أو غير موجود
    
    if (lower_shadow / total_range > 0.6 and 
        body_size / total_range < 0.3 and 
        upper_shadow / total_range < 0.1):
        return True
    
    return False

def find_support_resistance(prices, window=20):
    """
    العثور على مستويات الدعم والمقاومة من بيانات الأسعار
    
    :param prices: مصفوفة الأسعار
    :param window: حجم النافذة للبحث عن القمم والقيعان
    :return: قاموس يحتوي على قوائم مستويات الدعم والمقاومة
    """
    supports = []
    resistances = []
    
    # نحتاج إلى عدد كافٍ من النقاط للتحليل
    if len(prices) < window * 2:
        return {'support': supports, 'resistance': resistances}
    
    # البحث عن القمم والقيعان المحلية
    for i in range(window, len(prices) - window):
        # التحقق من القاع المحتمل (دعم)
        if all(prices[i] <= prices[i-j] for j in range(1, window//2+1)) and \
           all(prices[i] <= prices[i+j] for j in range(1, window//2+1)):
            supports.append(prices[i])
        
        # التحقق من القمة المحتملة (مقاومة)
        if all(prices[i] >= prices[i-j] for j in range(1, window//2+1)) and \
           all(prices[i] >= prices[i+j] for j in range(1, window//2+1)):
            resistances.append(prices[i])
    
    # إضافة السعر الحالي
    current_price = prices[-1]
    
    # فلترة المستويات لإزالة المتكررة
    filtered_supports = []
    filtered_resistances = []
    
    # التجميع بناءً على التقارب
    threshold = 0.01  # 1% تقارب
    
    for level in supports:
        # تخطي المستويات البعيدة جداً من السعر الحالي
        if abs(level / current_price - 1) > 0.2:  # 20% بعيد عن السعر الحالي
            continue
        
        # البحث عن مستويات قريبة
        found_similar = False
        for i, existing in enumerate(filtered_supports):
            if abs(level / existing - 1) < threshold:
                # تحديث المستوى بالمتوسط
                filtered_supports[i] = (existing + level) / 2
                found_similar = True
                break
        
        if not found_similar:
            filtered_supports.append(level)
    
    for level in resistances:
        # تخطي المستويات البعيدة جداً من السعر الحالي
        if abs(level / current_price - 1) > 0.2:  # 20% بعيد عن السعر الحالي
            continue
        
        # البحث عن مستويات قريبة
        found_similar = False
        for i, existing in enumerate(filtered_resistances):
            if abs(level / existing - 1) < threshold:
                # تحديث المستوى بالمتوسط
                filtered_resistances[i] = (existing + level) / 2
                found_similar = True
                break
        
        if not found_similar:
            filtered_resistances.append(level)
    
    # ترتيب المستويات
    filtered_supports.sort()
    filtered_resistances.sort()
    
    return {'support': filtered_supports, 'resistance': filtered_resistances}

def find_nearest_level(price, levels):
    """
    العثور على أقرب مستوى دعم/مقاومة للسعر الحالي
    
    :param price: السعر الحالي
    :param levels: قائمة المستويات
    :return: أقرب مستوى أو None إذا كانت القائمة فارغة
    """
    if not levels:
        return None
    
    # التركيز على المستويات تحت السعر الحالي (للدعم)
    below_levels = [level for level in levels if level < price]
    
    if not below_levels:
        return None
    
    # إرجاع أعلى مستوى تحت السعر الحالي
    return max(below_levels)


def start_market_scanner(interval=300):
    """
    بدء تشغيل مسح السوق الدوري
    
    :param interval: الفاصل الزمني بين عمليات المسح (بالثواني)
    :return: True إذا تم البدء بنجاح، False خلاف ذلك
    """
    global SCANNER_STATE
    
    # التحقق مما إذا كان المسح قيد التشغيل بالفعل
    if SCANNER_STATE['running']:
        logger.info("مسح السوق قيد التشغيل بالفعل")
        return True
    
    # تخزين الفاصل الزمني
    SCANNER_STATE['interval'] = interval
    
    # تحديث حالة التشغيل
    SCANNER_STATE['running'] = True
    
    # بدء خيط جديد لمسح السوق
    def scanner_thread():
        logger.info(f"بدء تشغيل مسح السوق كل {interval} ثانية")
        
        while SCANNER_STATE['running']:
            try:
                # تنفيذ عملية المسح
                opportunities = scan_market()
                
                # تحديث الفرص المتاحة
                SCANNER_STATE['opportunities'] = opportunities
                
                # تحديث وقت آخر مسح
                SCANNER_STATE['last_scan'] = datetime.now()
                
                # تحديث العملات المراقبة
                if opportunities:
                    watched = [opp['symbol'] for opp in opportunities]
                    SCANNER_STATE['watched_symbols'] = watched
                
                logger.info(f"تم العثور على {len(opportunities)} فرصة في عملية المسح الحالية")
            except Exception as e:
                logger.error(f"خطأ أثناء مسح السوق: {e}")
            
            # انتظار الفاصل الزمني المحدد
            time.sleep(interval)
    
    # تشغيل الخيط
    SCANNER_STATE['thread'] = threading.Thread(target=scanner_thread, daemon=True)
    SCANNER_STATE['thread'].start()
    
    logger.info("تم بدء تشغيل مسح السوق بنجاح")
    return True

def stop_market_scanner():
    """
    إيقاف مسح السوق
    
    :return: True إذا تم الإيقاف بنجاح، False خلاف ذلك
    """
    global SCANNER_STATE
    
    # التحقق مما إذا كان المسح قيد التشغيل
    if not SCANNER_STATE['running']:
        logger.info("مسح السوق متوقف بالفعل")
        return True
    
    # تحديث حالة التشغيل
    SCANNER_STATE['running'] = False
    
    # إذا كان هناك خيط تشغيل، انتظر انتهائه
    if SCANNER_STATE['thread'] and SCANNER_STATE['thread'].is_alive():
        # مهلة الانتظار (5 ثواني كحد أقصى)
        SCANNER_STATE['thread'].join(5)
    
    # إعادة تعيين حالة الخيط
    SCANNER_STATE['thread'] = None
    
    logger.info("تم إيقاف مسح السوق بنجاح")
    return True

def get_trading_opportunities():
    """
    الحصول على فرص التداول الحالية
    
    :return: قائمة الفرص
    """
    global SCANNER_STATE
    
    # إذا لم يكن هناك فرص متاحة، قم بمسح فوري
    if not SCANNER_STATE['opportunities']:
        try:
            opportunities = scan_market()
            SCANNER_STATE['opportunities'] = opportunities
            SCANNER_STATE['last_scan'] = datetime.now()
            
            # تحديث العملات المراقبة
            if opportunities:
                watched = [opp['symbol'] for opp in opportunities]
                SCANNER_STATE['watched_symbols'] = watched
        except Exception as e:
            logger.error(f"خطأ أثناء مسح فوري للسوق: {e}")
    
    return SCANNER_STATE['opportunities']

def get_watched_symbols():
    """
    الحصول على قائمة العملات المراقبة
    
    :return: قائمة العملات المراقبة
    """
    global SCANNER_STATE
    
    # إذا لم يكن هناك عملات مراقبة، حاول الحصول على بعضها
    if not SCANNER_STATE['watched_symbols']:
        opportunities = get_trading_opportunities()
        if opportunities:
            SCANNER_STATE['watched_symbols'] = [opp['symbol'] for opp in opportunities]
    
    return SCANNER_STATE['watched_symbols']

def get_symbol_analysis(symbol):
    """
    الحصول على تحليل مفصل لعملة محددة
    
    :param symbol: رمز العملة
    :return: تحليل العملة
    """
    # الحصول على البيانات التاريخية
    from app.exchange_manager import get_historical_klines, get_current_price
    
    # التحقق من وجود العملة
    current_price = get_current_price(symbol)
    if not current_price:
        return {"error": f"لم يتم العثور على عملة بالرمز {symbol}"}
    
    # الحصول على البيانات التاريخية
    klines_15m = get_historical_klines(symbol, "15m", limit=50)
    klines_1h = get_historical_klines(symbol, "1h", limit=24)
    klines_4h = get_historical_klines(symbol, "4h", limit=30)
    
    if not klines_15m or not klines_1h or not klines_4h:
        return {"error": f"لا توجد بيانات تاريخية كافية للعملة {symbol}"}
    
    # استخراج أسعار الإغلاق
    close_prices_15m = np.array([float(k[4]) for k in klines_15m])
    close_prices_1h = np.array([float(k[4]) for k in klines_1h])
    close_prices_4h = np.array([float(k[4]) for k in klines_4h])
    
    # حساب المتوسطات المتحركة
    ma7_15m = np.mean(close_prices_15m[-7:])
    ma25_15m = np.mean(close_prices_15m[-25:])
    
    ma7_1h = np.mean(close_prices_1h[-7:])
    ma25_1h = np.mean(close_prices_1h[-25:])
    
    ma7_4h = np.mean(close_prices_4h[-7:])
    ma25_4h = np.mean(close_prices_4h[-25:])
    
    # حساب النطاقات (Bollinger Bands)
    std20_15m = np.std(close_prices_15m[-20:])
    upper_band_15m = ma25_15m + (std20_15m * 2)
    lower_band_15m = ma25_15m - (std20_15m * 2)
    
    # حساب مؤشر القوة النسبية (RSI)
    delta_15m = np.diff(close_prices_15m)
    gain_15m = delta_15m.copy()
    loss_15m = delta_15m.copy()
    gain_15m[gain_15m < 0] = 0
    loss_15m[loss_15m > 0] = 0
    loss_15m = abs(loss_15m)
    
    avg_gain_15m = np.mean(gain_15m[-14:]) if len(gain_15m) >= 14 else 0
    avg_loss_15m = np.mean(loss_15m[-14:]) if len(loss_15m) >= 14 else 0
    
    rs_15m = avg_gain_15m / avg_loss_15m if avg_loss_15m != 0 else 0
    rsi_15m = 100 - (100 / (1 + rs_15m))
    
    # تحديد مستويات الدعم والمقاومة
    support_resistance = find_support_resistance(close_prices_15m)
    
    # تحديد الاتجاه العام
    trend = "غير محدد"
    if close_prices_4h[-1] > ma7_4h > ma25_4h:
        trend = "صاعد قوي"
    elif ma7_4h > close_prices_4h[-1] > ma25_4h:
        trend = "صاعد متوسط"
    elif ma7_4h > ma25_4h > close_prices_4h[-1]:
        trend = "هابط ضعيف"
    elif close_prices_4h[-1] < ma7_4h < ma25_4h:
        trend = "هابط قوي"
    elif ma7_4h < close_prices_4h[-1] < ma25_4h:
        trend = "هابط متوسط"
    elif ma7_4h < ma25_4h < close_prices_4h[-1]:
        trend = "صاعد ضعيف"
    else:
        trend = "حركة جانبية"
    
    # تحليل الفرص
    reasons = []
    signals = 0
    potential_profit = 0
    
    # 1. تحقق من تقاطع المتوسطات (golden cross)
    if close_prices_15m[-2] < ma7_15m and close_prices_15m[-1] >= ma7_15m:
        potential_profit += 0.01
        signals += 1
        reasons.append("تقاطع إيجابي للمتوسطات")
    
    # 2. تحقق من مؤشر القوة النسبية (RSI)
    if 30 <= rsi_15m <= 40:
        potential_profit += 0.005
        signals += 1
        reasons.append("RSI في منطقة ذروة البيع")
    elif rsi_15m < 30:
        potential_profit += 0.01
        signals += 1
        reasons.append("RSI في منطقة ذروة البيع القوية")
    
    # 3. تحقق من نطاقات بولينجر
    if float(current_price) <= lower_band_15m:
        potential_profit += 0.015
        signals += 1
        reasons.append("السعر عند/أسفل النطاق السفلي لبولينجر")
    
    # 4. تحقق من أنماط الشموع اليابانية
    if detect_hammer_pattern(klines_15m[-5:]):
        potential_profit += 0.01
        signals += 1
        reasons.append("نمط المطرقة مكتشف")
    
    # 5. تحقق من دعم/مقاومة
    nearest_support = find_nearest_level(float(current_price), support_resistance['support'])
    if nearest_support and (float(current_price) / nearest_support - 1) < 0.02:
        potential_profit += 0.01
        signals += 1
        reasons.append("السعر قريب من مستوى دعم")
    
    # تعديل الربح المحتمل بناءً على عدد الإشارات
    if signals >= 3:
        potential_profit *= 1.5
    
    # تصنيف الفرصة
    rating = "ضعيفة"
    if signals >= 4:
        rating = "ممتازة"
    elif signals >= 3:
        rating = "جيدة جداً"
    elif signals >= 2:
        rating = "جيدة"
    elif signals >= 1:
        rating = "متوسطة"
    
    # تجميع التحليل
    analysis = {
        "symbol": symbol,
        "current_price": float(current_price),
        "trend": trend,
        "rsi": round(rsi_15m, 2),
        "bollinger_bands": {
            "upper": round(upper_band_15m, 6),
            "middle": round(ma25_15m, 6),
            "lower": round(lower_band_15m, 6)
        },
        "moving_averages": {
            "15m": {
                "ma7": round(ma7_15m, 6),
                "ma25": round(ma25_15m, 6)
            },
            "1h": {
                "ma7": round(ma7_1h, 6),
                "ma25": round(ma25_1h, 6)
            },
            "4h": {
                "ma7": round(ma7_4h, 6),
                "ma25": round(ma25_4h, 6)
            }
        },
        "opportunity": {
            "rating": rating,
            "signals": signals,
            "potential_profit": round(potential_profit * 100, 2),
            "reasons": reasons
        },
        "support_resistance": {
            "support_levels": [round(s, 6) for s in support_resistance['support'][:3]],
            "resistance_levels": [round(r, 6) for r in support_resistance['resistance'][:3]]
        }
    }
    
    return analysis