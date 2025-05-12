#!/usr/bin/env python3
"""
سكريبت لمراقبة الصفقات الحقيقية ومتابعة تطبيق استراتيجيات الربح والحماية عليها
"""

import json
import logging
import time
from datetime import datetime, timedelta

from app.mexc_api import get_current_price, get_trades_history
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

def apply_trade_strategies():
    """تطبيق استراتيجيات الربح على الصفقات الحقيقية"""
    trades_data = load_trades()
    open_trades = trades_data.get('open', [])
    
    print(f"\n=== تطبيق استراتيجيات الربح على {len(open_trades)} صفقة حقيقية ===\n")
    
    now = datetime.now()
    
    # إنشاء تقرير
    report = f"⭐ تقرير حالة الصفقات ({now.strftime('%Y-%m-%d %H:%M')}) ⭐\n\n"
    
    for trade in open_trades:
        symbol = trade.get('symbol', '')
        entry_price = trade.get('entry_price', 0)
        order_id = trade.get('orderId', '')
        timestamp = trade.get('timestamp', 0)
        quantity = trade.get('quantity', 0)
        
        # تاريخ الصفقة
        trade_date = datetime.fromtimestamp(timestamp/1000) if timestamp else now
        age_days = (now - trade_date).days
        
        # الحصول على السعر الحالي
        current_price = get_current_price(symbol)
        
        if current_price:
            price_change = ((current_price - entry_price) / entry_price) * 100
            price_status = "🟢" if price_change >= 0 else "🔴"
            
            # استراتيجيات الربح المختلفة
            take_profit_1 = entry_price * 1.005  # 0.5% ربح
            take_profit_2 = entry_price * 1.01   # 1.0% ربح
            take_profit_3 = entry_price * 1.02   # 2.0% ربح
            stop_loss = entry_price * 0.999      # -0.1% وقف خسارة
            
            # تحديث أهداف الربح ووقف الخسارة في الصفقة
            trade['take_profit'] = take_profit_1
            trade['stop_loss'] = stop_loss
            
            # تحديد حالة الصفقة
            status = "⏳ انتظار"
            if current_price >= take_profit_3:
                status = "✅✅✅ وصلنا للهدف الثالث (2.0%)"
            elif current_price >= take_profit_2:
                status = "✅✅ وصلنا للهدف الثاني (1.0%)"
            elif current_price >= take_profit_1:
                status = "✅ وصلنا للهدف الأول (0.5%)"
            elif current_price <= stop_loss:
                status = "⚠️ تم الوصول لوقف الخسارة (-0.1%)"
                
            # طباعة معلومات الصفقة
            print(f"{symbol}: {price_status} {price_change:.2f}% | شراء: {entry_price:.6f} حالي: {current_price:.6f}")
            print(f"  الكمية: {quantity} | التاريخ: {trade_date.strftime('%Y-%m-%d %H:%M')} ({age_days} يوم)")
            print(f"  الهدف الأول (0.5%): {take_profit_1:.6f}")
            print(f"  الهدف الثاني (1.0%): {take_profit_2:.6f}")
            print(f"  الهدف الثالث (2.0%): {take_profit_3:.6f}")
            print(f"  وقف الخسارة (-0.1%): {stop_loss:.6f}")
            print(f"  الحالة: {status}")
            print(f"  معرف: {order_id}\n")
            
            # إضافة للتقرير
            report += f"{symbol}: {price_status} {price_change:.2f}% | {current_price:.6f}\n"
            report += f"  شراء: {entry_price:.6f} ({age_days} يوم)\n"
            
            if price_change >= 0:
                # تحليل نسب الربح
                if price_change >= 2.0:
                    report += f"  ✅ وصلنا للهدف الثالث (2.0%+)\n"
                elif price_change >= 1.0:
                    report += f"  ✅ وصلنا للهدف الثاني (1.0%+)\n"
                elif price_change >= 0.5:
                    report += f"  ✅ وصلنا للهدف الأول (0.5%+)\n"
                else:
                    report += f"  ⏳ ما زلنا في انتظار الهدف الأول ({price_change:.2f}%)\n"
            else:
                if price_change <= -0.1:
                    report += f"  ⚠️ تجاوزنا وقف الخسارة ({price_change:.2f}%)\n"
                else:
                    report += f"  🟡 اقتراب من وقف الخسارة ({price_change:.2f}%)\n"
            
            report += "\n"
            
        else:
            print(f"{symbol}: ⚠️ لم يتم الحصول على السعر الحالي")
            print(f"  الشراء: {entry_price:.6f} | التاريخ: {trade_date.strftime('%Y-%m-%d %H:%M')}")
            print(f"  معرف: {order_id}\n")
    
    # حفظ التغييرات
    trades_data['open'] = open_trades
    save_trades(trades_data)
    
    # إرسال التقرير عبر التلغرام
    try:
        send_telegram_message(report)
        print("\n✅ تم إرسال تقرير الصفقات إلى تلغرام")
    except Exception as e:
        print(f"\n❌ فشل إرسال التقرير: {e}")

def monitor_trades(interval_seconds=300):
    """مراقبة الصفقات الحقيقية بشكل مستمر"""
    print(f"بدء مراقبة الصفقات الحقيقية (الفاصل الزمني: {interval_seconds} ثانية، اضغط Ctrl+C للخروج)")
    
    try:
        while True:
            apply_trade_strategies()
            print(f"\nانتظار {interval_seconds} ثانية للتحقق التالي...")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nتم إيقاف المراقبة بواسطة المستخدم.")
    finally:
        print("انتهت عملية المراقبة.")

if __name__ == "__main__":
    print("مراقبة الصفقات الحقيقية وتطبيق استراتيجيات الربح...")
    
    # للمراقبة المستمرة، أزل التعليق عن السطر التالي
    # monitor_trades(interval_seconds=300)  # كل 5 دقائق
    
    # أو للتشغيل مرة واحدة:
    apply_trade_strategies()