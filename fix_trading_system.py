"""
ملف إصلاح لنظام التداول
"""
import json
import time
import logging
import os
import sys

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('fix_trading_system')

# محاولة استيراد الوحدات المطلوبة
try:
    from app.mexc_api import get_balance
    from app.config import BASE_CURRENCY
    from app.telegram_notify import notify_bot_status
    logger.info("✅ تم استيراد الوحدات الأساسية بنجاح")
except ImportError as e:
    logger.error(f"❌ خطأ في استيراد الوحدات: {e}")
    sys.exit(1)

def get_active_symbols():
    """الحصول على العملات المتداولة حالياً"""
    try:
        with open('active_trades.json', 'r') as f:
            data = json.load(f)
            active_trades = data.get('active', [])
            return set(trade.get('symbol') for trade in active_trades if 'symbol' in trade)
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def load_trades():
    """تحميل الصفقات من الملف"""
    try:
        with open('active_trades.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # إنشاء ملف جديد إذا لم يكن موجوداً
        data = {"active": [], "history": []}
        with open('active_trades.json', 'w') as f:
            json.dump(data, f, indent=2)
        return data

def save_trades(data):
    """حفظ الصفقات في الملف"""
    try:
        # إنشاء نسخة احتياطية
        timestamp = int(time.time())
        backup_file = f"active_trades.json.backup.{timestamp}"
        try:
            with open('active_trades.json', 'r') as src:
                with open(backup_file, 'w') as dst:
                    dst.write(src.read())
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_file}")
        except Exception as e:
            logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")
        
        # حفظ البيانات الجديدة
        with open('active_trades.json', 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def reset_trades_database():
    """إعادة تعيين قاعدة بيانات الصفقات"""
    try:
        # إنشاء نسخة احتياطية أولاً
        timestamp = int(time.time())
        backup_file = f"active_trades.json.backup.{timestamp}_RESET"
        try:
            with open('active_trades.json', 'r') as src:
                with open(backup_file, 'w') as dst:
                    dst.write(src.read())
            logger.info(f"تم إنشاء نسخة احتياطية قبل إعادة التعيين: {backup_file}")
        except Exception as e:
            logger.warning(f"تحذير: لم يتم إنشاء نسخة احتياطية قبل إعادة التعيين: {e}")
        
        # إنشاء بنية بيانات جديدة
        new_data = {"active": [], "history": []}
        with open('active_trades.json', 'w') as f:
            json.dump(new_data, f, indent=2)
        logger.info("✅ تم إعادة تعيين قاعدة بيانات الصفقات بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في إعادة تعيين قاعدة بيانات الصفقات: {e}")
        return False

def clean_and_restart_trading():
    """تنظيف قاعدة البيانات وإعادة تشغيل نظام التداول"""
    # التحقق من رصيد USDT
    try:
        usdt_balance = get_balance(BASE_CURRENCY)
        logger.info(f"📊 رصيد USDT الحالي: {usdt_balance}")
        
        if usdt_balance and float(usdt_balance) >= 5.0:
            # إعادة تعيين قاعدة البيانات
            if reset_trades_database():
                # تنظيف أي صفقات وهمية
                clean_result = clean_fake_trades()
                logger.info(f"🧹 نتيجة تنظيف الصفقات الوهمية: {clean_result}")
                
                # فتح 5 صفقات جديدة
                opened = 0
                for i in range(5):
                    result = open_new_trade()
                    if result:
                        opened += 1
                        logger.info(f"✅ تم فتح صفقة جديدة ({opened}/5)")
                    else:
                        logger.warning(f"⚠️ فشل فتح الصفقة رقم {i+1}")
                
                logger.info(f"📈 تم فتح {opened} صفقات جديدة بنجاح")
                
                # إرسال إشعار تلجرام
                notification_message = f"تم إعادة تعيين نظام التداول وفتح {opened} صفقات جديدة. الرصيد الحالي: {usdt_balance} USDT"
                notify_bot_status("info", notification_message)
                
                return True
        else:
            logger.error(f"❌ رصيد USDT غير كافٍ لبدء التداول. الرصيد الحالي: {usdt_balance}")
            return False
    except Exception as e:
        logger.error(f"❌ خطأ أثناء عملية الإصلاح: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔄 بدء عملية إصلاح نظام التداول...")
    result = clean_and_restart_trading()
    logger.info(f"🏁 نتيجة الإصلاح: {'✅ نجاح' if result else '❌ فشل'}")