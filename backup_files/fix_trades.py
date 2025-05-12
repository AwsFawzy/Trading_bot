#!/usr/bin/env python3
"""
سكريبت لتصحيح ملف الصفقات وإزالة الصفقات المكررة
"""
import json
import os
import time
from datetime import datetime

def create_backup(filename='active_trades.json'):
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    if os.path.exists(filename):
        timestamp = int(time.time())
        backup_file = f"{filename}.backup.{timestamp}"
        with open(filename, 'r') as src, open(backup_file, 'w') as dst:
            dst.write(src.read())
        print(f"تم إنشاء نسخة احتياطية: {backup_file}")
        return True
    return False

def fix_duplicate_trades(filename='active_trades.json'):
    """معالجة مشكلة الصفقات المكررة بالإبقاء على صفقة واحدة لكل عملة"""
    # إنشاء نسخة احتياطية أولاً
    create_backup(filename)
    
    try:
        # تحميل الصفقات
        with open(filename, 'r') as f:
            trades = json.load(f)
        
        print(f"عدد الصفقات قبل الإصلاح: {len(trades)}")
        print(f"عدد الصفقات المفتوحة قبل الإصلاح: {len([t for t in trades if t.get('status') == 'OPEN'])}")
        
        # استخراج الصفقات المفتوحة والمغلقة
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        closed_trades = [t for t in trades if t.get('status') != 'OPEN']
        
        # حساب العملات الفريدة
        symbols = set([t.get('symbol') for t in open_trades])
        print(f"العملات الفريدة المفتوحة: {symbols}")
        
        # الاحتفاظ بأحدث صفقة فقط لكل عملة
        kept_trades = []
        for symbol in symbols:
            # العثور على أحدث صفقة لكل عملة
            symbol_trades = [t for t in open_trades if t.get('symbol') == symbol]
            symbol_trades.sort(key=lambda x: int(x.get('timestamp', 0)), reverse=True)
            
            # الاحتفاظ بأحدث صفقة فقط وإغلاق البقية
            kept_trades.append(symbol_trades[0])
            
            # إغلاق بقية الصفقات لهذه العملة
            for t in symbol_trades[1:]:
                t['status'] = 'CLOSED_MANUALLY'
                t['close_reason'] = 'إغلاق تلقائي لإصلاح تكرار الصفقات'
                t['close_timestamp'] = int(time.time() * 1000)
                closed_trades.append(t)
        
        # تجميع الصفقات المحفوظة والمغلقة
        fixed_trades = kept_trades + closed_trades
        
        print(f"عدد الصفقات بعد الإصلاح: {len(fixed_trades)}")
        print(f"عدد الصفقات المفتوحة بعد الإصلاح: {len([t for t in fixed_trades if t.get('status') == 'OPEN'])}")
        
        # حفظ الصفقات المصححة
        with open(filename, 'w') as f:
            json.dump(fixed_trades, f, indent=2)
        
        print("تم إصلاح ملف الصفقات بنجاح")
        return True
    except Exception as e:
        print(f"حدث خطأ أثناء إصلاح الصفقات: {e}")
        return False

if __name__ == "__main__":
    fix_duplicate_trades()