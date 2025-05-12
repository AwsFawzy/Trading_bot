"""
آلية إعادة تشغيل تلقائية للبوت في حالة توقفه
تستخدم مع Cron job لضمان استمرارية التشغيل
"""
import os
import sys
import time
import logging
import requests
import subprocess
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('auto_restart')

# عنوان URL للتحقق من حالة البوت
BOT_URL = "http://localhost:5000/api/status"

def is_bot_running():
    """التحقق مما إذا كان البوت قيد التشغيل"""
    try:
        response = requests.get(BOT_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("running", False)
        return False
    except Exception as e:
        logger.error(f"خطأ في التحقق من حالة البوت: {e}")
        return False

def restart_bot():
    """إعادة تشغيل البوت"""
    try:
        logger.info("محاولة إعادة تشغيل البوت...")
        
        # إيقاف البوت الحالي إذا كان قيد التشغيل
        try:
            requests.get("http://localhost:5000/api/bot/stop", timeout=5)
            logger.info("تم إيقاف البوت الحالي")
            time.sleep(2)  # انتظار لإتمام عملية الإيقاف
        except:
            logger.info("لم يتم العثور على بوت قيد التشغيل")
        
        # بدء تشغيل البوت
        start_command = ["python", "start_bot_only.py"]
        subprocess.Popen(start_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        logger.info("تم إرسال أمر إعادة تشغيل البوت")
        return True
    except Exception as e:
        logger.error(f"خطأ في إعادة تشغيل البوت: {e}")
        return False

def check_and_restart():
    """التحقق من البوت وإعادة تشغيله إذا لزم الأمر"""
    logger.info("التحقق من حالة البوت...")
    
    if not is_bot_running():
        logger.warning("البوت غير قيد التشغيل! محاولة إعادة التشغيل...")
        if restart_bot():
            logger.info("تمت إعادة تشغيل البوت بنجاح")
        else:
            logger.error("فشل في إعادة تشغيل البوت")
    else:
        logger.info("البوت يعمل بشكل صحيح")

if __name__ == "__main__":
    logger.info("تشغيل آلية إعادة التشغيل التلقائية")
    check_and_restart()