"""
نسخة مصححة من main.py
"""
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
import os
import logging
import traceback
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('main_fixed')

# استيراد وحدات نظام التداول الأساسية
try:
    from app.trade_executor import get_open_trades, get_performance_stats
    from app.trading_bot import (
        start_bot, stop_bot, get_bot_status, clean_all_fake_trades,
        execute_manual_trade_cycle, sell_all_trades
    )
    from app.trading_system import load_trades, clean_fake_trades
    from app.capital_manager import get_capital_status, calculate_available_risk_capital
    from app.utils import calculate_total_profit, load_json_data, save_json_data, format_timestamp
    from app.config import (
        BASE_CURRENCY, MAX_ACTIVE_TRADES, TOTAL_RISK_CAPITAL_RATIO,
        RISK_CAPITAL_RATIO, TAKE_PROFIT, STOP_LOSS, DAILY_LOSS_LIMIT,
        TIME_STOP_LOSS_HOURS, MONITOR_INTERVAL_SECONDS, API_KEY, API_SECRET,
        TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    )
except Exception as e:
    logger.error(f"❌ خطأ في استيراد الوحدات الأساسية: {e}")
    traceback.print_exc()

# تكوين التطبيق
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = os.environ.get("SESSION_SECRET", "crypto_trading_bot_secret_key")

# تهيئة مرشحات Jinja المخصصة
try:
    from app.__init__ import init_jinja_filters
    init_jinja_filters(app)
except Exception as e:
    logger.error(f"❌ خطأ في تهيئة مرشحات Jinja: {e}")
    traceback.print_exc()

# المسارات الأساسية فقط
@app.route('/')
def home():
    """الصفحة الرئيسية / لوحة التحكم"""
    try:
        bot_status = get_bot_status()
        trades = get_open_trades()
        return render_template(
            'index.html',
            title="لوحة التحكم",
            bot_status=bot_status,
            trades=trades[:5],
            trades_count=len(trades),
            base_currency=BASE_CURRENCY
        )
    except Exception as e:
        logger.error(f"❌ خطأ في صفحة الرئيسية: {e}")
        traceback.print_exc()
        return render_template('error.html', error=str(e))

@app.route('/start')
def start():
    """بدء تشغيل البوت"""
    try:
        logger.info("محاولة تشغيل البوت من واجهة المستخدم")
        # التأكد من استيراد الدالة
        from app.trading_bot import start_bot, get_bot_status
        
        # تسجيل حالة البوت قبل المحاولة
        bot_status_before = get_bot_status().get('running', False)
        
        if start_bot():
            flash("تم تشغيل البوت بنجاح!", "success")
        else:
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
            flash("تم إيقاف البوت بنجاح!", "success")
        else:
            flash("البوت متوقف بالفعل.", "warning")
    except Exception as e:
        logger.error(f"❌ خطأ في إيقاف البوت: {e}")
        flash(f"حدث خطأ: {str(e)}", "danger")
    return redirect(url_for('home'))

@app.route('/debug')
def debug_info():
    """صفحة معلومات التصحيح"""
    return render_template('debug.html', title="معلومات التصحيح")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)