"""
نص فحص صحة البوت للتأكد من أنه يعمل بشكل صحيح على منصة الاستضافة الجديدة
"""
import os
import sys
import json
import logging
import requests
from datetime import datetime, timezone

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# تحديد مكان ملفات المشروع
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def check_environment_variables():
    """التحقق من متغيرات البيئة الضرورية"""
    required_vars = ['MEXC_API_KEY', 'MEXC_API_SECRET']
    optional_vars = ['DATABASE_URL', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'SESSION_SECRET']
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"متغيرات البيئة المفقودة: {', '.join(missing_vars)}")
        return False
    
    present_optional = []
    for var in optional_vars:
        if os.environ.get(var):
            present_optional.append(var)
    
    if present_optional:
        logger.info(f"متغيرات البيئة الاختيارية الموجودة: {', '.join(present_optional)}")
    
    logger.info("جميع متغيرات البيئة الضرورية موجودة")
    return True

def check_files_exist():
    """التحقق من وجود الملفات الضرورية"""
    required_files = [
        'main.py',
        'start_render.py',
        'Procfile',
        'render.yaml',
        'dependencies.txt',
        'app/trading_bot.py',
        'app/mexc_api.py',
        'app/config.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = os.path.join(PROJECT_DIR, file_path)
        if not os.path.exists(full_path):
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"الملفات المفقودة: {', '.join(missing_files)}")
        return False
    
    logger.info("جميع الملفات الضرورية موجودة")
    return True

def check_mexc_api():
    """التحقق من الاتصال بـ MEXC API"""
    api_key = os.environ.get('MEXC_API_KEY')
    if not api_key:
        logger.error("مفتاح MEXC API غير موجود")
        return False
    
    try:
        # فحص بسيط للوصول إلى الواجهة العامة لـ MEXC
        response = requests.get('https://api.mexc.com/api/v3/ping', timeout=10)
        if response.status_code == 200:
            logger.info("الاتصال بـ MEXC API ناجح")
            return True
        else:
            logger.error(f"فشل الاتصال بـ MEXC API. كود الحالة: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"خطأ في الاتصال بـ MEXC API: {str(e)}")
        return False

def check_database():
    """التحقق من اتصال قاعدة البيانات"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.warning("رابط قاعدة البيانات غير موجود. سيعمل البوت بدون قاعدة بيانات.")
        return True
    
    try:
        # تحاول استيراد SQLAlchemy للتحقق من الاتصال بقاعدة البيانات
        import sqlalchemy
        from sqlalchemy import create_engine
        
        engine = create_engine(db_url)
        connection = engine.connect()
        connection.close()
        
        logger.info("الاتصال بقاعدة البيانات ناجح")
        return True
    except ImportError:
        logger.warning("لم يتم تثبيت SQLAlchemy. تخطي فحص قاعدة البيانات.")
        return True
    except Exception as e:
        logger.error(f"فشل الاتصال بقاعدة البيانات: {str(e)}")
        return False

def check_active_trades_file():
    """التحقق من ملف الصفقات النشطة"""
    trades_file = os.path.join(PROJECT_DIR, 'active_trades.json')
    
    if not os.path.exists(trades_file):
        # إنشاء ملف فارغ إذا لم يكن موجودًا
        try:
            with open(trades_file, 'w') as f:
                json.dump([], f)
            logger.info("تم إنشاء ملف الصفقات النشطة لأنه لم يكن موجودًا")
            return True
        except Exception as e:
            logger.error(f"فشل إنشاء ملف الصفقات النشطة: {str(e)}")
            return False
    
    try:
        with open(trades_file, 'r') as f:
            trades = json.load(f)
        logger.info(f"تم قراءة ملف الصفقات النشطة بنجاح. عدد الصفقات: {len(trades)}")
        return True
    except Exception as e:
        logger.error(f"فشل قراءة ملف الصفقات النشطة: {str(e)}")
        return False

def run_health_checks():
    """تشغيل جميع فحوصات الصحة"""
    logger.info(f"بدء فحص الصحة في {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    results = {}
    results['environment_variables'] = check_environment_variables()
    results['files_exist'] = check_files_exist()
    results['mexc_api'] = check_mexc_api()
    results['database'] = check_database()
    results['active_trades_file'] = check_active_trades_file()
    
    failed_checks = [name for name, result in results.items() if not result]
    
    if failed_checks:
        logger.error(f"فشلت الفحوصات التالية: {', '.join(failed_checks)}")
        logger.error("المرجو إصلاح المشاكل المذكورة أعلاه قبل تشغيل البوت")
        return False
    else:
        logger.info("اجتاز البوت جميع فحوصات الصحة بنجاح!")
        return True

if __name__ == "__main__":
    success = run_health_checks()
    # إرجاع رمز الخروج المناسب
    sys.exit(0 if success else 1)