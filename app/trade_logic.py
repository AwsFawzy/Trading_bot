# app/trade_logic.py
import logging
import time
# استخدام مدير المنصات بدلاً من استهداف MEXC مباشرة
from app.exchange_manager import (
    get_klines, place_order, get_open_orders, get_current_price,
    get_balance, get_all_symbols_24h_data, get_account_balance,
    ACTIVE_EXCHANGE  # المنصة النشطة حالياً
)
from app.config import (
    BASE_CURRENCY, MAX_ACTIVE_TRADES, TOTAL_RISK_CAPITAL_RATIO,
    RISK_CAPITAL_RATIO, TAKE_PROFIT, TAKE_PROFIT_2, TAKE_PROFIT_3,
    STOP_LOSS, SMART_STOP_LOSS, SMART_STOP_THRESHOLD
)
from app.telegram_notify import send_telegram_message, notify_trade_status
from app.ai_model import predict_trend, filter_symbols_by_stability
from app.utils import calculate_percentage_change, format_price
from app.candlestick_patterns import get_entry_signal, calculate_take_profit_stop_loss

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trade_logic')

# Intentionally left empty since we're now using get_current_price directly from mexc_api.py

def get_open_trades():
    """
    الحصول على الصفقات المفتوحة
    
    :return: قائمة بالصفقات المفتوحة أو قائمة فارغة في حالة الفشل
    """
    try:
        return get_open_orders()
    except Exception as e:
        logger.error(f"Error getting open trades: {e}")
        return []

def close_trade(symbol, quantity):
    """
    إغلاق صفقة (بيع)
    
    :param symbol: رمز العملة
    :param quantity: الكمية
    :return: True في حالة النجاح، False في حالة الفشل
    """
    import traceback  # استيراد لتسجيل تفاصيل الأخطاء
    logger.info(f"⭐⭐⭐ تم استدعاء دالة close_trade لبيع {symbol} بكمية {quantity} ⭐⭐⭐")
    
    # تجربة مجموعة من تنسيقات الرموز المختلفة بشكل منهجي
    tried_symbols = []

    # إرسال إشعار عن محاولة البيع
    send_telegram_message(f"⏳ محاولة بيع {symbol} بكمية {quantity}")
    
    try:
        # 1. تنسيق الرمز بالشكل الصحيح للمنصة
        formatted_symbol = symbol.upper().replace('/', '')
        
        # 2. التأكد من وجود USDT كعملة أساسية
        if 'USDT' not in formatted_symbol:
            if formatted_symbol.endswith('USD'):
                formatted_symbol = formatted_symbol.replace('USD', 'USDT')
            else:
                formatted_symbol = f"{formatted_symbol}USDT"
                
        logger.info(f"تنسيق الرمز من {symbol} إلى {formatted_symbol}")
        
        # 3. تحديد اسم العملة الأساسية (بدون USDT)
        if 'USDT' in formatted_symbol:
            base_asset = formatted_symbol.replace('USDT', '')
        else:
            # إذا لم يكن يحتوي على USDT، استخدم الرمز كما هو كعملة أساسية
            base_asset = formatted_symbol
        
        logger.info(f"العملة الأساسية المستخرجة: {base_asset}")
        
        # 4. محاولة بيع العملة مباشرة بغض النظر عن الرصيد (نستخدم قيمة الكمية من الصفقة المفتوحة)
        logger.info(f"محاولة البيع المباشر لـ {formatted_symbol} بكمية {quantity}")
        direct_sell_result = place_order(formatted_symbol, 'SELL', quantity)
        if direct_sell_result:
            logger.info(f"✅ نجاح البيع المباشر: {direct_sell_result}")
            return True
        
        # في حالة فشل البيع المباشر، نتابع الخطوات العادية
        # 5. التحقق من رصيد العملة الفعلي قبل البيع
        account_balance = get_account_balance()
        actual_balance = 0
        
        # 5. إنشاء جميع التنسيقات المحتملة للرمز
        possible_symbols = [
            formatted_symbol,                 # BTCUSDT
            symbol.upper(),                   # BTC/USDT
            symbol.replace('/', '').upper(),  # BTCUSDT
            base_asset + 'USDT',              # BTCUSDT
            base_asset + '/USDT',             # BTC/USDT
            base_asset.upper() + 'USDT'       # BTCUSDT
        ]
        # إزالة التكرارات
        possible_symbols = list(set(possible_symbols))
        tried_symbols = possible_symbols.copy()
        
        logger.info(f"التنسيقات المحتملة للرمز: {possible_symbols}")
        
        # 6. محاولة العثور على الرصيد
        if account_balance and 'balances' in account_balance:
            # 6.1 البحث بالاسم الدقيق
            for balance in account_balance['balances']:
                asset_name = balance.get('asset', '')
                logger.info(f"فحص رصيد العملة: {balance}")
                
                if asset_name == base_asset:
                    actual_balance = float(balance.get('free', 0))
                    logger.info(f"تم العثور على رصيد {base_asset}: {actual_balance}")
                    break
            
            # 6.2 إذا لم نجد بالضبط، نبحث بشكل غير حساس للحالة
            if actual_balance <= 0:
                for balance in account_balance['balances']:
                    asset_name = balance.get('asset', '')
                    if asset_name.upper() == base_asset.upper():
                        actual_balance = float(balance.get('free', 0))
                        logger.info(f"تم العثور على رصيد {asset_name} (تطابق غير حساس للحالة): {actual_balance}")
                        base_asset = asset_name  # تحديث الاسم الصحيح للعملة
                        break
        
        logger.info(f"محاولة إغلاق صفقة {formatted_symbol}، الكمية المطلوبة: {quantity}، الرصيد المتاح: {actual_balance}")
        
        # 7. إذا كان الرصيد صفر، تحديث الصفقة محلياً
        if actual_balance <= 0:
            logger.warning(f"رصيد غير كافٍ لـ {formatted_symbol}. سيتم تحديث حالة الصفقة كمغلقة في الملف المحلي.")
            
            # تحديث حالة الصفقة محلياً
            from app.utils import load_json_data, save_json_data
            trades = load_json_data('active_trades.json', [])
            
            # بحث عن الصفقة وتحديث حالتها (محاولة بجميع تنسيقات الرموز المحتملة)
            updated = False
            for trade in trades:
                trade_symbol = trade.get('symbol', '')
                if trade_symbol in tried_symbols and trade.get('status') == 'OPEN':
                    trade['status'] = 'CLOSED'
                    updated = True
                    logger.info(f"تم تحديث حالة الصفقة {trade_symbol} إلى 'مغلقة' في الملف المحلي")
            
            if updated:
                save_json_data(trades, 'active_trades.json')
                logger.info(f"تم تحديث ملف الصفقات المحلي")
                send_telegram_message(f"تم تحديث حالة {formatted_symbol} إلى 'مغلقة' في الملف المحلي.")
                return True
            else:
                logger.warning(f"لم يتم العثور على صفقات مفتوحة لـ {formatted_symbol} في الملف المحلي")
                return False
                
        # 8. ضبط الكمية المطلوبة إذا كانت أكبر من الرصيد المتاح
        if actual_balance < float(quantity):
            logger.warning(f"الكمية المطلوبة {quantity} تتجاوز الرصيد المتاح {actual_balance}. ضبط الكمية إلى الرصيد المتاح.")
            quantity = actual_balance
        
        # 9. التحقق من أن الكمية موجبة
        if float(quantity) <= 0:
            logger.error(f"لا يمكن بيع {formatted_symbol}: يجب أن تكون الكمية موجبة، القيمة المستلمة {quantity}")
            return False
        
        # 10. محاولة البيع بجميع تنسيقات الرموز المحتملة
        for attempt_symbol in possible_symbols:
            # 10.1 الحصول على السعر الحالي
            price = get_current_price(attempt_symbol)
            if not price:
                logger.warning(f"لا يمكن الحصول على سعر {attempt_symbol}, تجاهل هذا التنسيق")
                continue
            
            logger.info(f"محاولة البيع باستخدام الرمز {attempt_symbol} بسعر {price} وكمية {quantity}")
            
            # 10.2 تنفيذ أمر البيع
            result = place_order(attempt_symbol, 'SELL', quantity)
            logger.info(f"نتيجة أمر البيع باستخدام {attempt_symbol}: {result}")
            
            # 10.3 إذا نجح البيع، تحديث ملف الصفقات
            if result and result.get('status') != 'REJECTED':
                logger.info(f"✅ تم إغلاق صفقة {attempt_symbol} بنجاح!")
                notify_trade_status(attempt_symbol, "تم البيع", price)
                
                # تحديث حالة الصفقة محلياً أيضاً بطريقة أكثر مرونة
                from app.utils import load_json_data, save_json_data
                trades = load_json_data('active_trades.json', [])
                
                updated_trades = 0
                base_asset_name = base_asset.lower()  # اسم العملة الأساسية بأحرف صغيرة
                
                # جمع كل التنسيقات المحتملة للمقارنة
                normalized_symbols = []
                for s in tried_symbols:
                    normalized_symbols.append(s.lower())
                    normalized_symbols.append(s.lower().replace('usdt', ''))
                    normalized_symbols.append(s.lower().replace('/', ''))
                    normalized_symbols.append(s.lower().replace('/usdt', ''))
                
                for trade in trades:
                    trade_symbol = trade.get('symbol', '').lower()
                    
                    # طرق متعددة لمطابقة الرمز
                    should_update = False
                    
                    # 1. مطابقة دقيقة مع الرموز المجربة
                    if trade_symbol in normalized_symbols and trade.get('status') == 'OPEN':
                        should_update = True
                    
                    # 2. مطابقة إذا كان اسم العملة الأساسية موجود في رمز الصفقة
                    elif base_asset_name in trade_symbol and trade.get('status') == 'OPEN':
                        should_update = True
                    
                    # 3. مطابقة بديلة - تحويل الرمز إلى تنسيق موحد وفحصه
                    elif trade.get('status') == 'OPEN':
                        trade_base = trade_symbol.replace('usdt', '').replace('/', '')
                        if trade_base == base_asset_name:
                            should_update = True
                    
                    # تحديث الصفقة إذا تم العثور على تطابق
                    if should_update:
                        symbol_to_record = trade.get('symbol', '')
                        
                        trade['status'] = 'CLOSED'
                        trade['close_timestamp'] = int(time.time() * 1000)
                        trade['close_price'] = price
                        updated_trades += 1
                        
                        # تسجيل العملة المباعة في نظام التنويع لفترة راحة إلزامية
                        try:
                            from app.coin_diversity import record_coin_sale
                            record_coin_sale(symbol_to_record)
                            logger.info(f"تم تسجيل {symbol_to_record} في نظام التنويع لفترة راحة")
                        except Exception as e:
                            logger.error(f"خطأ في تسجيل بيع العملة في نظام التنويع: {e}")
                        
                        logger.info(f"تم تحديث صفقة بالرمز {trade.get('symbol')} إلى 'مغلقة'")
                
                logger.info(f"تم تحديث {updated_trades} صفقة في الملف المحلي")
                save_json_data('active_trades.json', trades)
                
                return True
            elif result and isinstance(result, dict) and 'invalid symbol' in str(result.get('msg', '')).lower():
                logger.warning(f"الرمز {attempt_symbol} غير صالح, سيتم تجربة الرمز التالي")
                continue
            elif result and isinstance(result, dict) and 'filter failure' in str(result.get('msg', '')).lower():
                logger.warning(f"فشل في الكمية أو السعر للرمز {attempt_symbol}, سيتم تجربة الرمز التالي")
                continue
            elif result and isinstance(result, dict) and 'oversold' in str(result.get('msg', '')).lower():
                logger.warning(f"⚠️ خطأ Oversold للرمز {attempt_symbol}. لا يمكن البيع لعدم وجود رصيد كافٍ.")
                
                # لا نقوم بتحديث الصفقة إلى "مغلقة" عند استقبال خطأ Oversold
                # لأن هذا الخطأ يعني أن العملية لم تنجح، وأن الصفقة ما زالت مفتوحة
                
                # إرسال إشعار بالخطأ
                send_telegram_message(f"⚠️ تنبيه: محاولة بيع {formatted_symbol} فشلت بسبب خطأ Oversold (لا يوجد رصيد كافٍ). الصفقة ما زالت مفتوحة.")
                
                # وضع علامة على الصفقة أنها محاولة بيع فاشلة (دون تغيير الحالة)
                from app.utils import load_json_data, save_json_data
                trades = load_json_data('active_trades.json', [])
                
                # تحديث معلومات الصفقة دون تغيير حالتها
                updated_trades = 0
                for trade in trades:
                    trade_symbol = trade.get('symbol', '')
                    if trade_symbol in possible_symbols and trade.get('status') == 'OPEN':
                        # إضافة معلومات إضافية دون تغيير الحالة
                        if 'metadata' not in trade:
                            trade['metadata'] = {}
                        
                        # إضافة سجل بمحاولات البيع الفاشلة
                        if 'failed_sell_attempts' not in trade['metadata']:
                            trade['metadata']['failed_sell_attempts'] = []
                            
                        # إضافة معلومات محاولة البيع الفاشلة
                        trade['metadata']['failed_sell_attempts'].append({
                            'timestamp': int(time.time() * 1000),
                            'reason': 'Oversold',
                            'price': price if price and price > 0 else None
                        })
                        
                        # تعليم الصفقة للفحص مرة أخرى
                        trade['metadata']['needs_balance_check'] = True
                        
                        updated_trades += 1
                        logger.info(f"تم تحديث معلومات صفقة {trade.get('symbol')} مع تسجيل خطأ Oversold. الصفقة ما زالت مفتوحة.")
                
                if updated_trades > 0:
                    save_json_data('active_trades.json', trades)
                    logger.info(f"تم تحديث معلومات {updated_trades} صفقة في الملف المحلي بسبب خطأ Oversold")
                
                # نرجع False لأن البيع لم ينجح
                return False
                    
                logger.warning(f"لم يتم العثور على صفقات مفتوحة لـ {formatted_symbol} في الملف المحلي")
        
        # 11. إذا وصلنا إلى هنا، فشلت جميع المحاولات
        logger.error(f"❌ فشلت جميع محاولات بيع {symbol} بجميع التنسيقات: {tried_symbols}")
        send_telegram_message(f"⚠️ فشل في إغلاق الصفقة على {symbol} بعد تجربة جميع التنسيقات المحتملة")
        return False
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"❌ خطأ في إغلاق صفقة {symbol}:\n{error_details}")
        logger.error(f"الرموز التي تم تجربتها: {tried_symbols}")
        send_telegram_message(f"⚠️ خطأ أثناء محاولة بيع {symbol}: {e}")
        return False

def close_all_trades_of_symbol(symbol):
    """
    إغلاق جميع صفقات العملة الواحدة دفعة واحدة
    
    :param symbol: رمز العملة
    :return: عدد الصفقات التي تم إغلاقها بنجاح
    """
    import traceback
    try:
        # تنسيق الرمز بالشكل الصحيح: تحويل إلى أحرف كبيرة وإزالة الشرطة المائلة
        formatted_symbol = symbol.upper().replace('/', '')
        
        # التأكد من وجود USDT كعملة أساسية
        if 'USDT' not in formatted_symbol:
            if formatted_symbol.endswith('USD'):
                formatted_symbol = formatted_symbol.replace('USD', 'USDT')
            else:
                formatted_symbol = f"{formatted_symbol}USDT"
                
        logger.info(f"تنسيق الرمز من {symbol} إلى {formatted_symbol}")
        
        # تحديد اسم العملة الأساسية (بدون USDT)
        if 'USDT' in formatted_symbol:
            base_asset = formatted_symbol.replace('USDT', '')
        else:
            # إذا لم يكن يحتوي على USDT، استخدم الرمز كما هو كعملة أساسية
            base_asset = formatted_symbol
        
        logger.info(f"العملة الأساسية المستخرجة: {base_asset}")
        
        # التحقق من رصيد العملة الفعلي قبل البيع
        account_balance = get_account_balance()
        actual_balance = 0
        
        # محاولة بطريقتين للعثور على الرصيد الصحيح
        if account_balance and 'balances' in account_balance:
            # 1. البحث بالاسم الدقيق
            for balance in account_balance['balances']:
                asset_name = balance.get('asset', '')
                logger.info(f"فحص رصيد العملة: {balance}")
                
                if asset_name == base_asset:
                    actual_balance = float(balance.get('free', 0))
                    logger.info(f"تم العثور على رصيد {base_asset}: {actual_balance}")
                    break
            
            # 2. إذا لم نجد بالضبط، نبحث بشكل غير حساس للحالة
            if actual_balance <= 0:
                for balance in account_balance['balances']:
                    asset_name = balance.get('asset', '')
                    if asset_name.upper() == base_asset.upper():
                        actual_balance = float(balance.get('free', 0))
                        logger.info(f"تم العثور على رصيد {asset_name} (تطابق غير حساس للحالة): {actual_balance}")
                        base_asset = asset_name  # تحديث الاسم الصحيح للعملة
                        break
        
        logger.info(f"إغلاق جميع صفقات {formatted_symbol}، الرصيد المتاح: {actual_balance}")
        
        # إذا كان الرصيد صفر، نقوم بتحديث حالة كل الصفقات محلياً فقط
        if actual_balance <= 0:
            logger.warning(f"رصيد غير كافٍ لـ {formatted_symbol}. سيتم تحديث الصفقات كمغلقة في الملف المحلي فقط.")
            
            from app.utils import load_json_data, save_json_data
            trades = load_json_data('active_trades.json', [])
            
            # تحديث حالة جميع الصفقات المفتوحة للعملة - باستخدام منطق مطابقة محسن
            closed_count = 0
            base_asset_lower = base_asset.lower()  # اسم العملة الأساسية بأحرف صغيرة
            
            # تجميع كل التنسيقات المحتملة للرمز للمقارنة
            possible_symbols = [
                symbol.lower(),
                formatted_symbol.lower(),
                base_asset_lower,
                base_asset_lower + "usdt",
                base_asset_lower + "/usdt"
            ]
            
            # إنشاء المزيد من التنسيقات
            normalized_symbols = []
            for s in possible_symbols:
                normalized_symbols.append(s)
                normalized_symbols.append(s.replace('usdt', ''))
                normalized_symbols.append(s.replace('/', ''))
                normalized_symbols.append(s.replace('/usdt', ''))
            
            # إزالة التكرارات
            normalized_symbols = list(set(normalized_symbols))
            logger.info(f"الرموز المحتملة للمطابقة: {normalized_symbols}")
            
            for trade in trades:
                trade_symbol = trade.get('symbol', '').lower()
                
                # طرق متعددة لمطابقة الرمز
                should_update = False
                
                # 1. مطابقة دقيقة مع الرموز المجربة
                if trade_symbol in normalized_symbols and trade.get('status') == 'OPEN':
                    should_update = True
                
                # 2. مطابقة إذا كان اسم العملة الأساسية موجود في رمز الصفقة
                elif base_asset_lower in trade_symbol and trade.get('status') == 'OPEN':
                    should_update = True
                
                # 3. مطابقة بديلة - تحويل الرمز إلى تنسيق موحد وفحصه
                elif trade.get('status') == 'OPEN':
                    trade_base = trade_symbol.replace('usdt', '').replace('/', '')
                    if trade_base == base_asset_lower:
                        should_update = True
                
                # تحديث الصفقة إذا تم العثور على تطابق
                if should_update:
                    trade['status'] = 'CLOSED'
                    trade['close_timestamp'] = int(time.time() * 1000)
                    closed_count += 1
                    logger.info(f"تم تحديث حالة الصفقة {trade.get('symbol')} إلى 'مغلقة' في الملف المحلي")
            
            if closed_count > 0:
                save_json_data('active_trades.json', trades)
                logger.info(f"تم تحديث {closed_count} صفقة لعملة {formatted_symbol} إلى 'مغلقة' في الملف المحلي.")
                send_telegram_message(f"تم تحديث {closed_count} صفقة لعملة {formatted_symbol} إلى 'مغلقة' في الملف المحلي.")
            
            return closed_count
        
        # محاولة بيع كل الكمية المتاحة
        # جرب الحصول على السعر الحالي باستخدام الرمز المنسق
        price = get_current_price(formatted_symbol)
        if not price:
            # جرب مرة أخرى بالرمز الأصلي إذا فشل
            price = get_current_price(symbol)
            if not price:
                logger.error(f"لا يمكن إغلاق صفقات {formatted_symbol}: تعذر الحصول على السعر الحالي")
                return 0
        
        # بيع كامل الرصيد المتاح من العملة
        if actual_balance > 0:
            logger.info(f"محاولة بيع {actual_balance} من {base_asset} باستخدام الرمز {formatted_symbol}")
            
            # استخدم الرمز المنسق للبيع
            result = place_order(formatted_symbol, 'SELL', actual_balance)
            if result and result.get('status') != 'REJECTED':
                logger.info(f"✅ تم بيع جميع الرصيد المتاح من عملة {formatted_symbol}: {result}")
                notify_trade_status(formatted_symbol, f"تم بيع جميع الصفقات", price)
                
                # تحديث حالة جميع الصفقات المفتوحة للعملة بمنطق محسن
                from app.utils import load_json_data, save_json_data
                trades = load_json_data('active_trades.json', [])
                
                closed_count = 0
                base_asset_lower = base_asset.lower()  # اسم العملة الأساسية بأحرف صغيرة
                
                # تجميع كل التنسيقات المحتملة للرمز للمقارنة
                possible_symbols = [
                    symbol.lower(),
                    formatted_symbol.lower(),
                    base_asset_lower,
                    base_asset_lower + "usdt",
                    base_asset_lower + "/usdt"
                ]
                
                # إنشاء المزيد من التنسيقات
                normalized_symbols = []
                for s in possible_symbols:
                    normalized_symbols.append(s)
                    normalized_symbols.append(s.replace('usdt', ''))
                    normalized_symbols.append(s.replace('/', ''))
                    normalized_symbols.append(s.replace('/usdt', ''))
                
                # إزالة التكرارات
                normalized_symbols = list(set(normalized_symbols))
                logger.info(f"الرموز المحتملة للمطابقة عند إغلاق الصفقات: {normalized_symbols}")
                
                for trade in trades:
                    trade_symbol = trade.get('symbol', '').lower()
                    
                    # طرق متعددة لمطابقة الرمز
                    should_update = False
                    
                    # 1. مطابقة دقيقة مع الرموز المجربة
                    if trade_symbol in normalized_symbols and trade.get('status') == 'OPEN':
                        should_update = True
                    
                    # 2. مطابقة إذا كان اسم العملة الأساسية موجود في رمز الصفقة
                    elif base_asset_lower in trade_symbol and trade.get('status') == 'OPEN':
                        should_update = True
                    
                    # 3. مطابقة بديلة - تحويل الرمز إلى تنسيق موحد وفحصه
                    elif trade.get('status') == 'OPEN':
                        trade_base = trade_symbol.replace('usdt', '').replace('/', '')
                        if trade_base == base_asset_lower:
                            should_update = True
                    
                    # تحديث الصفقة إذا تم العثور على تطابق
                    if should_update:
                        orig_entry_price = float(trade.get('entry_price', 0))
                        trade['status'] = 'CLOSED'
                        trade['close_timestamp'] = int(time.time() * 1000)
                        trade['close_price'] = price
                        trade['profit_pct'] = calculate_percentage_change(orig_entry_price, price)
                        closed_count += 1
                        logger.info(f"تم إغلاق صفقة {trade.get('symbol')} بسعر {price} (دخول: {orig_entry_price}, ربح: {trade['profit_pct']}%)")
                
                if closed_count > 0:
                    save_json_data('active_trades.json', trades)
                    logger.info(f"تم إغلاق {closed_count} صفقة لعملة {symbol}")
                    send_telegram_message(f"⚡ تم بيع جميع صفقات {symbol} (عدد {closed_count}) مرة واحدة!")
                
                return closed_count
            else:
                logger.error(f"فشل في بيع جميع صفقات {symbol}: {result}")
                send_telegram_message(f"❌ فشل في بيع جميع صفقات {symbol}")
                return 0
        else:
            logger.warning(f"لا يوجد رصيد متاح لبيع {symbol}")
            return 0
            
    except Exception as e:
        logger.error(f"خطأ في إغلاق جميع صفقات {symbol}: {e}")
        send_telegram_message(f"❌ فشل في بيع جميع صفقات {symbol}: {e}")
        return 0

def find_trade_opportunities(open_trades, all_symbols):
    """
    البحث عن فرص التداول باستخدام استراتيجية محسّنة للتركيز على العملات الرئيسية عالية السيولة
    
    استراتيجية التداول المعدلة:
    1. التركيز على العملات ذات السيولة العالية جدًا (حجم تداول أكبر من 1,000,000$)
    2. اعطاء الأولوية للعملات الرئيسية المعروفة (مثل DOGE, SHIB, SOL, XRP)
    3. التركيز على العملات في نطاق سعري منخفض نسبيًا (0.0001$ إلى 5.0$) 
    4. البحث عن إشارات قوية للشراء (تقاطع EMA، RSI في منطقة ذروة البيع، أنماط انعكاس الشموع)
    5. هدف ربح أكثر واقعية: 0.8% لكل صفقة (لتحقيق إغلاق أسرع وربح متكرر)
    6. وقف خسارة ضيق: 0.5% مع إيقاف خسارة ذكي بعتبة 1% للحماية من التذبذب
    7. الاهتمام بحجم التداول اللحظي ونشاط المشترين كمؤشر للاتجاه
    
    :param open_trades: الصفقات المفتوحة حاليًا
    :param all_symbols: جميع رموز العملات المتاحة
    :return: قائمة بفرص التداول المتاحة
    """
    opportunities = []
    
    try:
        # استيراد وحدة فحص السوق
        from app.market_scanner import get_trading_opportunities
        
        # الحصول على رصيد العملة الأساسية
        balance = get_balance(BASE_CURRENCY)
        if not balance or balance <= 0:
            logger.warning(f"No available balance for {BASE_CURRENCY}")
            return opportunities
            
        # حساب رأس المال المتاح لكل صفقة
        available_slots = MAX_ACTIVE_TRADES - len(open_trades)
        if available_slots <= 0:
            return opportunities
            
        capital_per_trade = (balance * TOTAL_RISK_CAPITAL_RATIO) / MAX_ACTIVE_TRADES
        
        # الحصول على فرص التداول من فاحص السوق
        market_opportunities = get_trading_opportunities()
        
        # ترتيب الفرص حسب نسبة الربح المحتملة
        sorted_opportunities = sorted(market_opportunities, key=lambda x: x.get('potential_profit', 0), reverse=True)
        
        logger.info(f"تم العثور على {len(sorted_opportunities)} فرصة محتملة من فاحص السوق")
        
        # معالجة كل فرصة تم اكتشافها
        for opp in sorted_opportunities:
            # تجاوز الرموز التي لدينا صفقات مفتوحة عليها بالفعل
            symbol = opp.get('symbol')
            if not symbol or any(t.get('symbol') == symbol for t in open_trades):
                continue
            
            # تجاوز العملات التي ليست مقابل العملة الأساسية
            if not symbol.endswith(BASE_CURRENCY):
                continue
                
            # التحقق من الاتجاه والربح المحتمل والسعر
            trend = opp.get('trend')
            potential_profit = opp.get('potential_profit', 0)
            price = float(opp.get('current_price', 0))
            
            # تعديل: توسيع نطاق السعر المقبول للتداول
            # التحقق من أن السعر ضمن النطاق المطلوب (0.0001 إلى 10.0 دولار)
            if not (0.0001 <= price <= 10.0):
                logger.info(f"تم تخطي العملة {symbol} - السعر {price} خارج النطاق المطلوب (0.0001 - 10.0)")
                continue
                
            # تعديل: تخفيف شرط الاتجاه والربح المحتمل بشكل كبير
            # يمكن التداول مع أي اتجاه تقريبًا والربح المحتمل لا يقل عن 0.3%
            confidence = opp.get('confidence', 0.5)
            
            # استيراد قائمة العملات ذات الأولوية من market_scanner
            from app.config import HIGH_VOLUME_SYMBOLS
            
            # إزالة أي شروط تقريباً ماعدا الحد الأدنى للربح (0.2%) لزيادة الصفقات
            # التركيز على العملات ذات الأولوية وأي عملة لديها ربح متوقع
            # هذا تغيير جذري يسمح بالتداول في جميع الظروف تقريباً
            if symbol in HIGH_VOLUME_SYMBOLS or potential_profit >= 0.002:
                if price <= 0:
                    continue
                    
                logger.info(f"العملة {symbol} مؤهلة للتداول - السعر: {price}, الربح المحتمل: {potential_profit}%, الاتجاه: {trend}")
                    
                # حساب الكمية المناسبة للشراء
                quantity = format_price(capital_per_trade / price, 4)
                
                # إضافة الفرصة إلى القائمة
                opportunities.append({
                    'symbol': symbol,
                    'entry_price': price,
                    'quantity': quantity,
                    'reason': opp.get('reason', 'فرصة تداول مكتشفة'),
                    'potential_profit': potential_profit
                })
                
                # توقف عندما نصل إلى العدد المطلوب من الفرص
                if len(opportunities) >= available_slots:
                    break
        
        # طباعة تقرير حول الفرص المكتشفة
        if opportunities:
            logger.info(f"تم العثور على {len(opportunities)} فرصة تداول جديدة")
            for i, opp in enumerate(opportunities):
                logger.info(f"{i+1}. {opp['symbol']}: سعر الدخول {opp['entry_price']}, الربح المحتمل {opp.get('potential_profit', 0)}%")
        else:
            logger.info("لم يتم العثور على فرص تداول مناسبة")
                
        return opportunities
    except Exception as e:
        logger.error(f"Error finding trade opportunities: {e}")
        return []

def price_stopped_rising(symbol, current_price):
    """
    التحقق مما إذا كان السعر توقف عن الارتفاع
    
    :param symbol: رمز العملة
    :param current_price: السعر الحالي
    :return: True إذا توقف السعر عن الارتفاع، False خلاف ذلك
    """
    try:
        klines = get_klines(symbol, '5m', 3)
        if not klines or len(klines) < 3:
            return False
            
        # إذا كان السعر الحالي أقل من أعلى سعر في آخر فترتين، فقد توقف عن الارتفاع
        last_high = max(klines[-1]['high'], klines[-2]['high'])
        prev_close = klines[-2]['close']
        
        return current_price < last_high and current_price < prev_close
    except Exception as e:
        logger.error(f"Error checking if price stopped rising for {symbol}: {e}")
        return False

def execute_trade(symbol, amount):
    """
    تنفيذ صفقة (شراء)
    
    :param symbol: رمز العملة
    :param amount: المبلغ المراد استثماره (بالعملة الأساسية)
    :return: True في حالة النجاح، False في حالة الفشل
    """
    try:
        price = get_current_price(symbol)
        if not price:
            logger.error(f"Can't execute trade for {symbol}: Unable to get current price")
            return False
        
        # التحقق من معلومات السوق للعملة
        from app.mexc_api import get_exchange_info
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
                        step_size = float(filter_item.get('stepSize', '0.0001'))
                        min_qty = float(filter_item.get('minQty', '0.0001'))
                        
                        # حساب دقة الكمية من stepSize
                        if step_size < 1:
                            step_str = str(step_size).rstrip('0').rstrip('.')
                            decimal_places = len(step_str) - step_str.find('.') - 1
                            quantity_precision = decimal_places
                        
                        # تعيين الحد الأدنى للكمية
                        min_quantity = min_qty
                        break
        
        # حساب الكمية المناسبة للشراء مع مراعاة الدقة والحد الأدنى
        if price <= 0:
            logger.error(f"Can't execute trade for {symbol}: Price is zero or negative")
            return False
            
        raw_quantity = amount / price
        
        # التأكد من أن الكمية ليست سالبة أو صفر
        if raw_quantity <= 0:
            logger.error(f"Can't execute trade for {symbol}: Calculated quantity is zero or negative")
            return False
            
        quantity = format_price(raw_quantity, quantity_precision)
        
        # تحويل الكمية إلى رقم مع التعامل مع القيم الفارغة
        try:
            float_quantity = float(quantity)
            if float_quantity <= 0:
                logger.error(f"Can't execute trade for {symbol}: Formatted quantity is zero or negative")
                return False
                
            # التأكد من أن الكمية أكبر من الحد الأدنى
            if float_quantity < min_quantity:
                quantity = str(min_quantity)
                logger.warning(f"Adjusted quantity to minimum allowed: {quantity} for {symbol}")
                
        except (ValueError, TypeError):
            logger.error(f"Can't execute trade for {symbol}: Invalid quantity format")
            return False
        
        logger.info(f"Executing BUY order for {symbol}: amount={amount}, price={price}, quantity={quantity}")
        
        # محاولة وضع الطلب
        result = place_order(symbol, 'BUY', quantity)
        
        if result and result.get('status') != 'REJECTED':
            logger.info(f"Executed trade for {symbol} at price {price}: {result}")
            notify_trade_status(symbol, "تم الشراء", price)
            
            # حفظ بيانات الصفقة المنفذة في ملف محلي
            from app.utils import load_json_data, save_json_data
            from datetime import datetime
            
            trades = load_json_data('active_trades.json', [])
            
            # التأكد من أن trades هو قائمة
            if not isinstance(trades, list):
                trades = []
            
            # إضافة سجل الصفقة الجديدة
            trade_record = {
                'symbol': symbol,
                'side': 'BUY',
                'status': 'OPEN',
                'entry_price': price,
                'quantity': quantity,
                'timestamp': int(datetime.now().timestamp() * 1000),
                'orderId': result.get('orderId', ''),
                'clientOrderId': result.get('clientOrderId', '')
            }
            
            trades.append(trade_record)
            save_json_data('active_trades.json', trades)
            
            return True
        else:
            logger.error(f"Failed to execute trade for {symbol}: {result}")
            return False
    except Exception as e:
        logger.error(f"Error executing trade for {symbol}: {e}")
        send_telegram_message(f"فشل في تنفيذ الصفقة على {symbol}: {e}")
        return False

def monitor_trades(open_trades):
    """
    مراقبة الصفقات المفتوحة وتحديث حالتها
    
    :param open_trades: الصفقات المفتوحة
    :return: قائمة محدثة بالصفقات المفتوحة
    """
    updated_trades = []
    
    for trade in open_trades:
        try:
            symbol = trade.get('symbol')
            if not symbol:
                continue
                
            entry_price = trade.get('price')
            order_id = trade.get('orderId')
            
            if not entry_price or not order_id:
                updated_trades.append(trade)
                continue
                
            current_price = get_current_price(symbol)
            if not current_price:
                updated_trades.append(trade)
                continue
                
            # حساب نسبة التغيير
            change = calculate_percentage_change(float(entry_price), current_price) / 100  # تحويل النسبة المئوية إلى عشري
            
            # التحقق من وقف الخسارة
            if change <= -STOP_LOSS:
                # تنفيذ وقف الخسارة
                if close_trade(symbol, trade.get('origQty')):
                    notify_trade_status(
                        symbol, "وقف خسارة", 
                        current_price, 
                        calculate_percentage_change(float(entry_price), current_price)
                    )
                    # لا نضيف الصفقة مرة أخرى لأنها أغلقت
                else:
                    # في حالة فشل إغلاق الصفقة، نحتفظ بها في القائمة
                    updated_trades.append(trade)
                    
            # التحقق من جني الأرباح
            elif change >= TAKE_PROFIT:
                # تحقق مما إذا كان السعر توقف عن الارتفاع لجني الأرباح
                if price_stopped_rising(symbol, current_price):
                    # ✨ ميزة جديدة: بيع جميع صفقات العملة الواحدة عند تحقيق ربح لأي منها
                    logger.info(f"جني الأرباح لـ {symbol}: بدء محاولة بيع جميع صفقات هذه العملة (تم تحقيق {change*100:.2f}% من الربح)")
                    closed_count = close_all_trades_of_symbol(symbol)
                    
                    if closed_count > 0:
                        notify_trade_status(
                            symbol, f"تم بيع جميع صفقات العملة ({closed_count})", 
                            current_price, 
                            calculate_percentage_change(float(entry_price), current_price)
                        )
                        # لا نضيف الصفقة مرة أخرى لأنها أغلقت
                    else:
                        # في حالة فشل إغلاق الصفقات، نحتفظ بها في القائمة
                        updated_trades.append(trade)
                        # نحاول إغلاق صفقة فردية كخطة بديلة
                        if close_trade(symbol, trade.get('origQty')):
                            notify_trade_status(
                                symbol, "جني أرباح", 
                                current_price, 
                                calculate_percentage_change(float(entry_price), current_price)
                            )
                else:
                    # السعر ما زال يرتفع، نحتفظ بالصفقة
                    updated_trades.append(trade)
            else:
                # لم تتحقق أي من شروط الإغلاق، نحتفظ بالصفقة
                updated_trades.append(trade)
                
        except Exception as e:
            logger.error(f"Error monitoring trade {trade.get('symbol')}: {e}")
            # في حالة الخطأ، نحتفظ بالصفقة في القائمة
            updated_trades.append(trade)
            
    return updated_trades

def get_available_balance():
    """
    الحصول على الرصيد المتاح للتداول
    
    :return: الرصيد المتاح
    """
    try:
        return get_balance(BASE_CURRENCY)
    except Exception as e:
        logger.error(f"Error getting available balance: {e}")
        return 0
