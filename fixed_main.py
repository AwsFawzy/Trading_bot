"""
نسخة مبسطة من ملف main.py للتحقق من المشكلة
"""
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
import os
import logging
import traceback
from datetime import datetime

# إضافة مستوى سجل التصحيح
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = os.environ.get("SESSION_SECRET", "crypto_trading_bot_secret_key")

@app.route('/')
def home():
    return render_template('index.html', title="لوحة التحكم")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)