#!/usr/bin/env python3
"""
سكريبت للتحقق من الصفقات الحقيقية وحذف الصفقات الوهمية
وتطبيق قواعد الربح على الصفقات الحقيقية فقط
"""

import json
import logging
import time
from datetime import datetime

from app.mexc_api import (
    get_current_price, 
    place_order, 
    get_account_info,
    get_all_open_orders,
    get_trades_history,
    get_open_orders
)
from app.telegram_notify import send_telegram_message, notify_trade_status

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_backup():
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        import shutil
        import time
        timestamp = int(time.time())
        shutil.copy('active_trades.json', f'active_trades.json.backup.{timestamp}')
        logger.info(f"تم إنشاء نسخة احتياطية من ملف الصفقات: active_trades.json.backup.{timestamp}")
    except Exception as e:
        logger.error(f"فشل إنشاء نسخة احتياطية: {e}")

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

def get_real_trades():
    """الحصول على قائمة الصفقات الحقيقية من المنصة"""
    real_trades = {}
    
    # الطريقة 1: الحصول على الصفقات المفتوحة
    try:
        logger.info("الحصول على الصفقات المفتوحة من المنصة...")
        open_orders = get_all_open_orders()
        if open_orders:
            for order in open_orders:
                symbol = order.get('symbol')
                if symbol not in real_trades:
                    real_trades[symbol] = True
                    logger.info(f"✅ تم العثور على صفقة مفتوحة: {symbol}")
    except Exception as e:
        logger.error(f"خطأ في الحصول على الصفقات المفتوحة: {e}")
    
    # الطريقة 2: التحقق من تاريخ التداول لكل عملة
    symbols_to_check = set()
    trades_data = load_trades()
    for trade in trades_data.get('open', []):
        symbols_to_check.add(trade.get('symbol'))
    
    for symbol in symbols_to_check:
        try:
            logger.info(f"التحقق من تاريخ التداول لـ {symbol}...")
            trades_history = get_trades_history(symbol, 50)  # زيادة عدد الصفقات المستعلم عنها
            if trades_history:
                for trade in trades_history:
                    if trade.get('isBuyer') and symbol not in real_trades:
                        real_trades[symbol] = True
                        logger.info(f"✅ تم العثور على صفقة في تاريخ التداول: {symbol}")
                        break
        except Exception as e:
            logger.error(f"خطأ في الحصول على تاريخ التداول لـ {symbol}: {e}")
    
    # الطريقة 3: استعلام عن كل صفقة على حدة
    for symbol in symbols_to_check:
        if symbol not in real_trades:
            try:
                logger.info(f"الاستعلام عن الأوامر المفتوحة لـ {symbol}...")
                symbol_orders = get_open_orders(symbol)
                if symbol_orders:
                    real_trades[symbol] = True
                    logger.info(f"✅ تم العثور على أوامر مفتوحة لـ {symbol}")
            except Exception as e:
                logger.error(f"خطأ في الاستعلام عن الأوامر المفتوحة لـ {symbol}: {e}")
    
    # الطريقة 4: الاستعلام عن معلومات الحساب للتأكد من وجود رصيد للعملات
    try:
        logger.info("الحصول على معلومات الحساب...")
        account_info = get_account_info()
        if account_info and 'balances' in account_info:
            for balance in account_info['balances']:
                symbol = balance.get('asset') + 'USDT'
                free_balance = float(balance.get('free', 0))
                if free_balance > 0 and symbol in symbols_to_check and symbol not in real_trades:
                    real_trades[symbol] = True
                    logger.info(f"✅ تم العثور على رصيد إيجابي لـ {symbol}: {free_balance}")
    except Exception as e:
        logger.error(f"خطأ في الحصول على معلومات الحساب: {e}")
    
    return real_trades

def clean_fake_trades():
    """تنظيف الصفقات الوهمية وتحديث حالة الصفقات الحقيقية"""
    # إنشاء نسخة احتياطية أولاً
    create_backup()
    
    # تحميل الصفقات الحالية
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    # الحصول على الصفقات الحقيقية
    real_trades = get_real_trades()
    logger.info(f"تم العثور على {len(real_trades)} صفقة حقيقية: {', '.join(real_trades.keys())}")
    
    # تنظيف الصفقات وتحديث حالتها
    cleaned_open_trades = []
    
    for trade in open_trades:
        symbol = trade.get('symbol')
        
        if symbol in real_trades:
            # هذه صفقة حقيقية، احتفظ بها وحدث حالتها
            trade['api_confirmed'] = True
            trade['last_verified'] = int(datetime.now().timestamp() * 1000)
            cleaned_open_trades.append(trade)
            logger.info(f"✅ تأكيد صفقة حقيقية: {symbol}")
        else:
            # هذه صفقة وهمية، انقلها إلى الصفقات المغلقة
            trade['status'] = 'CLOSED'
            trade['api_confirmed'] = False
            trade['close_reason'] = 'FAKE_TRADE'
            trade['close_timestamp'] = int(datetime.now().timestamp() * 1000)
            trade['close_price'] = trade.get('entry_price', 0)
            trade['profit_loss'] = 0
            closed_trades.append(trade)
            logger.warning(f"❌ إغلاق صفقة وهمية: {symbol}")
    
    # حفظ التغييرات
    trades_data['open'] = cleaned_open_trades
    trades_data['closed'] = closed_trades
    save_trades(trades_data)
    
    logger.info(f"تم الاحتفاظ بـ {len(cleaned_open_trades)} صفقة حقيقية وإغلاق {len(open_trades) - len(cleaned_open_trades)} صفقة وهمية")
    return cleaned_open_trades

def apply_profit_rules():
    """تطبيق قواعد الربح على الصفقات المفتوحة"""
    # تحميل الصفقات الحالية بعد تنظيفها
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    logger.info(f"تطبيق قواعد الربح على {len(open_trades)} صفقة مفتوحة")
    
    trades_to_close = []
    
    for trade in open_trades:
        symbol = trade.get('symbol')
        entry_price = float(trade.get('entry_price', 0))
        quantity = float(trade.get('quantity', 0))
        
        # تحقق من أن الصفقة حقيقية ومؤكدة
        if not trade.get('api_confirmed', False):
            logger.warning(f"تجاهل تطبيق قواعد الربح على صفقة غير مؤكدة: {symbol}")
            continue
        
        # الحصول على السعر الحالي
        current_price = get_current_price(symbol)
        if not current_price:
            logger.error(f"لم يتم الحصول على السعر الحالي لـ {symbol}")
            continue
        
        # حساب نسبة الربح/الخسارة
        price_change_percent = ((current_price - entry_price) / entry_price) * 100
        logger.info(f"{symbol}: سعر الدخول={entry_price}, السعر الحالي={current_price}, نسبة التغير={price_change_percent:.2f}%")
        
        # تحديث أهداف الربح إذا لم تكن موجودة
        if 'take_profit_targets' not in trade:
            trade['take_profit_targets'] = [
                {'percent': 0.5, 'hit': False},
                {'percent': 1.0, 'hit': False},
                {'percent': 2.0, 'hit': False}
            ]
        
        # تحديث هدف وقف الخسارة إذا لم يكن موجودًا
        if 'stop_loss' not in trade:
            trade['stop_loss'] = -0.1  # وقف خسارة بنسبة 0.1%
        
        # تحقق من وقف الخسارة
        stop_loss = float(trade.get('stop_loss', -0.1))
        if price_change_percent <= stop_loss:
            logger.warning(f"⚠️ تم تفعيل وقف الخسارة لـ {symbol}: {price_change_percent:.2f}% <= {stop_loss}%")
            trades_to_close.append({
                'symbol': symbol,
                'quantity': quantity,
                'reason': 'STOP_LOSS',
                'profit_loss': price_change_percent,
                'trade': trade
            })
            continue
        
        # تحقق من أهداف الربح
        target_hit = False
        
        for target in trade['take_profit_targets']:
            target_percent = target.get('percent', 0)
            if price_change_percent >= target_percent and not target.get('hit', False):
                target['hit'] = True
                target['hit_time'] = int(datetime.now().timestamp() * 1000)
                target['hit_price'] = current_price
                
                logger.info(f"🎯 تم تحقيق هدف الربح {target_percent}% لـ {symbol}")
                notify_trade_status(
                    symbol=symbol,
                    status=f"تحقق هدف ربح {target_percent}%",
                    price=current_price,
                    profit_loss=price_change_percent,
                    api_verified=True
                )
                
                # إذا كان الهدف هو 2%، أغلق الصفقة
                if target_percent == 2.0:
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
            # تحديث الصفقة في الذاكرة
            for i, t in enumerate(open_trades):
                if t.get('symbol') == symbol:
                    open_trades[i] = trade
                    break
    
    # حفظ التغييرات قبل إغلاق أي صفقات
    trades_data['open'] = open_trades
    save_trades(trades_data)
    
    # إغلاق الصفقات التي حققت الهدف أو وصلت إلى وقف الخسارة
    for trade_to_close in trades_to_close:
        symbol = trade_to_close.get('symbol')
        quantity = trade_to_close.get('quantity')
        reason = trade_to_close.get('reason')
        profit_loss = trade_to_close.get('profit_loss')
        trade_obj = trade_to_close.get('trade')
        
        logger.info(f"محاولة إغلاق صفقة {symbol} بسبب: {reason}")
        
        try:
            # تنفيذ أمر البيع
            sell_result = place_order(symbol, "SELL", quantity, None, "MARKET")
            
            if sell_result and 'error' not in sell_result:
                # تمت عملية البيع بنجاح
                current_price = float(sell_result.get('price', 0))
                logger.info(f"✅ تم بيع {symbol} بسعر {current_price}")
                
                # تحديث معلومات الصفقة
                trade_obj['status'] = 'CLOSED'
                trade_obj['close_price'] = current_price
                trade_obj['close_timestamp'] = int(datetime.now().timestamp() * 1000)
                trade_obj['profit_loss'] = profit_loss
                trade_obj['close_reason'] = reason
                
                # إزالة الصفقة من القائمة المفتوحة وإضافتها إلى المغلقة
                trades_data = load_trades()  # إعادة تحميل لتجنب تعارض التغييرات
                open_trades = [t for t in trades_data.get('open', []) if t.get('symbol') != symbol]
                closed_trades = trades_data.get('closed', [])
                closed_trades.append(trade_obj)
                
                trades_data['open'] = open_trades
                trades_data['closed'] = closed_trades
                save_trades(trades_data)
                
                # إرسال إشعار
                notify_trade_status(
                    symbol=symbol,
                    status=f"تم البيع ({reason})",
                    price=current_price,
                    profit_loss=profit_loss,
                    order_id=sell_result.get('orderId'),
                    api_verified=True
                )
            else:
                logger.error(f"❌ فشل بيع {symbol}: {sell_result}")
        except Exception as e:
            logger.error(f"خطأ في بيع {symbol}: {e}")
    
    return len(trades_to_close)

def main():
    """الدالة الرئيسية"""
    logger.info("بدء عملية تنظيف الصفقات وتطبيق قواعد الربح...")
    
    # تنظيف الصفقات الوهمية أولاً
    real_trades = clean_fake_trades()
    
    # تطبيق قواعد الربح على الصفقات الحقيقية
    closed_count = apply_profit_rules()
    
    # إرسال ملخص
    message = f"✅ تم تنظيف الصفقات وتطبيق قواعد الربح:\n"
    message += f"- تم تأكيد {len(real_trades)} صفقة حقيقية\n"
    message += f"- تم إغلاق {closed_count} صفقات حققت الهدف أو وصلت لوقف الخسارة"
    
    logger.info(message)
    send_telegram_message(message)

if __name__ == "__main__":
    main()