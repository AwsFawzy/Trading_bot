#!/usr/bin/env python3
"""
سكريبت لتحديث ملف الصفقات النشطة ليعكس الصفقات الحقيقية
ويطبق استراتيجيات الربح عليها
"""

import json
import logging
from datetime import datetime

from app.mexc_api import get_trades_history, get_current_price

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# قائمة معرفات الصفقات الحقيقية التي تم اكتشافها (5 صفقات)
REAL_TRADE_IDS = [
    'C02__550239805418520578071',  # FILUSDT (مؤكدة)
    'C02__550036298245619712071',  # LINKUSDT
    'C02__550035861278879746071',  # LINKUSDT
    'C02__550035774007943170071',  # LINKUSDT
    'C02__550035688171544577071',  # LINKUSDT
]

# الرموز التي يجب البحث عنها
SYMBOLS_TO_SEARCH = [
    'LINKUSDT',
    'FILUSDT',
    'BTCUSDT',
    'ETHUSDT',
    'DOGEUSDT',
    'SOLUSDT',
    'BNBUSDT',
    'ADAUSDT',
    'XRPUSDT',
    'DOTUSDT',
    'TRXUSDT',
    'NEARUSDT',
    'AVAXUSDT',
]

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

def update_active_trades():
    """تحديث الصفقات النشطة بناءً على الصفقات الحقيقية"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    closed_trades = trades_data.get('closed', [])
    
    # حذف الصفقات الوهمية وإغلاقها
    new_open_trades = []
    
    for trade in open_trades:
        order_id = trade.get('orderId', '')
        symbol = trade.get('symbol', '')
        
        if order_id in REAL_TRADE_IDS:
            # التحقق من الصفقة باستخدام API
            is_real = False
            trades_history = get_trades_history(symbol, 10)
            
            for history_item in trades_history:
                if history_item.get('orderId') == order_id:
                    is_real = True
                    # تحديث الصفقة ببيانات حقيقية من API
                    trade['api_confirmed'] = True
                    new_open_trades.append(trade)
                    logger.info(f"✅ تم تأكيد الصفقة {symbol} بمعرف {order_id}")
                    break
            
            if not is_real:
                logger.warning(f"⚠️ لم يتم تأكيد الصفقة {symbol} بمعرف {order_id} رغم وجودها في قائمة الصفقات الحقيقية")
                trade['status'] = 'CLOSED'
                trade['close_reason'] = 'FAKE_TRADE_CLEANUP'
                trade['close_timestamp'] = int(datetime.now().timestamp() * 1000)
                closed_trades.append(trade)
        else:
            logger.warning(f"❌ إغلاق صفقة وهمية: {symbol} بمعرف {order_id}")
            trade['status'] = 'CLOSED'
            trade['close_reason'] = 'FAKE_TRADE_CLEANUP'
            trade['close_timestamp'] = int(datetime.now().timestamp() * 1000)
            closed_trades.append(trade)
    
    # تحديث الملف
    updated_data = {
        'open': new_open_trades,
        'closed': closed_trades
    }
    
    save_trades(updated_data)
    return new_open_trades

def add_missing_real_trades():
    """إضافة الصفقات الحقيقية المفقودة"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    
    # جمع معرفات الصفقات الموجودة
    existing_order_ids = set(trade.get('orderId', '') for trade in open_trades)
    
    # البحث عن الصفقات المفقودة وإضافتها
    for order_id in REAL_TRADE_IDS:
        if order_id not in existing_order_ids:
            logger.info(f"🔍 البحث عن صفقة مفقودة بمعرف: {order_id}")
            
            # البحث في جميع الرموز المعروفة
            symbols = SYMBOLS_TO_SEARCH
            
            for symbol in symbols:
                trades_history = get_trades_history(symbol, 10)
                
                for history_item in trades_history:
                    if history_item.get('orderId') == order_id:
                        # إنشاء بيانات الصفقة
                        price = float(history_item.get('price', 0))
                        qty = float(history_item.get('qty', 0))
                        timestamp = history_item.get('time', 0)
                        
                        # حساب أهداف الربح ووقف الخسارة (0.5% ربح و -0.1% وقف خسارة)
                        take_profit = price * 1.005
                        stop_loss = price * 0.999
                        
                        new_trade = {
                            'symbol': symbol,
                            'quantity': qty,
                            'entry_price': price,
                            'take_profit': take_profit,
                            'stop_loss': stop_loss,
                            'timestamp': timestamp,
                            'status': 'OPEN',
                            'api_executed': True,
                            'api_confirmed': True,
                            'orderId': order_id,
                            'order_type': 'MARKET'
                        }
                        
                        # إضافة الصفقة
                        open_trades.append(new_trade)
                        logger.info(f"✅ تمت إضافة صفقة حقيقية لـ {symbol} بمعرف {order_id}")
                        break
    
    # تحديث الملف
    trades_data['open'] = open_trades
    save_trades(trades_data)
    return open_trades

def verify_trade_strategies():
    """التحقق من تطبيق استراتيجيات الربح على الصفقات الحقيقية"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    
    print(f"\n=== التحقق من تطبيق استراتيجيات الربح على {len(open_trades)} صفقة حقيقية ===\n")
    
    for trade in open_trades:
        symbol = trade.get('symbol', '')
        entry_price = trade.get('entry_price', 0)
        current_price = get_current_price(symbol)
        
        if current_price:
            price_change = ((current_price - entry_price) / entry_price) * 100
            price_status = "🟢" if price_change >= 0 else "🔴"
            
            take_profit = trade.get('take_profit', 0)
            stop_loss = trade.get('stop_loss', 0)
            
            take_profit_pct = ((take_profit - entry_price) / entry_price) * 100
            stop_loss_pct = ((stop_loss - entry_price) / entry_price) * 100
            
            # تحديد حالة الصفقة
            status = "⏳ انتظار"
            if current_price >= take_profit:
                status = "✅ تم تحقيق هدف الربح"
            elif current_price <= stop_loss:
                status = "⚠️ تم الوصول لوقف الخسارة"
                
            print(f"{symbol}: السعر الأصلي {entry_price:.6f} -> الحالي {current_price:.6f} {price_status} ({price_change:.2f}%)")
            print(f"  هدف الربح: {take_profit:.6f} ({take_profit_pct:.2f}%)")
            print(f"  وقف الخسارة: {stop_loss:.6f} ({stop_loss_pct:.2f}%)")
            print(f"  الحالة: {status}\n")
            
            # تحديث أهداف الربح ووقف الخسارة عند الحاجة
            if take_profit_pct < 0.5:
                new_take_profit = entry_price * 1.005  # جعل هدف الربح 0.5%
                trade['take_profit'] = new_take_profit
                logger.info(f"تحديث هدف الربح لـ {symbol} إلى {new_take_profit:.6f} (0.5%)")
            
            if stop_loss_pct > -0.1:
                new_stop_loss = entry_price * 0.999  # جعل وقف الخسارة -0.1%
                trade['stop_loss'] = new_stop_loss
                logger.info(f"تحديث وقف الخسارة لـ {symbol} إلى {new_stop_loss:.6f} (-0.1%)")
    
    # حفظ التغييرات
    trades_data['open'] = open_trades
    save_trades(trades_data)

if __name__ == "__main__":
    print("جاري تحديث ملف الصفقات النشطة بالصفقات الحقيقية...")
    
    # تحديث الصفقات النشطة
    real_trades = update_active_trades()
    print(f"تم تحديث الصفقات الحقيقية: {len(real_trades)} صفقة")
    
    # إضافة الصفقات المفقودة
    all_real_trades = add_missing_real_trades()
    print(f"تم إضافة الصفقات المفقودة، إجمالي الصفقات الحقيقية: {len(all_real_trades)} صفقة")
    
    # التحقق من تطبيق استراتيجيات الربح
    verify_trade_strategies()