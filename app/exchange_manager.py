# app/exchange_manager.py
import logging
import os
from typing import Dict, List, Any, Optional, Union

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('exchange_manager')

# استيراد واجهة MEXC API
from app import mexc_api

# منصة MEXC فقط
ACTIVE_EXCHANGE = "MEXC"

def get_active_exchange() -> str:
    """
    الحصول على اسم المنصة النشطة حاليًا
    """
    return ACTIVE_EXCHANGE

def set_api_keys(api_key: str, api_secret: str) -> bool:
    """
    تعيين مفاتيح API لمنصة MEXC
    
    :param api_key: مفتاح API
    :param api_secret: سر API
    :return: نجاح العملية
    """
    # تحديث متغيرات البيئة للحفاظ على التوافق مع الشيفرة الحالية
    os.environ["MEXC_API_KEY"] = api_key
    os.environ["MEXC_API_SECRET"] = api_secret
    
    # تحديث الوحدة مباشرة
    from app.config import update_api_keys
    result = update_api_keys(api_key, api_secret)
    if result:
        logger.info("تم تعيين مفاتيح MEXC API بنجاح")
    return result

def convert_symbol_format(symbol: str) -> str:
    """
    تحويل رمز العملة إلى تنسيق MEXC إذا لزم الأمر
    
    :param symbol: رمز العملة بالتنسيق الحالي
    :return: رمز العملة بتنسيق MEXC
    """
    # إذا كان الرمز يحتوي على '-' (مثل BTC-USDT) نقوم بتحويله إلى تنسيق MEXC (BTCUSDT)
    if '-' in symbol:
        base, quote = symbol.split('-')
        return f"{base}{quote}"
    
    return symbol

def get_current_price(symbol: str) -> Optional[float]:
    """
    الحصول على السعر الحالي للعملة
    
    :param symbol: رمز العملة
    :return: السعر الحالي أو None في حالة الفشل
    """
    mexc_symbol = convert_symbol_format(symbol)
    return mexc_api.get_current_price(mexc_symbol)

def get_balance(asset: str = "USDT") -> float:
    """
    الحصول على رصيد العملة
    
    :param asset: رمز العملة
    :return: رصيد العملة
    """
    try:
        balance = mexc_api.get_balance(asset)
        return float(balance) if balance is not None else 0.0
    except Exception as e:
        logger.error(f"خطأ في جلب رصيد {asset}: {e}")
        return 0.0

def get_klines(symbol: str, interval: str = '15m', limit: int = 100) -> List[Dict[str, Any]]:
    """
    الحصول على بيانات الشموع
    
    :param symbol: رمز العملة
    :param interval: الفاصل الزمني
    :param limit: عدد الشموع
    :return: قائمة بيانات الشموع
    """
    try:
        mexc_symbol = convert_symbol_format(symbol)
        klines = mexc_api.get_klines(mexc_symbol, interval, limit)
        return klines or []
    except Exception as e:
        logger.error(f"خطأ في جلب بيانات الشموع لـ {symbol}: {e}")
        return []

def get_all_symbols_24h_data() -> List[Dict[str, Any]]:
    """
    الحصول على بيانات 24 ساعة لجميع العملات
    
    :return: قائمة بيانات جميع العملات
    """
    try:
        data = mexc_api.get_all_symbols_24h_data()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"خطأ في جلب بيانات 24 ساعة لجميع العملات: {e}")
        return []

def place_order(symbol: str, side: str, quantity: Union[str, float], price: Optional[float] = None, order_type: str = "MARKET") -> Optional[Dict[str, Any]]:
    """
    إنشاء أمر تداول
    
    :param symbol: رمز العملة
    :param side: جانب الأمر (BUY/SELL)
    :param quantity: الكمية
    :param price: السعر (للأوامر المحددة)
    :param order_type: نوع الأمر (MARKET/LIMIT)
    :return: بيانات الأمر المنشأ
    """
    logger.info(f"⭐⭐⭐ محاولة تنفيذ أمر من exchange_manager: {symbol} {side} {quantity} بنوع {order_type} ⭐⭐⭐")
    
    # التحقق من صلاحية مفاتيح API
    from app.config import API_KEY, API_SECRET
    if not API_KEY or not API_SECRET:
        logger.error("❌ فشل تنفيذ الأمر: مفاتيح API غير متوفرة")
        return None
        
    # التحقق من الكمية
    try:
        qty_float = float(quantity) if isinstance(quantity, str) else quantity
        if qty_float <= 0:
            logger.error(f"❌ فشل تنفيذ الأمر: الكمية يجب أن تكون موجبة وغير صفرية ({qty_float})")
            return None
    except:
        logger.error(f"❌ فشل تنفيذ الأمر: تنسيق الكمية غير صالح ({quantity})")
        return None
        
    # تأكد من أن side وorder_type بالأحرف الكبيرة
    side = side.upper()
    order_type = order_type.upper()
    
    mexc_symbol = convert_symbol_format(symbol)
    logger.info(f"إرسال طلب الأمر إلى MEXC API...")
    
    # تنفيذ الأمر عبر واجهة MEXC
    result = mexc_api.place_order(mexc_symbol, side, quantity, price, order_type)
    
    if result:
        logger.info(f"✅ تم تنفيذ الأمر بنجاح: {result}")
    else:
        logger.error(f"❌ فشل تنفيذ الأمر لـ {mexc_symbol}")
        # تجربة طلب OKX SPOT للتأكد من وجود أي صلاحيات في API
        logger.info("محاولة التحقق من صلاحيات API...")
        open_orders = mexc_api.get_open_orders()
        if isinstance(open_orders, list):
            logger.info(f"✅ صلاحيات API تعمل للاستعلام عن البيانات - العمليات المفتوحة: {len(open_orders)}")
        
    return result

def get_open_orders(symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    الحصول على الأوامر المفتوحة
    
    :param symbol: رمز العملة (اختياري)
    :return: قائمة الأوامر المفتوحة
    """
    try:
        orders = mexc_api.get_open_orders()
        return orders if isinstance(orders, list) else []
    except Exception as e:
        logger.error(f"خطأ في جلب الأوامر المفتوحة: {e}")
        return []

def cancel_order(symbol: str, order_id: str) -> Optional[Dict[str, Any]]:
    """
    إلغاء أمر
    
    :param symbol: رمز العملة
    :param order_id: معرف الأمر
    :return: نتيجة الإلغاء
    """
    mexc_symbol = convert_symbol_format(symbol)
    return mexc_api.cancel_order(mexc_symbol, order_id)

def get_account_balance() -> Optional[Dict[str, Any]]:
    """
    الحصول على رصيد الحساب الكامل
    
    :return: بيانات رصيد الحساب
    """
    return mexc_api.get_account_balance()

def get_exchange_info() -> Optional[Dict[str, Any]]:
    """
    الحصول على معلومات المنصة
    
    :return: معلومات المنصة
    """
    return mexc_api.get_exchange_info()

def get_exchange_symbols() -> List[str]:
    """
    الحصول على قائمة جميع رموز العملات المتاحة على المنصة
    
    :return: قائمة برموز العملات
    """
    try:
        # 1. محاولة الحصول على البيانات من تيكر 24 ساعة
        ticker_data = get_all_symbols_24h_data()
        if ticker_data and isinstance(ticker_data, list):
            symbols = [item.get('symbol') for item in ticker_data if 'symbol' in item]
            if symbols:
                logger.info(f"تم الحصول على {len(symbols)} رمز من بيانات التيكر")
                return symbols

        # 2. محاولة الحصول على البيانات من معلومات المنصة
        exchange_info = get_exchange_info()
        if exchange_info and 'symbols' in exchange_info:
            symbols = [item.get('symbol') for item in exchange_info['symbols'] if 'symbol' in item]
            logger.info(f"تم الحصول على {len(symbols)} رمز من معلومات المنصة")
            return symbols

        # 3. استخدام قائمة أساسية من العملات الشائعة في حالة الفشل
        logger.warning("استخدام قائمة أساسية من العملات الشائعة بسبب فشل الحصول على البيانات من API")
        basic_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "MATICUSDT", 
            "AVAXUSDT", "LTCUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT",
            "DOTUSDT", "ATOMUSDT", "LINKUSDT", "NEARUSDT", "TRXUSDT",
            "UNIUSDT", "FTMUSDT", "APEUSDT", "SANDUSDT", "MANAUSDT",
            "AXSUSDT", "FILUSDT", "HBARUSDT", "GRTUSDT", "ALGOUSDT"
        ]
        return basic_symbols
    except Exception as e:
        logger.error(f"خطأ في الحصول على رموز المنصة: {e}")
        # قائمة أساسية من العملات الرئيسية للطوارئ
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "MATICUSDT", "BNBUSDT", "XRPUSDT"]
        
def get_historical_klines(symbol: str, interval: str = '1h', limit: int = 100) -> List[List[Any]]:
    """
    الحصول على بيانات التداول التاريخية للعملة
    
    :param symbol: رمز العملة
    :param interval: الفاصل الزمني (1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d)
    :param limit: عدد الشموع المطلوبة
    :return: قائمة بيانات الشموع بالتنسيق [timestamp, open, high, low, close, volume, ...]
    """
    try:
        mexc_symbol = convert_symbol_format(symbol)
        # استدعاء دالة get_klines مع إضافة معالجة للتنسيق المتوقع
        klines_data = get_klines(mexc_symbol, interval, limit)
        
        # إذا كانت البيانات بتنسيق مختلف، نحولها إلى التنسيق المتوقع
        formatted_klines = []
        if klines_data:
            for kline in klines_data:
                # إذا كانت البيانات بتنسيق قاموس
                if isinstance(kline, dict):
                    formatted_kline = [
                        kline.get('openTime', 0),
                        kline.get('open', '0'),
                        kline.get('high', '0'),
                        kline.get('low', '0'),
                        kline.get('close', '0'),
                        kline.get('volume', '0'),
                        kline.get('closeTime', 0)
                    ]
                    formatted_klines.append(formatted_kline)
                # إذا كانت البيانات بتنسيق قائمة
                elif isinstance(kline, list) and len(kline) >= 5:
                    formatted_klines.append(kline)
                    
        return formatted_klines
    except Exception as e:
        logger.error(f"خطأ في الحصول على البيانات التاريخية لـ {symbol}: {e}")
        return []

def test_trade_execution(symbol: str = "BTCUSDT", quantity: float = 0.0001) -> Dict[str, Any]:
    """
    اختبار تنفيذ صفقة حقيقية بكمية صغيرة جداً للتأكد من عمل API
    
    :param symbol: رمز العملة (الافتراضي BTCUSDT)
    :param quantity: كمية صغيرة جداً للاختبار (الافتراضي 0.0001)
    :return: نتيجة الاختبار
    """
    result = {
        "success": False,
        "error": None,
        "api_result": None,
        "test_details": {}
    }
    
    try:
        logger.info(f"🧪 بدء اختبار تنفيذ صفقة لـ {symbol} بكمية {quantity}")
        
        # 1. اختبار صلاحيات API
        from app.mexc_api import test_api_permissions
        permissions = test_api_permissions()
        result["test_details"]["permissions"] = permissions
        
        if not permissions.get("trade_permission", False):
            result["error"] = "لا توجد صلاحيات كافية للتداول. يرجى التأكد من إعدادات API"
            return result
            
        # 2. التحقق من السعر الحالي
        current_price = get_current_price(symbol)
        result["test_details"]["current_price"] = current_price
        
        if not current_price:
            result["error"] = f"فشل في الحصول على سعر {symbol}"
            return result
            
        # 3. التحقق من الرصيد
        balance = get_balance("USDT")
        result["test_details"]["balance"] = balance
        
        estimated_cost = current_price * quantity
        result["test_details"]["estimated_cost"] = estimated_cost
        
        if balance < estimated_cost:
            result["error"] = f"الرصيد غير كافٍ. المطلوب: {estimated_cost} USDT، المتوفر: {balance} USDT"
            return result
            
        # 4. محاولة تنفيذ صفقة شراء صغيرة
        # نستخدم MARKET لضمان التنفيذ الفوري
        logger.info(f"⚡ محاولة تنفيذ صفقة شراء صغيرة: {symbol} - كمية: {quantity}")
        order_result = place_order(symbol, "BUY", quantity, None, "MARKET")
        result["api_result"] = order_result
        
        if order_result and isinstance(order_result, dict) and "orderId" in order_result:
            result["success"] = True
            logger.info(f"✅ تم تنفيذ صفقة الاختبار بنجاح! معرف الأمر: {order_result['orderId']}")
            
            # المزيد من المعلومات التفصيلية
            result["test_details"]["order_id"] = order_result.get("orderId")
            result["test_details"]["executed_qty"] = order_result.get("executedQty", order_result.get("origQty"))
            
            # 5. (اختياري) بيع الكمية المشتراة لتجنب تركها في المحفظة
            try:
                logger.info(f"🔄 محاولة بيع الكمية المشتراة من {symbol}")
                executed_qty = float(order_result.get("executedQty", order_result.get("origQty", quantity)))
                if executed_qty > 0:
                    sell_result = place_order(symbol, "SELL", executed_qty, None, "MARKET")
                    result["test_details"]["sell_result"] = sell_result
                    logger.info(f"✅ تم بيع الكمية المشتراة بنجاح: {executed_qty} من {symbol}")
            except Exception as sell_error:
                logger.warning(f"⚠️ لم يتم بيع الكمية المشتراة: {sell_error}")
                result["test_details"]["sell_error"] = str(sell_error)
        else:
            result["error"] = "فشل تنفيذ الصفقة. تحقق من السجل للمزيد من التفاصيل."
            logger.error(f"❌ فشل تنفيذ صفقة الاختبار: {order_result}")
            
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"❌ خطأ في اختبار تنفيذ صفقة: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    return result