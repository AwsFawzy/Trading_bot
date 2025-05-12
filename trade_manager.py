#!/usr/bin/env python3
"""
نظام إدارة التداول الموحد
يتضمن كل الوظائف اللازمة للتعامل مع الصفقات في ملف واحد:
1. فتح صفقات جديدة حقيقية (5 دولار لكل صفقة)
2. التحقق من الصفقات ومسح الصفقات الوهمية
3. تطبيق أهداف الربح ووقف الخسارة

طريقة الاستخدام:
- لفتح صفقات جديدة: python trade_manager.py --open
- لإغلاق جميع الصفقات: python trade_manager.py --close
- للتحقق من الصفقات وتنظيفها: python trade_manager.py --verify
- لتشغيل جميع العمليات: python trade_manager.py --all
"""

import json
import logging
import random
import time
import argparse
from datetime import datetime

from app.mexc_api import (
    get_current_price, 
    place_order, 
    get_all_symbols_24h_data,
    get_trades_history,
    get_open_orders,
    get_account_balance
)
from app.telegram_notify import send_telegram_message, notify_trade_status

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# إعدادات التداول
TRADE_SETTINGS = {
    'total_capital': 25.0,        # رأس المال الإجمالي (5 دولار × 5 صفقات)
    'amount_per_trade': 5.0,      # 5 دولار لكل صفقة
    'max_trades': 5,              # الحد الأقصى لعدد الصفقات المفتوحة
    'profit_targets': [0.5, 1.0, 2.0],  # أهداف الربح بالنسبة المئوية
    'stop_loss': -0.1,            # وقف الخسارة بالنسبة المئوية
    'blacklisted_symbols': ['XRPUSDT'],  # العملات المحظورة
}

# قائمة العملات المفضلة للتداول
PREFERRED_COINS = [
    'BTCUSDT',     # بيتكوين
    'ETHUSDT',     # إيثريوم
    'SOLUSDT',     # سولانا
    'AVAXUSDT',    # أفالانش
    'DOTUSDT',     # بولكادوت
    'BNBUSDT',     # بينانس كوين
    'MATICUSDT',   # بوليجون
    'ADAUSDT',     # كاردانو
    'APTUSDT',     # ابتوس
    'NEARUSDT',    # نير
    'ATOMUSDT',    # كوزموس
]

def create_backup():
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        import shutil
        timestamp = int(time.time())
        shutil.copy('active_trades.json', f'active_trades.json.backup.{timestamp}')
        logger.info(f"تم إنشاء نسخة احتياطية: active_trades.json.backup.{timestamp}")
        return True
    except Exception as e:
        logger.error(f"فشل إنشاء نسخة احتياطية: {e}")
        return False

def load_trades():
    """تحميل الصفقات من الملف"""
    try:
        with open('active_trades.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الصفقات: {e}")
        return {"open": [], "closed": []}

def save_trades(data):
    """حفظ الصفقات في الملف"""
    try:
        with open('active_trades.json', 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"تم حفظ {len(data.get('open', []))} صفقة مفتوحة و {len(data.get('closed', []))} صفقة مغلقة")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def get_active_symbols():
    """الحصول على العملات المتداولة حالياً"""
    active_symbols = set()
    trades_data = load_trades()
    
    for trade in trades_data.get('open', []):
        if trade.get('status') == 'OPEN':
            symbol = trade.get('symbol')
            if symbol:
                active_symbols.add(symbol)
    
    logger.info(f"العملات المتداولة حالياً: {active_symbols}")
    return active_symbols

def get_diverse_symbols(count=5):
    """الحصول على مجموعة متنوعة من رموز العملات للتداول"""
    # جلب قائمة العملات المفضلة
    preferred_coins = PREFERRED_COINS.copy()
    random.shuffle(preferred_coins)
    
    # تجنب العملات المحظورة والمتداولة حالياً
    active_symbols = get_active_symbols()
    blacklisted = TRADE_SETTINGS['blacklisted_symbols']
    
    if len(preferred_coins) < count * 2:
        try:
            # جلب قائمة بجميع العملات من السوق
            all_symbols_data = get_all_symbols_24h_data()
            available_symbols = [
                symbol_data.get('symbol')
                for symbol_data in all_symbols_data
                if symbol_data.get('symbol', '').endswith('USDT') and
                symbol_data.get('symbol') not in blacklisted
            ]
            random.shuffle(available_symbols)
            preferred_coins.extend(available_symbols)
        except Exception as e:
            logger.error(f"خطأ في جلب بيانات العملات: {e}")
    
    # اختيار العملات المناسبة
    selected_symbols = []
    
    for symbol in preferred_coins:
        if len(selected_symbols) >= count:
            break
        
        # تخطي العملات المحظورة والمتداولة حالياً
        if symbol in blacklisted or symbol in active_symbols:
            logger.info(f"تخطي {symbol}: محظورة أو متداولة حالياً")
            continue
        
        # التحقق من وجود سعر حالي
        current_price = get_current_price(symbol)
        if current_price:
            selected_symbols.append(symbol)
    
    logger.info(f"تم اختيار العملات: {selected_symbols}")
    return selected_symbols[:count]

def verify_real_trades():
    """التحقق من الصفقات الحقيقية وحذف الصفقات الوهمية"""
    # إنشاء نسخة احتياطية أولاً
    create_backup()
    
    real_trades = {}
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    # الطريقة 1: الأوامر المفتوحة
    symbols_to_check = {trade.get('symbol') for trade in open_trades}
    for symbol in symbols_to_check:
        try:
            logger.info(f"التحقق من الأوامر المفتوحة لـ {symbol}...")
            open_orders = get_open_orders(symbol)
            if open_orders:
                real_trades[symbol] = True
                logger.info(f"✅ أمر مفتوح: {symbol}")
        except Exception as e:
            logger.error(f"خطأ في الحصول على الأوامر المفتوحة لـ {symbol}: {e}")
    
    # الطريقة 2: تاريخ التداول
    symbols_to_check = {trade.get('symbol') for trade in open_trades}
    logger.info(f"التحقق من {len(symbols_to_check)} عملة في تاريخ التداول...")
    
    for symbol in symbols_to_check:
        if symbol in real_trades:
            continue
            
        try:
            trades_history = get_trades_history(symbol, 50)
            if trades_history:
                for trade in trades_history:
                    if trade.get('isBuyer'):
                        real_trades[symbol] = True
                        logger.info(f"✅ وجدت في التاريخ: {symbol}")
                        break
        except Exception as e:
            logger.error(f"خطأ في استعلام تاريخ التداول لـ {symbol}: {e}")
    
    # الطريقة 3: أوامر العملة
    for symbol in symbols_to_check:
        if symbol in real_trades:
            continue
            
        try:
            symbol_orders = get_open_orders(symbol)
            if symbol_orders:
                real_trades[symbol] = True
                logger.info(f"✅ أوامر مفتوحة لـ {symbol}")
        except Exception as e:
            logger.error(f"خطأ في استعلام أوامر {symbol}: {e}")
    
    # الطريقة 4: معلومات الحساب
    try:
        account_balance = get_account_balance()
        if account_balance:
            for asset, balance_info in account_balance.items():
                symbol = asset + 'USDT' if asset != 'USDT' else asset
                free_balance = float(balance_info.get('free', 0))
                
                if free_balance > 0 and symbol in symbols_to_check and symbol not in real_trades:
                    real_trades[symbol] = True
                    logger.info(f"✅ رصيد إيجابي لـ {symbol}: {free_balance}")
    except Exception as e:
        logger.error(f"خطأ في استعلام معلومات الحساب: {e}")
    
    # تنظيف الصفقات الوهمية
    new_open_trades = []
    logger.info(f"الصفقات الحقيقية: {list(real_trades.keys())}")
    
    for trade in open_trades:
        symbol = trade.get('symbol')
        
        if symbol in real_trades:
            # صفقة حقيقية
            trade['api_confirmed'] = True
            trade['last_verified'] = int(datetime.now().timestamp() * 1000)
            new_open_trades.append(trade)
            logger.info(f"✓ تأكيد صفقة حقيقية: {symbol}")
        else:
            # صفقة وهمية
            trade['status'] = 'CLOSED'
            trade['api_confirmed'] = False
            trade['close_reason'] = 'FAKE_TRADE'
            trade['close_timestamp'] = int(datetime.now().timestamp() * 1000)
            trade['close_price'] = trade.get('entry_price', 0)
            trade['profit_loss'] = 0
            closed_trades.append(trade)
            logger.warning(f"✗ إغلاق صفقة وهمية: {symbol}")
    
    # حفظ النتائج
    trades_data['open'] = new_open_trades
    trades_data['closed'] = closed_trades
    save_trades(trades_data)
    
    logger.info(f"تم تأكيد {len(new_open_trades)} صفقة حقيقية وإغلاق {len(open_trades) - len(new_open_trades)} صفقة وهمية")
    return new_open_trades

def apply_profit_rules():
    """تطبيق قواعد الربح على الصفقات الحقيقية"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    logger.info(f"تطبيق قواعد الربح على {len(open_trades)} صفقة...")
    
    trades_to_close = []
    updated_trades = []
    
    for trade in open_trades:
        symbol = trade.get('symbol')
        entry_price = float(trade.get('entry_price', 0))
        quantity = float(trade.get('quantity', 0))
        
        # تجاهل الصفقات غير المؤكدة
        if not trade.get('api_confirmed', False):
            logger.warning(f"تجاهل صفقة غير مؤكدة: {symbol}")
            updated_trades.append(trade)
            continue
        
        # الحصول على السعر الحالي
        current_price = get_current_price(symbol)
        if not current_price:
            logger.error(f"لم يتم الحصول على سعر {symbol}")
            updated_trades.append(trade)
            continue
        
        # حساب التغير في السعر
        price_change_percent = ((current_price - entry_price) / entry_price) * 100
        logger.info(f"{symbol}: دخول={entry_price}, حالي={current_price}, تغير={price_change_percent:.2f}%")
        
        # إنشاء أهداف الربح إذا لم تكن موجودة
        if 'take_profit_targets' not in trade:
            trade['take_profit_targets'] = [
                {'percent': percent, 'hit': False}
                for percent in TRADE_SETTINGS['profit_targets']
            ]
        
        # التحقق من وقف الخسارة
        stop_loss = float(trade.get('stop_loss', TRADE_SETTINGS['stop_loss']))
        if price_change_percent <= stop_loss:
            logger.warning(f"⚠️ تفعيل وقف الخسارة: {symbol} ({price_change_percent:.2f}%)")
            trades_to_close.append({
                'symbol': symbol,
                'quantity': quantity,
                'reason': 'STOP_LOSS',
                'profit_loss': price_change_percent,
                'trade': trade
            })
            continue
        
        # التحقق من أهداف الربح
        target_hit = False
        
        for target in trade['take_profit_targets']:
            target_percent = target.get('percent', 0)
            if price_change_percent >= target_percent and not target.get('hit', False):
                # تحقق هدف ربح
                target['hit'] = True
                target['hit_time'] = int(datetime.now().timestamp() * 1000)
                target['hit_price'] = current_price
                
                logger.info(f"🎯 هدف {target_percent}% محقق: {symbol}")
                notify_trade_status(
                    symbol=symbol,
                    status=f"تحقق هدف {target_percent}%",
                    price=current_price,
                    profit_loss=price_change_percent,
                    api_verified=True
                )
                
                # إذا كان الهدف الأخير (2%)، أغلق الصفقة
                if target_percent == max(TRADE_SETTINGS['profit_targets']):
                    target_hit = True
                    trades_to_close.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'reason': 'TARGET_REACHED',
                        'profit_loss': price_change_percent,
                        'trade': trade
                    })
                    break
        
        if not target_hit:
            updated_trades.append(trade)
    
    # حفظ التحديثات
    trades_data['open'] = updated_trades
    save_trades(trades_data)
    
    # إغلاق الصفقات التي وصلت للهدف أو وقف الخسارة
    closed_count = 0
    
    for trade_to_close in trades_to_close:
        symbol = trade_to_close.get('symbol')
        quantity = trade_to_close.get('quantity')
        reason = trade_to_close.get('reason')
        profit_loss = trade_to_close.get('profit_loss')
        trade_obj = trade_to_close.get('trade')
        
        logger.info(f"إغلاق صفقة {symbol} ({reason})...")
        
        try:
            # التحقق من وجود رصيد للعملة قبل تنفيذ البيع
            logger.info(f"🔍 التحقق من رصيد {symbol} قبل البيع...")
            
            coin_symbol = ""  # تعريف خارج النطاق
            current_coin_balance = 0.0  # تعريف خارج النطاق
            
            try:
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
                    # نستمر لأن الصفقة موجودة في السجلات، وقد يكون الحساب بدون API كاملة
            except Exception as e:
                logger.error(f"⚠️ خطأ في التحقق من الرصيد: {e}")
                # نستمر في محاولة البيع
            
            # تنفيذ أمر البيع
            logger.info(f"🔶 محاولة بيع {symbol}: الكمية={quantity}...")
            sell_result = place_order(symbol, "SELL", quantity, None, "MARKET")
            
            # التحقق من نجاح الأمر المبدئي
            if not sell_result or 'error' in sell_result or 'orderId' not in sell_result:
                logger.error(f"❌ فشل أمر البيع: {symbol} - {sell_result}")
                return False, sell_result
                
            logger.info(f"✅ تم إرسال أمر البيع بنجاح: {sell_result}")
            
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
                            if (str(trade_record.get('orderId')) == str(sell_result.get('orderId')) and 
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
                        # تأكد من أن لدينا معلومات عن رصيد العملة قبل وبعد البيع
                        _coin_symbol = symbol.replace('USDT', '')
                        # الحصول على رصيد العملة الحالي
                        new_balance = get_account_balance()
                        # استخدام كمية الصفقة كقيمة افتراضية لرصيد العملة
                        # هذا التغيير يحل مشكلة متغير coin_balance غير المحدد
                        old_coin_balance = float(quantity)
                        # نستخدم current_coin_balance المعرف في الأعلى إذا كان موجودًا
                        if 'current_coin_balance' in locals():
                            old_coin_balance = current_coin_balance
                            
                        # التحقق من انخفاض رصيد العملة
                        if new_balance and _coin_symbol in new_balance:
                            new_coin_balance = float(new_balance[_coin_symbol].get('free', 0))
                            if new_coin_balance < old_coin_balance * 0.5:  # انخفاض الرصيد بشكل كبير يعني نجاح البيع
                                sell_verified = True
                                logger.info(f"✅ تم تأكيد البيع من خلال تغير الرصيد: {old_coin_balance} → {new_coin_balance}")
                                # تم إصلاح جميع أخطاء المتغيرات غير المعرفة
                    except Exception as e:
                        logger.error(f"❌ خطأ في التحقق من تغير الرصيد: {e}")
                    
                    if not sell_verified:
                        logger.error(f"❌❌ لم يتم تأكيد عملية البيع بعد عدة محاولات: {symbol}")
                        # نستمر لأن الأمر تم إرساله وقد يكون التأخير في تحديث API
            except Exception as e:
                logger.error(f"❌ خطأ أثناء التحقق من تاريخ التداول للبيع: {e}")
                # نستمر في التنفيذ لأن الأمر قد يكون نجح رغم فشل التحقق
            
            # الحصول على سعر البيع الفعلي
            current_price = get_current_price(symbol)
            if not current_price and sell_result.get('price'):
                current_price = float(sell_result.get('price'))
            elif not current_price:
                # إذا لم نتمكن من الحصول على السعر، نستخدم سعر الصفقة الأصلي + نسبة الربح/الخسارة
                entry_price = float(trade_obj.get('entry_price', 0))
                current_price = entry_price * (1 + profit_loss/100)
            
            # تحديث معلومات الصفقة
            trade_obj['status'] = 'CLOSED'
            trade_obj['close_price'] = current_price
            trade_obj['close_timestamp'] = int(datetime.now().timestamp() * 1000)
            trade_obj['profit_loss'] = profit_loss
            trade_obj['close_reason'] = reason
            trade_obj['sell_verified'] = sell_verified  # إضافة علامة التحقق من البيع
            trade_obj['sell_order_id'] = sell_result.get('orderId', '')
            
            # تحديث ملف الصفقات
            trades_data = load_trades()  # إعادة تحميل لمنع تضارب التغييرات
            open_trades = [t for t in trades_data.get('open', []) if t.get('symbol') != symbol]
            closed_trades = trades_data.get('closed', [])
            closed_trades.append(trade_obj)
            
            trades_data['open'] = open_trades
            trades_data['closed'] = closed_trades
            save_trades(trades_data)
            
            closed_count += 1
            
            # إرسال إشعار
            notify_trade_status(
                symbol=symbol,
                status=f"تم البيع ({reason})",
                price=current_price,
                profit_loss=profit_loss,
                order_id=sell_result.get('orderId'),
                api_verified=sell_verified
            )
            
            verification_status = "✅✅ [تم التأكيد]" if sell_verified else "⚠️ [بانتظار التأكيد]"
            logger.info(f"✅ تم بيع {symbol} بسعر {current_price} ({profit_loss:.2f}%) {verification_status}")
        except Exception as e:
            logger.error(f"❌ خطأ في بيع {symbol}: {e}")
            # تسجيل تفاصيل الخطأ
            import traceback
            logger.error(traceback.format_exc())
    
    return closed_count

def execute_buy(symbol, amount):
    """تنفيذ عملية الشراء مع تأكيد قطعي للصفقات الحقيقية فقط"""
    try:
        # الحصول على السعر الحالي
        price = get_current_price(symbol)
        if not price:
            logger.error(f"لم يتم الحصول على سعر {symbol}")
            return False, {"error": "لم يتم الحصول على السعر"}
        
        # حساب الكمية
        quantity = amount / price
        
        logger.info(f"🔶 محاولة شراء {symbol}: السعر={price}, الكمية={quantity}, المبلغ={amount}")
        
        # متغير لتخزين رصيد USDT قبل الشراء (خارج نطاق try لاستخدامه لاحقاً)
        initial_usdt_balance = 0
        
        # تحقق أولاً من رصيد USDT
        try:
            logger.info("التحقق من رصيد USDT قبل تنفيذ عملية الشراء...")
            balance = get_account_balance()
            if not balance or 'USDT' not in balance:
                logger.error("❌ لم يتم العثور على رصيد USDT. تأكد من صلاحيات API.")
                return False, {"error": "لم يتم العثور على رصيد USDT"}
            
            initial_usdt_balance = float(balance['USDT'].get('free', 0))
            logger.info(f"💰 رصيد USDT المتاح: {initial_usdt_balance}")
            
            if initial_usdt_balance < amount:
                logger.error(f"❌ رصيد USDT غير كافٍ. متاح: {initial_usdt_balance}, مطلوب: {amount}")
                return False, {"error": f"رصيد USDT غير كافٍ. متاح: {initial_usdt_balance}, مطلوب: {amount}"}
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من الرصيد: {e}")
            # نستمر رغم الخطأ، فقد تكون المشكلة في الاستعلام عن الرصيد فقط
        
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
                trades_history = get_trades_history(symbol, 20)
                if trades_history:
                    for trade_record in trades_history:
                        if str(trade_record.get('orderId')) == str(result.get('orderId')):
                            trade_history_verified = True
                            logger.info(f"✅✅ تأكيد وجود الصفقة في تاريخ التداول: {symbol} (معرف الأمر: {result.get('orderId')})")
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
                    # نستمر لأن هناك عوامل أخرى مثل الرسوم قد تؤثر على الدقة
            
            # التحقق من وجود العملة في الرصيد بعد الشراء
            purchased_coin_symbol = symbol.replace('USDT', '')
            if new_balance and purchased_coin_symbol in new_balance:
                purchased_coin_balance = float(new_balance[purchased_coin_symbol].get('free', 0))
                logger.info(f"💰 رصيد {purchased_coin_symbol} الجديد: {purchased_coin_balance}")
                
                if purchased_coin_balance < quantity * 0.8:  # يجب أن تكون الكمية على الأقل 80% من المطلوب (بعد خصم الرسوم)
                    logger.warning(f"⚠️ كمية {purchased_coin_symbol} أقل من المتوقع: {purchased_coin_balance} < {quantity}")
                    # نستمر لأن الرسوم قد تؤثر على الكمية النهائية
                
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من تغير الرصيد: {e}")
            # نستمر رغم الخطأ لأن الصفقة تم تأكيدها بالفعل
        
        # إضافة أهداف الربح
        take_profit_targets = [
            {'percent': percent, 'hit': False}
            for percent in TRADE_SETTINGS['profit_targets']
        ]
        
        # إنشاء سجل للصفقة
        order_info = {
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': price,
            'stop_loss': TRADE_SETTINGS['stop_loss'],
            'take_profit_targets': take_profit_targets,
            'timestamp': int(datetime.now().timestamp() * 1000),
            'status': 'OPEN',
            'api_executed': True,
            'api_confirmed': True,  # تم التأكد من وجود الصفقة بالفعل
            'orderId': result.get('orderId', ''),
            'order_type': 'MARKET',
            'verified_by': 'trade_history'  # تسجيل طريقة التحقق
        }
        
        # تحديث ملف الصفقات
        trades_data = load_trades()
        trades_data['open'].append(order_info)
        save_trades(trades_data)
        
        logger.info(f"✅✅✅ تم تنفيذ الشراء وتأكيده: {symbol}")
        
        # إرسال إشعار
        notify_trade_status(
            symbol=symbol, 
            status="تم الشراء وتأكيده", 
            price=price, 
            order_id=result.get('orderId'),
            api_verified=True
        )
            
        return True, result
        
    except Exception as e:
        logger.error(f"❌ خطأ في عملية الشراء: {symbol} - {e}")
        return False, {"error": str(e)}

def close_all_trades():
    """إغلاق جميع الصفقات المفتوحة"""
    # تحميل الصفقات الحالية
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    if not open_trades:
        logger.info("لا توجد صفقات مفتوحة للإغلاق")
        return 0
    
    logger.info(f"محاولة إغلاق {len(open_trades)} صفقة...")
    closed_count = 0
    
    for trade in open_trades[:]:
        symbol = trade.get('symbol')
        quantity = float(trade.get('quantity', 0))
        entry_price = float(trade.get('entry_price', 0))
        
        logger.info(f"إغلاق صفقة {symbol}...")
        
        try:
            # تنفيذ أمر البيع
            sell_result = place_order(symbol, "SELL", quantity, None, "MARKET")
            
            if sell_result and 'error' not in sell_result:
                # تمت عملية البيع بنجاح
                current_price = float(sell_result.get('price', 0))
                profit_loss = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                
                logger.info(f"✅ تم بيع {symbol} بسعر {current_price} (تغير: {profit_loss:.2f}%)")
                
                # تحديث معلومات الصفقة
                trade['status'] = 'CLOSED'
                trade['close_price'] = current_price
                trade['close_timestamp'] = int(datetime.now().timestamp() * 1000)
                trade['profit_loss'] = profit_loss
                trade['close_reason'] = 'MANUAL_CLOSE'
                
                # إزالة من المفتوحة وإضافة إلى المغلقة
                open_trades.remove(trade)
                closed_trades.append(trade)
                
                closed_count += 1
                
                # إرسال إشعار
                notify_trade_status(
                    symbol=symbol,
                    status="تم البيع (إغلاق يدوي)",
                    price=current_price,
                    profit_loss=profit_loss,
                    order_id=sell_result.get('orderId'),
                    api_verified=True
                )
            else:
                logger.error(f"❌ فشل بيع {symbol}: {sell_result}")
        except Exception as e:
            logger.error(f"خطأ في بيع {symbol}: {e}")
    
    # حفظ التغييرات
    trades_data['open'] = open_trades
    trades_data['closed'] = closed_trades
    save_trades(trades_data)
    
    total = len(trades_data.get('open', [])) + closed_count
    logger.info(f"تم إغلاق {closed_count} صفقة من أصل {total}")
    return closed_count

def open_new_trades(count=5):
    """فتح صفقات جديدة متنوعة بعد التأكد من عدم وجود صفقات وهمية"""
    logger.info("🧹 تنظيف الصفقات الوهمية أولاً قبل فتح صفقات جديدة...")
    
    # تنظيف شامل وقوي للصفقات الوهمية
    try:
        from app.clean_trades import clean_fake_trades
        clean_result = clean_fake_trades()
        logger.info(f"نتائج التنظيف: تم إغلاق {clean_result.get('cleaned_count', 0)} صفقة وهمية")
    except Exception as e:
        logger.error(f"خطأ في تنظيف الصفقات الوهمية: {e}")
        # تنفيذ التحقق القديم للتوافقية
        verify_real_trades()
    
    # التحقق من الرصيد المتاح
    try:
        from app.mexc_api import get_account_balance
        balance = get_account_balance()
        if balance and 'USDT' in balance:
            usdt_balance = float(balance['USDT'].get('free', 0))
            logger.info(f"💰 رصيد USDT المتاح للتداول: {usdt_balance}")
            
            # التحقق إذا كان الرصيد كافٍ لفتح الصفقات الجديدة
            amount_needed = TRADE_SETTINGS['amount_per_trade'] * min(count, TRADE_SETTINGS['max_trades'])
            if usdt_balance < amount_needed:
                logger.warning(f"⚠️ رصيد USDT غير كافٍ لفتح {count} صفقات. متاح: {usdt_balance}, مطلوب: {amount_needed}")
                adjusted_count = int(usdt_balance // TRADE_SETTINGS['amount_per_trade'])
                if adjusted_count == 0:
                    logger.error("❌ رصيد USDT غير كافٍ لفتح أي صفقة جديدة")
                    return 0
                logger.info(f"⚠️ تعديل عدد الصفقات المراد فتحها إلى {adjusted_count} بناءً على الرصيد المتاح")
                count = adjusted_count
    except Exception as e:
        logger.error(f"خطأ في التحقق من الرصيد: {e}")
    
    # الحصول على عدد الصفقات المفتوحة حالياً
    trades_data = load_trades()
    open_count = len(trades_data.get('open', []))
    
    if open_count >= TRADE_SETTINGS['max_trades']:
        logger.info(f"يوجد بالفعل {open_count} صفقات مفتوحة، لن يتم فتح صفقات جديدة")
        return 0
    
    # تحديد عدد الصفقات المطلوب فتحها
    trades_to_open = min(count, TRADE_SETTINGS['max_trades'] - open_count)
    logger.info(f"🚀 محاولة فتح {trades_to_open} صفقات جديدة...")
    
    # الحصول على رموز متنوعة
    symbols = get_diverse_symbols(trades_to_open)
    
    if not symbols:
        logger.warning("⚠️ لم يتم العثور على عملات مناسبة للتداول")
        return 0
    
    # فتح الصفقات
    successful_trades = 0
    amount_per_trade = TRADE_SETTINGS['amount_per_trade']
    
    for symbol in symbols:
        # التحقق مرة أخرى من عدم وجود صفقة مفتوحة على هذه العملة (توقف إضافي)
        active_symbols = get_active_symbols()
        if symbol in active_symbols:
            logger.warning(f"⚠️ تخطي {symbol}: هناك بالفعل صفقة مفتوحة لهذه العملة")
            continue
            
        logger.info(f"🔶 محاولة شراء {symbol} بمبلغ {amount_per_trade} دولار...")
        success, result = execute_buy(symbol, amount_per_trade)
        
        if success:
            successful_trades += 1
            logger.info(f"✅ تم شراء {symbol} بنجاح")
            
            # التحقق من الصفقات بعد كل عملية شراء ناجحة
            # هذا سيمنع فتح صفقات متعددة للعملة نفسها
            active_symbols = get_active_symbols()
        else:
            logger.error(f"❌ فشل شراء {symbol}: {result}")
    
    logger.info(f"✅ تم فتح {successful_trades} صفقات جديدة من أصل {trades_to_open} محاولة")
    return successful_trades

def main():
    """الدالة الرئيسية"""
    parser = argparse.ArgumentParser(description="نظام إدارة التداول الموحد")
    parser.add_argument("--open", action="store_true", help="فتح صفقات جديدة")
    parser.add_argument("--close", action="store_true", help="إغلاق جميع الصفقات")
    parser.add_argument("--verify", action="store_true", help="التحقق من الصفقات وتنظيفها")
    parser.add_argument("--profit", action="store_true", help="تطبيق قواعد الربح")
    parser.add_argument("--all", action="store_true", help="تنفيذ جميع العمليات")
    parser.add_argument("--count", type=int, default=5, help="عدد الصفقات المطلوب فتحها")
    
    args = parser.parse_args()
    
    if args.verify or args.all:
        logger.info("بدء عملية التحقق من الصفقات...")
        real_trades = verify_real_trades()
        logger.info(f"تم تأكيد {len(real_trades)} صفقة حقيقية")
    
    if args.profit or args.all:
        logger.info("تطبيق قواعد الربح على الصفقات...")
        closed_count = apply_profit_rules()
        logger.info(f"تم إغلاق {closed_count} صفقات وفقاً لقواعد الربح")
    
    if args.close:
        logger.info("إغلاق جميع الصفقات المفتوحة...")
        closed_count = close_all_trades()
        logger.info(f"تم إغلاق {closed_count} صفقات")
    
    if args.open or args.all:
        logger.info("فتح صفقات جديدة...")
        new_trades = open_new_trades(args.count)
        logger.info(f"تم فتح {new_trades} صفقات جديدة")
    
    # إذا لم يتم تحديد أي خيار، عرض المساعدة
    if not (args.open or args.close or args.verify or args.profit or args.all):
        parser.print_help()
    
    # إرسال تقرير
    try:
        trades_data = load_trades()
        open_count = len(trades_data.get('open', []))
        
        message = f"📊 تقرير النظام:\n"
        message += f"- الصفقات المفتوحة: {open_count}/{TRADE_SETTINGS['max_trades']}\n"
        message += f"- رأس المال: {open_count * TRADE_SETTINGS['amount_per_trade']} دولار\n"
        
        if open_count > 0:
            message += "\nالصفقات المفتوحة:\n"
            for trade in trades_data.get('open', []):
                symbol = trade.get('symbol')
                entry_price = trade.get('entry_price', 0)
                current_price = get_current_price(symbol) or 0
                price_change = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                message += f"  • {symbol}: {price_change:.2f}%\n"
        
        send_telegram_message(message)
    except Exception as e:
        logger.error(f"خطأ في إرسال التقرير: {e}")

if __name__ == "__main__":
    main()