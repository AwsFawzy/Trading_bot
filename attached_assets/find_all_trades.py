#!/usr/bin/env python3
"""
سكريبت للبحث عن جميع الصفقات الحقيقية على منصة MEXC
يستخدم طرق متعددة للعثور على الصفقات
"""

import json
import logging
import sys
from datetime import datetime, timedelta

from app.mexc_api import (
    get_trades_history, 
    get_current_price,
    get_open_orders,
    get_all_symbols_24h_data,
    test_api_permissions,
    fetch_recent_trades,
    get_account_balance
)

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# قائمة العملات المشهورة للبحث فيها
POPULAR_COINS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'BNBUSDT', 'ADAUSDT',
    'XRPUSDT', 'DOTUSDT', 'LINKUSDT', 'LTCUSDT', 'AVAXUSDT', 'ATOMUSDT',
    'MATICUSDT', 'FILUSDT', 'TRXUSDT', 'NEARUSDT', 'AAVEUSDT', 'UNIUSDT',
    'ZECUSDT', 'APTUSDT', 'SUIUSDT', 'ETHUSDT', 'APEUSDT', 'SANDUSDT'
]

def load_trades_from_file():
    """تحميل الصفقات من الملف المحلي"""
    try:
        with open('active_trades.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الصفقات: {e}")
        return {"open": [], "closed": []}

def find_all_trades_on_mexc():
    """البحث عن جميع الصفقات الحقيقية على منصة MEXC"""
    print("\n=== البحث عن جميع الصفقات الحقيقية على منصة MEXC ===\n")
    
    # الحصول على الصفقات المخزنة محليًا
    local_trades = load_trades_from_file()
    local_open_trades = local_trades.get('open', [])
    
    print(f"الصفقات المفتوحة في الملف المحلي: {len(local_open_trades)}")
    
    # البحث عن الأوامر المفتوحة
    open_orders = get_open_orders()
    print(f"\nالأوامر المفتوحة على المنصة: {len(open_orders) if open_orders else 0}")
    
    # البحث عن تاريخ التداول لكل عملة مشهورة
    print("\n=== البحث عن صفقات في تاريخ التداول (آخر 24 ساعة) ===")
    
    all_trades = []
    time_threshold = datetime.now() - timedelta(days=1)  # صفقات آخر 24 ساعة فقط
    time_threshold_ms = int(time_threshold.timestamp() * 1000)
    
    # حفظ جميع الصفقات المجمعة
    aggregated_trades = {}
    
    for symbol in POPULAR_COINS:
        trades = get_trades_history(symbol, 20)  # زيادة العدد لاستخلاص المزيد من الصفقات
        recent_trades = []
        
        if trades:
            # تصفية الصفقات الحديثة فقط
            for trade in trades:
                if trade.get('time', 0) >= time_threshold_ms:
                    recent_trades.append(trade)
                    
                    # تحديث قائمة الصفقات المجمعة حسب المعرف
                    order_id = trade.get('orderId', '')
                    if order_id:
                        if order_id not in aggregated_trades:
                            aggregated_trades[order_id] = []
                        aggregated_trades[order_id].append(trade)
            
            if recent_trades:
                print(f"\n{symbol}: {len(recent_trades)} صفقة حديثة")
                for t in recent_trades:
                    order_id = t.get('orderId', '')
                    trade_time = datetime.fromtimestamp(t.get('time', 0)/1000).strftime('%Y-%m-%d %H:%M:%S')
                    price = t.get('price', '')
                    qty = t.get('qty', '')
                    side = "شراء" if t.get('isBuyer') else "بيع"
                    
                    print(f"- {side}: {qty} @ {price} | {trade_time} | معرف: {order_id}")
                    all_trades.append(t)
    
    # عرض الصفقات المجمعة حسب المعرف
    print(f"\n=== قائمة شاملة بجميع الصفقات حسب المعرف (إجمالي: {len(aggregated_trades)}) ===")
    for order_id, trades in aggregated_trades.items():
        if trades:
            first_trade = trades[0]
            symbol = first_trade.get('symbol', '')
            side = "شراء" if first_trade.get('isBuyer') else "بيع"
            trade_time = datetime.fromtimestamp(first_trade.get('time', 0)/1000).strftime('%Y-%m-%d %H:%M:%S')
            
            # حساب مجموع الكمية
            total_qty = sum(float(t.get('qty', 0)) for t in trades)
            avg_price = sum(float(t.get('price', 0)) * float(t.get('qty', 0)) for t in trades) / total_qty if total_qty > 0 else 0
            
            print(f"{order_id}: {symbol} {side} {total_qty:.6f} @ {avg_price:.6f} | {trade_time}")
    
    # الحصول على رصيد الحساب
    print("\n=== رصيد الحساب ===")
    try:
        balance = get_account_balance()
        if balance and isinstance(balance, dict):
            for asset, details in balance.items():
                if details and isinstance(details, dict):
                    free = details.get('free', '0')
                    locked = details.get('locked', '0')
                    if float(free) > 0 or float(locked) > 0:
                        print(f"{asset}: متاح={free} مقفل={locked}")
    except Exception as e:
        print(f"خطأ في جلب رصيد الحساب: {e}")
    
    print(f"\n=== إجمالي الصفقات الحقيقية المعثور عليها: {len(all_trades)} ===")
    return all_trades

def compare_local_vs_remote():
    """مقارنة الصفقات المحلية مع الصفقات على المنصة"""
    print("\n=== مقارنة الصفقات المحلية مع الصفقات على المنصة ===\n")
    
    local_trades = load_trades_from_file()
    local_open_trades = local_trades.get('open', [])
    
    found_trades = 0
    missing_trades = 0
    
    for trade in local_open_trades:
        symbol = trade.get('symbol', '')
        order_id = trade.get('orderId', '')
        
        # البحث في تاريخ التداول
        trade_found = False
        trades_history = get_trades_history(symbol, 10)
        
        for t in trades_history:
            if t.get('orderId') == order_id:
                trade_found = True
                found_trades += 1
                print(f"✓ تم تأكيد صفقة {symbol} بمعرف {order_id}")
                break
        
        if not trade_found:
            missing_trades += 1
            print(f"✗ لم يتم العثور على صفقة {symbol} بمعرف {order_id}")
    
    print(f"\nالنتائج: {found_trades} صفقة مؤكدة، {missing_trades} صفقة غير مؤكدة")

if __name__ == "__main__":
    print("جاري التحقق من الصفقات على منصة MEXC...")
    
    # التحقق من صلاحيات API
    api_perms = test_api_permissions()
    if api_perms:
        print(f"صلاحيات API: {api_perms}")
    
    # البحث عن جميع الصفقات
    all_trades = find_all_trades_on_mexc()
    
    # مقارنة الصفقات المحلية مع الصفقات على المنصة
    compare_local_vs_remote()