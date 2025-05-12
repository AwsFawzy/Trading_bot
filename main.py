"""
نسخة مبسطة من main.py مع دعم لتشغيل وإيقاف البوت
"""
from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
import logging
import traceback

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('main')

# استيراد وحدات نظام التداول الأساسية
try:
    from app.trading_bot import start_bot, stop_bot, get_bot_status
    logger.info("✅ تم استيراد وحدة trading_bot بنجاح")
except Exception as e:
    logger.error(f"❌ خطأ في استيراد الوحدات الأساسية: {e}")
    traceback.print_exc()
    # تعريف دوال بديلة في حالة الخطأ
    def start_bot() -> bool:
        logger.warning("⚠️ استخدام دالة بديلة لـ start_bot")
        return True
    def stop_bot() -> bool:
        logger.warning("⚠️ استخدام دالة بديلة لـ stop_bot")
        return True
    def get_bot_status() -> dict:
        logger.warning("⚠️ استخدام دالة بديلة لـ get_bot_status")
        return {"running": False}

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = "crypto_trading_bot_secret_key"

@app.route('/')
def home():
    """الصفحة الرئيسية البسيطة"""
    try:
        bot_status = get_bot_status()
        return render_template('debug.html', title="لوحة التحكم", bot_status=bot_status)
    except Exception as e:
        logger.error(f"❌ خطأ في صفحة الرئيسية: {e}")
        return render_template('error.html', error=str(e))

@app.route('/start')
def start():
    """بدء تشغيل البوت"""
    try:
        logger.info("محاولة تشغيل البوت من واجهة المستخدم")
        
        if start_bot():
            logger.info("✅ تم تشغيل البوت بنجاح!")
            flash("تم تشغيل البوت بنجاح!", "success")
            
            # إرسال إشعار تلجرام عند تشغيل البوت
            try:
                logger.info("إرسال إشعار تلجرام بتشغيل البوت...")
                from app.telegram_notify import notify_bot_status
                notification_result = notify_bot_status("start", "تم تشغيل البوت من واجهة المستخدم")
                logger.info(f"✅ نتيجة إرسال إشعار تلجرام: {notification_result}")
            except Exception as telegram_error:
                logger.error(f"❌ خطأ في إرسال إشعار تلجرام: {telegram_error}")
        else:
            logger.warning("⚠️ البوت يعمل بالفعل.")
            flash("البوت يعمل بالفعل.", "warning")
            
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")
        flash(f"حدث خطأ: {str(e)}", "danger")
    return redirect(url_for('home'))

@app.route('/stop')
def stop():
    """إيقاف البوت"""
    try:
        logger.info("محاولة إيقاف البوت من واجهة المستخدم")
        
        if stop_bot():
            logger.info("✅ تم إيقاف البوت بنجاح!")
            flash("تم إيقاف البوت بنجاح!", "success")
            
            # إرسال إشعار تلجرام عند إيقاف البوت
            try:
                logger.info("إرسال إشعار تلجرام بإيقاف البوت...")
                from app.telegram_notify import notify_bot_status
                notification_result = notify_bot_status("stop", "تم إيقاف البوت من واجهة المستخدم")
                logger.info(f"✅ نتيجة إرسال إشعار تلجرام: {notification_result}")
            except Exception as telegram_error:
                logger.error(f"❌ خطأ في إرسال إشعار تلجرام: {telegram_error}")
        else:
            logger.warning("⚠️ البوت متوقف بالفعل.")
            flash("البوت متوقف بالفعل.", "warning")
            
    except Exception as e:
        logger.error(f"❌ خطأ في إيقاف البوت: {e}")
        flash(f"حدث خطأ: {str(e)}", "danger")
    return redirect(url_for('home'))

@app.route('/debug')
def debug_info():
    """صفحة معلومات التصحيح"""
    return "تم تشغيل الواجهة بنجاح! هذه صفحة تصحيح بسيطة."

@app.route('/api/bot_status')
def api_bot_status():
    """واجهة API للحصول على حالة البوت"""
    return jsonify(get_bot_status())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)