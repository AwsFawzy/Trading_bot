"""
نسخة تدريجية من ملف main.py للتحقق من المشكلة
"""
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
import os
import logging
import traceback
from datetime import datetime

# إضافة مستوى سجل التصحيح
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# استيراد وحدات نظام التداول الجديد
try:
    from app.trading_bot import (
        start_bot, stop_bot, get_bot_status, clean_all_fake_trades,
        execute_manual_trade_cycle, sell_all_trades
    )
    logger.info("✅ تم استيراد app.trading_bot بنجاح")
except Exception as e:
    logger.error(f"❌ خطأ في استيراد app.trading_bot: {e}")
    traceback.print_exc()

try:
    from app.trading_system import load_trades, clean_fake_trades
    logger.info("✅ تم استيراد app.trading_system بنجاح")
except Exception as e:
    logger.error(f"❌ خطأ في استيراد app.trading_system: {e}")
    traceback.print_exc()

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = os.environ.get("SESSION_SECRET", "crypto_trading_bot_secret_key")

@app.route('/')
def home():
    return render_template('home_debug.html', title="تصحيح الأخطاء")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)