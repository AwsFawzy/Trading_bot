#!/usr/bin/env python3
"""
أداة فحص الصفقات الحالية والإحصائيات
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

# إضافة المجلد الحالي إلى مسار البحث
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_trades():
    """
    تحميل الصفقات من ملف JSON
    
    :return: قائمة بالصفقات المحملة
    """
    try:
        if os.path.exists('active_trades.json'):
            with open('active_trades.json', 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"خطأ في تحميل الصفقات: {e}")
        return []

def get_status_summary():
    """
    الحصول على ملخص لحالة الصفقات
    
    :return: ملخص حالة الصفقات
    """
    trades = load_trades()
    
    # إحصائيات عامة
    open_trades = [t for t in trades if t.get('status') == 'OPEN']
    closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
    
    # إحصائيات مقسمة زمنيًا
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    
    today_trades = []
    yesterday_trades = []
    week_trades = []
    
    for trade in closed_trades:
        close_timestamp = trade.get('close_timestamp', 0)
        if close_timestamp:
            close_date = datetime.fromtimestamp(close_timestamp / 1000)
            
            if close_date >= today:
                today_trades.append(trade)
            elif close_date >= yesterday:
                yesterday_trades.append(trade)
            elif close_date >= (today - timedelta(days=7)):
                week_trades.append(trade)
    
    # قائمة بالصفقات المفتوحة حاليًا
    print("\n=== الصفقات المفتوحة حاليًا ===")
    if open_trades:
        for i, trade in enumerate(open_trades):
            symbol = trade.get('symbol', 'غير معروف')
            quantity = trade.get('quantity', 0)
            entry_price = trade.get('entry_price', 0)
            timestamp = trade.get('timestamp', 0)
            
            # تحويل الطابع الزمني إلى تاريخ مقروء
            if timestamp:
                date_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            else:
                date_str = 'غير معروف'
                
            print(f"{i+1}. {symbol}: {quantity} @ {entry_price} (تاريخ الشراء: {date_str})")
    else:
        print("لا توجد صفقات مفتوحة حاليًا")
    
    # حساب إحصائيات الصفقات المغلقة
    total_profit = 0
    total_loss = 0
    profitable_trades = 0
    
    for trade in closed_trades:
        profit = trade.get('profit_pct', 0)
        if profit > 0:
            total_profit += profit
            profitable_trades += 1
        else:
            total_loss += abs(profit)
    
    # إحصائيات إجمالية
    print("\n=== إحصائيات الصفقات ===")
    print(f"إجمالي عدد الصفقات: {len(trades)}")
    print(f"الصفقات المفتوحة: {len(open_trades)}")
    print(f"الصفقات المغلقة: {len(closed_trades)}")
    
    # تحليل تفصيلي للفترات الزمنية
    print(f"\n- اليوم: {len(today_trades)} صفقة")
    print(f"- الأمس: {len(yesterday_trades)} صفقة")
    print(f"- هذا الأسبوع: {len(week_trades)} صفقة")
    
    if closed_trades:
        win_rate = (profitable_trades / len(closed_trades)) * 100
        print(f"\nمعدل الربح: {win_rate:.2f}%")
        print(f"إجمالي الربح: {total_profit:.2f}%")
        print(f"إجمالي الخسارة: {total_loss:.2f}%")
        
        # حساب صافي الربح/الخسارة
        net_profit = total_profit - total_loss
        print(f"صافي الربح/الخسارة: {net_profit:.2f}%")
        
        # حساب إحصائيات اليوم
        today_profit = sum([t.get('profit_pct', 0) for t in today_trades if t.get('profit_pct', 0) > 0])
        today_loss = sum([abs(t.get('profit_pct', 0)) for t in today_trades if t.get('profit_pct', 0) < 0])
        today_net = today_profit - today_loss
        
        if today_trades:
            print(f"\n=== إحصائيات اليوم ===")
            print(f"عدد الصفقات: {len(today_trades)}")
            print(f"صافي الربح/الخسارة: {today_net:.2f}%")
            
            # أداء العملات اليوم
            today_symbols = {}
            for trade in today_trades:
                symbol = trade.get('symbol', 'غير معروف')
                profit = trade.get('profit_pct', 0)
                
                if symbol not in today_symbols:
                    today_symbols[symbol] = []
                today_symbols[symbol].append(profit)
            
            if today_symbols:
                print("\nأداء العملات اليوم:")
                for symbol, profits in today_symbols.items():
                    avg_profit = sum(profits) / len(profits)
                    trade_count = len(profits)
                    print(f"  • {symbol}: {avg_profit:.2f}% ({trade_count} صفقة)")
    else:
        print("لم يتم إغلاق أي صفقات بعد")
        
    # الاحصائيات المفصلة
    if closed_trades:
        print("\n=== تفاصيل آخر 5 صفقات مغلقة ===")
        for i, trade in enumerate(sorted(closed_trades, key=lambda x: x.get('close_timestamp', 0), reverse=True)[:5]):
            symbol = trade.get('symbol', 'غير معروف')
            profit = trade.get('profit_pct', 0)
            entry_price = trade.get('entry_price', 0)
            close_price = trade.get('close_price', 0)
            close_time = trade.get('close_timestamp', 0)
            
            # تحويل الطابع الزمني إلى تاريخ مقروء
            if close_time:
                date_str = datetime.fromtimestamp(close_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
            else:
                date_str = 'غير معروف'
            
            # معالجة القيم الصفرية
            if entry_price == 0 and close_price == 0:
                entry_price = trade.get('entry_price', "غير متوفر")
                close_price = trade.get('close_price', "غير متوفر")
                
            result = "ربح ✅" if profit > 0 else "خسارة ❌"
            duration = ""
            
            # حساب مدة الصفقة
            open_timestamp = trade.get('timestamp')
            if open_timestamp and close_time:
                open_time = datetime.fromtimestamp(open_timestamp / 1000)
                close_time_dt = datetime.fromtimestamp(close_time / 1000)
                duration_seconds = (close_time_dt - open_time).total_seconds()
                
                if duration_seconds < 60:
                    duration = f" ({int(duration_seconds)} ثانية)"
                elif duration_seconds < 3600:
                    duration = f" ({int(duration_seconds/60)} دقيقة)"
                else:
                    duration = f" ({int(duration_seconds/3600)} ساعة)"
                
            print(f"{i+1}. {symbol}: {result} {profit:.2f}% (من {entry_price} إلى {close_price}, {date_str}{duration})")
            
    # تحليل أداء العملات بشكل عام
    if closed_trades:
        print("\n=== تحليل أداء العملات ===")
        symbol_stats = {}
        
        for trade in closed_trades:
            symbol = trade.get('symbol', 'غير معروف')
            profit = trade.get('profit_pct', 0)
            
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    'trades': 0,
                    'profit_trades': 0,
                    'loss_trades': 0,
                    'total_profit': 0,
                    'total_loss': 0
                }
                
            symbol_stats[symbol]['trades'] += 1
            
            if profit > 0:
                symbol_stats[symbol]['profit_trades'] += 1
                symbol_stats[symbol]['total_profit'] += profit
            else:
                symbol_stats[symbol]['loss_trades'] += 1
                symbol_stats[symbol]['total_loss'] += abs(profit)
        
        # ترتيب العملات حسب عدد الصفقات
        sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['trades'], reverse=True)
        
        for symbol, stats in sorted_symbols[:5]:  # عرض أفضل 5 عملات فقط
            win_rate = (stats['profit_trades'] / stats['trades']) * 100 if stats['trades'] > 0 else 0
            net_profit = stats['total_profit'] - stats['total_loss']
            
            print(f"• {symbol}: {stats['trades']} صفقة, معدل الربح: {win_rate:.1f}%, صافي الربح: {net_profit:.2f}%")
    
    # إرجاع قاموس بكل الإحصائيات
    today_profit = sum([t.get('profit_pct', 0) for t in today_trades if t.get('profit_pct', 0) > 0])
    today_loss = sum([abs(t.get('profit_pct', 0)) for t in today_trades if t.get('profit_pct', 0) < 0])
        
    return {
        'open_trades': len(open_trades),
        'closed_trades': len(closed_trades),
        'profitable_trades': profitable_trades,
        'total_profit': total_profit,
        'total_loss': total_loss,
        'net_profit': total_profit - total_loss if closed_trades else 0,
        'win_rate': (profitable_trades / len(closed_trades)) * 100 if closed_trades else 0,
        'today_trades': len(today_trades),
        'today_profit': today_profit,
        'today_loss': today_loss,
        'today_net': today_profit - today_loss
    }

def main():
    """
    النقطة الرئيسية للبرنامج
    """
    print("=== أداة فحص الصفقات ===")
    get_status_summary()

if __name__ == "__main__":
    main()