#!/usr/bin/env python3
"""
سكريبت للتحقق من الصفقات الحقيقية على منصة MEXC
ومتابعة تطبيق استراتيجيات الربح عليها
"""

import json
import logging
import sys
from datetime import datetime

from app.mexc_api import get_trades_history, get_current_price
from app.telegram_notify import send_telegram_message

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_trades():
    """تحميل الصفقات من الملف"""
    try:
        with open('active_trades.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الصفقات: {e}")
        return {"open": [], "closed": []}

def verify_real_trades():
    """التحقق من الصفقات الحقيقية على المنصة"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    
    print(f"\n=== الصفقات المفتوحة الحالية: {len(open_trades)} ===")
    
    real_trades = []
    
    # التحقق من كل صفقة مفتوحة
    for i, trade in enumerate(open_trades):
        symbol = trade.get('symbol', '')
        order_id = trade.get('orderId', '')
        entry_price = trade.get('entry_price', 0)
        quantity = trade.get('quantity', 0)
        take_profit = trade.get('take_profit', 0)
        stop_loss = trade.get('stop_loss', 0)
        timestamp = trade.get('timestamp', 0)
        trade_date = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S') if timestamp else "غير معروف"
        
        # جلب السعر الحالي
        current_price = get_current_price(symbol)
        if current_price:
            price_change = ((current_price - entry_price) / entry_price) * 100
            price_status = "🟢" if price_change >= 0 else "🔴"
        else:
            price_change = 0
            price_status = "⚪"
            current_price = "غير متوفر"
        
        # التحقق من وجود الصفقة في تاريخ التداول
        trade_history = get_trades_history(symbol, 10)
        trade_verified = False
        
        for history_item in trade_history:
            if history_item.get('orderId') == order_id:
                trade_verified = True
                break
        
        trade_status = "✅ حقيقية" if trade_verified else "❌ غير مؤكدة"
        
        print(f"\n{i+1}. {symbol} - {trade_status}")
        print(f"   السعر الأصلي: {entry_price}")
        print(f"   السعر الحالي: {current_price} {price_status} ({price_change:.2f}%)")
        print(f"   الكمية: {quantity}")
        print(f"   هدف الربح: {take_profit} ({((take_profit - entry_price) / entry_price) * 100:.2f}%)")
        print(f"   وقف الخسارة: {stop_loss} ({((stop_loss - entry_price) / entry_price) * 100:.2f}%)")
        print(f"   الوقت: {trade_date}")
        print(f"   معرف الأمر: {order_id}")
        
        if trade_verified:
            real_trades.append(trade)
    
    print(f"\n=== إجمالي الصفقات الحقيقية المؤكدة: {len(real_trades)} ===\n")
    
    # طباعة أسعار الصفقات للمقارنة
    if len(real_trades) > 0:
        print("=== مقارنة الأسعار الحالية ===")
        for trade in real_trades:
            symbol = trade.get('symbol', '')
            entry_price = trade.get('entry_price', 0)
            current_price = get_current_price(symbol)
            if current_price:
                price_change = ((current_price - entry_price) / entry_price) * 100
                price_status = "🟢" if price_change >= 0 else "🔴"
                
                # تحديد حالة الصفقة بالنسبة لاستراتيجية الربح
                take_profit_level = trade.get('take_profit', 0)
                stop_loss_level = trade.get('stop_loss', 0)
                
                if current_price >= take_profit_level:
                    profit_status = "✅ وصلت لهدف الربح!"
                elif current_price <= stop_loss_level:
                    profit_status = "⚠️ وصلت لوقف الخسارة!"
                else:
                    profit_status = "⏳ في انتظار الوصول للهدف"
                
                print(f"{symbol}: {entry_price} -> {current_price} {price_status} ({price_change:.2f}%) - {profit_status}")
    
    return real_trades

def run_trade_check_cycle():
    """تشغيل دورة فحص والتحقق من الصفقات"""
    print("بدء فحص الصفقات الحقيقية...")
    real_trades = verify_real_trades()
    
    if len(real_trades) > 0:
        message = f"تقرير الصفقات الحقيقية ({len(real_trades)} صفقة):\n\n"
        
        for trade in real_trades:
            symbol = trade.get('symbol', '')
            entry_price = trade.get('entry_price', 0)
            current_price = get_current_price(symbol)
            
            if current_price:
                price_change = ((current_price - entry_price) / entry_price) * 100
                
                message += f"{symbol}: {entry_price} -> {current_price} ({price_change:.2f}%)\n"
        
        print(f"\nإرسال تقرير بالصفقات إلى تلجرام...")
        try:
            send_telegram_message(message)
            print("✅ تم إرسال التقرير بنجاح.")
        except Exception as e:
            print(f"❌ فشل إرسال التقرير: {e}")
    else:
        print("لا توجد صفقات حقيقية مؤكدة للإبلاغ عنها.")

if __name__ == "__main__":
    run_trade_check_cycle()