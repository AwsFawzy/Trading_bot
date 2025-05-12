#!/usr/bin/env python
"""
سكريبت مستقل لتشغيل عملية التنويع الإلزامي للصفقات
يمكن تشغيله كوظيفة cron كل ساعة للتأكد من تطبيق قواعد التنويع
"""

import os
import sys
import time
import logging
import json
import subprocess
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("diversity_runner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def diversify_trades():
    """تنويع الصفقات وإصلاح المشاكل"""
    
    # 1. إنشاء نسخة احتياطية
    try:
        backup_time = int(time.time())
        backup_file = f"active_trades.json.backup.{backup_time}"
        
        with open('active_trades.json', 'r') as f:
            content = f.read()
            
        with open(backup_file, 'w') as f:
            f.write(content)
            
        logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_file}")
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء نسخة احتياطية: {e}")
        return
    
    try:
        # 2. تنفيذ أداة التنويع المتخصصة
        logger.info("▶️ تشغيل برنامج enforce_diversity.py...")
        result = subprocess.run(["python", "enforce_diversity.py"], 
                                capture_output=True, text=True, check=True)
        logger.info(f"✅ تم تنفيذ enforce_diversity.py بنجاح: {result.stdout}")
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ enforce_diversity.py: {e}")
        
    try:
        # 3. تنفيذ برنامج الإصلاح الأقوى
        logger.info("▶️ تشغيل برنامج force_fix.py...")
        result = subprocess.run(["python", "force_fix.py"], 
                                capture_output=True, text=True, check=True)
        logger.info(f"✅ تم تنفيذ force_fix.py بنجاح: {result.stdout}")
        
        # 4. إلغاء قفل الملف
        subprocess.run(["python", "force_fix.py", "unlock"], 
                       capture_output=True, text=True, check=True)
        logger.info("✅ تم إلغاء قفل الملف بنجاح")
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ force_fix.py: {e}")
    
    # 5. التحقق من النتيجة النهائية
    try:
        with open('active_trades.json', 'r') as f:
            trades = json.load(f)
        
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        unique_symbols = set([t.get('symbol') for t in open_trades if t.get('symbol')])
        
        logger.info(f"📊 الإحصائيات النهائية:")
        logger.info(f"   - الصفقات المفتوحة: {len(open_trades)}")
        logger.info(f"   - العملات الفريدة: {len(unique_symbols)}")
        logger.info(f"   - قائمة العملات: {unique_symbols}")
        
        # التحقق من وجود صفقات مكررة
        duplicates = False
        for symbol in unique_symbols:
            symbol_trades = [t for t in open_trades if t.get('symbol') == symbol]
            if len(symbol_trades) > 1:
                duplicates = True
                logger.error(f"⚠️ وجدنا {len(symbol_trades)} صفقة مفتوحة لـ {symbol}!")
                
        if not duplicates:
            logger.info("✅ لا توجد صفقات مكررة - التنويع مطبق بنجاح!")
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من النتيجة النهائية: {e}")
    
if __name__ == "__main__":
    logger.info("===== بدء تنفيذ عملية التنويع الإلزامي =====")
    diversify_trades()
    logger.info("===== انتهاء عملية التنويع الإلزامي =====")