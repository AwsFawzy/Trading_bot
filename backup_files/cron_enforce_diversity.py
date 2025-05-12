"""
برنامج لتنفيذه كمهمة cron كل ساعة
يقوم بفرض التنويع على الصفقات المفتوحة
"""

import os
import json
import time
import logging
import subprocess
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_diversity_check():
    """تشغيل برنامج التحقق من التنويع"""
    try:
        if os.path.exists('run_before_trade.py'):
            result = subprocess.run(['python', 'run_before_trade.py'], 
                                   capture_output=True, text=True, check=True)
            logger.info(f"نتيجة التحقق من التنويع: {result.stdout}")
            return True
        else:
            logger.warning("ملف run_before_trade.py غير موجود. محاولة استخدام البديل...")
            if os.path.exists('diversify_trades.py'):
                result = subprocess.run(['python', 'diversify_trades.py'], 
                                       capture_output=True, text=True, check=True)
                logger.info(f"نتيجة التحقق من التنويع البديل: {result.stdout}")
                return True
            else:
                logger.error("لم يتم العثور على برامج التنويع")
                return False
    except Exception as e:
        logger.error(f"خطأ في تشغيل فحص التنويع: {e}")
        return False

if __name__ == "__main__":
    # سجل التنفيذ
    log_path = "diversity_check.log"
    with open(log_path, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] بدأ تنفيذ فحص التنويع\n")
    
    # تنفيذ التحقق
    success = run_diversity_check()
    
    # تسجيل النتيجة
    with open(log_path, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] اكتمل التنفيذ بنجاح: {success}\n")
    
    sys.exit(0 if success else 1)