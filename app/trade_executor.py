# app/trade_executor.py
import json
import os
import time
import logging
import threading
from datetime import datetime
# استخدام مدير المنصات بدلاً من MEXC مباشرة
from app.exchange_manager import get_current_price, get_open_orders, ACTIVE_EXCHANGE, place_order, get_balance
from app.trade_logic import close_trade
from app.config import TAKE_PROFIT, TAKE_PROFIT_2, TAKE_PROFIT_3, STOP_LOSS, MIN_TRADE_AMOUNT, BASE_CURRENCY, SMART_STOP_THRESHOLD, TIMEFRAMES, USE_MULTI_TIMEFRAME
from app.telegram_notify import send_telegram_message

# استخدام نظام منع التكرار المحسّن
try:
    from app.symbol_enforcer import is_trade_allowed, enforce_trade_diversity, get_currently_traded_symbols
    SYMBOL_ENFORCER_AVAILABLE = True
except ImportError:
    SYMBOL_ENFORCER_AVAILABLE = False
    logger = logging.getLogger('trade_executor')
    logger.warning("⚠️ لم يتم العثور على نظام منع التكرار (symbol_enforcer). سيتم استخدام آلية تنويع بسيطة.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trade_executor')

TRADES_FILE = 'active_trades.json'
BOT_RUNNING = False
LOCK = threading.Lock()

def load_trades():
    """
    تحميل الصفقات من ملف JSON
    
    :return: قائمة بالصفقات المحملة
    """
    try:
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading trades: {e}")
        return []

def save_trades(trades):
    """
    حفظ الصفقات في ملف JSON
    
    :param trades: قائمة بالصفقات
    """
    try:
        with LOCK:
            with open(TRADES_FILE, 'w') as f:
                json.dump(trades, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving trades: {e}")

def get_open_trades():
    """
    الحصول على الصفقات المفتوحة مباشرة من المنصة النشطة (OKX/MEXC) أو من الملف المحلي إذا تعذر ذلك
    
    :return: قائمة بالصفقات المفتوحة
    """
    try:
        # استخدام معلومات الصفقات الأخيرة من API
        try_api_first = True
        
        if try_api_first:
            # محاولة الحصول على الصفقات المفتوحة من منصة MEXC
            logger.info(f"جلب الصفقات المفتوحة من المنصة النشطة: {ACTIVE_EXCHANGE}")
            logger.info("استخدام دالة get_open_orders من exchange_manager")
            api_open_orders = get_open_orders()
            
            # في حالة نجاح الوصول إلى API، نستخدم فقط الصفقات المؤكدة من المنصة
            if api_open_orders is not None and api_open_orders != []:
                # تحويل صفقات API إلى تنسيق البوت
                real_trades = []
                for order in api_open_orders:
                    symbol = order.get('symbol', '')
                    # تحويل البيانات من API إلى الصيغة المستخدمة في البوت
                    trade = {
                        'symbol': symbol,
                        'entry_price': float(order.get('price', 0)),
                        'quantity': float(order.get('origQty', 0)),
                        'timestamp': order.get('time', int(time.time() * 1000)),
                        'status': 'OPEN',
                        'order_id': order.get('orderId', ''),
                        'side': 'BUY',
                        'metadata': {
                            'api_confirmed': True,
                            'api_source': 'open_orders'
                        }
                    }
                    real_trades.append(trade)
                
                # تحديث الملف المحلي بالبيانات الحقيقية من API
                try:
                    local_trades = load_trades()
                    
                    # الاحتفاظ فقط بالصفقات المغلقة من الملف المحلي
                    closed_trades = [t for t in local_trades if t.get('status') == 'CLOSED']
                    
                    # دمج الصفقات المفتوحة من API مع الصفقات المغلقة
                    all_trades = closed_trades + real_trades
                    
                    # حفظ البيانات المحدثة
                    save_trades(all_trades)
                    logger.info(f"تم تحديث ملف الصفقات: {len(real_trades)} مفتوحة، {len(closed_trades)} مغلقة")
                except Exception as e:
                    logger.error(f"خطأ في مزامنة بيانات الصفقات: {e}")
                
                return real_trades
        
        # في حالة فشل الوصول إلى API أو إذا لم تكن هناك صلاحيات كافية
        logger.warning("لا توجد صفقات مفتوحة من API أو صلاحيات غير كافية. استخدام البيانات المحلية.")
        trades = load_trades()
        
        # تحقق من صحة حالة الصفقات وتنظيفها
        for trade in trades:
            if trade.get('status') not in ['OPEN', 'CLOSED']:
                trade['status'] = 'CLOSED'  # تصحيح الحالة غير المعروفة
        
        # إضافة علامة لتمييز أن هذه البيانات محلية وليست مؤكدة من API
        for trade in trades:
            if 'metadata' not in trade:
                trade['metadata'] = {}
            trade['metadata']['api_confirmed'] = False
            trade['metadata']['local_source'] = True
            
            # تأكد من وجود الحقول الأساسية
            if 'side' not in trade:
                trade['side'] = 'BUY'  # افتراض الشراء إذا كان غير محدد
                
        # حفظ التغييرات بعد التنظيف
        save_trades(trades)
        
        # إرجاع الصفقات المفتوحة فقط
        return [t for t in trades if t.get('status') == 'OPEN']
    except Exception as e:
        logger.error(f"Error getting open trades: {e}")
        return []

def execute_trade(symbol, quantity):
    """
    تنفيذ صفقة جديدة وحفظها مع تطبيق إلزامي لقواعد تنويع العملات
    
    :param symbol: رمز العملة
    :param quantity: الكمية
    :return: True إذا تم تنفيذ الصفقة بنجاح، False خلاف ذلك
    """
    try:
        # ===== توقف إلزامي وتشغيل نظام منع الصفقات المكررة =====
        
        # تشغيل أداة إصلاح الصفقات المكررة أولاً
        try:
            from daily_enforcer import enforce_trade_diversity
            enforce_trade_diversity()
            logger.error("✅ تم تنفيذ دالة إصلاح الصفقات المكررة")
        except Exception as e:
            logger.error(f"⚠️ فشل تشغيل أداة إصلاح الصفقات المكررة: {e}")
        
        # ===== فحص التنويع الإلزامي بطريقة مباشرة ومتعددة الطبقات =====
        try:
            # فحص مباشر لملف قاعدة البيانات (الطبقة الأولى)
            with open('active_trades.json', 'r') as f:
                all_trades = json.load(f)
                
            # فحص وجود أي صفقة مفتوحة لهذه العملة
            symbol_trades = [t for t in all_trades if t.get('symbol') == symbol and t.get('status') == 'OPEN']
            
            if len(symbol_trades) > 0:
                logger.error(f"⛔⛔⛔ منع تداول {symbol} - يوجد بالفعل {len(symbol_trades)} صفقة مفتوحة على هذه العملة ⛔⛔⛔")
                return False
                
            logger.warning(f"✅ لا توجد صفقات مفتوحة على {symbol} - الفحص الأول")
        except Exception as e:
            logger.error(f"خطأ في التحقق من الصفقات المفتوحة (الطبقة الأولى): {e}")
            # في حالة الخطأ، نمنع التداول ليكون آمنًا
            return False
            
        # الطبقة الثانية - فحص عبر وظيفة التنويع الجديدة
        try:
            from app.trade_diversifier import is_trade_allowed
            allowed, reason = is_trade_allowed(symbol)
            if not allowed:
                logger.error(f"⛔⛔⛔ منع تداول {symbol} - {reason} ⛔⛔⛔")
                return False
                
            logger.warning(f"✅ الصفقة مسموح بها - الفحص الثاني")
        except Exception as e:
            logger.error(f"خطأ في التحقق من التنويع (الطبقة الثانية): {e}")
            return False
            
        # الطبقة الثالثة - فحص نهائي اضافي
        try:
            # إعادة قراءة الملف للتأكد من عدم تغييره بعد الفحوصات السابقة
            with open('active_trades.json', 'r') as f:
                final_trades = json.load(f)
                
            final_symbols = set([t.get('symbol') for t in final_trades if t.get('status') == 'OPEN'])
            
            if symbol in final_symbols:
                logger.error(f"⛔⛔⛔ منع نهائي لتداول {symbol} - وُجدت في قائمة العملات المتداولة: {final_symbols} ⛔⛔⛔")
                return False
                
            logger.warning(f"✅ تم التحقق نهائياً من عدم وجود صفقات على {symbol} - الفحص الثالث")
        except Exception as e:
            logger.error(f"خطأ في الفحص النهائي: {e}")
            return False
            
        # التحقق أولاً من وجود العملة في القائمة السوداء
        from app.config import API_UNSUPPORTED_SYMBOLS
        if symbol in API_UNSUPPORTED_SYMBOLS:
            logger.warning(f"العملة {symbol} موجودة في القائمة السوداء ولا يمكن التداول عليها.")
            return False
        
        # الحصول على السعر الحالي
        current_price = get_current_price(symbol)
        if not current_price:
            logger.error(f"Failed to get price for {symbol}")
            return False
        
        # ⭐⭐⭐ تسجيل محاولة تنفيذ صفقة بتفاصيل كاملة ⭐⭐⭐
        logger.info(f"⭐⭐⭐ محاولة تنفيذ صفقة: {symbol} بكمية {quantity} عند سعر {current_price} ⭐⭐⭐")
        
        # تحضير المعلومات
        trades = load_trades()
        order_executed = False
        error_message = None
        
        # ⭐⭐⭐ التحقق من صلاحيات API قبل محاولة التنفيذ ⭐⭐⭐
        from app.mexc_api import test_api_permissions
        permissions = test_api_permissions()
        
        if not permissions.get('trade_permission', False):
            logger.error(f"⛔ لا توجد صلاحيات تداول كافية لتنفيذ صفقة على {symbol}")
            return False
            
        logger.info(f"✅ صلاحيات API كافية للتداول: {permissions}")
        
        # تنفيذ صفقة فعلية عبر API المنصة النشطة
        try:
            logger.info(f"🚀 محاولة تنفيذ صفقة فعلية لـ {symbol} بكمية {quantity} على منصة {ACTIVE_EXCHANGE}")
            
            # مسح أي قيم null
            if not symbol or not quantity:
                logger.error(f"قيم غير صالحة: {symbol=}, {quantity=}")
                return False
                
            # التحقق من السعر وتقدير القيمة للصفقة
            price_estimate = current_price * float(quantity)
            logger.info(f"💰 القيمة التقديرية للصفقة: {price_estimate} USDT للعملة {symbol}")
            
            # التحقق من أن قيمة الصفقة تتجاوز الحد الأدنى المحدد في config.py
            if price_estimate < MIN_TRADE_AMOUNT:  # 2.80 كما هو محدد في ملف config.py
                logger.warning(f"قيمة الصفقة صغيرة جداً ({price_estimate} USDT). يجب أن تكون أكبر من {MIN_TRADE_AMOUNT} USDT. تم التخطي.")
                return False
            
            # تحسين دقة الكمية
            try_quantity = float(f"{float(quantity):.6f}")
            logger.info(f"📊 استخدام كمية منسقة: {try_quantity} للتداول على {symbol}")
            
            # محاولة تنفيذ الصفقة - نستخدم MEXC فقط الآن
            
            # ⭐⭐⭐ لتنفيذ الصفقات بشكل فعلي، نستخدم مباشرة واجهة MEXC API ⭐⭐⭐
            from app.mexc_api import place_order as mexc_direct_place_order
            
            # أولاً: نحاول الحصول على معلومات دقة الكمية للعملة
            try:
                from app.mexc_api import get_exchange_info
                exchange_info = get_exchange_info()
                symbol_info = None
                
                if exchange_info and 'symbols' in exchange_info:
                    for info in exchange_info['symbols']:
                        if info.get('symbol') == symbol:
                            symbol_info = info
                            break
                
                # الحصول على دقة الكمية المطلوبة للعملة
                quantity_precision = 4  # القيمة الافتراضية
                if symbol_info and 'filters' in symbol_info:
                    for filter_item in symbol_info['filters']:
                        if filter_item.get('filterType') == 'LOT_SIZE':
                            step_size = filter_item.get('stepSize', '0.0001')
                            if float(step_size) < 1:
                                step_str = str(step_size).rstrip('0').rstrip('.')
                                decimal_places = len(step_str) - step_str.find('.') - 1
                                quantity_precision = decimal_places
                                logger.info(f"📏 تم تحديد دقة الكمية للعملة {symbol}: {quantity_precision} أرقام عشرية")
                
                # ضبط الكمية بدقة مناسبة
                if quantity_precision == 0:
                    formatted_quantity = str(int(try_quantity))
                else:
                    formatted_quantity = "{:.{}f}".format(try_quantity, quantity_precision)
                    # إزالة الأصفار النهائية
                    formatted_quantity = formatted_quantity.rstrip('0').rstrip('.') if '.' in formatted_quantity else formatted_quantity
                
                logger.info(f"🎯 الكمية النهائية المستخدمة للتداول: {formatted_quantity} {symbol}")
                
                # ⭐⭐⭐ تنفيذ الأمر مباشرة عبر MEXC API ⭐⭐⭐
                order_result = mexc_direct_place_order(symbol, "BUY", formatted_quantity, None, "MARKET")
                
                if order_result and isinstance(order_result, dict) and 'orderId' in order_result:
                    order_executed = True
                    logger.info(f"✅ تم تنفيذ الصفقة بنجاح! معرف الأمر: {order_result['orderId']}")
                    logger.info(f"✅ تفاصيل الأمر المنفذ: {order_result}")
                else:
                    logger.error(f"❌ فشل تنفيذ الأمر! نتيجة: {order_result}")
                
            except Exception as format_error:
                logger.error(f"خطأ في تنسيق الكمية أو الحصول على معلومات العملة: {format_error}")
                
                # نحاول تنفيذ الأمر بالكمية الأصلية
                order_result = mexc_direct_place_order(symbol, "BUY", try_quantity, None, "MARKET")
                
                if order_result and isinstance(order_result, dict) and 'orderId' in order_result:
                    order_executed = True
                    logger.info(f"✅ تم تنفيذ الصفقة بالكمية الأصلية بنجاح! معرف الأمر: {order_result['orderId']}")
                else:
                    logger.error(f"❌ فشل تنفيذ الأمر! نتيجة: {order_result}")
                
        except Exception as api_error:
            logger.error(f"فشل تنفيذ الصفقة عبر API: {api_error}")
            error_message = str(api_error)
            
            # محاولة أخرى بتعديل الكمية إذا كانت المشكلة في دقة الكمية
            if "quantity scale is invalid" in str(api_error).lower() or "invalid lot size" in str(api_error).lower():
                try:
                    from app.mexc_api import place_order as mexc_direct_place_order
                    # تقليل الكمية بنسبة 1% واستخدام 4 أرقام عشرية كحد أقصى
                    rounded_quantity = "{:.4f}".format(float(quantity) * 0.99)
                    logger.info(f"🔄 محاولة ثانية بكمية مصححة: {rounded_quantity} للعملة {symbol}")
                    
                    # تنفيذ الأمر مباشرة عبر MEXC API
                    order_result = mexc_direct_place_order(symbol, "BUY", rounded_quantity, None, "MARKET")
                    
                    if order_result and isinstance(order_result, dict) and 'orderId' in order_result:
                        order_executed = True
                        quantity = rounded_quantity
                        logger.info(f"✅ نجحت المحاولة الثانية! معرف الأمر: {order_result['orderId']}")
                    else:
                        logger.error(f"❌ فشل تنفيذ الأمر في المحاولة الثانية! نتيجة: {order_result}")
                        
                except Exception as retry_error:
                    logger.error(f"فشلت المحاولة الثانية أيضًا: {retry_error}")
            
            # محاولة ثالثة بتعديل مختلف للكمية
            try:
                # تجربة كمية صغيرة ثابتة كملاذ أخير إذا كان الأمر يتعلق بدقة الكمية
                from app.mexc_api import place_order as mexc_direct_place_order
                
                # استخدام كمية صغيرة جدًا للتحقق من قدرة API على تنفيذ الصفقات
                min_test_quantity = 0.001  # كمية صغيرة للاختبار
                logger.info(f"🧪 محاولة ثالثة (اختبارية) بكمية صغيرة: {min_test_quantity} للعملة {symbol}")
                
                # تنفيذ أمر اختباري
                test_order_result = mexc_direct_place_order(symbol, "BUY", min_test_quantity, None, "MARKET")
                
                if test_order_result and isinstance(test_order_result, dict) and 'orderId' in test_order_result:
                    # الأمر الاختباري نجح! لكن نحاول بالكمية الأصلية مجددًا لاحقًا
                    logger.info(f"✳️ نجح الأمر الاختباري! معرف الأمر: {test_order_result['orderId']}")
                    logger.info(f"⚠️ كان هناك مشكلة مع الكمية الأصلية، يرجى تعديل طريقة حساب الكمية أو التواصل مع الدعم الفني!")
                else:
                    logger.error(f"❌ فشل حتى الأمر الاختباري! المشكلة أعمق من مجرد دقة الكمية!")
            except Exception as test_error:
                logger.error(f"فشلت المحاولة الثالثة (الاختبارية): {test_error}")
        
        # حفظ المعلومات محليًا فقط إذا تم تنفيذ الصفقة بنجاح عبر API
        if order_executed:
            # تعريف متغير لحفظ معلومات الصفقة
            final_order_info = {
                'orderId': '',
                'executed': True
            }
            
            # الحصول على معرف الأمر الصحيح من الإطار الحالي
            # في حال نجاح أي من محاولات التنفيذ
            current_locals = locals()
            
            if 'order_result' in current_locals and current_locals['order_result'] and isinstance(current_locals['order_result'], dict):
                final_order_info = current_locals['order_result']
            
            # تحقق إضافي من وجود الصفقة فعلياً عن طريق API
            try:
                from app.mexc_api import get_open_orders
                open_orders = get_open_orders(symbol)
                logger.info(f"التحقق من الأوامر المفتوحة: {open_orders}")
                
                # عملة MEXC تنفذ أوامر السوق فورياً، لذلك نتحقق من تاريخ الصفقات الأخيرة بدلاً من الأوامر المفتوحة
                from app.mexc_api import fetch_recent_trades
                recent_trades = fetch_recent_trades(symbol, limit=10)
                
                if not recent_trades:
                    logger.warning(f"⚠️ لم يتم العثور على صفقات حديثة للعملة {symbol}")
                    if not open_orders:
                        logger.warning(f"⚠️ كما لم يتم العثور على أوامر مفتوحة للعملة {symbol}")
                        logger.error(f"❌ هناك تناقض - API أكد تنفيذ الصفقة ولكن لا يوجد تأكيد في تاريخ الصفقات أو الأوامر المفتوحة!")
                        
                        # تحقق نهائي قبل تسجيل الصفقة - التأكد من أن API أعطى orderId صحيح
                        if not final_order_info.get('orderId'):
                            logger.error(f"❌ لا يوجد معرف أمر صالح - لن يتم تسجيل هذه الصفقة محلياً!")
                            return False
                
                # التحقق من أن API لم يرجع خطأ
                if final_order_info.get('code') and final_order_info.get('code') != 200:
                    logger.error(f"❌ API أعاد رمز خطأ: {final_order_info.get('code')} - {final_order_info.get('msg')}")
                    return False
            except Exception as verify_error:
                logger.error(f"خطأ أثناء التحقق من وجود الصفقة فعلياً: {verify_error}")
                # استمر رغم ذلك لأن منصة MEXC قد تكون أكدت الصفقة عبر واجهة البرمجة
            
            # إنشاء مستويات متعددة لجني الأرباح وفقًا للإستراتيجية الجديدة
            new_trade = {
                'symbol': symbol,
                'quantity': float(quantity),
                'entry_price': current_price,
                'take_profit': round(current_price * (1 + TAKE_PROFIT), 8),
                'take_profit_2': round(current_price * (1 + TAKE_PROFIT_2), 8),
                'take_profit_3': round(current_price * (1 + TAKE_PROFIT_3), 8),
                'stop_loss': round(current_price * (1 - STOP_LOSS), 8),
                'timestamp': int(time.time() * 1000),
                'status': 'OPEN',
                'api_executed': True,
                'order_id': final_order_info.get('orderId', ''),  # حفظ معرف الأمر للتحقق لاحقاً
                'error': None,
                'strategy': {
                    'multi_timeframe': USE_MULTI_TIMEFRAME,
                    'trend_timeframe': TIMEFRAMES["trend"],
                    'signal_timeframe': TIMEFRAMES["signal"],
                    'entry_timeframe': TIMEFRAMES["entry"]
                }
            }
            
            trades.append(new_trade)
            save_trades(trades)
            logger.info(f"💾 تم حفظ صفقة حقيقية جديدة: {symbol} بسعر {current_price}")
            
            # إرسال إشعار تلجرام بالصفقة الجديدة إذا كان موجوداً
            try:
                from app.telegram_notify import send_telegram_message
                message = f"🟢 صفقة جديدة: {symbol}\n💰 السعر: {current_price}\n📊 الكمية: {quantity}\n⏱️ التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🆔 معرف الأمر: {final_order_info.get('orderId', 'غير معروف')}"
                send_telegram_message(message)
            except Exception as telegram_error:
                logger.warning(f"لم يتم إرسال إشعار تلجرام: {telegram_error}")
                
            return True
        else:
            logger.warning(f"⚠️ لم يتم تنفيذ الصفقة بنجاح عبر API، لن يتم تسجيلها محلياً: {symbol}")
            return False

    except Exception as e:
        logger.error(f"Error executing trade for {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def close_executed_trade(symbol):
    """
    إغلاق صفقة مفتوحة وتحديث حالتها
    يمكن إغلاق جميع الصفقات المفتوحة لنفس العملة دفعة واحدة
    
    :param symbol: رمز العملة
    :return: True إذا تم إغلاق الصفقة بنجاح، False خلاف ذلك
    """
    try:
        trades = load_trades()
        trades_to_close = []
        total_quantity = 0
        
        # تحديد جميع الصفقات المفتوحة للعملة المطلوبة
        for t in trades:
            if t.get('symbol') == symbol and t.get('status') == 'OPEN':
                trades_to_close.append(t)
                total_quantity += float(t.get('quantity', 0))
        
        if not trades_to_close:
            logger.warning(f"لا توجد صفقات مفتوحة للعملة {symbol}")
            return False
        
        # التحقق من الرصيد الفعلي قبل البيع
        try:
            # استخدام get_balance من exchange_manager
            crypto_balance = get_balance(symbol.replace('USDT', ''))
            if crypto_balance < total_quantity * 0.99:  # تحقق مع هامش 1% للتقريب
                logger.warning(f"لا يوجد رصيد كافٍ لبيع {symbol} على منصة {ACTIVE_EXCHANGE}. الكمية المطلوبة: {total_quantity}, الرصيد الفعلي: {crypto_balance}")
                # تعديل الكمية لتتناسب مع الرصيد الفعلي
                total_quantity = crypto_balance * 0.99  # استخدام 99% من الرصيد المتاح للأمان
        except Exception as balance_error:
            logger.error(f"خطأ في التحقق من الرصيد: {balance_error}")
        
        # تنفيذ أمر البيع دفعة واحدة لجميع الكمية
        current_price = get_current_price(symbol)
        if not current_price:
            logger.error(f"فشل في الحصول على سعر {symbol}")
            return False
        
        # تنفيذ أمر بيع إجمالي واحد بدلاً من أوامر متعددة
        sell_executed = False
        try:
            if total_quantity > 0:
                # ضبط دقة الكمية
                try_quantity = float(f"{float(total_quantity):.6f}")
                logger.info(f"محاولة تنفيذ أمر بيع لكمية إجمالية {try_quantity} من {symbol} على منصة {ACTIVE_EXCHANGE}")
                
                # استخدام place_order من exchange_manager حيث يتم توجيهه إلى MEXC
                order_result = place_order(symbol, "SELL", try_quantity, price=None, order_type="MARKET")
                
                if order_result and isinstance(order_result, dict) and 'orderId' in order_result:
                    sell_executed = True
                    logger.info(f"تم تنفيذ بيع {symbol} بنجاح! معرف الأمر: {order_result['orderId']}")
            else:
                logger.warning(f"كمية الصفقة أقل من أو تساوي الصفر: {total_quantity}")
        except Exception as api_error:
            logger.error(f"فشل تنفيذ البيع عبر API: {api_error}")
            
            # محاولة أخرى بتعديل الكمية إذا كانت المشكلة في دقة الكمية
            if "quantity scale is invalid" in str(api_error).lower() or "invalid lot size" in str(api_error).lower():
                try:
                    rounded_quantity = float(f"{float(total_quantity) * 0.98:.5f}")
                    logger.info(f"محاولة ثانية بكمية مصححة: {rounded_quantity} على منصة {ACTIVE_EXCHANGE}")
                    
                    # استخدام place_order من exchange_manager
                    order_result = place_order(symbol, "SELL", rounded_quantity, price=None, order_type="MARKET")
                    
                    if order_result and isinstance(order_result, dict) and 'orderId' in order_result:
                        sell_executed = True
                        logger.info(f"نجحت المحاولة الثانية! معرف الأمر: {order_result['orderId']}")
                except Exception as retry_error:
                    logger.error(f"فشلت المحاولة الثانية أيضًا: {retry_error}")
        
        # تحديث حالات الصفقات بغض النظر عن نجاح تنفيذ البيع
        updated = False
        for t in trades_to_close:
            t['status'] = 'CLOSED'
            t['close_price'] = current_price
            t['close_timestamp'] = int(time.time() * 1000)
            t['api_executed'] = sell_executed
            
            if current_price > t['entry_price']:
                profit_pct = (current_price - t['entry_price']) / t['entry_price'] * 100
                t['profit_pct'] = round(profit_pct, 2)
                t['result'] = 'PROFIT'
            else:
                loss_pct = (current_price - t['entry_price']) / t['entry_price'] * 100
                t['profit_pct'] = round(loss_pct, 2)
                t['result'] = 'LOSS'
                
            updated = True
        
        if updated:
            save_trades(trades)
            status_msg = "تنفيذ فعلي" if sell_executed else "تتبع محلي فقط"
            logger.info(f"تم إغلاق {len(trades_to_close)} صفقة لـ {symbol} ({status_msg})")
            send_telegram_message(f"تم بيع {total_quantity} من {symbol} بسعر {current_price} - {status_msg}")
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"خطأ في إغلاق صفقة {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def check_trades():
    """
    التحقق من حالة الصفقات المفتوحة وتنفيذ الإجراءات المناسبة
    """
    try:
        trades = load_trades()
        updated = False
        
        # التحقق من وجود صفقات ناقصة البيانات وإصلاحها
        for i, t in enumerate(trades):
            # إضافة حقول مفقودة
            if 'symbol' not in t:
                logger.warning(f"صفقة بدون رمز عملة في الموضع {i}. سيتم تعليمها كمغلقة.")
                t['status'] = 'CLOSED'
                t['symbol'] = 'UNKNOWN'
                updated = True
                
            # تأكد من احتواء الصفقات المغلقة على حقول الربح/الخسارة
            if t.get('status') == 'CLOSED' and 'profit_pct' not in t and 'close_price' in t and 'entry_price' in t:
                try:
                    entry_price = float(t.get('entry_price', 0))
                    close_price = float(t.get('close_price', 0))
                    
                    if entry_price > 0 and close_price > 0:
                        profit_pct = (close_price - entry_price) / entry_price * 100
                        t['profit_pct'] = round(profit_pct, 2)
                        t['result'] = 'PROFIT' if profit_pct > 0 else 'LOSS'
                        updated = True
                        logger.info(f"تم إضافة بيانات الربح/الخسارة لصفقة مغلقة: {t.get('symbol', 'UNKNOWN')}, {profit_pct:.2f}%")
                except Exception as calc_err:
                    logger.error(f"خطأ في حساب الربح/الخسارة: {calc_err}")
                    
        # الآن نتحقق من الصفقات المفتوحة
        for t in trades:
            if t.get('status') != 'OPEN':
                continue
                
            symbol = t.get('symbol')
            entry_price = t.get('entry_price')
            current_price = get_current_price(symbol)
            
            if not current_price:
                continue
                
            # الحصول على إعدادات وقف الخسارة الذكي من ملف التكوين
            from app.config import SMART_STOP_LOSS, SMART_STOP_THRESHOLD
            
            # حساب نسبة الربح/الخسارة الحالية
            current_pct_change = (current_price - entry_price) / entry_price * 100
            
            # تحديد ما إذا يجب إغلاق الصفقة
            should_close = False
            close_reason = ""
            
            # استراتيجية جني الأرباح المتعددة باستخدام تحليل الإطارات الزمنية المتعددة
            
            # التحقق مما إذا كان السعر قد وصل لأي من مستويات الربح
            profit_level_reached = 0
            if 'take_profit_3' in t and current_price >= t.get('take_profit_3'):
                profit_level_reached = 3
            elif 'take_profit_2' in t and current_price >= t.get('take_profit_2'):
                profit_level_reached = 2
            elif current_price >= t.get('take_profit'):
                profit_level_reached = 1
                
            # إذا وصلنا لأي مستوى ربح، نقوم بتحليل الوضع الحالي للسوق لاتخاذ القرار الأمثل
            if profit_level_reached > 0:
                should_hold = False  # افتراضيًا سنقوم بالبيع وجني الأرباح
                
                try:
                    # نحاول تحليل الإطارات الزمنية المتعددة قبل اتخاذ القرار
                    from app.config import TIMEFRAMES, USE_MULTI_TIMEFRAME
                    from app.ai_model import analyze_market_sentiment, predict_trend
                    from app.exchange_manager import get_klines
                    
                    # متغيرات التحليل
                    trend_1h = 'neutral'
                    trend_15m = 'neutral'
                    trend_5m = 'neutral'
                    sentiment_value = 'neutral'
                    
                    if USE_MULTI_TIMEFRAME:
                        # جلب بيانات الإطارات الزمنية للتحليل
                        klines_1h = get_klines(symbol, TIMEFRAMES["trend"], 25)
                        klines_15m = get_klines(symbol, TIMEFRAMES["signal"], 30)
                        klines_5m = get_klines(symbol, TIMEFRAMES["entry"], 20)
                        
                        # تحليل الاتجاهات
                        if klines_1h and len(klines_1h) >= 10:
                            trend_1h_result = predict_trend(klines_1h)
                            trend_1h = trend_1h_result[0] if isinstance(trend_1h_result, tuple) and len(trend_1h_result) >= 1 else 'neutral'
                        
                        if klines_15m and len(klines_15m) >= 10:
                            trend_15m_result = predict_trend(klines_15m)
                            trend_15m = trend_15m_result[0] if isinstance(trend_15m_result, tuple) and len(trend_15m_result) >= 1 else 'neutral'
                            
                            # تحليل الشعور العام
                            sentiment = analyze_market_sentiment(klines_15m)
                            sentiment_value = sentiment.get('sentiment', 'neutral')
                        
                        if klines_5m and len(klines_5m) >= 10:
                            trend_5m_result = predict_trend(klines_5m)
                            trend_5m = trend_5m_result[0] if isinstance(trend_5m_result, tuple) and len(trend_5m_result) >= 1 else 'neutral'
                        
                        # قرار ما إذا كان يجب الاحتفاظ بالصفقة للحصول على ربح أكبر
                        if profit_level_reached == 1:  # وصلنا للمستوى الأول من الربح (1%)
                            # إذا كانت جميع المؤشرات صاعدة، نحتفظ للمستوى الثاني
                            if trend_1h == 'up' and trend_15m == 'up' and trend_5m == 'up':
                                should_hold = True
                                logger.info(f"🔍 تحليل متعدد الإطارات: الاحتفاظ بـ {symbol} بعد الوصول لمستوى الربح الأول، جميع المؤشرات صاعدة")
                                send_telegram_message(f"💡 استراتيجية متقدمة: احتفاظ {symbol} (ربح: {round(current_pct_change, 2)}%)، جميع المؤشرات صاعدة، نتوقع ربح أكبر")
                            # أو إذا كان الاتجاه العام قوياً مع شعور إيجابي
                            elif trend_1h == 'up' and sentiment_value in ['bullish', 'strongly_bullish']:
                                should_hold = True
                                logger.info(f"🔍 تحليل متعدد الإطارات: الاحتفاظ بـ {symbol} بعد الوصول لمستوى الربح الأول، اتجاه قوي وشعور إيجابي")
                                send_telegram_message(f"💡 استراتيجية متقدمة: احتفاظ {symbol} (ربح: {round(current_pct_change, 2)}%)، اتجاه عام صاعد مع شعور إيجابي")
                                
                        elif profit_level_reached == 2:  # وصلنا للمستوى الثاني من الربح (2%)
                            # نبقي فقط إذا كانت كل الظروف مثالية
                            if trend_1h == 'up' and trend_15m == 'up' and trend_5m == 'up' and sentiment_value == 'strongly_bullish':
                                should_hold = True
                                logger.info(f"🔍 تحليل متعدد الإطارات: الاحتفاظ بـ {symbol} بعد الوصول لمستوى الربح الثاني، ظروف مثالية")
                                send_telegram_message(f"💡 استراتيجية متقدمة: احتفاظ {symbol} (ربح: {round(current_pct_change, 2)}%)، جميع المؤشرات ممتازة، نتوقع الوصول للمستوى الثالث")
                    
                except Exception as analysis_error:
                    logger.error(f"خطأ في تحليل الإطارات الزمنية عند جني الأرباح: {analysis_error}")
                    # في حالة الخطأ، نتخذ القرار الآمن بجني الأرباح
                    should_hold = False
                
                # اتخاذ القرار النهائي بناءً على التحليل
                if should_hold:
                    # لا نغلق الصفقة ونسمح لها بالاستمرار للوصول لمستوى ربح أعلى
                    should_close = False
                else:
                    # إغلاق الصفقة وجني الأرباح على المستوى الحالي
                    should_close = True
                    
                    if profit_level_reached == 3:
                        close_reason = f"🟢🟢🟢 جني أرباح مستوى 3: {symbol} بسعر {current_price} (ربح: {round(current_pct_change, 2)}%)"
                    elif profit_level_reached == 2:
                        close_reason = f"🟢🟢 جني أرباح مستوى 2: {symbol} بسعر {current_price} (ربح: {round(current_pct_change, 2)}%)"
                    else:
                        close_reason = f"🟢 جني أرباح مستوى 1: {symbol} بسعر {current_price} (ربح: {round(current_pct_change, 2)}%)"
            
            # حالة الخسارة - تطبيق استراتيجية وقف الخسارة الذكي مع تحليل الإطارات الزمنية المتعددة
            elif current_price <= t.get('stop_loss'):
                from app.config import TIMEFRAMES, USE_MULTI_TIMEFRAME
                from app.ai_model import analyze_market_sentiment, identify_trend_reversal, predict_trend
                from app.exchange_manager import get_klines

                # متغير للتتبع إذا تم تحليل الإطارات الزمنية أم لا
                multi_timeframe_analyzed = False
                
                # متغيرات التحليل
                trend_1h = 'neutral'
                trend_15m = 'neutral'
                trend_5m = 'neutral'
                reversal_potential = False
                sentiment_value = 'neutral'
                sentiment_confidence = 0.0
                
                try:
                    if USE_MULTI_TIMEFRAME:
                        # 1. جلب بيانات من ثلاثة إطارات زمنية
                        klines_1h = get_klines(symbol, TIMEFRAMES["trend"], 25)  # إطار ساعة (اتجاه)
                        klines_15m = get_klines(symbol, TIMEFRAMES["signal"], 30)  # إطار 15 دقيقة (إشارة)
                        klines_5m = get_klines(symbol, TIMEFRAMES["entry"], 20)  # إطار 5 دقائق (دخول)
                        
                        # 2. تحليل الاتجاه في كل إطار زمني
                        if klines_1h and len(klines_1h) >= 10:
                            trend_1h_result = predict_trend(klines_1h)
                            trend_1h = trend_1h_result[0] if isinstance(trend_1h_result, tuple) and len(trend_1h_result) >= 1 else 'neutral'
                        
                        if klines_15m and len(klines_15m) >= 10:
                            trend_15m_result = predict_trend(klines_15m)
                            trend_15m = trend_15m_result[0] if isinstance(trend_15m_result, tuple) and len(trend_15m_result) >= 1 else 'neutral'
                            
                            # تحليل الشعور العام للسوق
                            sentiment = analyze_market_sentiment(klines_15m)
                            sentiment_value = sentiment.get('sentiment', 'neutral')
                            sentiment_confidence = sentiment.get('confidence', 0.0)
                            
                            # التحقق من احتمال انعكاس الاتجاه
                            reversal_potential = not identify_trend_reversal(klines_15m)
                        
                        if klines_5m and len(klines_5m) >= 10:
                            trend_5m_result = predict_trend(klines_5m)
                            trend_5m = trend_5m_result[0] if isinstance(trend_5m_result, tuple) and len(trend_5m_result) >= 1 else 'neutral'
                        
                        # تحديد أن التحليل متعدد الإطارات تم بنجاح
                        multi_timeframe_analyzed = True
                        logger.info(f"تحليل الإطارات الزمنية المتعددة لـ {symbol}: 1h={trend_1h}, 15m={trend_15m}, 5m={trend_5m}")
                    else:
                        # استخدام التحليل التقليدي (إطار زمني واحد)
                        klines = get_klines(symbol, '15m', 30)
                        if klines and len(klines) >= 20:
                            # تحليل الشعور العام للسوق
                            sentiment = analyze_market_sentiment(klines)
                            sentiment_value = sentiment.get('sentiment', 'neutral')
                            sentiment_confidence = sentiment.get('confidence', 0.0)
                            
                            # التحقق من احتمال انعكاس الاتجاه
                            reversal_potential = not identify_trend_reversal(klines)
                except Exception as analysis_error:
                    logger.error(f"خطأ في تحليل الإطارات الزمنية المتعددة: {analysis_error}")
                    # استخدام استراتيجية الخروج التقليدية في حالة الخطأ
                    should_close = True
                    close_reason = f"🔴 وقف خسارة: {symbol} بسعر {current_price} (خسارة: {round(current_pct_change, 2)}%) - خطأ في التحليل"
                    
                # اتخاذ القرار بناءً على نتائج التحليل متعدد الإطارات
                if multi_timeframe_analyzed:
                    # الحالة المثالية: جميع الإطارات الزمنية تشير إلى اتجاه صاعد
                    if trend_1h == 'up' and trend_15m == 'up' and trend_5m == 'up':
                        # فرصة ارتداد قوية جداً - يمكن الاحتفاظ طالما الخسارة محدودة
                        if abs(current_pct_change) < SMART_STOP_THRESHOLD:
                            should_close = False
                            logger.info(f"🧠🧠🧠 استراتيجية ذكية متعددة الإطارات: الاحتفاظ بـ {symbol} (ثقة عالية جداً في الارتداد)")
                            send_telegram_message(f"🧠🧠🧠 استراتيجية متقدمة: احتفاظ {symbol} (خسارة: {round(current_pct_change, 2)}%)، جميع الإطارات الزمنية صاعدة")
                        else:
                            should_close = True
                            close_reason = f"🔴 وقف خسارة: {symbol} بسعر {current_price} (خسارة: {round(current_pct_change, 2)}%) - تجاوزت العتبة المسموح بها رغم الإشارات الإيجابية"
                    
                    # الحالة القوية: الاتجاه العام صاعد والإطار المتوسط صاعد
                    elif trend_1h == 'up' and trend_15m == 'up':
                        # فرصة ارتداد قوية - يمكن الاحتفاظ طالما الخسارة معقولة
                        if abs(current_pct_change) < (SMART_STOP_THRESHOLD * 0.8):
                            should_close = False
                            logger.info(f"🧠🧠 استراتيجية ذكية متعددة الإطارات: الاحتفاظ بـ {symbol} (ثقة عالية في الارتداد)")
                            send_telegram_message(f"🧠🧠 استراتيجية متقدمة: احتفاظ {symbol} (خسارة: {round(current_pct_change, 2)}%)، الإطارات الزمنية 1h و 15m صاعدة")
                        else:
                            should_close = True
                            close_reason = f"🔴 وقف خسارة: {symbol} بسعر {current_price} (خسارة: {round(current_pct_change, 2)}%) - تجاوزت العتبة المسموح بها"
                    
                    # الحالة المتوسطة: الاتجاه العام صاعد وشعور السوق إيجابي
                    elif trend_1h == 'up' and sentiment_value in ['bullish', 'strongly_bullish']:
                        # فرصة ارتداد متوسطة - أكثر حذراً مع حد الخسارة
                        if abs(current_pct_change) < (SMART_STOP_THRESHOLD * 0.6):
                            should_close = False
                            logger.info(f"🧠 استراتيجية ذكية متعددة الإطارات: الاحتفاظ بـ {symbol} (ثقة متوسطة في الارتداد)")
                            send_telegram_message(f"🧠 استراتيجية متقدمة: احتفاظ {symbol} (خسارة: {round(current_pct_change, 2)}%)، الاتجاه العام صاعد مع شعور إيجابي للسوق")
                        else:
                            should_close = True
                            close_reason = f"🔴 وقف خسارة: {symbol} بسعر {current_price} (خسارة: {round(current_pct_change, 2)}%) - تجاوزت العتبة المسموح بها رغم الاتجاه العام الصاعد"
                    
                    # في حالة تعارض التحليلات أو عدم وجود اتجاه واضح
                    else:
                        # نستخدم احتمال الانعكاس والشعور العام كعوامل ثانوية
                        if reversal_potential and sentiment_value in ['bullish', 'strongly_bullish'] and abs(current_pct_change) < (SMART_STOP_THRESHOLD * 0.4):
                            should_close = False
                            logger.info(f"🧠 استراتيجية ذكية: الاحتفاظ بـ {symbol} (احتمال ارتداد مع مؤشرات إيجابية)")
                            send_telegram_message(f"🧠 استراتيجية متقدمة: احتفاظ {symbol} (خسارة: {round(current_pct_change, 2)}%)، احتمال ارتداد مع شعور سوق إيجابي")
                        else:
                            should_close = True
                            close_reason = f"🔴 وقف خسارة: {symbol} بسعر {current_price} (خسارة: {round(current_pct_change, 2)}%) - تحليل الإطارات الزمنية سلبي أو متعارض"
                
                # الاعتماد على التحليل التقليدي إذا لم يتم تنفيذ التحليل متعدد الإطارات
                elif SMART_STOP_LOSS and sentiment_value in ['bullish', 'strongly_bullish'] and reversal_potential:
                    # التحقق من أن الخسارة لم تتجاوز العتبة المسموح بها
                    if abs(current_pct_change) < SMART_STOP_THRESHOLD:
                        # لا نغلق الصفقة ونراهن على الارتداد
                        should_close = False
                        logger.info(f"🧠 استراتيجية وقف الخسارة الذكي: الاحتفاظ بـ {symbol} رغم الوصول لوقف الخسارة، نتوقع ارتداد قريب")
                        send_telegram_message(f"🧠 وقف خسارة ذكي: احتفاظ {symbol} (خسارة: {round(current_pct_change, 2)}%)، تحليلات السوق إيجابية")
                    else:
                        # إذا تجاوزت الخسارة العتبة المسموح بها، نغلق الصفقة
                        should_close = True
                        close_reason = f"🔴 وقف خسارة: {symbol} بسعر {current_price} (خسارة: {round(current_pct_change, 2)}%) - تجاوزت العتبة المسموح بها"
                else:
                    # وقف الخسارة العادي إذا لم يكن التحليل إيجابياً
                    should_close = True
                    close_reason = f"🔴 وقف خسارة: {symbol} بسعر {current_price} (خسارة: {round(current_pct_change, 2)}%)"
            
            # إذا تقرر إغلاق الصفقة
            if should_close:
                # التحقق من وجود الصفقة في الأوامر المفتوحة على المنصة
                exchange_orders = get_open_orders(symbol)
                
                # إذا كانت الصفقة موجودة على المنصة، قم بإغلاقها
                if exchange_orders:
                    for order in exchange_orders:
                        if order.get('side') == 'BUY':
                            close_trade(symbol, t.get('quantity'))
                
                # تحديث حالة الصفقة في السجل المحلي
                t['status'] = 'CLOSED'
                t['close_price'] = current_price
                t['close_timestamp'] = int(time.time() * 1000)
                
                if current_price > entry_price:
                    profit_pct = (current_price - entry_price) / entry_price * 100
                    t['profit_pct'] = round(profit_pct, 2)
                    t['result'] = 'PROFIT'
                else:
                    loss_pct = (current_price - entry_price) / entry_price * 100
                    t['profit_pct'] = round(loss_pct, 2)
                    t['result'] = 'LOSS'
                
                # إرسال إشعار
                send_telegram_message(close_reason)
                updated = True
            else:
                logger.info(f"Trade for {symbol} is still active at price {current_price}")
                
        if updated:
            save_trades(trades)
    except Exception as e:
        logger.error(f"Error checking trades: {e}")

def monitor_trades():
    """
    مراقبة الصفقات في خلفية التشغيل
    """
    global BOT_RUNNING
    while BOT_RUNNING:
        try:
            check_trades()
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error in monitor_trades: {e}")
            time.sleep(30)  # أخذ استراحة أطول في حالة حدوث خطأ

def start_bot():
    """
    بدء تشغيل البوت
    """
    global BOT_RUNNING
    if not BOT_RUNNING:
        BOT_RUNNING = True
        thread = threading.Thread(target=monitor_trades, daemon=True)
        thread.start()
        logger.info("Bot started")
        send_telegram_message("🟢 تم تشغيل بوت التداول")

def stop_bot():
    """
    إيقاف البوت
    """
    global BOT_RUNNING
    if BOT_RUNNING:
        BOT_RUNNING = False
        logger.info("Bot stopped")
        send_telegram_message("🔴 تم إيقاف بوت التداول")

def get_performance_stats():
    """
    الحصول على إحصائيات أداء البوت
    
    :return: قاموس بإحصائيات الأداء
    """
    try:
        trades = load_trades()
        
        total_trades = len(trades)
        closed_trades = len([t for t in trades if t.get('status') == 'CLOSED'])
        open_trades = len([t for t in trades if t.get('status') == 'OPEN'])
        
        profit_trades = len([t for t in trades if t.get('result') == 'PROFIT'])
        loss_trades = len([t for t in trades if t.get('result') == 'LOSS'])
        
        win_rate = (profit_trades / closed_trades * 100) if closed_trades > 0 else 0
        
        total_profit = sum([t.get('profit_pct', 0) for t in trades if t.get('result') == 'PROFIT'])
        total_loss = sum([t.get('profit_pct', 0) for t in trades if t.get('result') == 'LOSS'])
        
        net_profit = total_profit + total_loss
        
        return {
            'total_trades': total_trades,
            'closed_trades': closed_trades,
            'open_trades': open_trades,
            'profit_trades': profit_trades,
            'loss_trades': loss_trades,
            'win_rate': round(win_rate, 2),
            'total_profit': round(total_profit, 2),
            'total_loss': round(total_loss, 2),
            'net_profit': round(net_profit, 2)
        }
    except Exception as e:
        logger.error(f"Error getting performance stats: {e}")
        return {
            'total_trades': 0,
            'closed_trades': 0,
            'open_trades': 0,
            'profit_trades': 0,
            'loss_trades': 0,
            'win_rate': 0,
            'total_profit': 0,
            'total_loss': 0,
            'net_profit': 0
        }
