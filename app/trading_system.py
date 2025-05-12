"""
نظام التداول الموحد - المسؤول الرئيسي عن إدارة جميع عمليات التداول
يعمل كواجهة مركزية لتنفيذ جميع عمليات الشراء والبيع والتحقق من الصفقات
"""
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any, Optional

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trading_system')

# ملف تخزين الصفقات
TRADES_FILE = 'active_trades.json'

# قفل للتعامل مع الملفات
import threading
FILE_LOCK = threading.RLock()

# استيراد الإعدادات والوظائف المساعدة
try:
    from app.config import SYSTEM_SETTINGS
except ImportError:
    # إعدادات افتراضية في حالة عدم وجود SYSTEM_SETTINGS
    logger.warning("❌ لم يتم العثور على SYSTEM_SETTINGS في ملف config.py، استخدام الإعدادات الافتراضية")
    SYSTEM_SETTINGS = {
        'blacklisted_symbols': [],
        'max_trades': 10,  # تم زيادة الحد الأقصى للصفقات من 5 إلى 10
        'total_capital': 25.0,
        'per_trade_amount': 5.0,
        'min_profit': 0.005,
        'multi_tp_targets': [0.005, 0.01, 0.02],
        'tp_quantity_ratios': [0.4, 0.3, 0.3],
        'max_loss': 0.01,
        'max_hold_hours': 2,
        'trade_cycle_interval': 300,  # تم تغييره من 900 (15 دقيقة) إلى 300 (5 دقائق) لجعل البوت أكثر نشاطاً
        'enforce_diversity': True,
        'prioritized_coins': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT']
    }
from app.mexc_api import (
    get_current_price, 
    place_order, 
    get_account_balance, 
    get_all_symbols_24h_data,
    get_open_orders,
    get_trades_history
)
from app.telegram_notify import notify_trade_status

# قائمة العملات ذات الأولوية للتداول
PRIORITY_COINS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 
    'DOGEUSDT', 'SOLUSDT', 'MATICUSDT', 'DOTUSDT', 'LTCUSDT'
]

def create_backup() -> str:
    """
    إنشاء نسخة احتياطية من ملف الصفقات
    
    :return: اسم ملف النسخة الاحتياطية
    """
    try:
        if not os.path.exists(TRADES_FILE):
            logger.warning(f"ملف الصفقات {TRADES_FILE} غير موجود لإنشاء نسخة احتياطية")
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
                        'open': data,
                        'closed': []
                    }
            
            # إنشاء ملف جديد إذا لم يكن موجودًا
            return {
                'open': [],
                'closed': []
            }
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {
            'open': [],
            'closed': []
        }

def save_trades(data: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    حفظ الصفقات في الملف
    
    :param data: بيانات الصفقات
    :return: نجاح العملية
    """
    try:
        with FILE_LOCK:
            with open(TRADES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def get_active_symbols() -> Set[str]:
    """
    الحصول على مجموعة العملات المتداولة حالياً
    
    :return: مجموعة من العملات المتداولة
    """
    try:
        data = load_trades()
        return {trade.get('symbol', '') for trade in data.get('open', [])}
    except Exception as e:
        logger.error(f"خطأ في الحصول على العملات المتداولة: {e}")
        return set()

def is_trade_allowed(symbol: str) -> Tuple[bool, str]:
    """
    التحقق ما إذا كان مسموحاً بتداول العملة
    
    :param symbol: رمز العملة
    :return: (مسموح، السبب)
    """
    # تحقق من وجود العملة في القائمة السوداء
    if symbol in SYSTEM_SETTINGS['blacklisted_symbols']:
        return False, "العملة في القائمة السوداء"
        
    # تحقق من عدم تجاوز الحد الأقصى للصفقات
    active_trades = load_trades().get('open', [])
    if len(active_trades) >= SYSTEM_SETTINGS['max_trades']:
        return False, f"وصلنا للحد الأقصى للصفقات: {SYSTEM_SETTINGS['max_trades']}"
        
    # تحقق من عدم وجود صفقة مفتوحة للعملة
    active_symbols = get_active_symbols()
    if symbol in active_symbols:
        return False, "توجد صفقة مفتوحة بالفعل لهذه العملة"
    
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
            # والتركيز على العملات ذات الحجم الجيد
            available_coins = [
                symbol_data.get('symbol') 
                for symbol_data in all_symbols_data 
                if symbol_data.get('symbol', '').endswith('USDT') and 
                   symbol_data.get('symbol') not in excluded_symbols and
                   float(symbol_data.get('quoteVolume', 0)) > 1000000  # حجم تداول جيد
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
    return SYSTEM_SETTINGS['per_trade_amount']

def verify_trade_with_api(trade: Dict[str, Any]) -> bool:
    """
    التحقق من وجود الصفقة في سجلات API المنصة
    يستخدم عدة طرق للتحقق من وجود الصفقة
    
    :param trade: بيانات الصفقة
    :return: ما إذا كانت الصفقة موجودة فعلاً في المنصة
    """
    try:
        symbol = trade.get('symbol')
        order_id = trade.get('orderId')
        
        if not symbol or not order_id:
            logger.warning(f"بيانات الصفقة غير مكتملة: {trade}")
            return False
            
        # طريقة 1: البحث في تاريخ التداول
        trade_history = get_trades_history(symbol, limit=50)
        for hist_trade in trade_history:
            if str(hist_trade.get('orderId')) == str(order_id):
                logger.info(f"✅ تم تأكيد الصفقة في تاريخ التداول: {symbol}")
                return True
                
        # طريقة 2: التحقق من وجود العملة في الرصيد
        account_data = get_account_balance()
        coin_symbol = symbol.replace('USDT', '')
        
        # البحث عن العملة في هيكل البيانات الصحيح لـ MEXC
        has_coin_balance = False
        reason = ""
        
        if account_data and 'balances' in account_data:
            for asset in account_data['balances']:
                if asset['asset'] == coin_symbol:
                    free_balance = float(asset.get('free', 0))
                    locked_balance = float(asset.get('locked', 0))
                    total_balance = free_balance + locked_balance
                    
                    if total_balance > 0:
                        logger.info(f"✅ تم تأكيد الصفقة من خلال وجود رصيد {total_balance} من العملة: {coin_symbol}")
                        return True
                    else:
                        reason = f"العملة {coin_symbol} موجودة ولكن رصيدها 0"
                        
        if not has_coin_balance:
            logger.warning(f"⚠️ لم يتم العثور على رصيد كافي للعملة {coin_symbol}: {reason}")
                
        # طريقة 3: التحقق من الأوامر المفتوحة
        open_orders = get_open_orders()
        for order in open_orders:
            if str(order.get('orderId')) == str(order_id):
                logger.info(f"✅ تم تأكيد الصفقة في الأوامر المفتوحة: {symbol}")
                return True
        
        # إذا وصلنا إلى هنا، لم نتمكن من تأكيد الصفقة
        close_reason = f"FAKE_TRADE_CLEANUP: لا يوجد أمر مفتوح ولا رصيد للعملة"
        logger.warning(f"❌ لم يتم تأكيد الصفقة عبر أي طريقة: {symbol} - {close_reason}")
        return False
    except Exception as e:
        logger.error(f"خطأ أثناء التحقق من الصفقة: {e}")
        return False

def restore_missing_trades() -> int:
    """
    استعادة الصفقات المفقودة استنادًا إلى أرصدة العملات في الحساب
    
    :return: عدد الصفقات التي تم استعادتها
    """
    logger.info("🔄 البدء في استعادة الصفقات المفقودة بناءً على أرصدة العملات...")
    
    try:
        # استيراد دالة get_current_price
        from app.mexc_api import get_current_price
        
        # إنشاء نسخة احتياطية قبل التعديل
        create_backup()
        
        # الحصول على الصفقات المفتوحة
        data = load_trades()
        open_trades = data.get('open', [])
        
        # الحصول على العملات المتداولة حاليًا
        active_symbols = set([trade['symbol'] for trade in open_trades])
        
        # الحصول على أرصدة العملات
        account_data = get_account_balance()
        restored_count = 0
        
        if account_data and 'balances' in account_data:
            for asset in account_data['balances']:
                symbol = asset['asset']
                # تجاهل USDT
                if symbol == 'USDT':
                    continue
                    
                free_balance = float(asset.get('free', 0))
                locked_balance = float(asset.get('locked', 0))
                total_balance = free_balance + locked_balance
                
                # إذا كان هناك رصيد كافٍ وليس هناك صفقة مفتوحة لهذه العملة
                market_symbol = f"{symbol}USDT"
                if total_balance > 0 and market_symbol not in active_symbols:
                    # الحصول على سعر العملة الحالي
                    try:
                        current_price = get_current_price(market_symbol)
                        logger.info(f"تم الحصول على سعر للعملة {market_symbol}: {current_price}")
                    except Exception as price_error:
                        logger.error(f"خطأ في الحصول على سعر {market_symbol}: {price_error}")
                        current_price = 0
                    
                    if current_price is not None and current_price > 0:
                        # إنشاء صفقة جديدة
                        new_trade = {
                            'symbol': market_symbol,
                            'quantity': total_balance,
                            'entry_price': current_price,  # نستخدم السعر الحالي كسعر الدخول
                            'timestamp': int(time.time() * 1000),
                            'status': 'OPEN',
                            'api_executed': True,
                            'api_confirmed': True,  # تأكيد الصفقة مباشرة
                            'order_type': 'MARKET',
                            'stop_loss': -3.0,  # وقف خسارة بنسبة 3%
                            'take_profit_targets': [
                                {'percent': 0.01, 'hit': False},
                                {'percent': 0.01, 'hit': False},
                                {'percent': 0.01, 'hit': False}
                            ]
                        }
                        
                        # إضافة الصفقة إلى القائمة
                        open_trades.append(new_trade)
                        restored_count += 1
                        
                        logger.info(f"✅ تمت استعادة صفقة مفقودة: {market_symbol} بكمية {total_balance} وسعر دخول {current_price}")
                    else:
                        logger.warning(f"⚠️ لم يتم استعادة صفقة {market_symbol} لأن السعر الحالي غير متوفر")
            
            # حفظ البيانات
            if restored_count > 0:
                data['open'] = open_trades
                save_trades(data)
                logger.info(f"✅ تم استعادة {restored_count} صفقة مفقودة بنجاح")
                
        return restored_count
    except Exception as e:
        logger.error(f"❌ خطأ في استعادة الصفقات المفقودة: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0

def clean_fake_trades() -> Dict[str, int]:
    """
    تنظيف الصفقات الوهمية
    
    :return: إحصائيات التنظيف
    """
    try:
        # إنشاء نسخة احتياطية قبل التنظيف
        create_backup()
        
        # تحميل الصفقات
        trades_data = load_trades()
        original_count = len(trades_data.get('open', []))
        
        # الأوامر المفتوحة على المنصة
        try:
            api_orders = get_open_orders() or []
            api_order_ids = [str(o.get('orderId')) for o in api_orders if o.get('orderId')]
            logger.info(f"وجدت {len(api_orders)} أمر مفتوح على المنصة")
        except Exception as e:
            logger.error(f"خطأ في الاتصال بـ API للتحقق من الأوامر المفتوحة: {e}")
            api_order_ids = []
        
        # أرصدة الحساب للتحقق من وجود العملات
        try:
            account_data = get_account_balance()
            assets_with_balance = []
            
            if account_data and 'balances' in account_data:
                for asset in account_data['balances']:
                    if float(asset.get('free', 0)) > 0 or float(asset.get('locked', 0)) > 0:
                        assets_with_balance.append(asset['asset'])
            
            logger.info(f"العملات التي لدينا رصيد منها: {assets_with_balance}")
        except Exception as e:
            logger.error(f"خطأ في الاتصال بـ API للتحقق من أرصدة الحساب: {e}")
            assets_with_balance = []
        
        # تنظيف الصفقات الوهمية
        cleaned_open = []
        closed_fake = []
        
        for trade in trades_data.get('open', []):
            symbol = trade.get('symbol', '')
            is_fake = False
            fake_reason = ''
            
            # الطريقة 1: التحقق من العلامات الصريحة
            if trade.get('test_trade') == True or trade.get('api_executed') == False or trade.get('api_confirmed') == False:
                is_fake = True
                fake_reason = 'علامات صريحة'
                
            # الطريقة 2: التحقق من وجود أمر مفتوح على المنصة
            elif str(trade.get('orderId', '')) not in api_order_ids:
                # إذا لم يكن هناك أمر مفتوح، نتحقق من وجود رصيد للعملة
                coin_symbol = symbol.replace('USDT', '')
                if coin_symbol not in assets_with_balance:
                    is_fake = True
                    fake_reason = 'لا يوجد أمر مفتوح ولا رصيد للعملة'
            
            # إغلاق الصفقات الوهمية
            if is_fake:
                trade['status'] = 'CLOSED'
                trade['api_confirmed'] = False
                trade['close_reason'] = f'FAKE_TRADE_CLEANUP: {fake_reason}'
                trade['close_timestamp'] = int(time.time() * 1000)
                closed_fake.append(trade)
            else:
                cleaned_open.append(trade)
        
        # تحديث الصفقات
        trades_data['open'] = cleaned_open
        
        # نقل الصفقات الوهمية إلى المغلقة
        if closed_fake:
            trades_data['closed'].extend(closed_fake)
            
        # حفظ التغييرات
        save_trades(trades_data)
        
        current_count = len(trades_data.get('open', []))
        cleaned_count = original_count - current_count
        
        logger.info(f"🧹 تم تنظيف {cleaned_count} صفقة وهمية من أصل {original_count} صفقة مفتوحة")
        
        return {
            'original_count': original_count,
            'current_count': current_count,
            'cleaned_count': cleaned_count
        }
    except Exception as e:
        logger.error(f"خطأ في تنظيف الصفقات الوهمية: {e}")
        # إزالة حقل error لتجنب مشكلة الأنواع المختلطة
        return {
            'original_count': 0,
            'current_count': 0,
            'cleaned_count': 0
        }

def execute_buy(symbol: str, amount: float) -> Tuple[bool, Dict]:
    """
    تنفيذ عملية الشراء مع تأكيد قطعي للصفقات الحقيقية فقط
    
    :param symbol: رمز العملة
    :param amount: المبلغ بالدولار
    :return: (نجاح العملية، بيانات الأمر)
    """
    try:
        # متغير لتخزين رصيد USDT قبل الشراء
        initial_usdt_balance = 0
        
        # تحقق أولاً من رصيد USDT - مع دعم جميع الهياكل الممكنة
        try:
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
                
                # استيراد get_balance من mexc_api إذا لم يكن موجودًا
                try:
                    from app.mexc_api import get_balance
                    direct_balance = get_balance('USDT')
                    initial_usdt_balance = float(direct_balance) if direct_balance else 0
                    logger.info(f"💰 رصيد USDT المتاح (بطريقة مباشرة): {initial_usdt_balance}")
                except Exception as import_error:
                    logger.error(f"❌ خطأ في استيراد get_balance: {import_error}")
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
        
        # تحضير أهداف الربح - تم تعديلها لتكون 0.01% (1 سنت) لزيادة حركة التداول
        take_profit_targets = [
            {'percent': 0.01, 'hit': False},
            {'percent': 0.01, 'hit': False},
            {'percent': 0.01, 'hit': False}
        ]
        
        # إنشاء سجل للصفقة
        order_info = {
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': price,
            'stop_loss': -3.0,  # وقف خسارة 3%
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

def execute_sell(symbol: str, quantity: float, trade_data: Dict[str, Any]) -> Tuple[bool, Dict]:
    """
    تنفيذ عملية البيع مع تأكيد قطعي للصفقات الحقيقية فقط
    
    :param symbol: رمز العملة
    :param quantity: الكمية
    :param trade_data: بيانات الصفقة
    :return: (نجاح العملية، بيانات الأمر)
    """
    try:
        # الرصيد الأولي للعملة
        initial_coin_balance = 0
        coin_symbol = symbol.replace('USDT', '')
        
        # تحقق من الرصيد قبل البيع
        try:
            logger.info(f"التحقق من رصيد {coin_symbol} قبل البيع...")
            balance = get_account_balance()
            if balance and coin_symbol in balance:
                initial_coin_balance = float(balance[coin_symbol].get('free', 0))
                logger.info(f"💰 رصيد {coin_symbol} المتاح: {initial_coin_balance}")
                
                if initial_coin_balance < quantity * 0.95:  # نسمح بفارق 5% للرسوم
                    logger.warning(f"⚠️ رصيد {coin_symbol} أقل من المتوقع. متاح: {initial_coin_balance}, مطلوب: {quantity}")
                    # لكننا نستمر ونبيع ما هو متاح
                    quantity = initial_coin_balance
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من الرصيد: {e}")
            # نستمر للمحاولة مع الكمية الأصلية
        
        # الحصول على السعر الحالي
        price = get_current_price(symbol)
        if not price:
            logger.error(f"لم يتم الحصول على سعر العملة {symbol}")
            return False, {"error": "لم يتم الحصول على السعر"}
        
        logger.info(f"🔶 محاولة بيع {symbol}: السعر={price}, الكمية={quantity}")
        
        # تنفيذ أمر البيع
        result = place_order(symbol, "SELL", quantity, None, "MARKET")
        
        # تحقق من نجاح الأمر المبدئي
        if not result or 'error' in result or 'orderId' not in result:
            logger.error(f"❌ فشل أمر البيع: {symbol} - {result}")
            return False, result
            
        logger.info(f"✅ تم إرسال أمر البيع بنجاح: {result}")
        
        # التحقق من تنفيذ الصفقة فعلياً - إنتظار قصير للتأكد من تحديث تاريخ التداول
        time.sleep(2)
        
        # نتحقق عبر تاريخ التداول أولاً
        trade_history_verified = False
        try:
            logger.info(f"🔍 التحقق من تنفيذ صفقة البيع {symbol} في تاريخ التداول...")
            
            # محاولات متعددة للتحقق من تنفيذ الصفقة خلال 10 ثوانٍ
            for attempt in range(3):
                recent_trades = get_trades_history(symbol, 20)
                order_id = result.get('orderId')
                
                if recent_trades:
                    for trade_record in recent_trades:
                        if str(trade_record.get('orderId')) == str(order_id):
                            trade_history_verified = True
                            logger.info(f"✅✅ تأكيد وجود صفقة البيع في تاريخ التداول: {symbol} (معرف الأمر: {order_id})")
                            break
                
                if trade_history_verified:
                    break
                    
                # إنتظار قصير ثم محاولة مرة أخرى
                logger.warning(f"⚠️ محاولة {attempt+1}/3: لم يتم العثور على صفقة البيع في تاريخ التداول بعد. إنتظار...")
                time.sleep(2)
            
            if not trade_history_verified:
                logger.error(f"❌❌ لم يتم تأكيد صفقة البيع في تاريخ التداول بعد 3 محاولات: {symbol}")
                return False, {"error": "لم يتم تأكيد صفقة البيع في تاريخ التداول"}
                
        except Exception as e:
            logger.error(f"❌ خطأ أثناء التحقق من تاريخ التداول: {e}")
            return False, {"error": f"خطأ أثناء التحقق من تاريخ التداول: {e}"}
        
        # حساب الربح/الخسارة
        entry_price = trade_data.get('entry_price', 0)
        profit_percent = ((price - entry_price) / entry_price) * 100 if entry_price else 0
        
        # التحقق من تغير الرصيد بعد البيع
        try:
            new_balance = get_account_balance()
            if new_balance and coin_symbol in new_balance:
                new_coin_balance = float(new_balance[coin_symbol].get('free', 0))
                balance_diff = initial_coin_balance - new_coin_balance
                logger.info(f"💰 تغير رصيد {coin_symbol}: {initial_coin_balance} → {new_coin_balance} (فرق: {balance_diff})")
                
                # التحقق إذا كان هناك تغير فعلي في الرصيد يقارب قيمة الصفقة
                if balance_diff < quantity * 0.8:  # يجب أن يكون التغير على الأقل 80% من قيمة الصفقة
                    logger.warning(f"⚠️ تغير الرصيد أقل من المتوقع: {balance_diff} < {quantity}")
                    # لكننا نستمر لأن الصفقة تم تأكيدها بالفعل في تاريخ التداول
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من تغير الرصيد: {e}")
            # نستمر لأن الصفقة تم تأكيدها بالفعل في تاريخ التداول
        
        # إرسال إشعار بنجاح البيع
        notify_trade_status(
            symbol=symbol,
            status=f"تم البيع بربح {profit_percent:.2f}%",
            price=price,
            profit_loss=profit_percent,
            order_id=result.get('orderId'),
            api_verified=True
        )
        
        return True, result
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ البيع لـ {symbol}: {e}")
        return False, {"error": str(e)}

def close_trade(trade: Dict[str, Any], reason: str, api_verified: bool = True) -> bool:
    """
    إغلاق صفقة وتحديث ملف الصفقات - يتعامل فقط مع الصفقات الحقيقية المؤكدة
    
    :param trade: بيانات الصفقة
    :param reason: سبب الإغلاق
    :param api_verified: هل تم التحقق من الصفقة عبر API
    :return: نجاح العملية
    """
    try:
        symbol = trade.get('symbol')
        quantity = trade.get('quantity', 0)
        
        # تنفيذ البيع إذا كانت الصفقة مؤكدة
        success = False
        result = None
        
        if api_verified and symbol and quantity > 0:
            logger.info(f"تنفيذ بيع {symbol} بكمية {quantity} (سبب: {reason})")
            success, result = execute_sell(symbol, quantity, trade)
            
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
    التركيز على الصفقات ذات القيمة (5 دولار فأكثر)
    
    تم تعديل هدف الربح ليكون 0.01% (1 سنت) لزيادة حركة التداول في البوت والمنصة
    مما يتيح تنفيذ عمليات بيع أكثر تكرارًا وزيادة النشاط
    
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
        
        # تحديد الصفقات ذات قيمة 5 دولار أو أكثر
        high_value_trades = []
        low_value_trades = []
        
        # تصنيف الصفقات حسب قيمتها
        for trade in open_trades:
            symbol = trade.get('symbol', '')
            quantity = trade.get('quantity', 0)
            entry_price = trade.get('entry_price', 0)
            
            # حساب القيمة بالدولار
            value_usd = quantity * entry_price
            trade['value_usd'] = value_usd  # إضافة القيمة للصفقة
            
            if value_usd >= 5.0:
                high_value_trades.append(trade)
                logger.info(f"📊 صفقة ذات قيمة عالية: {symbol} - {value_usd:.2f}$")
            else:
                low_value_trades.append(trade)
                logger.info(f"📊 صفقة ذات قيمة منخفضة: {symbol} - {value_usd:.2f}$")
        
        logger.info(f"💰 عدد الصفقات ذات القيمة العالية: {len(high_value_trades)}/{len(open_trades)}")
        logger.info(f"💸 عدد الصفقات ذات القيمة المنخفضة: {len(low_value_trades)}/{len(open_trades)}")
        
        # تنظيف الصفقات غير المؤكدة
        for trade in list(open_trades):  # نسخة من القائمة لتجنب مشاكل التعديل أثناء التكرار
            symbol = trade.get('symbol')
            
            # إذا كانت الصفقة غير مؤكدة، نغلقها ونعلمها كصفقة وهمية
            if not trade.get('api_confirmed', False):
                logger.warning(f"⚠️ تنظيف صفقة غير مؤكدة: {symbol}")
                
                # إغلاق الصفقة وتعليمها كصفقة وهمية
                if close_trade(trade, "FAKE_TRADE_CLEANUP", api_verified=False):
                    cleaned_count += 1
                    
        if cleaned_count > 0:
            logger.info(f"✅ تم تنظيف {cleaned_count} صفقة وهمية")
            
            # قراءة الملف مرة أخرى لأنه تم تعديله في close_trade
            data = load_trades()
            open_trades = data.get('open', [])
        
        # التعامل مع الصفقات المؤكدة (التركيز على الصفقات ذات القيمة العالية)
        for trade in list(open_trades):  # نسخة جديدة من القائمة بعد التنظيف
            symbol = trade.get('symbol')
            
            # نتحقق من أن الصفقة مؤكدة (أضفنا للأمان)
            if not trade.get('api_confirmed', False):
                continue
                
            entry_price = trade.get('entry_price', 0)
            timestamp = trade.get('timestamp', 0)
            value_usd = trade.get('value_usd', 0)
            
            # التأكد من وجود بيانات صالحة
            if not symbol or not entry_price:
                continue
            
            # التركيز فقط على الصفقات ذات القيمة العالية (5 دولار فأكثر)
            if value_usd < 5.0:
                logger.info(f"⏩ تجاهل صفقة {symbol} ذات قيمة منخفضة ({value_usd:.2f}$)")
                continue
            
            # الحصول على السعر الحالي
            current_price = get_current_price(symbol)
            if not current_price:
                continue
            
            # حساب نسبة الربح/الخسارة
            profit_percent = (current_price - entry_price) / entry_price * 100
            
            # حساب مدة الاحتفاظ بالصفقة بالساعات
            hold_time_hours = (current_time - timestamp) / (1000 * 60 * 60)
            
            logger.info(f"فحص صفقة {symbol}: الربح/الخسارة={profit_percent:.2f}%, مدة الاحتفاظ={hold_time_hours:.2f} ساعة, القيمة={value_usd:.2f}$")
            
            # فحص أهداف الربح المتعددة
            tp_targets = trade.get('take_profit_targets', [])
            target_hit = False
            
            for i, target in enumerate(tp_targets):
                target_percent = target.get('percent', 0)
                already_hit = target.get('hit', False)
                
                if not already_hit and profit_percent >= target_percent:
                    # تعليم الهدف كمحقق
                    tp_targets[i]['hit'] = True
                    target_hit = True
                    
                    # تحديث الصفقة في الملف
                    update_data = load_trades()
                    for t in update_data.get('open', []):
                        if t.get('symbol') == symbol and t.get('timestamp') == timestamp:
                            t['take_profit_targets'] = tp_targets
                            break
                    save_trades(update_data)
                    
                    logger.info(f"🎯 تم تحقيق هدف الربح {target_percent}% للعملة {symbol}")
                    
                    # إرسال إشعار بتحقيق الهدف
                    notify_trade_status(
                        symbol=symbol,
                        status=f"تم تحقيق هدف {target_percent}%",
                        price=current_price,
                        profit_loss=profit_percent,
                        api_verified=True
                    )
            
            # شروط البيع
            sell_reason = None
            
            # 1. تحقق أهداف الربح
            # نتحقق إذا تم تحقيق جميع الأهداف
            all_targets_hit = all(target.get('hit', False) for target in tp_targets)
            if all_targets_hit:
                sell_reason = "all_targets_hit"
            
            # 2. وقف الخسارة
            elif profit_percent <= trade.get('stop_loss', -3.0):
                sell_reason = "stop_loss"
                
            # 3. تجاوز المدة القصوى
            elif hold_time_hours >= SYSTEM_SETTINGS['max_hold_hours']:
                sell_reason = "max_hold_time"
            
            # تنفيذ البيع إذا تحقق أي شرط
            if sell_reason:
                logger.info(f"سيتم بيع {symbol}: {sell_reason}, الربح/الخسارة={profit_percent:.2f}%")
                
                if close_trade(trade, sell_reason, api_verified=True):
                    sold_count += 1
        
        return sold_count
    except Exception as e:
        logger.error(f"خطأ في التحقق من الصفقات: {e}")
        return 0

def diversify_portfolio() -> int:
    """
    تنويع المحفظة عن طريق فتح صفقات متنوعة
    التركيز على الصفقات ذات القيمة العالية (5 دولار فأكثر)
    
    :return: عدد الصفقات الجديدة التي تم فتحها
    """
    try:
        # تنظيف الصفقات الوهمية قبل فتح صفقات جديدة
        clean_result = clean_fake_trades()
        
        # فحص عدد الصفقات المفتوحة حالياً
        data = load_trades()
        open_trades = data.get('open', [])
        
        # تحديد الصفقات ذات القيمة العالية (5 دولار أو أكثر)
        high_value_trades = []
        
        for trade in open_trades:
            symbol = trade.get('symbol', '')
            quantity = trade.get('quantity', 0)
            entry_price = trade.get('entry_price', 0)
            
            # حساب القيمة بالدولار
            value_usd = quantity * entry_price
            
            if value_usd >= 5.0:
                high_value_trades.append(trade)
                logger.info(f"💰 صفقة ذات قيمة عالية: {symbol} - {value_usd:.2f}$")
        
        current_high_value_count = len(high_value_trades)
        logger.info(f"💰 عدد الصفقات ذات القيمة العالية الحالية: {current_high_value_count}")
        
        # عدد الصفقات المتاحة للفتح (بالتركيز على الصفقات ذات القيمة العالية)
        available_slots = SYSTEM_SETTINGS['max_trades'] - current_high_value_count
        
        if available_slots <= 0:
            logger.info(f"لا توجد فرص لفتح صفقات جديدة. الحد الأقصى للصفقات ذات القيمة العالية ({SYSTEM_SETTINGS['max_trades']}) مستخدم بالفعل.")
            return 0
        
        # اختيار عملات متنوعة
        selected_coins = select_diverse_coins(available_slots)
        
        # فحص رصيد USDT
        try:
            balances = get_account_balance()
            usdt_balance = 0
            
            # طريقة 1: البحث عن USDT كمفتاح مباشر (الطريقة القديمة)
            if balances and 'USDT' in balances:
                usdt_balance = float(balances['USDT'].get('free', 0))
                logger.info(f"💰 رصيد USDT المتاح (كمفتاح مباشر): {usdt_balance}")
            
            # طريقة 2: البحث في قائمة 'balances' (الهيكل الجديد)
            elif balances and 'balances' in balances:
                for asset in balances['balances']:
                    if isinstance(asset, dict) and asset.get('asset') == 'USDT':
                        usdt_balance = float(asset.get('free', 0))
                        logger.info(f"💰 رصيد USDT المتاح (من balances): {usdt_balance}")
                        break
            
            if usdt_balance <= 0:
                logger.error("❌ لم يتم العثور على رصيد USDT. لا يمكن فتح صفقات جديدة.")
                return 0
            
            # المبلغ المخصص لكل صفقة - إجبار القيمة لتكون 5 دولار على الأقل
            per_trade_amount = max(5.0, calculate_per_trade_amount())
            logger.info(f"💵 المبلغ المخصص لكل صفقة: {per_trade_amount}$ (لضمان صفقات ذات قيمة عالية)")
            
            # التحقق من كفاية الرصيد لجميع الصفقات
            total_required = per_trade_amount * len(selected_coins)
            
            if usdt_balance < total_required:
                logger.warning(f"⚠️ رصيد USDT ({usdt_balance}) غير كافٍ لفتح {len(selected_coins)} صفقة. المطلوب: {total_required}")
                
                # تعديل عدد الصفقات بناءً على الرصيد المتاح
                max_possible_trades = int(usdt_balance / per_trade_amount)
                logger.info(f"🔄 تعديل عدد الصفقات إلى {max_possible_trades} بناءً على الرصيد المتاح")
                
                if max_possible_trades <= 0:
                    logger.error("❌ رصيد USDT غير كافٍ لفتح أي صفقة ذات قيمة 5 دولار أو أكثر.")
                    return 0
                
                selected_coins = selected_coins[:max_possible_trades]
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من رصيد USDT: {e}")
            return 0
        
        # تنفيذ الصفقات
        opened_count = 0
        
        for coin in selected_coins:
            # التحقق مرة أخرى من إمكانية فتح صفقة
            allowed, reason = is_trade_allowed(coin)
            
            if not allowed:
                logger.warning(f"⚠️ لا يمكن فتح صفقة لـ {coin}: {reason}")
                continue
            
            # محاولة فتح صفقة
            success, result = execute_buy(coin, per_trade_amount)
            
            if success:
                opened_count += 1
                logger.info(f"✅ تم فتح صفقة جديدة ذات قيمة عالية: {coin} بمبلغ {per_trade_amount}$")
            else:
                logger.error(f"❌ فشل فتح صفقة: {coin} - {result}")
        
        logger.info(f"📊 تم فتح {opened_count} صفقة جديدة من أصل {len(selected_coins)} محاولة")
        return opened_count
    except Exception as e:
        logger.error(f"خطأ في تنويع المحفظة: {e}")
        return 0

def manage_trades() -> Dict[str, Any]:
    """
    إدارة شاملة للصفقات: التحقق من شروط البيع وتنويع المحفظة
    
    :return: إحصائيات العمليات
    """
    try:
        # إنشاء نسخة احتياطية
        create_backup()
        
        # تنظيف الصفقات الوهمية
        clean_result = clean_fake_trades()
        
        # بيع الصفقات التي استوفت الشروط
        sold_count = check_and_sell_trades()
        
        # فتح صفقات جديدة للتنويع
        opened_count = diversify_portfolio()
        
        return {
            'cleaned_count': clean_result.get('cleaned_count', 0),
            'sold_count': sold_count,
            'opened_count': opened_count
        }
    except Exception as e:
        logger.error(f"خطأ في إدارة الصفقات: {e}")
        # إزالة حقل error لتجنب مشكلة الأنواع المختلطة
        return {
            'cleaned_count': 0,
            'sold_count': 0,
            'opened_count': 0
        }

def force_sell_all() -> int:
    """
    بيع جميع الصفقات المفتوحة بشكل قسري
    
    :return: عدد الصفقات التي تم بيعها
    """
    try:
        # إنشاء نسخة احتياطية
        create_backup()
        
        # تنظيف الصفقات الوهمية
        clean_fake_trades()
        
        # تحميل الصفقات
        data = load_trades()
        open_trades = data.get('open', [])
        
        if not open_trades:
            logger.info("لا توجد صفقات مفتوحة للبيع")
            return 0
        
        sold_count = 0
        
        # بيع جميع الصفقات
        for trade in list(open_trades):
            # نتحقق فقط من الصفقات المؤكدة
            if not trade.get('api_confirmed', False):
                continue
                
            symbol = trade.get('symbol')
            
            if close_trade(trade, "FORCE_SELL", api_verified=True):
                sold_count += 1
                logger.info(f"✅ تم بيع {symbol} بشكل قسري")
        
        logger.info(f"📊 تم بيع {sold_count} صفقة بشكل قسري")
        return sold_count
    except Exception as e:
        logger.error(f"خطأ في البيع القسري: {e}")
        return 0

def run_trade_cycle():
    """
    تشغيل دورة تداول كاملة: التحقق من شروط البيع، تنويع المحفظة
    """
    try:
        logger.info("🔄 بدء دورة تداول جديدة")
        
        # استعادة الصفقات المفقودة أولاً
        restored_trades = restore_missing_trades()
        if restored_trades > 0:
            logger.info(f"✅ تم استعادة {restored_trades} صفقة مفقودة في بداية الدورة")
            
        # إدارة الصفقات
        stats = manage_trades()
        
        # إضافة عدد الصفقات المستعادة إلى الإحصائيات
        if restored_trades > 0:
            stats['restored_count'] = restored_trades
            
        logger.info(f"📊 إحصائيات دورة التداول: {stats}")
        
        # إنتظار المدة المحددة قبل الدورة التالية
        cycle_interval = SYSTEM_SETTINGS.get('trade_cycle_interval', 300)  # 5 دقائق افتراضياً (تم تغييره من 15 دقيقة)
        logger.info(f"⏱️ انتظار {cycle_interval} ثانية قبل الدورة التالية")
        
        return stats
    except Exception as e:
        logger.error(f"خطأ في دورة التداول: {e}")
        return {'error': str(e)}