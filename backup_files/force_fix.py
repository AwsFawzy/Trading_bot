#!/usr/bin/env python
"""
أداة الإصلاح الحاسم لمنع الصفقات المكررة
تقوم بإغلاق جميع الصفقات المكررة على العملات
وتعديل ملف active_trades.json
ثم قفل الملف بصلاحيات خاصة لمنع التعديل عليه حتى إعادة تشغيل البوت
"""

import json
import os
import time
import logging
import sys
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_backup(filename='active_trades.json'):
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        backup_name = f"{filename}.backup.{int(time.time())}"
        with open(filename, 'r') as f:
            content = f.read()
        with open(backup_name, 'w') as f:
            f.write(content)
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
        return True
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")
        return False

def force_close_all_duplicates(filename='active_trades.json'):
    """
    فرض إغلاق جميع الصفقات المكررة وإبقاء واحدة فقط لكل عملة
    """
    # إنشاء نسخة احتياطية أولاً
    create_backup(filename)
    
    try:
        # تحميل الصفقات
        with open(filename, 'r') as f:
            trades = json.load(f)
        
        total_trades = len(trades)
        print(f"إجمالي الصفقات: {total_trades}")
        
        # حساب الصفقات المفتوحة
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        print(f"الصفقات المفتوحة: {len(open_trades)}")
        
        # حساب العملات الفريدة
        unique_symbols = list(set([t.get('symbol') for t in open_trades if t.get('symbol')]))
        print(f"العملات الفريدة المفتوحة: {unique_symbols}")
        
        # للتأكد من وجود صفقة واحدة فقط لكل عملة
        for symbol in unique_symbols:
            symbol_trades = [t for t in trades if t.get('symbol') == symbol and t.get('status') == 'OPEN']
            if len(symbol_trades) > 1:
                print(f"⚠️ وجدنا {len(symbol_trades)} صفقة مفتوحة لـ {symbol}. سيتم الاحتفاظ بواحدة فقط.")
                
                # فرز الصفقات حسب وقت الإنشاء للاحتفاظ بأحدثها
                symbol_trades.sort(key=lambda x: int(x.get('id', 0)), reverse=True)
                
                # الاحتفاظ بالصفقة الأحدث فقط وإغلاق البقية
                for i, trade in enumerate(symbol_trades):
                    if i > 0:  # نحتفظ بأول صفقة فقط (الأحدث)
                        # إيجاد الصفقة في القائمة الأصلية وتعديلها
                        for j, t in enumerate(trades):
                            if t.get('id') == trade.get('id'):
                                trades[j]['status'] = 'CLOSED'
                                trades[j]['close_price'] = trade.get('entry_price')
                                trades[j]['close_time'] = int(time.time() * 1000)
                                trades[j]['profit'] = "0.0"
                                trades[j]['profit_percentage'] = "0.0"
                                print(f"✅ تم إغلاق صفقة مكررة لـ {symbol} (معرف: {trade.get('id')})")
        
        # حفظ التغييرات
        with open(filename, 'w') as f:
            json.dump(trades, f, indent=2)
        
        # قفل الملف لمنع التعديل عليه مؤقتًا
        subprocess.run(['chmod', '444', filename], check=True)
        
        open_trades_after = len([t for t in trades if t.get('status') == 'OPEN'])
        print(f"الصفقات المفتوحة بعد الإصلاح: {open_trades_after}")
        
        # طباعة العملات الفريدة بعد الإصلاح
        unique_symbols_after = list(set([t.get('symbol') for t in trades if t.get('status') == 'OPEN' and t.get('symbol')]))
        print(f"العملات الفريدة المفتوحة بعد الإصلاح: {unique_symbols_after}")
        
        print("✅ تم إصلاح الصفقات المكررة بنجاح")
        return True
    
    except Exception as e:
        logger.error(f"خطأ في إصلاح الصفقات المكررة: {e}")
        return False

def unlock_file(filename='active_trades.json'):
    """
    إلغاء قفل الملف لاستئناف العمل العادي
    """
    try:
        subprocess.run(['chmod', '664', filename], check=True)
        print(f"✅ تم إلغاء قفل الملف {filename}")
        return True
    except Exception as e:
        logger.error(f"خطأ في إلغاء قفل الملف: {e}")
        return False

if __name__ == "__main__":
    print("==== أداة الإصلاح الحاسم للصفقات المكررة ====")
    
    if len(sys.argv) > 1 and sys.argv[1] == 'unlock':
        unlock_file()
    else:
        force_close_all_duplicates()