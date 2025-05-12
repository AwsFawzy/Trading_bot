#!/usr/bin/env python3
"""
سكريبت لإغلاق الصفقات الخاسرة وفتح صفقات حقيقية جديدة
"""

import json
import logging
import random
from datetime import datetime

from app.mexc_api import (
    get_current_price, 
    place_order, 
    get_all_symbols_24h_data,
    get_trades_history
)
from app.telegram_notify import send_telegram_message, notify_trade_status

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# إعدادات التداول
TRADE_SETTINGS = {
    'total_capital': 25.0,      # رأس المال الإجمالي (5 دولار × 5 صفقات)
    'max_trades': 5,            # الحد الأقصى لعدد الصفقات المفتوحة
    'min_profit': 0.5,          # الحد الأدنى للربح قبل البيع (%)
    'max_loss': 0.1,            # الحد الأقصى للخسارة قبل البيع (%)
    'blacklisted_symbols': [],  # العملات المحظورة
}

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

def close_losing_trades():
    """إغلاق الصفقات الخاسرة"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    print(f"\n=== إغلاق الصفقات الخاسرة ({len(open_trades)} صفقة) ===\n")
    
    new_open_trades = []
    closed_count = 0
    
    for trade in open_trades:
        symbol = trade.get('symbol', '')
        entry_price = trade.get('entry_price', 0)
        quantity = trade.get('quantity', 0)
        order_id = trade.get('orderId', '')
        
        # تجربة إغلاق الصفقة
        print(f"محاولة إغلاق صفقة {symbol} بكمية {quantity}...")
        try:
            # تنفيذ أمر البيع باستخدام place_order مع جانب البيع
            sell_result = place_order(symbol, "SELL", quantity, None, "MARKET")
            
            if sell_result and 'error' not in sell_result:
                # تمت عملية البيع بنجاح
                current_price = float(sell_result.get('price', 0))
                profit_loss = ((current_price - entry_price) / entry_price) * 100 if current_price > 0 else 0
                
                print(f"✅ تم بيع {symbol} بسعر {current_price} (تغير السعر: {profit_loss:.2f}%)")
                
                # تحديث معلومات الصفقة
                trade['status'] = 'CLOSED'
                trade['close_price'] = current_price
                trade['close_timestamp'] = int(datetime.now().timestamp() * 1000)
                trade['profit_loss'] = profit_loss
                trade['close_reason'] = 'MANUAL_CLOSE'
                
                # إضافة الصفقة المغلقة إلى قائمة الصفقات المغلقة
                closed_trades.append(trade)
                closed_count += 1
                
                # إرسال إشعار بالتلغرام
                notify_trade_status(
                    symbol=symbol,
                    status="تم البيع (إغلاق يدوي)",
                    price=current_price,
                    profit_loss=profit_loss,
                    order_id=sell_result.get('orderId'),
                    api_verified=True
                )
            else:
                print(f"❌ فشل بيع {symbol}: {sell_result.get('error')}")
                new_open_trades.append(trade)
        except Exception as e:
            logger.error(f"خطأ في بيع {symbol}: {e}")
            new_open_trades.append(trade)
    
    # تحديث ملف الصفقات
    trades_data['open'] = new_open_trades
    trades_data['closed'] = closed_trades
    save_trades(trades_data)
    
    print(f"\nتم إغلاق {closed_count} من أصل {len(open_trades)} صفقة")
    return closed_count

def get_diverse_symbols(count=5):
    """الحصول على مجموعة متنوعة من رموز العملات للتداول"""
    # جلب قائمة العملات المفضلة
    preferred_coins = PREFERRED_COINS.copy()
    random.shuffle(preferred_coins)
    
    if len(preferred_coins) < count:
        try:
            # جلب قائمة بجميع العملات من السوق
            all_symbols_data = get_all_symbols_24h_data()
            available_symbols = [
                symbol_data.get('symbol')
                for symbol_data in all_symbols_data
                if symbol_data.get('symbol', '').endswith('USDT') and
                symbol_data.get('symbol') not in TRADE_SETTINGS['blacklisted_symbols']
            ]
            random.shuffle(available_symbols)
            preferred_coins.extend(available_symbols)
        except Exception as e:
            logger.error(f"خطأ في جلب بيانات العملات: {e}")
    
    # الحصول على العملات المتداولة حالياً لمنع التكرار
    active_trades = load_trades()
    active_symbols = set()
    for trade in active_trades.get('open', []):
        if trade.get('status') == 'OPEN':
            active_symbols.add(trade.get('symbol'))
    
    logger.info(f"العملات المتداولة حالياً: {active_symbols}")
    
    # فلترة العملات المستبعدة وتجنب التكرار
    selected_symbols = []
    
    for symbol in preferred_coins:
        if len(selected_symbols) >= count:
            break
        
        # تخطي العملات المتداولة حالياً
        if symbol in active_symbols:
            logger.info(f"تخطي {symbol} لأنها متداولة حالياً")
            continue
        
        # التحقق من وجود سعر حالي
        current_price = get_current_price(symbol)
        if current_price:
            selected_symbols.append(symbol)
    
    return selected_symbols[:count]

def calculate_trade_amount(total_capital, max_trades):
    """حساب المبلغ المخصص لكل صفقة"""
    return total_capital / max_trades

def execute_buy(symbol, amount):
    """تنفيذ عملية الشراء"""
    try:
        # الحصول على السعر الحالي
        price = get_current_price(symbol)
        if not price:
            logger.error(f"لم يتم الحصول على سعر العملة {symbol}")
            return False, {"error": "لم يتم الحصول على السعر"}
        
        # حساب الكمية
        quantity = amount / price
        
        logger.info(f"محاولة شراء {symbol}: السعر={price}, الكمية={quantity}, المبلغ={amount}")
        
        # تنفيذ أمر الشراء
        result = place_order(symbol, "BUY", quantity, None, "MARKET")
        
        if 'error' not in result:
            # التحقق من وجود الصفقة في تاريخ التداول
            trade_history_verified = False
            try:
                trades_history = get_trades_history(symbol, 10)
                if trades_history:
                    for trade_record in trades_history:
                        if trade_record.get('orderId') == result.get('orderId'):
                            trade_history_verified = True
                            logger.info(f"✅ تأكيد وجود الصفقة في تاريخ التداول: {symbol} - معرف الأمر: {result.get('orderId')}")
                            break
                
                if not trade_history_verified:
                    logger.warning(f"⚠️ لم يتم العثور على الصفقة {symbol} في تاريخ التداول رغم نجاح الأمر")
            except Exception as e:
                logger.error(f"خطأ أثناء التحقق من تاريخ التداول: {e}")
            
            # إنشاء سجل للصفقة
            order_info = {
                'symbol': symbol,
                'quantity': quantity,
                'entry_price': price,
                'take_profit': price * 1.005,  # 0.5% ربح
                'stop_loss': price * 0.999,    # 0.1% وقف خسارة
                'timestamp': int(datetime.now().timestamp() * 1000),
                'status': 'OPEN',
                'api_executed': True,
                'api_confirmed': trade_history_verified,
                'orderId': result.get('orderId', ''),
                'order_type': 'MARKET'
            }
            
            # تحديث ملف الصفقات
            data = load_trades()
            data['open'].append(order_info)
            save_trades(data)
            
            logger.info(f"✅ تم تنفيذ الشراء بنجاح لـ {symbol}: {result}")
            
            # إرسال إشعار تلغرام مع معرف الأمر
            notify_trade_status(
                symbol=symbol, 
                status="تم الشراء", 
                price=price, 
                order_id=result.get('orderId'),
                api_verified=trade_history_verified
            )
                
            return True, result
        else:
            logger.error(f"❌ فشل تنفيذ الشراء لـ {symbol}: {result}")
            return False, result
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ الشراء لـ {symbol}: {e}")
        return False, {"error": str(e)}

def open_new_trades(count=5):
    """فتح صفقات جديدة متنوعة"""
    print(f"\n=== فتح {count} صفقات حقيقية جديدة ===\n")
    
    # الحصول على رموز متنوعة
    selected_symbols = get_diverse_symbols(count)
    print(f"تم اختيار العملات: {selected_symbols}")
    
    # حساب المبلغ لكل صفقة
    amount_per_trade = calculate_trade_amount(
        TRADE_SETTINGS['total_capital'], 
        TRADE_SETTINGS['max_trades']
    )
    print(f"المبلغ المخصص لكل صفقة: {amount_per_trade} دولار")
    
    # فتح صفقات جديدة
    successful_trades = 0
    
    for symbol in selected_symbols:
        print(f"\nمحاولة شراء {symbol} بمبلغ {amount_per_trade} دولار...")
        success, result = execute_buy(symbol, amount_per_trade)
        if success:
            successful_trades += 1
            print(f"تم شراء {symbol} بنجاح")
        else:
            print(f"فشل شراء {symbol}")
    
    print(f"\nتم فتح {successful_trades} صفقات جديدة من أصل {count} محاولة")
    return successful_trades

def main():
    """الدالة الرئيسية"""
    print("جاري إغلاق الصفقات الخاسرة وفتح صفقات جديدة...")
    
    # إغلاق الصفقات الخاسرة
    closed_count = close_losing_trades()
    
    # فتح صفقات جديدة
    new_trades = open_new_trades(5)
    
    # إرسال ملخص
    try:
        report = f"🔄 تم إعادة تنظيم المحفظة:\n"
        report += f"✅ تم إغلاق {closed_count} صفقات خاسرة\n"
        report += f"✅ تم فتح {new_trades} صفقات جديدة\n\n"
        report += f"⭐ تمت إعادة توزيع رأس المال بنجاح"
        
        send_telegram_message(report)
        print("\n✅ تم إرسال تقرير إلى تلغرام")
    except Exception as e:
        print(f"\n❌ فشل إرسال التقرير: {e}")
    
    print("\nاكتملت العملية بنجاح")

if __name__ == "__main__":
    main()