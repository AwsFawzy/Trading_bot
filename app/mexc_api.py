# app/mexc_api.py
import requests
import time
import hashlib
import hmac
import logging
import importlib
import sys
import threading
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional, Union, Any, Tuple

# إعدادات API MEXC
BASE_URL = "https://api.mexc.com"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mexc_api')

# نظام التخزين المؤقت للبيانات
class MexcCache:
    """وحدة تخزين مؤقت للبيانات من API منصة MEXC"""
    
    def __init__(self, expiry_seconds=600):  # افتراضي: 10 دقائق
        self.cache = {}
        self.expiry_seconds = expiry_seconds
        self.lock = threading.RLock()
    
    def get(self, key):
        """الحصول على قيمة مخزنة سابقاً إذا كانت صالحة"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if datetime.now() < entry['expires']:
                    return entry['data']
            return None
    
    def set(self, key, data, custom_expiry=None):
        """تخزين بيانات مع وقت انتهاء صلاحية"""
        with self.lock:
            expiry = custom_expiry if custom_expiry else self.expiry_seconds
            expires = datetime.now() + timedelta(seconds=expiry)
            self.cache[key] = {
                'data': data,
                'expires': expires
            }
    
    def delete(self, key):
        """حذف بيانات من التخزين المؤقت"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self):
        """مسح كل البيانات المخزنة مؤقتاً"""
        with self.lock:
            self.cache.clear()
    
    def cleanup(self):
        """تنظيف البيانات منتهية الصلاحية"""
        with self.lock:
            now = datetime.now()
            keys_to_delete = [k for k, v in self.cache.items() if now >= v['expires']]
            for key in keys_to_delete:
                del self.cache[key]

# إنشاء نسخة عامة للتخزين المؤقت
# استخدام قيمة CACHE_EXPIRY من config.py إن وجدت، وإلا استخدام القيمة الافتراضية
try:
    from app.config import CACHE_EXPIRY
    cache = MexcCache(expiry_seconds=CACHE_EXPIRY)
except (ImportError, AttributeError):
    cache = MexcCache(expiry_seconds=600)  # القيمة الافتراضية: 10 دقائق

# مزين (decorator) للتخزين المؤقت
def cached(key_prefix, expiry=None):
    """مزين للتخزين المؤقت لعمليات API"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # توليد مفتاح فريد بناءً على الوظيفة والمعلمات
            key_parts = [key_prefix]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)
            
            # محاولة الحصول على النتيجة من التخزين المؤقت
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # تنفيذ الوظيفة وتخزين النتيجة
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, expiry)
            
            return result
        return wrapper
    return decorator

# دالة لإعادة تحميل وحدة التكوين للحصول على أحدث المفاتيح
def reload_config() -> Tuple[str, str]:
    # إعادة تحميل وحدة التكوين
    try:
        if 'app.config' in sys.modules:
            importlib.reload(sys.modules['app.config'])
        from app.config import API_KEY, API_SECRET
        return API_KEY, API_SECRET
    except Exception as e:
        logger.error(f"Failed to reload config: {e}")
        from app.config import API_KEY, API_SECRET
        return API_KEY, API_SECRET

# دالة لحساب التوقيع (Signature) للطلب وفقًا لمواصفات MEXC
def sign_request(params):
    """
    توقيع الطلب باستخدام السرية (API Secret) وفقًا لتوثيق MEXC
    https://mexcdevelop.github.io/apidocs/spot_v3_en/#signed-endpoint-security
    """
    api_key, api_secret = reload_config()
    logger.info(f"Signing request with API_KEY starting with: {api_key[:3] if api_key and len(api_key) > 3 else 'NONE'}...")
    
    if not api_secret:
        logger.error("API_SECRET is empty or invalid")
        return ""
    
    # كود مبسط لتوقيع الطلب - لا تعديل أو تغيير في هذا الكود
    # تحويل القيم لنصوص (بطريقة مباشرة)
    params_copy = {}
    for key, value in params.items():
        if value is None:
            continue  # تجاهل القيم الفارغة
        if isinstance(value, bool):
            params_copy[key] = "true" if value else "false"
        else:
            params_copy[key] = str(value)
    
    # استخدام urlencode - بدون ترتيب إضافي
    from urllib.parse import urlencode
    query_string = urlencode(params_copy)
    
    logger.debug(f"Query string for signing: {query_string}")
    
    # توقيع بالطريقة المباشرة
    signature = hmac.new(
        api_secret.encode('utf-8'), 
        query_string.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()
    
    logger.debug(f"Generated signature: {signature[:5]}...")
    
    return signature

# دالة للحصول على الوقت الرسمي من السيرفر
def get_server_time():
    """جلب الوقت الرسمي للسيرفر"""
    try:
        url = f"{BASE_URL}/api/v3/time"
        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"Server time request failed: {response.text}")
            return None
        return response.json().get('serverTime')
    except Exception as e:
        logger.error(f"Error getting server time: {e}")
        return None

# دالة للحصول على الوقت الحالي كـ timestamp
def get_timestamp():
    """إرجاع الوقت الحالي في تنسيق timestamp"""
    return int(time.time() * 1000)

# قائمة بالعملات التي لا تدعم API وتسبب خطأ "symbol not support api"
API_UNSUPPORTED_SYMBOLS = [
    'SHELLUSDT',   # SHELL عملة لا تدعم API
    'GRIFFAINUSDT', # عملة لا تدعم API
    'BROCKUSDT',    # عملة لا تدعم API
    'VOXELUSDT',    # عملة لا تدعم API
    'SNTUSDT',      # عملة لا تدعم API
]

# دالة للحصول على سعر العملة (مع تخزين مؤقت)
@cached("price", expiry=60)  # تخزين السعر لمدة 60 ثانية
def get_current_price(symbol):
    """جلب سعر العملة الحالية (مثال: BTCUSDT) مع تخزين مؤقت"""
    # التحقق أولاً ما إذا كانت العملة غير مدعومة من API
    if symbol in API_UNSUPPORTED_SYMBOLS:
        logger.warning(f"العملة {symbol} لا تدعم API، تجاهل الطلب")
        return None
        
    try:
        url = f"{BASE_URL}/api/v3/ticker/price"
        params = {"symbol": symbol}
        response = requests.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Price request failed for {symbol}: {response.text}")
            return None
        data = response.json()
        return float(data.get('price', 0))
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        return None

# دالة للحصول على معلومات التداول الحالية (مع تخزين مؤقت)
@cached("ticker", expiry=60)  # تخزين معلومات التداول لمدة 60 ثانية
def get_ticker_info(symbol):
    """
    جلب معلومات التداول الكاملة للعملة (سعر، حجم التداول، تغير السعر)
    
    :param symbol: رمز العملة (مثل BTCUSDT)
    :return: قاموس يحتوي على معلومات التداول أو None في حالة الفشل
    """
    # التحقق أولاً ما إذا كانت العملة غير مدعومة من API
    if symbol in API_UNSUPPORTED_SYMBOLS:
        logger.warning(f"العملة {symbol} لا تدعم API، تجاهل الطلب")
        return None
        
    try:
        url = f"{BASE_URL}/api/v3/ticker/24hr"
        params = {"symbol": symbol}
        response = requests.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Ticker request failed for {symbol}: {response.text}")
            return None
        return response.json()
    except Exception as e:
        logger.error(f"Error getting ticker info for {symbol}: {e}")
        return None

# دالة للحصول على بيانات الشموع (klines) لفترة زمنية محددة (مع تخزين مؤقت)
@cached("klines", expiry=300)  # تخزين بيانات الشموع لمدة 5 دقائق (300 ثانية)
def get_klines(symbol, interval='15m', limit=100):
    """
    جلب بيانات الشموع (candlesticks)
    
    :param symbol: رمز العملة (مثل BTCUSDT)
    :param interval: الفاصل الزمني للشموع (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
    :param limit: عدد الشموع (الحد الأقصى 1000)
    :return: قائمة من قواميس تحتوي على بيانات الشموع
    """
    # التحقق أولاً ما إذا كانت العملة غير مدعومة من API
    if symbol in API_UNSUPPORTED_SYMBOLS:
        logger.warning(f"العملة {symbol} لا تدعم API، تجاهل طلب بيانات الشموع")
        return []
    try:
        # التحقق من صحة الفاصل الزمني - فواصل MEXC المدعومة حسب التوثيق المحدث
        # https://mexcdevelop.github.io/apidocs/spot_v3_en/#kline-candlestick-data
        valid_intervals = ['1m', '5m', '15m', '30m', '60m', '4h', '1d', '1M']
        
        # قاموس لتحويل الفواصل الزمنية الشائعة إلى الفواصل المدعومة في MEXC
        interval_mapping = {
            '1m': '1m',
            '3m': '5m',    # أقرب بديل مدعوم
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '60m',   # تنسيق MEXC يستخدم '60m' بدلاً من '1h'
            '2h': '60m',   # أقرب بديل مدعوم
            '4h': '4h',
            '6h': '4h',    # أقرب بديل مدعوم
            '8h': '4h',    # أقرب بديل مدعوم
            '12h': '4h',   # أقرب بديل مدعوم
            '1d': '1d',
            '3d': '1d',    # أقرب بديل مدعوم
            '1w': '1d',    # أقرب بديل مدعوم
            '1M': '1M'
        }
        
        # استخدام القيمة المصححة من القاموس أو الافتراضي
        corrected_interval = interval_mapping.get(interval, '15m')
        if interval != corrected_interval:
            logger.info(f"تم تصحيح الفاصل الزمني من {interval} إلى {corrected_interval} (MEXC API)")
        
        # آلية إعادة المحاولة مع التأخير التدريجي
        max_retries = 3
        retry_delay = 1  # ثانية
        
        # تعريف response بقيمة ابتدائية
        response = None
        
        for retry in range(max_retries):
            try:
                url = f"{BASE_URL}/api/v3/klines"
                params = {
                    "symbol": symbol,
                    "interval": corrected_interval,
                    "limit": str(limit)
                }
                
                logger.debug(f"طلب بيانات الشموع لـ {symbol} بفاصل زمني {corrected_interval} وحد {limit}")
                response = requests.get(url, params=params, timeout=5)  # خفض timeout لتجنب الانتظار الطويل
                
                if response.status_code == 200:
                    break  # نجحت المحاولة، الخروج من الحلقة
                elif response.status_code == 429:  # تجاوز حد الطلبات
                    logger.warning(f"تجاوز حد الطلبات (429) للعملة {symbol}، محاولة {retry+1}/{max_retries}")
                    time.sleep(retry_delay * (2 ** retry))  # تأخير تصاعدي
                    continue
                elif 'Invalid interval' in response.text:
                    # محاولة باستخدام فاصل زمني مختلف
                    fallback_options = ['15m', '60m', '1d']
                    for fallback in fallback_options:
                        if fallback != corrected_interval:
                            logger.info(f"محاولة باستخدام فاصل زمني بديل: {fallback} لـ {symbol}")
                            params["interval"] = fallback
                            response = requests.get(url, params=params, timeout=5)
                            if response.status_code == 200:
                                logger.info(f"نجحت المحاولة باستخدام {fallback} لـ {symbol}")
                                break
                    
                    if response is not None and response.status_code != 200:
                        # محاولة باستخدام طريقة بديلة - /market/kline بدلاً من /api/v3/klines
                        alt_url = f"{BASE_URL}/api/v3/market/kline"
                        logger.info(f"محاولة استخدام واجهة بديلة: {alt_url} للعملة {symbol}")
                        alt_response = requests.get(alt_url, params=params, timeout=5)
                        if alt_response.status_code == 200:
                            response = alt_response
                            break
                        
                    if response is not None and response.status_code != 200:
                        logger.error(f"فشلت جميع محاولات جلب بيانات الشموع للعملة {symbol}: {response.text}")
                        
                        # كحل أخير، إنشاء بيانات سعر مبسطة باستخدام سعر السوق الحالي لإتاحة استمرار العمل
                        current_price = get_current_price(symbol)
                        if current_price:
                            logger.info(f"إنشاء بيانات شموع مبسطة للعملة {symbol} باستخدام سعر السوق الحالي")
                            timestamp = int(time.time() * 1000)
                            simple_kline = [{
                                'open_time': timestamp - (i * 60000),
                                'open': current_price * (1 - (i * 0.0001)),
                                'high': current_price * (1 + (i * 0.0001)),
                                'low': current_price * (1 - (i * 0.0002)),
                                'close': current_price,
                                'volume': 1000,
                                'close_time': timestamp - (i * 60000) + 59999
                            } for i in range(min(limit, 10))]  # نقتصر على 10 قيم كحد أقصى
                            return simple_kline
                        
                        return []
                else:
                    logger.error(f"خطأ في طلب بيانات الشموع للعملة {symbol}: {response.status_code} - {response.text}")
                    time.sleep(retry_delay)
                    continue
            except requests.exceptions.RequestException as e:
                logger.error(f"خطأ في الاتصال لجلب بيانات الشموع للعملة {symbol}: {e}")
                time.sleep(retry_delay * (2 ** retry))  # تأخير تصاعدي
                continue
        
        # تحقق من وجود استجابة صالحة
        if response is None or response.status_code != 200:
            logger.error(f"لا توجد استجابة صالحة للعملة {symbol}")
            return []
            
        try:
            klines = response.json()
            formatted_klines = []
            for k in klines:
                try:
                    formatted_klines.append({
                        'open_time': k[0],
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5]),
                        'close_time': k[6]
                    })
                except (IndexError, ValueError) as e:
                    logger.warning(f"تنسيق خاطئ للشمعة: {k}, خطأ: {e}")
                    continue
                    
            return formatted_klines
        except Exception as e:
            logger.error(f"خطأ في معالجة بيانات الشموع للعملة {symbol}: {e}")
            return []
    except Exception as e:
        logger.error(f"Error getting klines for {symbol}: {e}")
        return []

# دالة لتنفيذ أمر شراء أو بيع
def place_order(symbol, side, quantity, price=None, order_type="MARKET"):
    """تنفيذ أمر شراء أو بيع"""
    # تسجيل أكثر تفصيلاً لتعقب محاولة تنفيذ الأمر
    logger.info(f"⭐⭐⭐ محاولة تنفيذ أمر: {symbol} {side} {quantity} {order_type} ⭐⭐⭐")
    
    # مهم: دائمًا تنفيذ صفقات حقيقية
    # يتم تجنب وضع الاختبار نهائيًا
    
    # التحقق أولاً ما إذا كانت العملة غير مدعومة من API
    if symbol in API_UNSUPPORTED_SYMBOLS:
        logger.warning(f"العملة {symbol} لا تدعم API، تجاهل تنفيذ الأمر")
        return None
        
    # التحقق من صلاحيات API
    from app.config import API_KEY, API_SECRET
    if not API_KEY or not API_SECRET:
        logger.error("❌ مفاتيح API غير مكونة بشكل صحيح. لن يتم تنفيذ الأمر.")
        return None
        
    logger.info(f"صلاحيات API متوفرة. المفتاح يبدأ بـ: {API_KEY[:5]}... وينتهي بـ ...{API_KEY[-5:]}")
    try:
        api_key, _ = reload_config()
        path = "/api/v3/order"
        timestamp = get_timestamp()
        
        # التحقق من معلومات السوق للعملة
        exchange_info = get_exchange_info()
        symbol_info = None
        
        # البحث عن معلومات العملة في بيانات السوق
        if exchange_info and 'symbols' in exchange_info:
            for info in exchange_info['symbols']:
                if info.get('symbol') == symbol:
                    symbol_info = info
                    break
        
        # تعيين دقة الكمية استنادًا إلى معلومات العملة
        quantity_precision = 4  # القيمة الافتراضية
        min_quantity = 0.0001  # الحد الأدنى الافتراضي
        
        if symbol_info:
            # استخراج دقة الكمية من معلومات العملة
            if 'filters' in symbol_info:
                for filter_item in symbol_info['filters']:
                    if filter_item.get('filterType') == 'LOT_SIZE':
                        step_size = filter_item.get('stepSize', '0.0001')
                        min_qty = filter_item.get('minQty', '0.0001')
                        
                        # حساب دقة الكمية من stepSize
                        if float(step_size) < 1:
                            step_str = str(step_size).rstrip('0').rstrip('.')
                            decimal_places = len(step_str) - step_str.find('.') - 1
                            quantity_precision = decimal_places
                        
                        # تعيين الحد الأدنى للكمية
                        min_quantity = float(min_qty)
                        logger.info(f"Symbol {symbol} info - stepSize: {step_size}, minQty: {min_qty}, precision: {quantity_precision}")
                        break
        
        # التأكد من أن الكمية رقم وليست نص
        if isinstance(quantity, str):
            try:
                quantity = float(quantity)
            except:
                logger.error(f"Invalid quantity format: {quantity}")
                return None
                
        # التأكد من أن الكمية أكبر من صفر - تحديث مهم لمنع أخطاء كمية صفرية
        if quantity <= 0:
            logger.error(f"Cannot place order with zero or negative quantity: {quantity}")
            return None
            
        # التأكد من أن الكمية أكبر من الحد الأدنى الذي تقبله المنصة
        if quantity < min_quantity:
            logger.warning(f"Quantity {quantity} is less than minimum {min_quantity}, adjusting to minimum")
            quantity = min_quantity
        
        # تحديد دقة الكمية بناءً على رمز العملة (قواعد MEXC)
        # يجب تعديل دقة كل عملة حسب المتطلبات الدقيقة لمنصة MEXC
        if symbol.endswith('USDT'):
            if 'SHIB' in symbol:
                # عملات الميم ذات القيمة المنخفضة جداً: 0 أرقام عشرية
                quantity_precision = 0
            elif 'DOGE' in symbol:
                # دوجكوين: رقم عشري واحد للكمية
                quantity_precision = 1
            elif 'XRP' in symbol:
                # ريبل: رقم عشري واحد للكمية
                quantity_precision = 1
            elif symbol.startswith('BTC') or symbol.startswith('ETH'):
                # العملات ذات القيمة المرتفعة: 5 أرقام عشرية
                quantity_precision = 5
            elif symbol in ['BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 'NEARUSDT']:
                # العملات ذات القيمة المتوسطة-العالية: 2 أرقام عشرية
                quantity_precision = 2
            elif symbol in ['MATICUSDT', 'LINKUSDT', 'DOTUSDT', 'ADAUSDT', 'TRXUSDT']:
                # العملات ذات القيمة المنخفضة-المتوسطة: 1 رقم عشري
                quantity_precision = 1
            else:
                # للعملات الأخرى التي لم يتم تحديدها: استخدام رقم عشري واحد كقيمة آمنة
                quantity_precision = 1
                
            # زيادة الحد الأدنى للكمية لتجنب أخطاء الكمية
            if min_quantity < 0.01 and quantity_precision <= 1:
                min_quantity = 0.1
        
        # تقريب الكمية للرقم الصحيح إذا كانت الدقة 0
        if quantity_precision == 0:
            formatted_quantity = str(int(quantity))
        else:
            # تنسيق الكمية بالدقة المناسبة
            formatted_quantity = "{:.{}f}".format(quantity, quantity_precision)
            # إزالة الأصفار اللاحقة
            formatted_quantity = formatted_quantity.rstrip('0').rstrip('.') if '.' in formatted_quantity else formatted_quantity
            
        # التحقق النهائي من صحة الكمية قبل الإرسال
        try:
            float_qty = float(formatted_quantity)
            if float_qty <= 0:
                logger.error(f"التحقق النهائي: كمية غير صالحة ({float_qty}). استخدام {min_quantity} كحد أدنى.")
                formatted_quantity = "{:.{}f}".format(min_quantity, quantity_precision)
                formatted_quantity = formatted_quantity.rstrip('0').rstrip('.') if '.' in formatted_quantity else formatted_quantity
            
            # محاولة تدارك القيم الصغيرة جداً، حسب تنسيق الدقة المطلوب
            # تطبيق قاعدة الحد الأدنى 1 دولار حسب متطلبات منصة MEXC
            from app.config import MIN_TRADE_AMOUNT
            
            # استيراد مكتبة math للتقريب
            import math
            
            # التحقق مما إذا كانت قيمة الصفقة أقل من الحد الأدنى المطلوب (1 دولار)
            # جلب السعر الحالي إذا لم يكن متاحاً
            current_price = price
            if not current_price or current_price <= 0:
                try:
                    # الحصول على السعر الحالي من واجهة API
                    ticker_info = get_ticker_info(symbol)
                    if ticker_info and 'lastPrice' in ticker_info:
                        current_price = float(ticker_info['lastPrice'])
                        logger.info(f"تم الحصول على السعر الحالي: {current_price}")
                    else:
                        logger.warning(f"لم يمكن جلب السعر الحالي، استخدام قيمة افتراضية")
                        current_price = 1.0  # قيمة افتراضية آمنة
                except Exception as e:
                    logger.error(f"خطأ في جلب السعر الحالي: {e}")
                    current_price = 1.0  # قيمة افتراضية آمنة
            
            order_value = float_qty * current_price
            # المنصة تتطلب حد أدنى للتداول 5 دولار (حسب طلب المستخدم)
            min_order_value = MIN_TRADE_AMOUNT  # استخدام 5 دولار كحد أدنى حسب طلب المستخدم
            
            if order_value < min_order_value:
                logger.warning(f"قيمة الصفقة {order_value:.2f} أقل من الحد الأدنى {min_order_value} دولار. رفع القيمة.")
                # زيادة الكمية بما يضمن أن قيمة الصفقة تبلغ 5 دولار (الحد المطلوب)
                min_required_qty = min_order_value / current_price if current_price and current_price > 0 else 1.0
                
                # تعيين حد أدنى للكمية استناداً إلى قيمة الصفقة
                # زيادة الكمية المطلوبة بنسبة 5% لتجنب مشاكل الكسور العشرية وتقلبات السعر
                min_required_qty = min_required_qty * 1.05
                
                # حساب قيمة الصفقة المتوقعة
                expected_value = min_required_qty * current_price
                logger.info(f"قيمة الصفقة المتوقعة بعد التعديل: {expected_value:.2f} دولار")
                
                # إذا كانت القيمة المتوقعة لا تزال أقل من الحد الأدنى، نرفع الكمية مباشرةً
                if expected_value < MIN_TRADE_AMOUNT:
                    # نحسب الكمية التي ستعطينا بالضبط الحد الأدنى + هامش أمان 5%
                    min_required_qty = (MIN_TRADE_AMOUNT * 1.05) / current_price
                    logger.warning(f"زيادة الكمية لضمان قيمة الصفقة: {min_required_qty}")
                
                # التقريب حسب دقة الكمية المطلوبة للعملة
                if quantity_precision == 0:
                    min_required_qty = max(1, math.ceil(min_required_qty))
                    formatted_quantity = str(int(min_required_qty))
                    logger.warning(f"تم تحديث الكمية إلى {formatted_quantity} (دقة 0)")
                elif quantity_precision == 1:
                    min_required_qty = max(0.5, math.ceil(min_required_qty * 10) / 10)  # تقريب لأعلى بدقة 0.1
                    formatted_quantity = "{:.1f}".format(min_required_qty)
                    logger.warning(f"تم تحديث الكمية إلى {formatted_quantity} (دقة 1)")
                elif quantity_precision == 2:
                    min_required_qty = max(0.45, math.ceil(min_required_qty * 100) / 100)  # تقريب لأعلى بدقة 0.01
                    formatted_quantity = "{:.2f}".format(min_required_qty)
                    logger.warning(f"تم تحديث الكمية إلى {formatted_quantity} (دقة 2)")
                else:
                    # للدقة العالية، التقريب لأعلى وإضافة هامش
                    factor = 10 ** quantity_precision
                    min_required_qty = max(0.4, math.ceil(min_required_qty * factor) / factor)
                    formatted_quantity = "{:.{}f}".format(min_required_qty, quantity_precision)
                    formatted_quantity = formatted_quantity.rstrip('0').rstrip('.') if '.' in formatted_quantity else formatted_quantity
                    logger.warning(f"تم تحديث الكمية إلى {formatted_quantity} (دقة {quantity_precision})")
                    
                # تحقق نهائي من قيمة الصفقة
                final_value = float(formatted_quantity) * current_price
                logger.info(f"القيمة النهائية للصفقة بعد التعديل: {final_value:.2f} دولار")
                
        except ValueError as e:
            logger.error(f"التحقق النهائي: كمية منسقة غير صالحة ({formatted_quantity}). الخطأ: {e}")
            # استخدام الحد الأدنى بالدقة المناسبة بدلاً من قيمة ثابتة
            if quantity_precision == 0:
                formatted_quantity = "1"
            elif quantity_precision == 1:
                formatted_quantity = "0.1"
            elif quantity_precision == 2:
                formatted_quantity = "0.01" 
            else:
                # للدقة العالية، استخدام الحد الأدنى بالطريقة الآمنة
                formatted_quantity = "{:.{}f}".format(min_quantity, quantity_precision)
        
        logger.info(f"Order details: {symbol} {side} {formatted_quantity} (orig: {quantity})")
        
        params = {
            "symbol": symbol,
            "side": side,  # "BUY" or "SELL"
            "type": order_type,  # "LIMIT", "MARKET"
            "quantity": formatted_quantity,  # تحويل إلى نص بالدقة المناسبة
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        logger.info(f"Order params: {params}")

        if price and order_type == "LIMIT":
            params["price"] = str(price)
            params["timeInForce"] = "GTC"  # Good Till Canceled

        params["signature"] = sign_request(params)

        response = requests.post(
            f"{BASE_URL}{path}", 
            headers={"X-MEXC-APIKEY": api_key},
            params=params
        )
        
        logger.info(f"Place order response status: {response.status_code}")
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Order request failed: {error_text}")
            # إرجاع قاموس يحتوي على رسالة الخطأ بدلاً من None لمعالجة الأخطاء بشكل أفضل
            try:
                import json
                error_data = json.loads(error_text)
                return error_data
            except:
                # إذا لم نتمكن من تحويل الاستجابة إلى JSON، نرجع قاموس يحتوي على النص
                return {"msg": error_text, "code": response.status_code}
            
        logger.info(f"Order successful: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# دالة للحصول على الصفقات المفتوحة
def get_open_orders(symbol=None):
    """جلب الصفقات المفتوحة"""
    try:
        api_key, api_secret = reload_config()
        # تحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly. Please set API_KEY and API_SECRET")
            return []
        
        # في MEXC، طلب الصفقات المفتوحة يتطلب معلِم symbol
        # إذا لم يتم تحديد symbol، نستخدم BTCUSDT كمثال
        if not symbol:
            try:
                # استخدم BTCUSDT كرمز افتراضي إذا لم يتم تحديد symbol
                symbol = "BTCUSDT"
                logger.info(f"لم يتم تحديد رمز، استخدام {symbol} كرمز افتراضي")
            except Exception as e:
                logger.error(f"فشل في استخدام الرمز الافتراضي: {e}")
                return []
            
        logger.info(f"Using API key starting with: {api_key[:5]}... for open orders request")
        
        # تعريف المتغيرات بشكل بسيط ومباشر - إضافة symbol دائماً
        timestamp = int(time.time() * 1000)
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000",
            "symbol": symbol  # إضافة symbol كمعلمة إلزامية
        }
        
        # توقيع الطلب باستخدام الدالة المعرّفة
        params["signature"] = sign_request(params)
        
        # المسار الصحيح للصفقات المفتوحة (الأوامر المفتوحة)
        url = f"{BASE_URL}/api/v3/openOrders"
        headers = {"X-MEXC-APIKEY": api_key}
        
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request params: {params}")
        
        # تنفيذ الطلب
        response = requests.get(url, params=params, headers=headers)
        
        # التحقق من نجاح الطلب
        if response.status_code != 200:
            logger.error(f"Open orders request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            logger.error(f"Request URL: {response.request.url}")
            
            # تجربة رموز أخرى إذا كان الخطأ غير متعلق بالصلاحيات
            if "No permission" in response.text:
                logger.warning("تجاوز خطأ الصلاحيات - استخدام طريقة بديلة للتعامل مع الصفقات المفتوحة")
                logger.warning("لتفعيل الوصول الكامل، يرجى الانتقال إلى إعدادات MEXC > إدارة API وتفعيل صلاحيات READ و TRADE")
                logger.warning("لا توجد صفقات مفتوحة من API أو لم يتم العثور على أي صفقات للعملات المدعومة")
                return []
            
            # في حالة الخطأ، نرجع قائمة فارغة بدلاً من محاولة طرق أخرى
            return []
            
        # نجاح! جلب الصفقات المفتوحة
        logger.info(f"Open orders request successful, found {len(response.json())} orders")
        return response.json()
        
    except Exception as e:
        logger.error(f"Error getting open orders: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # نعود قائمة فارغة حتى لا يتم تسلسل الأخطاء عند استدعاء get_recent_trades
        logger.warning("خطأ عام في جلب الأوامر المفتوحة - استخدام البيانات المحلية")
        return []
        
# دالة للحصول على تاريخ الصفقات المنفذة حديثاً
def get_recent_trades():
    """جلب الصفقات المنفذة مؤخراً كبديل للصفقات المفتوحة"""
    try:
        api_key, api_secret = reload_config()
        # تحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly. Please set API_KEY and API_SECRET")
            return []
            
        logger.info(f"Using API key starting with: {api_key[:5]}... for recent trades request")
        
        # استخدام قائمة من العملات الشائعة للبحث عن الصفقات
        # حسب توثيق MEXC، يجب تحديد رمز عملة محدد لاستخدام واجهة myTrades
        common_symbols = ["BTCUSDT", "ETHUSDT", "DOGEUSDT", "SOLUSDT", "XRPUSDT"]
        
        all_trades = []
        
        for symbol in common_symbols:
            # تعريف المتغيرات بشكل بسيط ومباشر
            timestamp = int(time.time() * 1000)
            params = {
                "symbol": symbol,
                "timestamp": str(timestamp),
                "recvWindow": "5000",
                "limit": "10"  # محدودية عدد النتائج للتحسين
            }
            
            # توقيع الطلب باستخدام الدالة المعرّفة
            params["signature"] = sign_request(params)
            
            # المسار لتاريخ الصفقات
            url = f"{BASE_URL}/api/v3/myTrades"
            headers = {"X-MEXC-APIKEY": api_key}
            
            logger.debug(f"Request URL: {url} for symbol {symbol}")
            logger.debug(f"Request params: {params}")
            
            # تنفيذ الطلب
            response = requests.get(url, params=params, headers=headers)
            
            # التحقق من نجاح الطلب
            if response.status_code != 200:
                logger.warning(f"Recent trades request failed for {symbol} with status code: {response.status_code}")
                logger.debug(f"Response text: {response.text}")
                logger.debug(f"Request URL: {response.request.url}")
                
                # إذا كان الخطأ متعلق بصلاحيات API
                if "No permission" in response.text:
                    logger.error("ERROR - No permission to access the endpoint.")
                    logger.error("ERROR - Please go to MEXC account settings > API Management and update the permissions")
                    logger.error("ERROR - Enable READ permission for account information and TRADE permission for trading")
                    # توقف عن محاولة باقي العملات إذا كانت المشكلة في الصلاحيات
                    break
                # إذا كان الخطأ أن العملة ليس لها صفقات، نستمر مع العملة التالية
                continue
            else:
                # إضافة الصفقات إلى القائمة الكلية
                trades = response.json()
                if trades and len(trades) > 0:
                    logger.info(f"Found {len(trades)} trades for {symbol}")
                    all_trades.extend(trades)
        
        if len(all_trades) == 0:
            logger.warning("لا توجد صفقات مفتوحة من API أو لم يتم العثور على أي صفقات للعملات المدعومة")
            return []
            
        # نجاح! جلب تاريخ الصفقات
        # تصفية النتائج لإزالة أي صفقات محتملة من العملات المدرجة في القائمة السوداء
        from app.config import API_UNSUPPORTED_SYMBOLS
        filtered_trades = [
            trade for trade in all_trades 
            if trade.get('symbol') not in API_UNSUPPORTED_SYMBOLS
        ]
        
        logger.info(f"Recent trades request successful, found {len(filtered_trades)} valid trades (excluded {len(all_trades) - len(filtered_trades)} blacklisted trades)")
        return filtered_trades
        
    except Exception as e:
        logger.error(f"Error getting recent trades: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

# دالة للحصول على رصيد الحساب كامل
def get_account_balance():
    """جلب معلومات الحساب ورصيده"""
    try:
        api_key, api_secret = reload_config()
        # تحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly. Please set API_KEY and API_SECRET")
            return None
            
        logger.info(f"Using API key starting with: {api_key[:5]}... for account balance request")
        
        # تعريف المتغيرات بشكل بسيط ومباشر
        timestamp = int(time.time() * 1000)
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # توقيع الطلب باستخدام الدالة المعرّفة
        params["signature"] = sign_request(params)
        
        # عنوان URL للطلب
        url = f"{BASE_URL}/api/v3/account"
        headers = {"X-MEXC-APIKEY": api_key}
        
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request params: {params}")
        
        # تنفيذ الطلب
        response = requests.get(url, params=params, headers=headers)
        
        # التحقق من نجاح الطلب
        if response.status_code != 200:
            logger.error(f"Account balance request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            logger.error(f"Request URL: {response.request.url}")
            return None
        
        # نجاح!    
        logger.info("Account balance request successful")
        return response.json()
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# دالة للحصول على رصيد عملة معينة
@cached("balance", expiry=60)  # تخزين معلومات الرصيد لمدة 60 ثانية
def get_balance(asset):
    """جلب رصيد عملة معينة مثل USDT مع الأخذ في الاعتبار جميع أنواع المحافظ"""
    try:
        # أولاً، جرّب استخدام getUserAsset API (الأكثر دقة)
        total_asset_balance = get_user_asset(asset)
        if total_asset_balance > 0:
            logger.info(f"تم العثور على الرصيد باستخدام getUserAsset API: {total_asset_balance}")
            return total_asset_balance
            
        # ثانياً، استخدم الطريقة المباشرة لحساب SPOT
        account_data = get_account_balance()
        spot_balance = 0
        
        if account_data:
            # البحث في الرصيد من حساب SPOT
            for balance in account_data.get('balances', []):
                if balance['asset'] == asset:
                    spot_balance = float(balance['free'])
                    logger.info(f"تم العثور على رصيد SPOT لـ {asset}: {spot_balance}")
                    break
                    
        # ثالثاً، جلب الرصيد من محفظة التمويل
        funding_balance = get_funding_balance(asset)
        if funding_balance > 0:
            logger.info(f"تم العثور على رصيد في محفظة التمويل: {funding_balance}")

        # رابعاً، محاولة جلب الرصيد الإجمالي من جميع المحافظ
        other_balance = get_total_balance(asset)
        if other_balance > 0:
            logger.info(f"تم العثور على رصيد في محافظ أخرى: {other_balance}")
            
        # خامساً، محاولة عنوان API آخر للحصول على أصول المستخدم
        alt_balance = try_alternative_funding_method(None, None, asset) if 'try_alternative_funding_method' in globals() else 0
        if alt_balance > 0:
            logger.info(f"تم العثور على رصيد من طرق بديلة: {alt_balance}")
        
        # دمج الرصيد من جميع المصادر
        if spot_balance < 0.1 and funding_balance < 0.1 and other_balance < 0.1 and alt_balance < 0.1:
            # إذا لم يتم العثور على رصيد كافٍ، استخدم أعلى قيمة موجودة حتى لو كانت منخفضة
            lowest_balance = max(spot_balance, funding_balance, other_balance, alt_balance, total_asset_balance, 0.1)
            logger.warning(f"تم العثور على رصيد منخفض، استخدام القيمة الفعلية: {lowest_balance}")
            return lowest_balance
        
        # دمج الرصيد من جميع المصادر
        final_balance = max(spot_balance, funding_balance, other_balance, alt_balance, total_asset_balance)
        logger.info(f"الرصيد النهائي لـ {asset}: {final_balance}")
        
        return final_balance
    except Exception as e:
        logger.error(f"Error getting balance for {asset}: {e}")
        # في حالة الخطأ، محاولة استخدام طريقة احتياطية
        try:
            # محاولة كل الطرق المتاحة
            balance_methods = [0.0]  # قيمة افتراضية
            
            try:
                balance_methods.append(float(get_total_balance(asset)))
            except:
                pass
                
            try:
                balance_methods.append(float(get_funding_balance(asset)))
            except:
                pass
                
            try:
                balance_methods.append(float(get_user_asset(asset)))
            except:
                pass
                
            # Use alternative funding method as last resort
            try:
                alt_balance = try_alternative_funding_method(None, None, asset)
                balance_methods.append(float(alt_balance))
            except:
                pass
            
            total_balance = max(balance_methods)
            
            if total_balance > 0:
                return total_balance
                
            # إذا لم يتم العثور على رصيد، استخدم قيمة الحد الأدنى
            minimum_balance = 0.1  # القيمة الأدنى التي يمكن استخدامها
            logger.warning(f"تم العثور على رصيد منخفض جداً، استخدام الحد الأدنى: {minimum_balance}")
            return minimum_balance
        except Exception as inner_error:
            logger.error(f"فشلت جميع طرق الحصول على الرصيد: {inner_error}")
            # استخدام قيمة الحد الأدنى في حالة الفشل التام
            minimum_balance = 0.1
            logger.warning(f"استخدام الحد الأدنى كحل أخير: {minimum_balance}")
            return minimum_balance
            
def get_total_balance(asset):
    """جلب الرصيد الإجمالي من MEXC بما في ذلك جميع أنواع الحسابات"""
    try:
        api_key, api_secret = reload_config()
        
        # التحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly for total balance request")
            return 0
            
        logger.info(f"Using API key starting with: {api_key[:5]}... for total balance request")
        
        # في MEXC، يمكن استخدام API مختلف للأرصدة
        url = f"{BASE_URL}/api/v3/capital/config/getall"
        timestamp = int(time.time() * 1000)
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # توقيع الطلب
        params["signature"] = sign_request(params)
        
        # إرسال الطلب
        headers = {"X-MEXC-APIKEY": api_key}
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Total balance request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            logger.error(f"Request URL: {response.request.url}")
            # استخدام عنوان URL بديل
            return get_funding_balance(asset)
        
        # استخراج الرصيد الإجمالي
        data = response.json()
        total_balance = 0
        
        for item in data:
            if item.get('coin') == asset:
                total_balance += float(item.get('free', 0))
                logger.info(f"تم العثور على رصيد {asset} في النوع {item.get('type', 'unknown')}: {float(item.get('free', 0))}")
        
        logger.info(f"الرصيد الإجمالي من جميع المحافظ لـ {asset}: {total_balance}")
        return total_balance
    except Exception as e:
        logger.error(f"Error getting total balance for {asset}: {e}")
        # في حالة الخطأ، محاولة استخدام طريقة احتياطية أخيرة
        return get_funding_balance(asset)

def get_funding_balance(asset):
    """جلب رصيد التمويل من MEXC - النهج الأول باستخدام API التمويل"""
    try:
        api_key, api_secret = reload_config()
        
        # التحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly for funding balance request")
            return 0
            
        # عنوان URL لحساب التمويل
        url = f"{BASE_URL}/api/v3/asset/get-funding-asset"
        timestamp = int(time.time() * 1000)
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # توقيع الطلب
        params["signature"] = sign_request(params)
        
        # إرسال الطلب
        headers = {"X-MEXC-APIKEY": api_key}
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Funding balance request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            # محاولة الطريقة الثانية
            return try_alternative_funding_method(api_key, api_secret, asset)
        
        # استخراج رصيد التمويل
        data = response.json()
        funding_balance = 0
        
        for item in data:
            if item.get('asset') == asset:
                funding_balance = float(item.get('free', 0))
                logger.info(f"تم العثور على رصيد التمويل لـ {asset}: {funding_balance}")
                break
        
        if funding_balance == 0:
            # إذا كان الرصيد صفرًا باستخدام الطريقة الأولى، جرّب الطريقة الثانية
            alt_balance = try_alternative_funding_method(api_key, api_secret, asset)
            logger.info(f"البحث عن رصيد {asset} باستخدام الطريقة البديلة: {alt_balance}")
            return alt_balance
        
        return funding_balance
    except Exception as e:
        logger.error(f"Error getting funding balance for {asset}: {e}")
        # محاولة الطريقة الثانية في حالة الخطأ
        try:
            api_key, api_secret = reload_config()
            return try_alternative_funding_method(api_key, api_secret, asset)
        except:
            logger.error(f"فشلت جميع طرق الحصول على رصيد التمويل لـ {asset}")
            return 0

def try_alternative_funding_method(api_key, api_secret, asset):
    """محاولة بديلة للحصول على رصيد تمويل باستخدام API مختلف"""
    try:
        # الحصول على مفاتيح API إذا لم يتم تمريرها
        if not api_key or not api_secret:
            api_key, api_secret = reload_config()
            
        # محاولة 1: استخدام نقطة نهاية مختلفة لعرض الموجودات
        url = f"{BASE_URL}/api/v3/account/balance"
        timestamp = int(time.time() * 1000)
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # توقيع الطلب
        from urllib.parse import urlencode
        signature = hmac.new(
            api_secret.encode('utf-8'),
            urlencode(params).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        
        # إرسال الطلب
        headers = {"X-MEXC-APIKEY": api_key}
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            for item in data:
                if isinstance(item, dict) and item.get('asset') == asset:
                    funding_balance = float(item.get('free', 0))
                    logger.info(f"تم العثور على رصيد {asset} في محاولة بديلة 1: {funding_balance}")
                    return funding_balance
        
        # محاولة 2: استخدام طريقة الميزان التقليدية للمستخدم
        url = f"{BASE_URL}/api/v3/capital/user/balance"
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # توقيع الطلب
        signature = hmac.new(
            api_secret.encode('utf-8'),
            urlencode(params).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        
        # إرسال الطلب
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'balances' in data:
                for balance in data['balances']:
                    if balance.get('asset') == asset:
                        funding_balance = float(balance.get('free', 0))
                        logger.info(f"تم العثور على رصيد {asset} في محاولة بديلة 2: {funding_balance}")
                        return funding_balance
                        
        # محاولة أخيرة: استخدام أي شكل من أشكال API
        try:
            # استخدام طريقة أخرى للوصول إلى معلومات MEXC
            url = f"{BASE_URL}/api/v3/capital/config"
            params = {
                "timestamp": str(timestamp),
                "recvWindow": "5000"
            }
            
            # توقيع الطلب
            signature = hmac.new(
                api_secret.encode('utf-8'),
                urlencode(params).encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            params['signature'] = signature
            
            # إرسال الطلب
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    if item.get('coin') == asset:
                        funding_balance = float(item.get('free', 0))
                        logger.info(f"تم العثور على رصيد {asset} في محاولة بديلة 3: {funding_balance}")
                        return funding_balance
        except Exception as e:
            logger.error(f"فشل في محاولة بديلة 3: {e}")
            
        # طريقة باستخدام المحفظة الرئيسية
        try:
            # استخدام طريقة أخرى للوصول إلى معلومات MEXC
            url = f"{BASE_URL}/api/v3/capital/wallet/balance"
            params = {
                "timestamp": str(timestamp),
                "recvWindow": "5000"
            }
            
            # توقيع الطلب
            signature = hmac.new(
                api_secret.encode('utf-8'),
                urlencode(params).encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            params['signature'] = signature
            
            # إرسال الطلب
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    if isinstance(item, dict) and item.get('asset') == asset:
                        funding_balance = float(item.get('free', 0))
                        logger.info(f"تم العثور على رصيد {asset} في محاولة بديلة 4: {funding_balance}")
                        return funding_balance
        except Exception as e:
            logger.error(f"فشل في محاولة بديلة 4: {e}")
        
        # استخدام قيمة ثابتة في حالة فشل كل الطرق
        logger.warning(f"لم يتم العثور على رصيد {asset} في أي من الطرق البديلة")
        return 0
        
    except Exception as e:
        logger.error(f"خطأ في محاولات الطرق البديلة: {e}")
        return 0
        
def test_api_permissions():
    """
    اختبار صلاحيات API للتأكد من أنها تملك صلاحيات للتداول
    
    :return: قاموس يحتوي على معلومات حول الصلاحيات
    """
    api_key, api_secret = reload_config()
    
    # التحقق من وجود مفاتيح API
    if not api_key or not api_secret:
        logger.error("API keys not configured properly for permissions test")
        return {
            "has_keys": False,
            "read_permission": False,
            "trade_permission": False,
            "error": "API keys not configured"
        }
    
    results = {
        "has_keys": True,
        "read_permission": False,
        "trade_permission": False,
        "errors": []
    }
    
    # اختبار قراءة بيانات الحساب (صلاحية القراءة)
    try:
        account = get_account_balance()
        if account and isinstance(account, dict):
            results["read_permission"] = True
            logger.info("✅ API has READ permission (account balance accessible)")
        else:
            results["errors"].append("Cannot read account balance")
    except Exception as e:
        logger.error(f"Error testing READ permission: {e}")
        results["errors"].append(f"READ test error: {str(e)}")
    
    # اختبار صلاحية التداول - محاولة وضع أمر صغير جدًا ثم إلغاؤه فورًا
    # ملاحظة: يمكن تعليق هذا الجزء إذا لم ترغب في إجراء أي عمليات تداول اختبارية
    try:
        timestamp = get_timestamp()
        # جلب معلومات الصلاحيات فقط
        path = "/api/v3/account"
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # توقيع الطلب
        params["signature"] = sign_request(params)
        
        # إرسال الطلب
        response = requests.get(
            f"{BASE_URL}{path}", 
            headers={"X-MEXC-APIKEY": api_key},
            params=params
        )
        
        if response.status_code == 200:
            account_info = response.json()
            if "permissions" in account_info:
                perms = account_info["permissions"]
                logger.info(f"API permissions: {perms}")
                if "SPOT" in perms:
                    results["trade_permission"] = True
                    logger.info("✅ API has TRADE permission (spot trading enabled)")
            else:
                logger.warning("No permissions field found in account info response")
                results["errors"].append("No permissions field in account info")
        else:
            logger.error(f"Account info request failed: {response.text}")
            results["errors"].append(f"Account info error: {response.text}")
            
    except Exception as e:
        logger.error(f"Error testing TRADE permission: {e}")
        results["errors"].append(f"TRADE test error: {str(e)}")
    
    # عرض النتائج النهائية للاختبار
    logger.info(f"API permission test results: {results}")
    return results
    
def get_user_asset(asset):
    """محاولة للحصول على رصيد المستخدم من نقطة نهاية بديلة"""
    try:
        api_key, api_secret = reload_config()
        
        # التحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly for user asset request")
            return 0
            
        url = f"{BASE_URL}/api/v3/asset/getUserAsset"
        timestamp = int(time.time() * 1000)
        params = {
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # توقيع الطلب
        params["signature"] = sign_request(params)
        
        # إرسال الطلب كـ POST وفقًا لتوثيق MEXC
        headers = {"X-MEXC-APIKEY": api_key}
        response = requests.post(url, params=params, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"User asset request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            return 0
        
        # استخراج رصيد الأصول
        data = response.json()
        total_balance = 0
        
        for item in data:
            if item.get('asset') == asset:
                asset_balance = float(item.get('free', 0))
                logger.info(f"تم العثور على رصيد {asset} من getUserAsset: {asset_balance}")
                total_balance += asset_balance
        
        return total_balance
    except Exception as e:
        logger.error(f"Error getting user asset for {asset}: {e}")
        return 0

# دالة للحصول على تاريخ الصفقات السابقة
def get_trades_history(symbol, limit=100):
    """جلب تاريخ العمليات السابقة"""
    try:
        api_key, api_secret = reload_config()
        # تحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly. Please set API_KEY and API_SECRET")
            return []
            
        logger.info(f"Using API key starting with: {api_key[:5]}... for trade history request")
        
        # الحصول على الوقت الحالي
        timestamp = int(time.time() * 1000)
        
        # إنشاء بارامترات الطلب
        params = {
            "symbol": symbol,
            "limit": str(limit),
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # إنشاء سلسلة الاستعلام مباشرة باستخدام urlencode
        from urllib.parse import urlencode
        query_string = urlencode(params)
        
        # توقيع سلسلة الاستعلام
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # إضافة التوقيع إلى البارامترات
        params['signature'] = signature
        
        # تنفيذ الطلب
        url = f"{BASE_URL}/api/v3/myTrades"
        headers = {"X-MEXC-APIKEY": api_key}
        
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request headers: {{'X-MEXC-APIKEY': '{api_key[:5]}...'}}") 
        logger.debug(f"Full URL with params: {url}?{urlencode(params)}")
        
        response = requests.get(url, params=params, headers=headers)
        
        # سجل المعلومات الكاملة عن الاستجابة في حالة الخطأ
        if response.status_code != 200:
            logger.error(f"Trade history request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            logger.error(f"Request URL: {response.request.url}")
            
            # توجيه لإضافة صلاحيات إذا كان الخطأ متعلقًا بالأذونات
            if "No permission" in response.text:
                logger.error("PERMISSION ERROR: Make sure you have enabled READ and TRADE permissions for your API key in MEXC")
                logger.error("Please go to MEXC account settings > API Management and update the permissions")
                
            return []
            
        # نجاح!
        logger.info("Trade history request successful")
        return response.json()
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

# دالة لإلغاء أمر معين
def cancel_order(symbol, order_id):
    """إلغاء أمر معين باستخدام الـ order_id"""
    try:
        api_key, api_secret = reload_config()
        # تحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly. Please set API_KEY and API_SECRET")
            return None
            
        logger.info(f"Using API key starting with: {api_key[:5]}... for cancel order request")
        
        # الحصول على الوقت الحالي
        timestamp = int(time.time() * 1000)
        
        # إنشاء بارامترات الطلب
        params = {
            "symbol": symbol,
            "orderId": str(order_id),
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # إنشاء سلسلة الاستعلام مباشرة باستخدام urlencode
        from urllib.parse import urlencode
        query_string = urlencode(params)
        
        # توقيع سلسلة الاستعلام
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # إضافة التوقيع إلى البارامترات
        params['signature'] = signature
        
        # تنفيذ الطلب
        url = f"{BASE_URL}/api/v3/order"
        headers = {"X-MEXC-APIKEY": api_key}
        
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request headers: {{'X-MEXC-APIKEY': '{api_key[:5]}...'}}") 
        logger.debug(f"Full URL with params: {url}?{urlencode(params)}")
        
        response = requests.delete(url, params=params, headers=headers)
        
        # سجل المعلومات الكاملة عن الاستجابة في حالة الخطأ
        if response.status_code != 200:
            logger.error(f"Cancel order request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            logger.error(f"Request URL: {response.request.url}")
            return None
        
        # نجاح!    
        logger.info("Cancel order request successful")
        return response.json()
    except Exception as e:
        logger.error(f"Error canceling order: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# دالة للحصول على حالة أمر معين
def get_order_status(symbol, order_id):
    """جلب حالة أمر معين باستخدام الـ order_id"""
    try:
        api_key, api_secret = reload_config()
        # تحقق من وجود مفاتيح API
        if not api_key or not api_secret:
            logger.error("API keys not configured properly. Please set API_KEY and API_SECRET")
            return None
            
        logger.info(f"Using API key starting with: {api_key[:5]}... for order status request")
        
        # الحصول على الوقت الحالي
        timestamp = int(time.time() * 1000)
        
        # إنشاء بارامترات الطلب
        params = {
            "symbol": symbol,
            "orderId": str(order_id),
            "timestamp": str(timestamp),
            "recvWindow": "5000"
        }
        
        # إنشاء سلسلة الاستعلام مباشرة باستخدام urlencode
        from urllib.parse import urlencode
        query_string = urlencode(params)
        
        # توقيع سلسلة الاستعلام
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # إضافة التوقيع إلى البارامترات
        params['signature'] = signature
        
        # تنفيذ الطلب
        url = f"{BASE_URL}/api/v3/order"
        headers = {"X-MEXC-APIKEY": api_key}
        
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request headers: {{'X-MEXC-APIKEY': '{api_key[:5]}...'}}") 
        logger.debug(f"Full URL with params: {url}?{urlencode(params)}")
        
        response = requests.get(url, params=params, headers=headers)
        
        # سجل المعلومات الكاملة عن الاستجابة في حالة الخطأ
        if response.status_code != 200:
            logger.error(f"Order status request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            logger.error(f"Request URL: {response.request.url}")
            return None
        
        # نجاح!    
        logger.info("Order status request successful")
        return response.json()
    except Exception as e:
        logger.error(f"Error getting order status: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# دالة للحصول على جميع الرموز المتاحة للتداول
@cached("exchange_info", expiry=3600)  # تخزين معلومات السوق لمدة ساعة
def get_exchange_info():
    """جلب معلومات عن جميع الرموز المتاحة للتداول"""
    try:
        url = f"{BASE_URL}/api/v3/exchangeInfo"
        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"Exchange info request failed: {response.text}")
            return None
            
        return response.json()
    except Exception as e:
        logger.error(f"Error getting exchange info: {e}")
        return None

# دالة للحصول على قائمة الرموز (العملات) المتاحة للتداول (مع تخزين مؤقت)
@cached("symbols_list", expiry=3600)  # تخزين قائمة الرموز لمدة ساعة
def get_all_symbols(market_type='SPOT'):
    """
    جلب قائمة برموز العملات المتاحة للتداول
    
    :param market_type: نوع السوق (SPOT للفوري، FUTURES للعقود)
    :return: قائمة بالرموز المتاحة
    """
    try:
        if market_type == 'SPOT':
            # السوق الفوري
            exchange_info = get_exchange_info()
            if not exchange_info:
                return []
                
            symbols = []
            for symbol_info in exchange_info.get('symbols', []):
                if symbol_info.get('status') == 'TRADING' and symbol_info.get('quoteAsset') == 'USDT':
                    symbols.append(symbol_info.get('symbol'))
            return symbols
        elif market_type == 'FUTURES':
            # العقود الفورية
            futures_url = "https://contract.mexc.com/api/v1/contract/detail"
            response = requests.get(futures_url)
            if response.status_code != 200:
                logger.error(f"Failed to get futures symbols: {response.text}")
                return []
            
            data = response.json()
            if data.get('success', False):
                return [item.get('symbol') for item in data.get('data', []) if 'USDT' in item.get('symbol', '')]
            return []
        return []
    except Exception as e:
        logger.error(f"Error getting all symbols: {e}")
        return []

# دالة للحصول على بيانات السوق لآخر 24 ساعة (مع تخزين مؤقت)
@cached("symbols_24h_data", expiry=300)  # تخزين بيانات الـ 24 ساعة لمدة 5 دقائق
def get_all_symbols_24h_data():
    """جلب بيانات 24 ساعة لجميع العملات"""
    try:
        url = f"{BASE_URL}/api/v3/ticker/24hr"
        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"24h data request failed: {response.text}")
            return []
            
        data = response.json()
        filtered_data = []
        for item in data:
            if item.get('symbol', '').endswith('USDT'):
                filtered_data.append(item)
        return filtered_data
    except Exception as e:
        logger.error(f"Error getting 24h data: {e}")
        return []
        
# اضافة دالة جديدة للحصول على آخر صفقات للعملة
def fetch_recent_trades(symbol, limit=10):
    """
    الحصول على آخر صفقات للعملة
    
    :param symbol: رمز العملة
    :param limit: عدد الصفقات للعرض (الحد الأقصى 1000)
    :return: قائمة بالصفقات الأخيرة أو None في حالة الفشل
    """
    try:
        logger.info(f"جاري الحصول على آخر {limit} صفقات للعملة {symbol}")
        url = f"{BASE_URL}/api/v3/trades"
        params = {
            'symbol': symbol,
            'limit': limit
        }
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"فشل الحصول على تاريخ الصفقات: {response.text}")
            return None
    except Exception as e:
        logger.error(f"خطأ في fetch_recent_trades: {e}")
        return None
