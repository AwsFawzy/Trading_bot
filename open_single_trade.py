"""
ملف لفتح صفقة واحدة بطريقة مباشرة مع توثيق كامل لكل الخطوات
"""
import json
import logging
import time
import os
import random
import sys
from datetime import datetime

# إعداد التسجيل بمستوى تفصيلي عالي
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_trade.log')
    ]
)
logger = logging.getLogger('open_single_trade')

try:
    # استيراد المكونات المطلوبة
    from app.config import BASE_CURRENCY, MIN_TRADE_AMOUNT, TAKE_PROFIT, STOP_LOSS
    from app.mexc_api import get_balance, get_current_price
    from app.telegram_notify import send_telegram_message, notify_trade_status
    
    # استيراد وظائف التداول مباشرة من تنفيذ الصفقات أو من النظام الموحد
    try:
        logger.info("محاولة استيراد وظائف التداول من trading_system...")
        from app.trading_system import execute_buy, save_trades, load_trades
    except ImportError:
        logger.warning("لم يتم العثور على trading_system، محاولة استيراد وظائف التداول من mexc_api...")
        from app.mexc_api import create_market_order
except ImportError as e:
    logger.critical(f"فشل استيراد المكونات الأساسية: {e}")
    sys.exit(1)

# تعريف دوال المساعدة
def save_to_active_trades(trade_data):
    """حفظ بيانات صفقة جديدة في ملف الصفقات"""
    try:
        # تحميل البيانات الحالية
        try:
            with open('active_trades.json', 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"active": [], "history": []}
        
        # إضافة الصفقة الجديدة للصفقات النشطة
        if isinstance(data, dict) and "active" in data:
            data["active"].append(trade_data)
        else:
            # التعامل مع الهيكل القديم (إذا كان موجودًا)
            if isinstance(data, list):
                data = {"active": data, "history": []}
            else:
                data = {"active": [trade_data], "history": []}
        
        # حفظ البيانات
        with open('active_trades.json', 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"✅ تم حفظ بيانات الصفقة في ملف الصفقات")
        
        # إرسال إشعار تلجرام
        try:
            notify_trade_status(
                symbol=trade_data.get('symbol', 'غير معروف'),
                status="شراء جديد",
                price=trade_data.get('entry_price', 0),
                order_id=trade_data.get('order_id', None),
                api_verified=True
            )
            logger.info("✅ تم إرسال إشعار تلجرام")
        except Exception as e:
            logger.error(f"❌ خطأ في إرسال إشعار تلجرام: {e}")
            
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ الصفقة: {e}")
        return False

def select_profitable_symbol():
    """اختيار رمز محتمل للربح بناءً على العملات الشائعة ذات السيولة العالية"""
    # قائمة العملات المشهورة والأكثر تداولًا - تمت مراجعتها
    top_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'SOLUSDT', 'ATOMUSDT', 'LTCUSDT', 'TRXUSDT']
    
    # تجربة كل رمز في القائمة حتى نجد واحدًا يعمل
    for selected_symbol in top_symbols:
        try:
            # التحقق من السعر الحالي
            current_price = get_current_price(selected_symbol)
            
            # تأكد من أن السعر صالح
            if current_price and float(current_price) > 0:
                logger.info(f"✅ تم اختيار {selected_symbol} بسعر حالي {current_price}")
                return selected_symbol, float(current_price)
            else:
                logger.warning(f"⚠️ سعر غير صالح لـ {selected_symbol}: {current_price}")
                continue
            
        except Exception as e:
            logger.warning(f"⚠️ خطأ في اختيار الرمز {selected_symbol}: {e}")
            continue
    
    # إذا لم تنجح أي من الرموز، نجرب BTCUSDT صراحة
    try:
        logger.info("محاولة استخدام BTCUSDT كملاذ أخير...")
        current_price = get_current_price('BTCUSDT')
        if current_price:
            return 'BTCUSDT', float(current_price)
    except Exception as e:
        logger.error(f"❌ خطأ في الحصول على سعر BTCUSDT: {e}")
    
    # فشلت جميع المحاولات
    logger.error("❌ فشلت جميع محاولات الحصول على سعر لأي عملة")
    return None, 0.0

def open_trade():
    """فتح صفقة جديدة مع التوثيق الكامل لكل الخطوات"""
    try:
        # 1. التحقق من وجود رصيد USDT
        usdt_balance = get_balance(BASE_CURRENCY)
        logger.info(f"💰 رصيد {BASE_CURRENCY}: {usdt_balance}")
        
        if not usdt_balance or float(usdt_balance) < MIN_TRADE_AMOUNT:
            logger.error(f"❌ الرصيد غير كافٍ. الرصيد الحالي: {usdt_balance}, المطلوب: {MIN_TRADE_AMOUNT}")
            send_telegram_message(f"⚠️ لا يمكن فتح صفقة جديدة. الرصيد غير كافٍ ({usdt_balance} {BASE_CURRENCY}).")
            return False
        
        # 2. اختيار العملة المناسبة للتداول
        symbol, current_price = select_profitable_symbol()
        
        # التحقق من وجود رمز صالح وسعر صالح
        if not symbol or not current_price or current_price <= 0:
            logger.error(f"❌ تعذر الحصول على رمز أو سعر صالح للعملة: الرمز={symbol}, السعر={current_price}")
            send_telegram_message("⚠️ فشل فتح صفقة: تعذر الحصول على معلومات العملة الصحيحة.")
            return False
            
        # 3. حساب كمية العملة التي سيتم شراؤها
        amount_usdt = min(float(usdt_balance) * 0.15, 5.0)  # 15% من الرصيد أو 5 دولار كحد أقصى
        quantity = amount_usdt / current_price
        logger.info(f"📊 مبلغ الشراء: {amount_usdt} {BASE_CURRENCY}, الكمية: {quantity} من {symbol}")
        
        # 4. وقف الخسارة وهدف الربح
        stop_loss_price = current_price * (1 - STOP_LOSS)
        take_profit_price = current_price * (1 + TAKE_PROFIT)
        
        logger.info(f"🎯 هدف الربح: {take_profit_price} ({TAKE_PROFIT*100}%)")
        logger.info(f"🛑 وقف الخسارة: {stop_loss_price} ({STOP_LOSS*100}%)")
        
        # 5. إنشاء وتنفيذ أمر الشراء
        logger.info(f"🚀 جارٍ تنفيذ أمر الشراء...")
        
        # استخدام دالة execute_buy إذا كانت متاحة من trading_system
        order_result = None
        success = False
        
        try:
            # محاولة استخدام وظيفة التداول من trading_system
            from app.trading_system import execute_buy
            # هنا نكون متأكدين أن symbol ليس None لأننا تحققنا مسبقًا
            if symbol and amount_usdt > 0:
                success, order_result = execute_buy(symbol, amount_usdt)
                logger.info(f"نتيجة التنفيذ (trading_system): {success}")
            else:
                raise ValueError(f"بيانات الصفقة غير صالحة: الرمز={symbol}, المبلغ={amount_usdt}")
        except Exception as ts_err:
            # محاولة استخدام وظيفة التداول من mexc_api
            logger.warning(f"خطأ في استخدام trading_system.execute_buy: {ts_err}")
            logger.warning("محاولة استخدام وظائف بديلة...")
            
            try:
                from app.mexc_api import place_order
                
                # تنفيذ أمر شراء مباشر
                order_result = place_order(symbol, "BUY", quantity, None, "MARKET")
                
                if order_result and 'orderId' in order_result:
                    success = True
                    logger.info(f"نتيجة التنفيذ (place_order): {success}")
                else:
                    success = False
                    logger.error(f"فشل place_order: {order_result}")
            except Exception as market_err:
                logger.error(f"❌ خطأ في place_order: {market_err}")
                success = False
        
        # 6. حفظ بيانات الصفقة في حالة النجاح
        if success and order_result:
            logger.info(f"✅ تم تنفيذ أمر الشراء بنجاح: {order_result}")
            
            # إنشاء كائن الصفقة
            trade_data = {
                "symbol": symbol,
                "entry_price": current_price,
                "quantity": quantity,
                "entry_time": int(time.time() * 1000),
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
                "order_id": order_result.get("orderId") if isinstance(order_result, dict) else str(time.time()),
                "status": "OPEN",
                "api_confirmed": True,
                "api_executed": True,
                "entry_amount_usdt": amount_usdt
            }
            
            # حفظ الصفقة
            save_result = save_to_active_trades(trade_data)
            
            if save_result:
                logger.info(f"✅ تم فتح وحفظ الصفقة بنجاح: {symbol}")
                
                # إرسال إشعار بالنجاح
                message = f"""
🟢 تم فتح صفقة جديدة:
رمز: {symbol}
سعر الدخول: {current_price}
الكمية: {quantity}
هدف الربح: {take_profit_price} ({TAKE_PROFIT*100}%)
وقف الخسارة: {stop_loss_price} ({STOP_LOSS*100}%)
الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                send_telegram_message(message)
                
                return True
            else:
                logger.error("❌ فشل حفظ الصفقة، على الرغم من نجاح الأمر")
                return False
        else:
            logger.error(f"❌ فشل تنفيذ أمر الشراء")
            error_message = f"❌ فشل فتح صفقة جديدة على {symbol}. يرجى مراجعة السجلات لمزيد من التفاصيل."
            send_telegram_message(error_message)
            return False
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")
        # استخدام traceback لمزيد من التفاصيل
        import traceback
        logger.error(traceback.format_exc())
        send_telegram_message(f"⚠️ حدث خطأ غير متوقع أثناء فتح صفقة جديدة: {str(e)}")
        return False
    
if __name__ == "__main__":
    logger.info("🚀 بدء تنفيذ فتح صفقة جديدة...")
    
    # محاولة إرسال إشعار بدء العملية
    try:
        send_telegram_message("🔄 بدء عملية فتح صفقة جديدة للاختبار...")
    except Exception as e:
        logger.warning(f"⚠️ لم يمكن إرسال إشعار البدء: {e}")
    
    # تنفيذ فتح الصفقة
    result = open_trade()
    
    if result:
        logger.info("✅ تم فتح الصفقة بنجاح")
    else:
        logger.error("❌ فشل فتح الصفقة")
    
    # محاولة إرسال إشعار نهاية العملية
    try:
        final_message = "✅ تم فتح الصفقة بنجاح" if result else "❌ فشل فتح الصفقة. يرجى مراجعة السجلات للمزيد من التفاصيل."
        send_telegram_message(final_message)
    except Exception as e:
        logger.warning(f"⚠️ لم يمكن إرسال إشعار النهاية: {e}")