"""
نسخة كاملة من main.py مع إصلاح مشكلة BOT_STATE
"""
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
import os
import logging
import traceback
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('main')

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
    # استخدام مدير المنصات بدلاً من واجهة MEXC المباشرة
    from app.exchange_manager import get_current_price, get_all_symbols_24h_data, get_klines, get_account_balance
    from app.telegram_notify import generate_daily_report, start_daily_report_timer
    # إضافة وحدة فحص السوق
    from app.market_scanner import scan_market
except Exception as e:
    logger.error(f"❌ خطأ في استيراد الوحدات الأساسية: {e}")
    traceback.print_exc()

# استيراد الدوال من market_scanner مع معالجة الأخطاء
try:
    from app.market_scanner import (
        start_market_scanner, stop_market_scanner, get_trading_opportunities,
        get_watched_symbols, get_symbol_analysis
    )
    logger.info("✅ تم استيراد وحدة market_scanner بنجاح")
except ImportError:
    logger.warning("⚠️ تعذر استيراد بعض دوال market_scanner، استخدام دوال بديلة مؤقتة")
    
    def start_market_scanner(interval=300):
        logger.info(f"تم استدعاء وظيفة بديلة لـ start_market_scanner مع interval={interval}")
        return True
        
    def stop_market_scanner():
        logger.info("تم استدعاء وظيفة بديلة لـ stop_market_scanner")
        return True
        
    def get_trading_opportunities():
        logger.info("تم استدعاء وظيفة بديلة لـ get_trading_opportunities")
        return []
        
    def get_watched_symbols():
        logger.info("تم استدعاء وظيفة بديلة لـ get_watched_symbols")
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "MATICUSDT"]
        
    def get_symbol_analysis(symbol):
        logger.info(f"تم استدعاء وظيفة بديلة لـ get_symbol_analysis مع symbol={symbol}")
        return {"symbol": symbol, "error": "لا تتوفر وظيفة التحليل حاليًا"}

# إضافة وحدة مراقبة السوق المتخصصة
try:
    from app.market_monitor import (
        start_market_monitor, stop_market_monitor, get_latest_opportunities,
        get_best_opportunities, get_opportunity_details, get_market_summary,
        analyze_price_action, MarketOpportunity
    )
    logger.info("✅ تم استيراد وحدة market_monitor بنجاح")
except ImportError:
    logger.warning("⚠️ تعذر استيراد وحدة market_monitor، استخدام دوال بديلة مؤقتة")
    
    def start_market_monitor(interval=300):
        logger.info(f"تم استدعاء وظيفة بديلة لـ start_market_monitor مع interval={interval}")
        return True
        
    def stop_market_monitor():
        logger.info("تم استدعاء وظيفة بديلة لـ stop_market_monitor")
        return True
        
    def get_latest_opportunities():
        logger.info("تم استدعاء وظيفة بديلة لـ get_latest_opportunities")
        return []
        
    def get_best_opportunities():
        logger.info("تم استدعاء وظيفة بديلة لـ get_best_opportunities")
        return []
        
    def get_opportunity_details(symbol):
        logger.info(f"تم استدعاء وظيفة بديلة لـ get_opportunity_details مع symbol={symbol}")
        return {"symbol": symbol, "error": "لا تتوفر وظيفة التحليل حاليًا"}
        
    def get_market_summary():
        logger.info("تم استدعاء وظيفة بديلة لـ get_market_summary")
        return {"status": "غير متاح"}
        
    def analyze_price_action(symbol):
        logger.info(f"تم استدعاء وظيفة بديلة لـ analyze_price_action مع symbol={symbol}")
        return {"symbol": symbol, "error": "لا تتوفر وظيفة التحليل حاليًا"}
        
    class MarketOpportunity:
        def __init__(self, symbol, price, signal):
            self.symbol = symbol
            self.price = price
            self.signal = signal

# تكوين التطبيق
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.secret_key = os.environ.get("SESSION_SECRET", "crypto_trading_bot_secret_key")

# تهيئة مرشحات Jinja المخصصة
try:
    from app.__init__ import init_jinja_filters
    init_jinja_filters(app)
    logger.info("✅ تم تهيئة مرشحات Jinja بنجاح")
except Exception as e:
    logger.error(f"❌ خطأ في تهيئة مرشحات Jinja: {e}")
    traceback.print_exc()

# تشغيل البوت تلقائياً عند بدء التطبيق
from app.trading_bot import start_bot, get_bot_status, check_bot_health, BOT_STATUS
if not BOT_STATUS.get('running', False):
    logger.info("🤖 بدء تشغيل البوت تلقائياً عند بدء التطبيق...")
    start_bot()

# إضافة آلية فحص دوري للتأكد من استمرارية البوت
import threading
import time

def bot_watchdog():
    """آلية حارسة للتأكد من استمرارية البوت وإعادة تشغيله تلقائياً في حالة التوقف"""
    while True:
        try:
            # فحص حالة البوت
            bot_status = get_bot_status()
            if not bot_status.get('running', False):
                logger.warning("🔍 اكتشف نظام المراقبة أن البوت متوقف، سيتم محاولة إعادة تشغيله تلقائياً...")
                check_bot_health()
        except Exception as e:
            logger.error(f"خطأ في نظام مراقبة البوت: {e}")
        
        # انتظار قبل الفحص التالي (كل 5 دقائق)
        time.sleep(300)

# تشغيل حارس البوت في خلفية النظام
watchdog_thread = threading.Thread(target=bot_watchdog, daemon=True)
watchdog_thread.start()
logger.info("🔒 تم تشغيل نظام حماية البوت للتأكد من استمرارية التشغيل")

# متغيرات للتخزين المؤقت
dashboard_cache = {
    'last_update': 0,
    'data': None,
    'cache_time': 60  # تخزين مؤقت لمدة 60 ثانية لتحسين الأداء
}

# تخزين مؤقت لكل صفحة
page_caches = {
    'settings': {'last_update': 0, 'data': None, 'cache_time': 120},
    'trades': {'last_update': 0, 'data': None, 'cache_time': 60},
    'watched_coins': {'last_update': 0, 'data': None, 'cache_time': 60}
}

from functools import wraps

def cache_dashboard_data(func):
    """
    مغلف (decorator) للتخزين المؤقت لبيانات لوحة التحكم
    يقوم بتخزين البيانات مؤقتاً لتقليل الحمل على API
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        current_time = time.time()
        force_refresh = kwargs.get('force_refresh', False)
        
        # إذا كانت البيانات المخزنة مؤقتاً حديثة بما فيه الكفاية وليس هناك طلب تحديث إجباري
        if dashboard_cache['data'] and not force_refresh and current_time - dashboard_cache['last_update'] < dashboard_cache['cache_time']:
            logger.info("استخدام بيانات لوحة التحكم المخزنة مؤقتاً")
            return dashboard_cache['data']
        
        # وإلا، استدعاء الدالة الأصلية والتخزين المؤقت للنتيجة
        # استخدام نسخة من البيانات القديمة في حالة فشل التحديث
        old_data = dashboard_cache['data']
        try:
            # نزيل force_refresh من kwargs إذا وجد
            if 'force_refresh' in kwargs:
                kwargs.pop('force_refresh')
                
            result = func(*args, **kwargs)
            dashboard_cache['data'] = result
            dashboard_cache['last_update'] = current_time
            logger.info("تم تحديث بيانات لوحة التحكم وتخزينها مؤقتاً")
            return result
        except Exception as e:
            logger.error(f"خطأ في تحديث البيانات: {e}")
            # إذا كان هناك بيانات قديمة، نستخدمها بدلاً من إظهار الخطأ
            if old_data:
                logger.info("استخدام البيانات المخزنة سابقاً بسبب خطأ في التحديث")
                return old_data
            # في حالة عدم وجود بيانات سابقة، نرمي الخطأ
            raise
    return wrapper

def cache_page_data(page_name):
    """
    مغلف (decorator) عام للتخزين المؤقت لبيانات أي صفحة
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            force_refresh = kwargs.get('force_refresh', False)
            
            # إذا كانت البيانات المخزنة مؤقتاً حديثة بما فيه الكفاية وليس هناك طلب تحديث إجباري
            if page_caches[page_name]['data'] and not force_refresh and current_time - page_caches[page_name]['last_update'] < page_caches[page_name]['cache_time']:
                logger.info(f"استخدام بيانات صفحة {page_name} المخزنة مؤقتاً")
                return page_caches[page_name]['data']
            
            # وإلا، استدعاء الدالة الأصلية والتخزين المؤقت للنتيجة
            # استخدام نسخة من البيانات القديمة في حالة فشل التحديث
            old_data = page_caches[page_name]['data']
            try:
                # نزيل force_refresh من kwargs إذا وجد
                if 'force_refresh' in kwargs:
                    kwargs.pop('force_refresh')
                    
                result = func(*args, **kwargs)
                page_caches[page_name]['data'] = result
                page_caches[page_name]['last_update'] = current_time
                logger.info(f"تم تحديث بيانات صفحة {page_name} وتخزينها مؤقتاً")
                return result
            except Exception as e:
                logger.error(f"خطأ في تحديث بيانات صفحة {page_name}: {e}")
                # إذا كان هناك بيانات قديمة، نستخدمها بدلاً من إظهار الخطأ
                if old_data:
                    logger.info(f"استخدام البيانات المخزنة سابقاً لصفحة {page_name} بسبب خطأ في التحديث")
                    return old_data
                # في حالة عدم وجود بيانات سابقة، نرمي الخطأ
                raise
        return wrapper
    return decorator

@cache_dashboard_data
def get_dashboard_data():
    """
    الحصول على جميع بيانات لوحة التحكم بطريقة فعالة مع تطبيق التخزين المؤقت
    """
    try:
        # جلب البيانات المطلوبة
        bot_status = get_bot_status()
        trades = get_open_trades()
        capital_status = get_capital_status()
        performance = get_performance_stats()
        available_capital = calculate_available_risk_capital()
        
        # جمع البيانات في قاموس واحد
        data = {
            'bot_status': bot_status,
            'trades': trades,
            'trades_count': len(trades),
            'capital_status': capital_status,
            'performance': performance,
            'available_capital': available_capital,
            'base_currency': BASE_CURRENCY,
            'timestamp': int(time.time())
        }
        return data
    except Exception as e:
        logger.error(f"خطأ في جلب بيانات لوحة التحكم: {e}")
        return {
            'error': str(e),
            'bot_status': {'running': False, 'error': str(e)},
            'trades': [],
            'trades_count': 0,
            'capital_status': {},
            'performance': {},
            'available_capital': 0,
            'base_currency': BASE_CURRENCY,
            'timestamp': int(time.time())
        }

@app.route('/')
def home():
    """الصفحة الرئيسية / لوحة التحكم"""
    try:
        data = get_dashboard_data()
        # تحسين الاستجابة للمستخدم باستخدام البيانات المخزنة مؤقتاً
        # مع إضافة وظيفة تحديث البيانات في الخلفية
        return render_template(
            'index.html',
            title="لوحة التحكم",
            bot_status=data['bot_status'],
            trades=data['trades'][:5],  # عرض أحدث 5 صفقات فقط
            trades_count=data['trades_count'],
            capital_status=data['capital_status'],
            performance=data['performance'],
            available_capital=data['available_capital'],
            base_currency=data['base_currency'],
            timestamp=data['timestamp']
        )
    except Exception as e:
        logger.error(f"خطأ في صفحة الرئيسية: {e}")
        flash(f"حدث خطأ في تحميل البيانات: {str(e)}", "danger")
        return render_template('error.html', error=str(e))

@cache_page_data('trades')
def get_trades_data():
    """
    الحصول على بيانات الصفقات للعرض في صفحة الصفقات
    تم فصلها عن route لتمكين التخزين المؤقت
    """
    try:
        trades = get_open_trades()
        closed_trades = load_json_data('closed_trades.json', default=[])
        
        # تحليل البيانات
        total_profit = calculate_total_profit(closed_trades)
        
        # الحصول على أسعار حالية للصفقات المفتوحة
        for trade in trades:
            symbol = trade.get('symbol')
            if symbol:
                current_price = get_current_price(symbol)
                if current_price:
                    trade['current_price'] = current_price
                    
                    # حساب الربح/الخسارة الحالية
                    entry_price = float(trade.get('entry_price', 0))
                    if entry_price > 0:
                        profit_pct = ((current_price / entry_price) - 1) * 100
                        trade['current_profit_pct'] = profit_pct
                    
        return {
            'open_trades': trades,
            'closed_trades': closed_trades[:50],  # عرض آخر 50 صفقة مغلقة فقط
            'total_profit': total_profit,
            'base_currency': BASE_CURRENCY,
            'timestamp': int(time.time())
        }
    except Exception as e:
        logger.error(f"خطأ في الحصول على بيانات الصفقات: {e}")
        return {
            'error': str(e),
            'open_trades': [],
            'closed_trades': [],
            'total_profit': 0,
            'base_currency': BASE_CURRENCY,
            'timestamp': int(time.time())
        }

@app.route('/trades')
def trades():
    """صفحة الصفقات"""
    try:
        data = get_trades_data()
        return render_template(
            'trades.html',
            title="الصفقات",
            open_trades=data['open_trades'],
            closed_trades=data['closed_trades'],
            total_profit=data['total_profit'],
            base_currency=data['base_currency']
        )
    except Exception as e:
        logger.error(f"خطأ في صفحة الصفقات: {e}")
        flash(f"حدث خطأ في تحميل بيانات الصفقات: {str(e)}", "danger")
        return render_template('error.html', error=str(e))

@app.route('/settings')
def settings():
    """صفحة الإعدادات"""
    try:
        return render_template(
            'settings.html',
            title="الإعدادات",
            max_active_trades=MAX_ACTIVE_TRADES,
            base_currency=BASE_CURRENCY,
            total_risk_capital_ratio=TOTAL_RISK_CAPITAL_RATIO * 100,
            risk_capital_ratio=RISK_CAPITAL_RATIO * 100,
            take_profit=TAKE_PROFIT * 100,
            stop_loss=STOP_LOSS * 100,
            daily_loss_limit=DAILY_LOSS_LIMIT * 100,
            time_stop_loss_hours=TIME_STOP_LOSS_HOURS,
            monitor_interval_seconds=MONITOR_INTERVAL_SECONDS,
            bot_status=get_bot_status()
        )
    except Exception as e:
        logger.error(f"خطأ في صفحة الإعدادات: {e}")
        flash(f"حدث خطأ في تحميل الإعدادات: {str(e)}", "danger")
        return render_template('error.html', error=str(e))

@app.route('/reports')
def reports():
    """صفحة التقارير"""
    try:
        reporting_settings = load_json_data('reporting_settings.json', default={
            'daily_report_enabled': True,
            'daily_report_time': '20:00',
            'recipients': []
        })
        
        return render_template(
            'reports.html',
            title="التقارير",
            reporting_settings=reporting_settings,
            telegram_configured=bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        )
    except Exception as e:
        logger.error(f"خطأ في صفحة التقارير: {e}")
        flash(f"حدث خطأ في تحميل إعدادات التقارير: {str(e)}", "danger")
        return render_template('error.html', error=str(e))

@app.route('/api_settings')
def api_settings():
    """صفحة إعدادات API"""
    try:
        return render_template(
            'api_settings.html',
            title="إعدادات API",
            api_key_configured=bool(API_KEY),
            api_secret_configured=bool(API_SECRET)
        )
    except Exception as e:
        logger.error(f"خطأ في صفحة إعدادات API: {e}")
        flash(f"حدث خطأ في تحميل إعدادات API: {str(e)}", "danger")
        return render_template('error.html', error=str(e))

@app.route('/start')
def start():
    """بدء تشغيل البوت"""
    try:
        logger.info("محاولة تشغيل البوت من واجهة المستخدم")
        # التأكد من استيراد الدالة
        from app.trading_bot import start_bot, get_bot_status, BOT_STATUS
        
        # تسجيل حالة البوت قبل المحاولة
        bot_status_before = get_bot_status().get('running', False)
        logger.info(f"حالة البوت قبل محاولة التشغيل: {bot_status_before}, BOT_STATUS={BOT_STATUS}")
        
        if start_bot():
            # تسجيل حالة البوت بعد المحاولة
            bot_status_after = get_bot_status().get('running', False)
            logger.info(f"تم تشغيل البوت! حالة البوت بعد التشغيل: {bot_status_after}, BOT_STATUS={BOT_STATUS}")
            flash("تم تشغيل البوت بنجاح!", "success")
        else:
            logger.warning("البوت يعمل بالفعل.")
            flash("البوت يعمل بالفعل.", "warning")
        
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")
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
        logger.error(f"خطأ في إيقاف البوت: {e}")
        flash(f"حدث خطأ: {str(e)}", "danger")
    return redirect(url_for('home'))

@app.route('/scan_market')
def scan_market_route():
    """تشغيل فحص يدوي للسوق"""
    try:
        logger.info("بدء فحص يدوي للسوق من واجهة المستخدم")
        result = scan_market()
        opportunities_count = len(result.get('opportunities', []))
        flash(f"تم فحص السوق بنجاح. تم العثور على {opportunities_count} فرصة محتملة.", "success")
    except Exception as e:
        logger.error(f"خطأ في فحص السوق: {e}")
        flash(f"حدث خطأ أثناء فحص السوق: {str(e)}", "danger")
    return redirect(url_for('home'))

@app.route('/watched_coins')
def watched_coins():
    """صفحة العملات المراقبة"""
    try:
        coins = get_watched_symbols()
        symbols_data = {}
        
        for symbol in coins:
            current_price = get_current_price(symbol)
            symbol_data = {
                'symbol': symbol,
                'current_price': current_price,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # محاولة الحصول على مزيد من البيانات إذا كانت متاحة
            try:
                analysis = get_symbol_analysis(symbol)
                symbol_data.update(analysis)
            except Exception as e:
                logger.warning(f"لم نتمكن من الحصول على تحليل للعملة {symbol}: {e}")
                
            symbols_data[symbol] = symbol_data
            
        return render_template(
            'watched_coins.html',
            title="العملات المراقبة",
            symbols=coins,
            symbols_data=symbols_data,
            base_currency=BASE_CURRENCY
        )
    except Exception as e:
        logger.error(f"خطأ في صفحة العملات المراقبة: {e}")
        flash(f"حدث خطأ في تحميل بيانات العملات المراقبة: {str(e)}", "danger")
        return render_template('error.html', error=str(e))

@app.route('/debug')
def debug_info():
    """صفحة معلومات التصحيح"""
    return render_template('debug.html', title="معلومات التصحيح")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)