#!/usr/bin/env python3
"""
سكريبت مُبسط لإضافة الصفقات الحقيقية المفقودة
"""

import json
import logging
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# الصفقات الحقيقية الثلاث المفقودة
MISSING_TRADES = [
    {
        'symbol': 'LINKUSDT',
        'quantity': 0.5,
        'entry_price': 17.37,
        'take_profit': 17.37 * 1.005,  # 0.5% هدف ربح
        'stop_loss': 17.37 * 0.999,    # 0.1% وقف خسارة
        'timestamp': 1746921004000,    # 2025-05-10 23:50:04
        'status': 'OPEN',
        'api_executed': True,
        'api_confirmed': True,
        'orderId': 'C02__550035861278879746071',
        'order_type': 'MARKET'
    },
    {
        'symbol': 'LINKUSDT',
        'quantity': 0.5,
        'entry_price': 17.37,
        'take_profit': 17.37 * 1.005,  # 0.5% هدف ربح
        'stop_loss': 17.37 * 0.999,    # 0.1% وقف خسارة
        'timestamp': 1746920984000,    # 2025-05-10 23:49:44
        'status': 'OPEN',
        'api_executed': True,
        'api_confirmed': True,
        'orderId': 'C02__550035774007943170071',
        'order_type': 'MARKET'
    },
    {
        'symbol': 'LINKUSDT',
        'quantity': 0.5,
        'entry_price': 17.37,
        'take_profit': 17.37 * 1.005,  # 0.5% هدف ربح
        'stop_loss': 17.37 * 0.999,    # 0.1% وقف خسارة
        'timestamp': 1746920963000,    # 2025-05-10 23:49:23
        'status': 'OPEN',
        'api_executed': True,
        'api_confirmed': True,
        'orderId': 'C02__550035688171544577071',
        'order_type': 'MARKET'
    }
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

def add_remaining_trades():
    """إضافة الصفقات الحقيقية المتبقية"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    
    # جمع معرفات الصفقات الموجودة
    existing_order_ids = set(trade.get('orderId', '') for trade in open_trades)
    
    # إضافة الصفقات المفقودة
    added_count = 0
    for trade in MISSING_TRADES:
        order_id = trade.get('orderId', '')
        if order_id not in existing_order_ids:
            open_trades.append(trade)
            logger.info(f"✅ تمت إضافة صفقة {trade.get('symbol')} بمعرف {order_id}")
            added_count += 1
        else:
            logger.info(f"⚠️ الصفقة {trade.get('symbol')} بمعرف {order_id} موجودة بالفعل")
    
    # حفظ التغييرات
    trades_data['open'] = open_trades
    save_trades(trades_data)
    
    print(f"تم إضافة {added_count} صفقات جديدة، إجمالي الصفقات المفتوحة: {len(open_trades)}")
    return open_trades

if __name__ == "__main__":
    print("جاري إضافة الصفقات الحقيقية المفقودة...")
    add_remaining_trades()
    
    # عرض ملخص للصفقات
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    
    print("\n=== الصفقات الحقيقية المفتوحة ===")
    for i, trade in enumerate(open_trades):
        symbol = trade.get('symbol', '')
        entry_price = trade.get('entry_price', 0)
        order_id = trade.get('orderId', '')
        qty = trade.get('quantity', 0)
        print(f"{i+1}. {symbol}: {qty} @ {entry_price} - معرف: {order_id}")
    
    print(f"\nإجمالي: {len(open_trades)} صفقة حقيقية مفتوحة")