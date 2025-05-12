#!/usr/bin/env python
"""
سكريبت لتنظيف ملف الصفقات وإزالة الصفقات المكررة والوهمية
"""

import json
import os
import sys
import time
from collections import defaultdict

def load_json_data(filename):
    """تحميل بيانات JSON"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"خطأ في قراءة الملف {filename}: {e}")
        return []

def save_json_data(filename, data):
    """حفظ بيانات JSON"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"خطأ في حفظ الملف {filename}: {e}")
        return False

def create_backup(filename):
    """إنشاء نسخة احتياطية من الملف"""
    backup_name = f"{filename}.backup.{int(time.time())}"
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as src:
                content = src.read()
                with open(backup_name, 'w') as dest:
                    dest.write(content)
            print(f"تم إنشاء نسخة احتياطية: {backup_name}")
            return backup_name
        else:
            print(f"الملف {filename} غير موجود")
            return None
    except Exception as e:
        print(f"خطأ في إنشاء نسخة احتياطية: {e}")
        return None

def clean_and_deduplicate(filename='active_trades.json'):
    """تنظيف الصفقات المكررة والمعالجة"""
    # إنشاء نسخة احتياطية أولاً
    backup_file = create_backup(filename)
    if not backup_file:
        print("فشل إنشاء نسخة احتياطية. إلغاء العملية.")
        return False
    
    # تحميل البيانات
    trades = load_json_data(filename)
    if not trades:
        print("لا توجد صفقات للمعالجة")
        return False
    
    print(f"تم تحميل {len(trades)} صفقة من الملف")
    
    # تنظيم الصفقات حسب الرمز والحالة
    trades_by_symbol = defaultdict(list)
    for trade in trades:
        symbol = trade.get('symbol', '')
        status = trade.get('status', '')
        if symbol and status:
            trade_key = f"{symbol}_{status}"
            trades_by_symbol[trade_key].append(trade)
    
    # تتبع الصفقات المكررة للإزالة
    duplicates_found = 0
    cleaned_trades = []
    
    # معالجة كل مجموعة من الصفقات
    for trade_key, symbol_trades in trades_by_symbol.items():
        symbol, status = trade_key.split('_')
        
        if len(symbol_trades) > 1 and status == 'OPEN':
            # ترتيب الصفقات حسب الطابع الزمني (الأحدث أولاً)
            sorted_trades = sorted(symbol_trades, key=lambda x: x.get('timestamp', 0), reverse=True)
            
            # الاحتفاظ بالصفقة الأحدث فقط
            cleaned_trades.append(sorted_trades[0])
            duplicates_found += len(sorted_trades) - 1
            
            print(f"تم العثور على {len(sorted_trades)} صفقة مكررة لـ {symbol}. تم الاحتفاظ بالصفقة الأحدث.")
        else:
            # لا يوجد تكرار، إضافة جميع الصفقات
            cleaned_trades.extend(symbol_trades)
    
    # حفظ النتائج
    if save_json_data(filename, cleaned_trades):
        print(f"تم حفظ {len(cleaned_trades)} صفقة في الملف بعد إزالة {duplicates_found} صفقة مكررة")
        return True
    else:
        print("فشل حفظ الصفقات المنظفة")
        return False

def verify_trade_format(filename='active_trades.json'):
    """التحقق من تنسيق الصفقات وتصحيح المشاكل المعروفة"""
    trades = load_json_data(filename)
    if not trades:
        return False
    
    fixed_count = 0
    for i, trade in enumerate(trades):
        # إضافة معرف إذا لم يكن موجوداً
        if 'id' not in trade and 'timestamp' in trade:
            trades[i]['id'] = str(trade['timestamp'])
            fixed_count += 1
        
        # التأكد من وجود metadata
        if 'metadata' not in trade:
            trades[i]['metadata'] = {'local_source': True}
            fixed_count += 1
    
    if fixed_count > 0:
        print(f"تم تصحيح {fixed_count} مشكلة في تنسيق الصفقات")
        save_json_data(filename, trades)
    
    return True

def add_trade_targets(filename='active_trades.json'):
    """إضافة أهداف للصفقات المفتوحة التي لا تحتوي على أهداف"""
    trades = load_json_data(filename)
    if not trades:
        return False
    
    targets_added = 0
    for i, trade in enumerate(trades):
        if trade.get('status') == 'OPEN' and 'targets' not in trade:
            # إضافة أهداف بسيطة
            entry_price = float(trade.get('entry_price', 0))
            quantity = float(trade.get('quantity', 0))
            
            if entry_price > 0 and quantity > 0:
                # حساب الكميات والأسعار للأهداف الثلاثة
                target1_price = entry_price * 1.005  # هدف ربح 0.5%
                target2_price = entry_price * 1.01   # هدف ربح 1%
                target3_price = entry_price * 1.02   # هدف ربح 2%
                
                target1_quantity = quantity * 0.4  # 40% من الكمية
                target2_quantity = quantity * 0.3  # 30% من الكمية
                target3_quantity = quantity * 0.3  # 30% من الكمية
                
                trades[i]['targets'] = {
                    'target1': {
                        'price': target1_price,
                        'quantity': target1_quantity,
                        'profit_pct': 0.005,
                        'executed': False,
                        'executed_price': None,
                        'executed_time': None
                    },
                    'target2': {
                        'price': target2_price,
                        'quantity': target2_quantity,
                        'profit_pct': 0.01,
                        'executed': False,
                        'executed_price': None,
                        'executed_time': None
                    },
                    'target3': {
                        'price': target3_price,
                        'quantity': target3_quantity,
                        'profit_pct': 0.02,
                        'executed': False,
                        'executed_price': None,
                        'executed_time': None
                    }
                }
                targets_added += 1
    
    if targets_added > 0:
        print(f"تم إضافة أهداف لـ {targets_added} صفقة")
        save_json_data(filename, trades)
    
    return True

if __name__ == "__main__":
    filename = 'active_trades.json'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
    print(f"تنظيف ملف الصفقات: {filename}")
    
    if clean_and_deduplicate(filename):
        verify_trade_format(filename)
        add_trade_targets(filename)
        print("تم تنظيف ملف الصفقات بنجاح")
    else:
        print("فشل تنظيف ملف الصفقات")