"""
وحدة التداول التلقائي المحسنة بالكامل
تعالج المشاكل الأساسية في التداول:
1. تضمن تنويع الصفقات (5 عملات مختلفة)
2. تضمن إتمام البيع وجني الأرباح
3. تمنع تكرار التداول على نفس العملة
"""

import os
import json
import time
import logging
import random
import threading
from datetime import datetime
from typing import List, Dict, Any, Tuple, Set

# استيراد المكونات اللازمة
from app.mexc_api import get_current_price, place_order, get_all_symbols_24h_data, get_trades_history
from app.config import TAKE_PROFIT, STOP_LOSS
from app.telegram_notify import send_telegram_message, notify_trade_status

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# قفل للتحكم في الوصول المتزامن إلى الملفات
FILE_LOCK = threading.Lock()

# ملف الصفقات
TRADES_FILE = 'active_trades.json'

# بارامترات النظام
SYSTEM_SETTINGS = {
    'total_capital': 5.0,       # رأس المال الإجمالي (تم تخفيضه من 30.0 إلى 5.0 لجعل الصفقات أصغر وأكثر واقعية)
    'max_trades': 5,            # الحد الأقصى لعدد الصفقات المفتوحة
    'min_profit': 0.5,          # الحد الأدنى للربح قبل البيع (%)
    'max_loss': 1.0,            # الحد الأقصى للخسارة قبل البيع (%)
    'max_hold_hours': 12,       # الحد الأقصى لساعات الاحتفاظ بالصفقة
    'blacklisted_symbols': ['XRPUSDT'],  # العملات المحظورة
}

# العملات المفضلة للتنويع
PRIORITY_COINS = [
    'BTCUSDT',     # بيتكوين
    'ETHUSDT',     # إيثريوم
    'DOGEUSDT',    # دوج كوين
    'SOLUSDT',     # سولانا
    'BNBUSDT',     # بينانس كوين
    'MATICUSDT',   # بوليجون
    'AVAXUSDT',    # أفالانش
    'LINKUSDT',    # تشينلينك
    'TRXUSDT',     # ترون
    'LTCUSDT',     # لايتكوين
    'ADAUSDT',     # كاردانو
    'ETCUSDT',     # إيثريوم كلاسيك
    'DOTUSDT',     # بولكادوت
    'FILUSDT',     # فايلكوين
    'ATOMUSDT',    # كوزموس
]

def create_backup() -> str:
    """
    إنشاء نسخة احتياطية من ملف الصفقات
    
    :return: اسم ملف النسخة الاحتياطية
    """
    try:
        if not os.path.exists(TRADES_FILE):
            return ""
            
        timestamp = int(time.time())
        backup_file = f"{TRADES_FILE}.backup.{timestamp}"
        
        with FILE_LOCK:
            os.system(f"cp {TRADES_FILE} {backup_file}")
            
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_file}")
        return backup_file
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")
        return ""

def load_trades() -> Dict[str, List[Dict[str, Any]]]:
    """
    تحميل الصفقات من الملف
    
    :return: بيانات الصفقات
    """
    try:
        with FILE_LOCK:
            if os.path.exists(TRADES_FILE):
                with open(TRADES_FILE, 'r') as f:
                    data = json.load(f)
                
                # تحويل البيانات إلى التنسيق الصحيح إذا لزم الأمر
                if isinstance(data, dict) and 'open' in data and 'closed' in data:
                    return data
                elif isinstance(data, list):
                    return {
                        'open': [t for t in data if t.get('status') == 'OPEN'],
                        'closed': [t for t in data if t.get('status') != 'OPEN']
                    }
                else:
                    logger.warning(f"صيغة غير متوقعة لملف الصفقات: {type(data)}")
                    return {'open': [], 'closed': []}
            
            return {'open': [], 'closed': []}
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {'open': [], 'closed': []}

def save_trades(data: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    حفظ الصفقات في الملف
    
    :param data: بيانات الصفقات
    :return: نجاح العملية
    """
    try:
        # إنشاء نسخة احتياطية
        create_backup()
        
        # حفظ البيانات
        with FILE_LOCK:
            with open(TRADES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
                
        logger.info(f"تم حفظ {len(data.get('open', []))} صفقة مفتوحة و {len(data.get('closed', []))} صفقة مغلقة")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def get_active_symbols() -> Set[str]:
    """
    الحصول على مجموعة العملات المتداولة حالياً
    
    :return: مجموعة من العملات المتداولة
    """
    data = load_trades()
    open_trades = data.get('open', [])
    
    # استخراج رموز العملات
    symbols = set()
    for trade in open_trades:
        symbol = trade.get('symbol', '')
        if symbol:
            symbols.add(symbol.upper())
    
    return symbols

def is_trade_allowed(symbol: str) -> Tuple[bool, str]:
    """
    التحقق ما إذا كان مسموحاً بتداول العملة
    
    :param symbol: رمز العملة
    :return: (مسموح، السبب)
    """
    # منع العملات المحظورة
    if symbol.upper() in SYSTEM_SETTINGS['blacklisted_symbols']:
        return False, f"العملة {symbol} محظورة"
    
    # التحقق من عدم وجود صفقات مفتوحة على نفس العملة
    active_symbols = get_active_symbols()
    if symbol.upper() in active_symbols:
        return False, f"توجد صفقة مفتوحة بالفعل على {symbol}"
    
    # التحقق من عدد الصفقات المفتوحة
    if len(active_symbols) >= SYSTEM_SETTINGS['max_trades']:
        return False, f"تم الوصول للحد الأقصى من الصفقات المفتوحة: {len(active_symbols)}/{SYSTEM_SETTINGS['max_trades']}"
    
    return True, "مسموح بالتداول"

def select_diverse_coins(count: int = 5) -> List[str]:
    """
    اختيار عملات متنوعة للتداول
    
    :param count: عدد العملات المطلوبة
    :return: قائمة بالعملات المختارة
    """
    # الحصول على العملات المتداولة حالياً
    active_symbols = get_active_symbols()
    
    # العملات المحظورة الموسعة تشمل العملات النشطة والمحظورة
    excluded_symbols = set(SYSTEM_SETTINGS['blacklisted_symbols']) | active_symbols
    
    # استبعاد العملات المحظورة والمتداولة حالياً
    available_coins = [
        coin for coin in PRIORITY_COINS 
        if coin not in excluded_symbols
    ]
    
    # إذا لم تكن هناك عملات متاحة، جلب عملات من السوق
    if not available_coins:
        try:
            # جلب جميع العملات المتاحة من السوق
            all_symbols_data = get_all_symbols_24h_data()
            
            # استبعاد العملات المحظورة والمتداولة حالياً
            available_coins = [
                symbol_data.get('symbol') 
                for symbol_data in all_symbols_data 
                if symbol_data.get('symbol', '').endswith('USDT') and 
                   symbol_data.get('symbol') not in excluded_symbols
            ]
        except Exception as e:
            logger.error(f"خطأ في جلب العملات من السوق: {e}")
    
    # خلط العملات المتاحة لضمان التنويع العشوائي
    random.shuffle(available_coins)
    
    # اختيار العدد المطلوب من العملات
    selected_coins = available_coins[:count]
    
    logger.info(f"تم اختيار {len(selected_coins)} عملة للتنويع: {selected_coins}")
    return selected_coins

def calculate_per_trade_amount() -> float:
    """
    حساب المبلغ المخصص لكل صفقة
    
    :return: المبلغ بالدولار
    """
    # قسمة رأس المال على الحد الأقصى للصفقات
    return SYSTEM_SETTINGS['total_capital'] / SYSTEM_SETTINGS['max_trades']

def execute_buy(symbol: str, amount: float) -> Tuple[bool, Dict]:
    """
    تنفيذ عملية الشراء مع تأكيد قطعي للصفقات الحقيقية فقط
    
    :param symbol: رمز العملة
    :param amount: المبلغ بالدولار
    :return: (نجاح العملية، بيانات الأمر)
    """
    try:
        # متغير لتخزين رصيد USDT قبل الشراء (خارج نطاق try)
        initial_usdt_balance = 0
        
        # تحقق أولاً من رصيد USDT - مع دعم جميع الهياكل الممكنة
        try:
            from app.mexc_api import get_account_balance, get_balance
            logger.info("التحقق من رصيد USDT قبل تنفيذ عملية الشراء...")
            balance = get_account_balance()
            
            # التحقق من وجود البيانات
            if not balance:
                logger.error("❌ تعذر الحصول على بيانات الحساب.")
                return False, {"error": "تعذر الحصول على بيانات الحساب"}
            
            # طريقة 1: البحث عن USDT كمفتاح مباشر (الطريقة القديمة)
            if 'USDT' in balance:
                initial_usdt_balance = float(balance['USDT'].get('free', 0))
                logger.info(f"💰 رصيد USDT المتاح (كمفتاح مباشر): {initial_usdt_balance}")
            
            # طريقة 2: البحث في قائمة 'balances' (الهيكل الجديد)
            elif 'balances' in balance:
                initial_usdt_balance = 0
                for asset in balance['balances']:
                    if isinstance(asset, dict) and asset.get('asset') == 'USDT':
                        initial_usdt_balance = float(asset.get('free', 0))
                        logger.info(f"💰 رصيد USDT المتاح (من balances): {initial_usdt_balance}")
                        break
            
            # طريقة 3: الاستعلام المباشر عن الرصيد
            else:
                logger.warning("⚠️ هيكل بيانات الحساب غير معروف. محاولة استخدام طريقة بديلة...")
                
                # استخدام get_balance الذي تم استيراده مسبقًا
                try:
                    direct_balance = get_balance('USDT')
                    initial_usdt_balance = float(direct_balance) if direct_balance else 0
                    logger.info(f"💰 رصيد USDT المتاح (بطريقة مباشرة): {initial_usdt_balance}")
                except Exception as balance_error:
                    logger.error(f"❌ خطأ في جلب الرصيد المباشر: {balance_error}")
                    # استخدام قيمة افتراضية آمنة
                    initial_usdt_balance = 0
            
            # التحقق من وجود رصيد كافٍ
            if initial_usdt_balance <= 0:
                logger.error(f"❌ لم يتم العثور على رصيد USDT.")
                return False, {"error": "لم يتم العثور على رصيد USDT"}
            
            if initial_usdt_balance < amount:
                logger.error(f"❌ رصيد USDT غير كافٍ. متاح: {initial_usdt_balance}, مطلوب: {amount}")
                return False, {"error": f"رصيد USDT غير كافٍ. متاح: {initial_usdt_balance}, مطلوب: {amount}"}
                
            # تسجيل الرصيد المتاح للتأكيد
            logger.info(f"💰 رصيد USDT المتاح للتداول: {initial_usdt_balance}")
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من الرصيد: {e}")
            return False, {"error": f"خطأ في التحقق من الرصيد: {e}"}

        # الحصول على السعر الحالي
        price = get_current_price(symbol)
        if not price:
            logger.error(f"لم يتم الحصول على سعر العملة {symbol}")
            return False, {"error": "لم يتم الحصول على السعر"}
        
        # حساب الكمية
        quantity = amount / price
        
        # تقريب الكمية للأسفل لضمان عدم تجاوز المبلغ
        quantity = float(f"{quantity:.6f}")
        
        logger.info(f"🔶 محاولة شراء {symbol}: السعر={price}, الكمية={quantity}, المبلغ={amount}")
        
        # تنفيذ أمر الشراء
        result = place_order(symbol, "BUY", quantity, None, "MARKET")
        
        # تحقق من نجاح الأمر المبدئي
        if not result or 'error' in result or 'orderId' not in result:
            logger.error(f"❌ فشل أمر الشراء: {symbol} - {result}")
            return False, result
            
        logger.info(f"✅ تم إرسال أمر الشراء بنجاح: {result}")
        
        # التحقق من تنفيذ الصفقة فعلياً - إنتظار قصير للتأكد من تحديث تاريخ التداول
        time.sleep(2)
        
        # نتحقق عبر تاريخ التداول أولاً
        trade_history_verified = False
        try:
            logger.info(f"🔍 التحقق من تنفيذ صفقة {symbol} في تاريخ التداول...")
            
            # محاولات متعددة للتحقق من تنفيذ الصفقة خلال 10 ثوانٍ
            for attempt in range(3):
                recent_trades = get_trades_history(symbol, 20)
                order_id = result.get('orderId')
                
                if recent_trades:
                    for trade_record in recent_trades:
                        if str(trade_record.get('orderId')) == str(order_id):
                            trade_history_verified = True
                            logger.info(f"✅✅ تأكيد وجود الصفقة في تاريخ التداول: {symbol} (معرف الأمر: {order_id})")
                            break
                
                if trade_history_verified:
                    break
                    
                # إنتظار قصير ثم محاولة مرة أخرى
                logger.warning(f"⚠️ محاولة {attempt+1}/3: لم يتم العثور على الصفقة في تاريخ التداول بعد. إنتظار...")
                time.sleep(2)
            
            if not trade_history_verified:
                logger.error(f"❌❌ لم يتم تأكيد الصفقة في تاريخ التداول بعد 3 محاولات: {symbol}")
                return False, {"error": "لم يتم تأكيد الصفقة في تاريخ التداول"}
                
        except Exception as e:
            logger.error(f"❌ خطأ أثناء التحقق من تاريخ التداول: {e}")
            return False, {"error": f"خطأ أثناء التحقق من تاريخ التداول: {e}"}
        
        # وصلنا إلى هنا فقط إذا تم تأكيد الصفقة فعلياً
        logger.info(f"🎯 تم تأكيد تنفيذ صفقة حقيقية: {symbol}")
        
        # التحقق من تغير الرصيد بعد الشراء
        try:
            new_balance = get_account_balance()
            if new_balance and 'USDT' in new_balance:
                new_usdt_balance = float(new_balance['USDT'].get('free', 0))
                balance_diff = initial_usdt_balance - new_usdt_balance
                logger.info(f"💰 تغير رصيد USDT: {initial_usdt_balance} → {new_usdt_balance} (فرق: {balance_diff})")
                
                # التحقق إذا كان هناك تغير فعلي في الرصيد يقارب قيمة الصفقة
                if balance_diff < amount * 0.8:  # يجب أن يكون التغير على الأقل 80% من قيمة الصفقة
                    logger.warning(f"⚠️ تغير الرصيد أقل من المتوقع: {balance_diff} < {amount}")
                    # لكننا نستمر لأن الصفقة تم تأكيدها بالفعل في تاريخ التداول
            
            # التحقق من وجود العملة في الرصيد بعد الشراء
            purchased_coin_symbol = symbol.replace('USDT', '')
            if new_balance and purchased_coin_symbol in new_balance:
                purchased_coin_balance = float(new_balance[purchased_coin_symbol].get('free', 0))
                logger.info(f"💰 رصيد {purchased_coin_symbol} الجديد: {purchased_coin_balance}")
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من تغير الرصيد: {e}")
            # نستمر لأن الصفقة تم تأكيدها بالفعل في تاريخ التداول
        
        # تحضير أهداف الربح
        take_profit_targets = [
            {'percent': percent, 'hit': False}
            for percent in [0.5, 1.0, 2.0]  # أهداف ربح متعددة
        ]
        
        # إنشاء سجل للصفقة
        order_info = {
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': price,
            'stop_loss': -0.1,  # استخدام -0.1 كقيمة نسبية بدلاً من قيمة مطلقة
            'take_profit_targets': take_profit_targets,
            'timestamp': int(time.time() * 1000),
            'status': 'OPEN',
            'api_executed': True,
            'api_confirmed': True,  # نؤكد أنها صفقة حقيقية تم التحقق منها
            'orderId': result.get('orderId', ''),
            'order_type': 'MARKET'
        }
        
        # تحديث ملف الصفقات
        data = load_trades()
        data['open'].append(order_info)
        save_trades(data)
        
        logger.info(f"✅✅ تم تسجيل صفقة حقيقية مؤكدة: {symbol}")
        
        # إرسال إشعار تلجرام
        notify_trade_status(
            symbol=symbol, 
            status="تم الشراء", 
            price=price, 
            order_id=result.get('orderId'),
            api_verified=True
        )
        
        return True, result
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ الشراء لـ {symbol}: {e}")
        return False, {"error": str(e)}

def execute_sell(symbol: str, quantity: float) -> Tuple[bool, Dict]:
    """
    تنفيذ عملية البيع مع تأكيد قطعي للصفقات الحقيقية فقط
    
    :param symbol: رمز العملة
    :param quantity: الكمية
    :return: (نجاح العملية، بيانات الأمر)
    """
    try:
        # تحقق من وجود رصيد للعملة قبل البيع
        coin_symbol = ""
        current_coin_balance = 0.0
        
        try:
            from app.mexc_api import get_account_balance
            logger.info(f"🔍 التحقق من رصيد {symbol} قبل البيع...")
            
            coin_symbol = symbol.replace('USDT', '')
            account_balance = get_account_balance()
            
            if account_balance and coin_symbol in account_balance:
                current_coin_balance = float(account_balance[coin_symbol].get('free', 0))
                logger.info(f"💰 رصيد {coin_symbol} المتاح للبيع: {current_coin_balance}")
                
                if current_coin_balance < float(quantity) * 0.8:  # 80% من الكمية المطلوبة على الأقل (بعد الرسوم)
                    logger.error(f"⚠️ رصيد {coin_symbol} غير كافي للبيع. متاح: {current_coin_balance}, مطلوب: {quantity}")
                    return False, {"error": f"رصيد {coin_symbol} غير كافي للبيع"}
            else:
                logger.warning(f"⚠️ لم يتم العثور على رصيد {coin_symbol}، قد يكون طلب البيع غير صالح")
                return False, {"error": f"لم يتم العثور على رصيد {coin_symbol}"}
        except Exception as e:
            logger.error(f"⚠️ خطأ في التحقق من الرصيد: {e}")
            return False, {"error": f"خطأ في التحقق من الرصيد: {e}"}
        
        # الحصول على السعر الحالي
        price = get_current_price(symbol)
        if not price:
            logger.error(f"لم يتم الحصول على سعر العملة {symbol}")
            return False, {"error": "لم يتم الحصول على السعر"}
        
        logger.info(f"🔶 محاولة بيع {symbol}: السعر={price}, الكمية={quantity}")
        
        # تنفيذ أمر البيع
        result = place_order(symbol, "SELL", quantity, None, "MARKET")
        
        # التحقق من نجاح الأمر المبدئي
        if not result or 'error' in result or 'orderId' not in result:
            logger.error(f"❌ فشل أمر البيع: {symbol} - {result}")
            return False, result
        
        logger.info(f"✅ تم إرسال أمر البيع بنجاح: {result}")
        
        # التحقق من تنفيذ الصفقة فعلياً - إنتظار قصير للتأكد من تحديث تاريخ التداول
        time.sleep(2)
        
        # نتحقق عبر تاريخ التداول
        sell_verified = False
        try:
            logger.info(f"🔍 التحقق من تنفيذ عملية بيع {symbol} في تاريخ التداول...")
            
            # محاولات متعددة للتحقق من تنفيذ الصفقة
            for attempt in range(3):
                trades_history = get_trades_history(symbol, 20)
                if trades_history:
                    for trade_record in trades_history:
                        # نبحث عن صفقة بيع حديثة بنفس معرف الأمر
                        if (str(trade_record.get('orderId')) == str(result.get('orderId')) and 
                            trade_record.get('side') == 'SELL'):
                            sell_verified = True
                            logger.info(f"✅✅ تأكيد تنفيذ عملية البيع في تاريخ التداول: {symbol}")
                            break
                
                if sell_verified:
                    break
                    
                # إنتظار قصير ثم محاولة مرة أخرى
                logger.warning(f"⚠️ محاولة {attempt+1}/3: لم يتم العثور على عملية البيع في تاريخ التداول بعد. إنتظار...")
                time.sleep(2)
            
            if not sell_verified:
                # إذا لم نتمكن من التحقق من البيع، نحاول التحقق من تغير الرصيد كوسيلة بديلة
                logger.warning(f"⚠️ لم يتم تأكيد عملية البيع في تاريخ التداول. التحقق من تغير الرصيد...")
                
                try:
                    # استخدام كمية الصفقة كقيمة افتراضية لرصيد العملة
                    old_coin_balance = current_coin_balance
                        
                    # التحقق من انخفاض رصيد العملة
                    new_balance = get_account_balance()
                    if new_balance and coin_symbol in new_balance:
                        new_coin_balance = float(new_balance[coin_symbol].get('free', 0))
                        if new_coin_balance < old_coin_balance * 0.5:  # انخفاض الرصيد بشكل كبير يعني نجاح البيع
                            sell_verified = True
                            logger.info(f"✅ تم تأكيد البيع من خلال تغير الرصيد: {old_coin_balance} → {new_coin_balance}")
                except Exception as e:
                    logger.error(f"❌ خطأ في التحقق من تغير الرصيد: {e}")
                
                if not sell_verified:
                    logger.error(f"❌❌ لم يتم تأكيد عملية البيع {symbol} بعد عدة محاولات")
                    return False, {"error": "لم يتم تأكيد تنفيذ عملية البيع"}
        except Exception as e:
            logger.error(f"❌ خطأ أثناء التحقق من عملية البيع: {e}")
            return False, {"error": f"خطأ أثناء التحقق من عملية البيع: {e}"}
        
        # وصلنا إلى هنا فقط إذا تم التأكد من تنفيذ البيع فعلياً
        logger.info(f"🎯 تم تأكيد تنفيذ عملية بيع حقيقية: {symbol}")
        
        # إرسال إشعار تلجرام عن عملية البيع
        notify_trade_status(
            symbol=symbol,
            status=f"تم البيع",
            price=price,
            order_id=result.get('orderId'),
            api_verified=True
        )
        
        return True, result
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ البيع لـ {symbol}: {e}")
        return False, {"error": str(e)}

def verify_trade_with_api(trade: Dict[str, Any]) -> bool:
    """
    التحقق من وجود الصفقة في سجلات API المنصة
    يستخدم عدة طرق للتحقق من وجود الصفقة
    
    :param trade: بيانات الصفقة
    :return: ما إذا كانت الصفقة موجودة فعلاً في المنصة
    """
    try:
        symbol = trade.get('symbol')
        if not symbol:
            logger.error("الرمز غير متوفر في الصفقة للتحقق")
            return False
            
        order_id = trade.get('orderId', trade.get('order_id'))
        if not order_id:
            logger.warning(f"معرف الأمر غير متوفر في الصفقة {symbol} للتحقق")
            return False
        
        # طريقة 1: التحقق من تاريخ التداول الأخير
        try:
            recent_trades = get_trades_history(symbol, 50)  # زيادة عدد الصفقات للبحث
            
            # البحث عن الصفقة بناءً على معرف الأمر
            for trade_record in recent_trades:
                if str(trade_record.get('orderId')) == str(order_id):
                    logger.info(f"✅ تم تأكيد وجود الصفقة {symbol} على المنصة بمعرف {order_id} عبر تاريخ التداول")
                    return True
        except Exception as e:
            logger.warning(f"فشل التحقق من تاريخ التداول لـ {symbol}: {e}")
        
        # طريقة 2: التحقق من الأوامر المفتوحة
        try:
            from app.mexc_api import get_open_orders
            open_orders = get_open_orders(symbol)
            
            for order in open_orders:
                if str(order.get('orderId')) == str(order_id):
                    logger.info(f"✅ تم تأكيد وجود الصفقة {symbol} على المنصة بمعرف {order_id} عبر الأوامر المفتوحة")
                    return True
        except Exception as e:
            logger.warning(f"فشل التحقق من الأوامر المفتوحة لـ {symbol}: {e}")
        
        # طريقة 3: التحقق من حالة الأمر مباشرة
        try:
            from app.mexc_api import get_order_status
            order_status = get_order_status(symbol, order_id)
            if order_status and 'status' in order_status:
                logger.info(f"✅ تم تأكيد وجود الصفقة {symbol} على المنصة بمعرف {order_id} عبر استعلام حالة الأمر")
                return True
        except Exception as e:
            logger.warning(f"فشل استعلام حالة الأمر لـ {symbol}: {e}")
            
        # إذا لم يتم العثور على الصفقة في أي من الطرق
        logger.warning(f"⚠️ لم يتم العثور على الصفقة {symbol} بمعرف {order_id} في أي من سجلات المنصة")
        return False
    except Exception as e:
        logger.error(f"خطأ في التحقق من الصفقة مع API: {e}")
        return False

def close_trade(trade: Dict[str, Any], reason: str) -> bool:
    """
    إغلاق صفقة وتحديث ملف الصفقات - يتعامل فقط مع الصفقات الحقيقية المؤكدة
    
    :param trade: بيانات الصفقة
    :param reason: سبب الإغلاق
    :return: نجاح العملية
    """
    try:
        # أولاً إنشاء نسخة احتياطية
        create_backup()
        
        symbol = trade.get('symbol')
        quantity = trade.get('quantity', 0)
        
        if not symbol or quantity <= 0:
            logger.error(f"بيانات الصفقة غير صالحة: {trade}")
            return False
        
        # التحقق من وجود الصفقة على المنصة
        api_verified = verify_trade_with_api(trade)
        
        if not api_verified:
            logger.warning(f"⚠️ محاولة إغلاق صفقة غير موجودة على المنصة: {symbol}")
            
            # إذا كانت الصفقة غير مؤكدة، نعلمها كصفقة وهمية ونغلقها بدون تنفيذ بيع فعلي
            trade['api_confirmed'] = False
            
            # تحديث ملف الصفقات لإزالة الصفقة من القائمة المفتوحة
            data = load_trades()
            
            # نبحث عن الصفقة في القائمة المفتوحة
            found_index = None
            for i, t in enumerate(data['open']):
                if (t.get('symbol') == symbol and 
                    t.get('timestamp') == trade.get('timestamp')):
                    found_index = i
                    break
            
            # إذا وجدنا الصفقة، نحذفها من المفتوحة ونضيفها للمغلقة
            if found_index is not None:
                current_price = get_current_price(symbol) or trade.get('entry_price', 0)
                
                # إضافة معلومات الإغلاق
                trade_to_close = data['open'].pop(found_index)
                trade_to_close['status'] = 'CLOSED'
                trade_to_close['close_price'] = 0.0
                trade_to_close['close_timestamp'] = int(time.time() * 1000)
                trade_to_close['profit_loss'] = 0
                trade_to_close['close_reason'] = "FAKE_TRADE"
                
                # إضافة الصفقة للمغلقة
                data['closed'].append(trade_to_close)
                save_trades(data)
                
                logger.info(f"✅ تم حذف الصفقة الوهمية {symbol} من قائمة المفتوحة")
                
                # إرسال إشعار عن إغلاق الصفقة الوهمية
                notify_trade_status(
                    symbol=symbol,
                    status=f"تم حذف صفقة وهمية",
                    price=current_price,
                    profit_loss=0,
                    order_id="",
                    api_verified=False
                )
                
                return True
            
            return False
            
        # إذا وصلنا إلى هنا، فالصفقة مؤكدة وموجودة فعلاً
        # تنفيذ أمر البيع على المنصة للصفقة المؤكدة
        success = False
        result = {}
        
        if api_verified:
            logger.info(f"محاولة بيع صفقة مؤكدة {symbol} بكمية {quantity}")
            success, result = execute_sell(symbol, quantity)
            if not success:
                logger.error(f"فشل تنفيذ أمر البيع لـ {symbol} بكمية {quantity}")
        else:
            logger.warning(f"❌ تجاهل تنفيذ أمر البيع لصفقة غير مؤكدة: {symbol}")
        
        # قراءة ملف الصفقات
        trades_data = load_trades()
        
        # البحث عن الصفقة وتحديثها
        for i, t in enumerate(trades_data.get('open', [])):
            if t.get('symbol') == symbol and t.get('timestamp') == trade.get('timestamp'):
                # إغلاق الصفقة
                t['status'] = 'CLOSED'
                t['close_reason'] = reason
                t['close_timestamp'] = int(time.time() * 1000)
                t['api_confirmed'] = api_verified  # إضافة علامة التحقق من API
                
                # إضافة بيانات البيع إذا نجح
                if success and result:
                    t['sell_price'] = result.get('price', 0)
                    t['sell_time'] = result.get('transactTime', 0)
                    
                # نقل الصفقة إلى المغلقة
                if 'closed' not in trades_data:
                    trades_data['closed'] = []
                    
                trades_data['closed'].append(t)
                trades_data['open'].pop(i)
                
                # حفظ التغييرات
                save_trades(trades_data)
                
                # إرسال إشعار تلجرام للصفقات المؤكدة فقط
                if api_verified:
                    sell_price = result.get('price', 0) if success and result else 0
                    profit_loss = ((sell_price - trade.get('entry_price', 0)) / trade.get('entry_price', 1)) * 100 if sell_price > 0 else 0
                    
                    # إرسال إشعار بنجاح البيع
                    notify_trade_status(
                        symbol=symbol,
                        status=f"تم البيع ({reason})",
                        price=sell_price,
                        profit_loss=profit_loss,
                        order_id=result.get('orderId') if success and result else None,
                        api_verified=True
                    )
                else:
                    logger.warning(f"⚠️ تم إغلاق صفقة غير مؤكدة: {symbol} - لم يتم إرسال إشعار")
                
                return True
        
        logger.warning(f"لم يتم العثور على الصفقة لإغلاقها: {symbol} - {trade.get('timestamp')}")
        return False
    except Exception as e:
        logger.error(f"خطأ في إغلاق الصفقة: {e}")
        return False

def check_and_sell_trades() -> int:
    """
    التحقق من الصفقات وبيعها إذا استوفت شروط البيع
    التعامل فقط مع الصفقات المؤكدة والتخلص من الصفقات الوهمية
    
    :return: عدد الصفقات التي تم بيعها
    """
    try:
        # أولاً إنشاء نسخة احتياطية
        create_backup()
        
        data = load_trades()
        open_trades = data.get('open', [])
        
        if not open_trades:
            logger.info("لا توجد صفقات مفتوحة للتحقق")
            return 0
        
        current_time = int(time.time() * 1000)
        sold_count = 0
        cleaned_count = 0
        
        # تنظيف الصفقات غير المؤكدة
        for trade in list(open_trades):  # نسخة من القائمة لتجنب مشاكل التعديل أثناء التكرار
            symbol = trade.get('symbol')
            
            # إذا كانت الصفقة غير مؤكدة، نغلقها ونعلمها كصفقة وهمية
            if not trade.get('api_confirmed', False):
                logger.warning(f"⚠️ تنظيف صفقة غير مؤكدة: {symbol}")
                
                # إغلاق الصفقة وتعليمها كصفقة وهمية
                if close_trade(trade, "FAKE_TRADE_CLEANUP"):
                    cleaned_count += 1
                    
        if cleaned_count > 0:
            logger.info(f"✅ تم تنظيف {cleaned_count} صفقة وهمية")
            
            # قراءة الملف مرة أخرى لأنه تم تعديله في close_trade
            data = load_trades()
            open_trades = data.get('open', [])
        
        # التعامل مع الصفقات المؤكدة
        for trade in list(open_trades):  # نسخة جديدة من القائمة بعد التنظيف
            symbol = trade.get('symbol')
            
            # نتحقق من أن الصفقة مؤكدة (أضفنا للأمان)
            if not trade.get('api_confirmed', False):
                continue
            entry_price = trade.get('entry_price', 0)
            timestamp = trade.get('timestamp', 0)
            
            # التأكد من وجود بيانات صالحة
            if not symbol or not entry_price:
                continue
            
            # الحصول على السعر الحالي
            current_price = get_current_price(symbol)
            if not current_price:
                continue
            
            # حساب نسبة الربح/الخسارة
            profit_percent = (current_price - entry_price) / entry_price * 100
            
            # حساب مدة الاحتفاظ بالصفقة بالساعات
            hold_time_hours = (current_time - timestamp) / (1000 * 60 * 60)
            
            logger.info(f"فحص صفقة {symbol}: الربح/الخسارة={profit_percent:.2f}%, مدة الاحتفاظ={hold_time_hours:.2f} ساعة")
            
            # شروط البيع
            sell_reason = None
            
            # 1. تحقق هدف الربح
            if profit_percent >= SYSTEM_SETTINGS['min_profit']:
                sell_reason = "target_profit"
                
            # 2. وقف الخسارة
            elif profit_percent <= -SYSTEM_SETTINGS['max_loss']:
                sell_reason = "stop_loss"
                
            # 3. تجاوز المدة القصوى
            elif hold_time_hours >= SYSTEM_SETTINGS['max_hold_hours']:
                sell_reason = "max_hold_time"
            
            # تنفيذ البيع إذا تحقق أي شرط
            if sell_reason:
                logger.info(f"سيتم بيع {symbol}: {sell_reason}, الربح/الخسارة={profit_percent:.2f}%")
                
                if close_trade(trade, sell_reason):
                    sold_count += 1
                    logger.info(f"تم بيع {symbol} بنجاح: {sell_reason}")
                else:
                    logger.error(f"فشل بيع {symbol}: {sell_reason}")
        
        return sold_count
    except Exception as e:
        logger.error(f"خطأ في التحقق من الصفقات: {e}")
        return 0

def diversify_portfolio() -> int:
    """
    تنويع المحفظة عن طريق فتح صفقات متنوعة
    
    :return: عدد الصفقات الجديدة التي تم فتحها
    """
    try:
        # الحصول على العملات المتداولة حالياً
        active_symbols = get_active_symbols()
        
        # إذا كان عدد العملات المتداولة وصل للحد الأقصى
        max_trades = SYSTEM_SETTINGS['max_trades']
        if len(active_symbols) >= max_trades:
            logger.info(f"تم الوصول للحد الأقصى من العملات المتداولة: {len(active_symbols)}/{max_trades}")
            return 0
        
        # حساب عدد الصفقات التي يمكن فتحها
        trades_to_open = max_trades - len(active_symbols)
        
        # اختيار عملات متنوعة
        coins_to_buy = select_diverse_coins(trades_to_open)
        
        # مبلغ كل صفقة
        per_trade_amount = calculate_per_trade_amount()
        
        # فتح صفقات جديدة
        opened_count = 0
        
        for coin in coins_to_buy:
            # التحقق إذا كان مسموحاً بتداول العملة
            allowed, reason = is_trade_allowed(coin)
            if not allowed:
                logger.warning(f"تجاهل العملة {coin}: {reason}")
                continue
            
            # تنفيذ الشراء
            logger.info(f"محاولة شراء {coin} بمبلغ {per_trade_amount} دولار")
            success, result = execute_buy(coin, per_trade_amount)
            
            if success:
                opened_count += 1
                logger.info(f"تم شراء {coin} بنجاح")
            else:
                logger.error(f"فشل شراء {coin}")
        
        return opened_count
    except Exception as e:
        logger.error(f"خطأ في تنويع المحفظة: {e}")
        return 0

def manage_trades() -> Dict[str, int]:
    """
    إدارة شاملة للصفقات: التحقق من شروط البيع وتنويع المحفظة
    
    :return: إحصائيات العمليات
    """
    try:
        logger.info("بدء إدارة الصفقات")
        
        # تنظيف أي صفقات وهمية قبل البدء في إدارة الصفقات
        try:
            from app.clean_trades import clean_fake_trades
            cleanup_result = clean_fake_trades()
            cleaned_count = cleanup_result.get('cleaned_count', 0)
            if cleaned_count > 0:
                logger.info(f"تم تنظيف {cleaned_count} صفقة وهمية قبل بدء إدارة الصفقات")
        except ImportError:
            logger.warning("لم يتم العثور على وحدة clean_trades لتنظيف الصفقات الوهمية")
        except Exception as cleanup_error:
            logger.error(f"خطأ في تنظيف الصفقات الوهمية: {cleanup_error}")
            
        # التحقق من الصفقات وبيعها إذا استوفت شروط البيع
        sold_count = check_and_sell_trades()
        
        # تنويع المحفظة
        opened_count = diversify_portfolio()
        
        stats = {
            'sold_trades': sold_count,
            'opened_trades': opened_count
        }
        
        logger.info(f"إحصائيات إدارة الصفقات: {stats}")
        return stats
    except Exception as e:
        logger.error(f"خطأ في إدارة الصفقات: {e}")
        return {'sold_trades': 0, 'opened_trades': 0}

def force_sell_all() -> int:
    """
    بيع جميع الصفقات المفتوحة بشكل قسري
    
    :return: عدد الصفقات التي تم بيعها
    """
    try:
        data = load_trades()
        open_trades = data.get('open', [])
        
        sold_count = 0
        
        for trade in list(open_trades):  # نسخة من القائمة لتجنب مشاكل التعديل أثناء التكرار
            if close_trade(trade, "forced_sell"):
                sold_count += 1
        
        logger.info(f"تم بيع {sold_count} صفقة بشكل قسري")
        return sold_count
    except Exception as e:
        logger.error(f"خطأ في البيع القسري: {e}")
        return 0

def run_trade_cycle():
    """
    تشغيل دورة تداول كاملة: التحقق من شروط البيع، تنويع المحفظة
    """
    try:
        # إدارة الصفقات
        stats = manage_trades()
        
        # عرض العملات المتداولة بعد الدورة
        active_symbols = get_active_symbols()
        logger.info(f"العملات المتداولة بعد دورة التداول: {active_symbols}")
        
        # مراقبة حالة التنويع
        if len(active_symbols) < SYSTEM_SETTINGS['max_trades']:
            logger.warning(f"⚠️ التنويع غير مكتمل. عدد العملات المتداولة: {len(active_symbols)}/{SYSTEM_SETTINGS['max_trades']}")
        
        return stats
    except Exception as e:
        logger.error(f"خطأ في دورة التداول: {e}")
        return {'sold_trades': 0, 'opened_trades': 0}