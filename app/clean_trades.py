"""
أداة لتنظيف ملف الصفقات وإزالة السجلات المكررة والخاطئة والصفقات الوهمية
"""
import json
import logging
import os
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('clean_trades')

TRADES_FILE = 'active_trades.json'
BACKUP_FILE = 'active_trades.json.backup'

def backup_trades_file():
    """
    إنشاء نسخة احتياطية من ملف الصفقات
    """
    try:
        if os.path.exists(TRADES_FILE):
            import shutil
            backup_name = f"{BACKUP_FILE}.{int(time.time())}"
            shutil.copy2(TRADES_FILE, backup_name)
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
            return True
        return False
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")
        return False

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
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return []

def save_trades(trades):
    """
    حفظ الصفقات في ملف JSON
    
    :param trades: قائمة بالصفقات
    """
    try:
        with open(TRADES_FILE, 'w') as f:
            json.dump(trades, f, indent=2)
        logger.info(f"تم حفظ {len(trades)} صفقة في الملف")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def clean_trades():
    """
    تنظيف ملف الصفقات:
    1. إزالة السجلات المكررة
    2. إصلاح حقول البيانات الناقصة
    3. تحديث حالة الصفقات المغلقة
    4. ترتيب الصفقات حسب التاريخ والحالة
    
    :return: عدد الصفقات قبل وبعد التنظيف
    """
    try:
        # نسخ احتياطي قبل التنظيف
        backup_trades_file()
        
        # تحميل الصفقات الحالية
        trades = load_trades()
        original_count = len(trades)
        logger.info(f"تم تحميل {original_count} صفقة من الملف")
        
        # تنظيف وإصلاح البيانات
        cleaned_trades = []
        seen_trades = set()  # لتجنب التكرار
        
        for trade in trades:
            # إصلاح الحالة
            if 'status' not in trade:
                trade['status'] = 'CLOSED'
            
            # إصلاح الرمز
            if 'symbol' not in trade or trade['symbol'] == 'UNKNOWN':
                trade['symbol'] = 'UNKNOWN'
                # الصفقات المجهولة تُعتبر مغلقة دائمًا
                trade['status'] = 'CLOSED'
            
            # تأكد من إغلاق الصفقات التي تم بيعها
            if 'close_timestamp' in trade:
                trade['status'] = 'CLOSED'
            
            # إنشاء مفتاح فريد للصفقة
            trade_key = f"{trade.get('symbol')}_{trade.get('timestamp')}_{trade.get('entry_price', '')}"
            
            # تجنب التكرار
            if trade_key not in seen_trades:
                seen_trades.add(trade_key)
                cleaned_trades.append(trade)
        
        # ترتيب الصفقات: المفتوحة أولاً، ثم حسب التاريخ (الأحدث أولاً)
        cleaned_trades.sort(key=lambda x: (
            0 if x.get('status') == 'OPEN' else 1,  # المفتوحة أولاً
            -x.get('timestamp', 0)  # ترتيب تنازلي حسب الوقت
        ))
        
        # حفظ الصفقات المنظفة
        save_trades(cleaned_trades)
        
        # حساب الإحصائيات
        open_trades = [t for t in cleaned_trades if t.get('status') == 'OPEN']
        closed_trades = [t for t in cleaned_trades if t.get('status') == 'CLOSED']
        
        logger.info(f"تم تنظيف {original_count - len(cleaned_trades)} صفقة متكررة أو خاطئة")
        logger.info(f"الإحصائيات النهائية: {len(open_trades)} مفتوحة، {len(closed_trades)} مغلقة، من أصل {len(cleaned_trades)}")
        
        return {
            'original_count': original_count,
            'cleaned_count': len(cleaned_trades),
            'open_count': len(open_trades),
            'closed_count': len(closed_trades),
            'removed_count': original_count - len(cleaned_trades)
        }
    
    except Exception as e:
        logger.error(f"خطأ أثناء تنظيف الصفقات: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'error': str(e),
            'original_count': 0,
            'cleaned_count': 0,
            'open_count': 0,
            'closed_count': 0,
            'removed_count': 0
        }

def clean_fake_trades():
    """
    تنظيف الصفقات الوهمية التي لا تتوافق مع منصة MEXC بطريقة شاملة وصارمة
    
    آلية التنظيف المحسنة:
    1. التحقق من كل صفقة مفتوحة في السجلات بطرق متعددة
    2. التأكد من وجود صفقة بنفس المعرف في API الخاص بالمنصة
    3. التحقق من وجود رصيد للعملة في حساب المستخدم
    4. إغلاق أي صفقة غير موجودة على المنصة
    5. تعليم الصفقات الوهمية ب api_confirmed=False
    
    :return: عدد الصفقات التي تم تنظيفها
    """
    try:
        # نسخ احتياطي قبل التنظيف
        backup_trades_file()
        
        # تحميل الصفقات الحالية
        trades_data = {}
        try:
            with open(TRADES_FILE, 'r') as f:
                trades_data = json.load(f)
                if not isinstance(trades_data, dict):
                    # تحويل إلى صيغة dict في حال كان التنسيق قديماً (قائمة)
                    trades_data = {'open': trades_data, 'closed': []}
        except Exception as e:
            logger.error(f"خطأ في تحميل ملف الصفقات: {e}")
            trades_data = {'open': [], 'closed': []}
        
        # تحديد العدد الأصلي
        original_open = len(trades_data.get('open', []))
        
        # الحصول على صفقات وأرصدة MEXC API
        api_orders = []
        account_balances = {}
        # استيراد دوال API مرة واحدة في بداية الدالة
        trades_history_function = None
        
        try:
            from app.mexc_api import get_open_orders, get_account_balance, get_trades_history
            # حفظ مرجع دالة تاريخ التداول لاستخدامها لاحقاً
            trades_history_function = get_trades_history
            
            # 1. الأوامر المفتوحة على المنصة
            try:
                api_orders = get_open_orders() or []
                logger.info(f"وجد {len(api_orders)} صفقة مفتوحة على المنصة API")
            except Exception as api_err:
                logger.error(f"خطأ في الاتصال بـ API للتحقق من الصفقات المفتوحة: {api_err}")
            
            # 2. أرصدة الحساب للتحقق من وجود العملات
            try:
                account_balances = get_account_balance() or {}
                logger.info(f"تم الحصول على معلومات {len(account_balances)} عملة من رصيد الحساب")
            except Exception as balance_err:
                logger.error(f"خطأ في الاتصال بـ API للتحقق من أرصدة الحساب: {balance_err}")
                
        except ImportError:
            logger.warning("لم يمكن استدعاء وحدة MEXC API")
        
        # فرز الصفقات المفتوحة بمعرفاتها
        api_order_ids = [str(o.get('orderId')) for o in api_orders if o.get('orderId')]
        logger.info(f"معرفات الأوامر المفتوحة على المنصة: {api_order_ids}")
        
        # قائمة العملات التي لدينا رصيد منها
        assets_with_balance = []
        if account_balances and isinstance(account_balances, dict):
            for asset, balance_info in account_balances.items():
                if balance_info and isinstance(balance_info, dict):
                    if float(balance_info.get('free', 0)) > 0 or float(balance_info.get('locked', 0)) > 0:
                        assets_with_balance.append(asset)
        logger.info(f"العملات التي لدينا رصيد منها: {assets_with_balance}")
        
        cleaned_open = []
        closed_fake = []
        
        # تحليل كل صفقة مفتوحة بطرق تحقق متعددة
        for trade in trades_data.get('open', []):
            symbol = trade.get('symbol', 'UNKNOWN')
            # الصفقات بدون رمز تعتبر وهمية تلقائياً
            if symbol == 'UNKNOWN':
                trade['status'] = 'CLOSED'
                trade['api_confirmed'] = False
                trade['close_reason'] = 'UNKNOWN_SYMBOL'
                trade['close_timestamp'] = int(time.time() * 1000)
                closed_fake.append(trade)
                continue
                
            # التحقق مما إذا كانت هذه صفقة وهمية عبر عدة طرق
            is_fake = False
            fake_reason = ''
            
            # الطريقة 1: التحقق من علامات الاختبار الصريحة
            if trade.get('test_trade') == True or trade.get('api_executed') == False or trade.get('api_confirmed') == False:
                logger.info(f"🔴 صفقة تجريبية صريحة: {symbol}")
                is_fake = True
                fake_reason = 'TEST_FLAG'
            
            # الطريقة 2: التحقق من معرف الأمر في قائمة الأوامر المفتوحة
            order_id = trade.get('order_id', trade.get('orderId', None))
            if not is_fake and order_id and api_order_ids and str(order_id) not in api_order_ids:
                logger.info(f"🔴 أمر غير موجود على المنصة: {symbol} - {order_id}")
                is_fake = True
                fake_reason = 'ORDER_NOT_FOUND'
            
            # الطريقة 3: التحقق من وجود رصيد للعملة في الحساب
            coin_symbol = symbol.replace('USDT', '')
            if not is_fake and account_balances and coin_symbol not in assets_with_balance:
                logger.info(f"🔴 لا يوجد رصيد للعملة {coin_symbol} في الحساب")
                is_fake = True
                fake_reason = 'NO_BALANCE'
            
            # الطريقة 4: محاولة التحقق عبر تاريخ التداول إذا لم يتم تحديد حالة الصفقة بعد
            if not is_fake and order_id and trades_history_function:
                try:
                    # التحقق من وجود الصفقة في تاريخ التداول باستخدام المرجع المحفوظ
                    recent_trades = trades_history_function(symbol, 50) or []
                    found_in_history = False
                    
                    for trade_history in recent_trades:
                        if str(trade_history.get('orderId')) == str(order_id):
                            found_in_history = True
                            logger.info(f"✅ تم العثور على الصفقة في تاريخ التداول: {symbol}")
                            break
                    
                    if not found_in_history:
                        logger.info(f"🔴 لم يتم العثور على الصفقة في تاريخ التداول: {symbol}")
                        is_fake = True
                        fake_reason = 'NOT_IN_HISTORY'
                except Exception as history_err:
                    logger.error(f"خطأ في التحقق من تاريخ التداول: {history_err}")
            elif not is_fake and order_id and not trades_history_function:
                logger.warning(f"⚠️ لا يمكن التحقق من تاريخ التداول: وظيفة get_trades_history غير متاحة")
            
            # التعامل مع الصفقة بناءً على نتيجة التحقق
            if is_fake:
                # إغلاق الصفقة وتعليمها كمزيفة
                trade['status'] = 'CLOSED'
                trade['api_confirmed'] = False
                trade['close_reason'] = f'FAKE_TRADE_{fake_reason}'
                trade['close_timestamp'] = int(time.time() * 1000)
                logger.warning(f"⛔ تعليم الصفقة كوهمية: {symbol} - السبب: {fake_reason}")
                closed_fake.append(trade)
            else:
                # تأكيد الصفقة الحقيقية
                trade['api_confirmed'] = True
                trade['last_verified'] = int(time.time() * 1000)
                logger.info(f"✅ صفقة حقيقية مؤكدة: {symbol}")
                cleaned_open.append(trade)
        
        # تحديث ملف الصفقات
        trades_data['open'] = cleaned_open
        trades_data['closed'].extend(closed_fake)
        
        # حفظ البيانات المحدثة
        with open(TRADES_FILE, 'w') as f:
            json.dump(trades_data, f, indent=2)
        
        # النتائج
        num_cleaned = original_open - len(cleaned_open)
        logger.info(f"🧹 تم تنظيف {num_cleaned} صفقة وهمية من أصل {original_open} صفقة مفتوحة")
        
        return {
            'original_count': original_open,
            'current_count': len(cleaned_open),
            'cleaned_count': num_cleaned
        }
    except Exception as e:
        logger.error(f"خطأ في تنظيف الصفقات الوهمية: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'error': str(e),
            'original_count': 0,
            'current_count': 0,
            'cleaned_count': 0
        }

if __name__ == "__main__":
    # تنفيذ التنظيف العادي
    result = clean_trades()
    print(f"تم تنظيف ملف الصفقات:")
    print(f"- عدد الصفقات الأصلي: {result['original_count']}")
    print(f"- عدد الصفقات بعد التنظيف: {result['cleaned_count']}")
    print(f"- صفقات مفتوحة: {result['open_count']}")
    print(f"- صفقات مغلقة: {result['closed_count']}")
    print(f"- صفقات تمت إزالتها: {result['removed_count']}")
    
    # تنفيذ تنظيف الصفقات الوهمية
    fake_result = clean_fake_trades()
    print(f"\nتم تنظيف الصفقات الوهمية:")
    print(f"- عدد الصفقات المفتوحة الأصلي: {fake_result['original_count']}")
    print(f"- عدد الصفقات المفتوحة بعد التنظيف: {fake_result['current_count']}")
    print(f"- صفقات وهمية تم إغلاقها: {fake_result['cleaned_count']}")