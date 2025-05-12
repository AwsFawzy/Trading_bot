"""
وحدة التداول الديناميكي للتكيف مع ظروف السوق وتحقيق أقصى ربح ممكن
تقوم بتحسين استراتيجيات الدخول والخروج بشكل مستمر
"""
import logging
import time
import threading
from typing import Dict, Any, List
from datetime import datetime

from app.mexc_api import get_current_price, get_market_trends, get_klines
from app.ai_model import predict_trend, analyze_market_sentiment
from app.utils import load_json_data, save_json_data
from app.trade_executor import get_open_trades, close_trade
from app.auto_trader import trade_settings, start_auto_trader, stop_auto_trader

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('dynamic_trading')

# المتغيرات العالمية
dynamic_trader_running = False
dynamic_trader_thread = None
last_settings_update = 0
market_conditions = 'normal'  # normal, bullish, bearish, volatile

# فترة تحديث الإعدادات (بالثواني)
SETTINGS_UPDATE_INTERVAL = 900  # 15 دقيقة

# قائمة مؤقتة للعملات ذات الأداء الجيد
performing_coins = set()
blacklisted_coins = set()

def analyze_market_conditions() -> str:
    """
    تحليل ظروف السوق الحالية وتحديد الحالة العامة
    
    :return: حالة السوق (normal, bullish, bearish, volatile)
    """
    try:
        # الحصول على اتجاهات السوق من API
        market_trends = get_market_trends()
        
        # استخراج البيانات المهمة
        up_percent = market_trends.get('up_percent', 0)
        down_percent = market_trends.get('down_percent', 0)
        total_volume = market_trends.get('total_volume', 0)
        volatility = market_trends.get('average_volatility', 0)
        
        # تحليل بيتكوين كمؤشر رئيسي للسوق
        btc_analysis = analyze_btc_trend()
        
        # تحديد حالة السوق بناءً على المعايير المختلفة
        if up_percent > 65 and btc_analysis == 'up':
            return 'bullish'  # سوق صاعد
        elif down_percent > 65 and btc_analysis == 'down':
            return 'bearish'  # سوق هابط
        elif volatility > 5:
            return 'volatile'  # سوق متقلب
        else:
            return 'normal'  # سوق عادي
    except Exception as e:
        logger.error(f"خطأ في تحليل ظروف السوق: {e}")
        return 'normal'


def analyze_btc_trend() -> str:
    """
    تحليل اتجاه البيتكوين كمؤشر للسوق
    
    :return: اتجاه البيتكوين (up, down, neutral)
    """
    try:
        # الحصول على بيانات الشموع للبيتكوين
        btc_klines_1h = get_klines('BTCUSDT', interval='60m', limit=24)
        
        if not btc_klines_1h:
            return 'neutral'
        
        # تحليل الاتجاه
        trend = predict_trend(btc_klines_1h)
        
        return trend
    except Exception as e:
        logger.error(f"خطأ في تحليل اتجاه البيتكوين: {e}")
        return 'neutral'


def identify_performing_coins() -> None:
    """
    تحديد العملات ذات الأداء الجيد للتركيز عليها
    """
    global performing_coins
    
    try:
        # الحصول على الصفقات المغلقة
        trades = load_json_data('active_trades.json', [])
        closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
        
        # تحليل الصفقات المغلقة للعثور على العملات ذات الأداء الجيد
        performance_data = {}
        
        for trade in closed_trades:
            symbol = trade.get('symbol')
            profit_pct = trade.get('profit_pct', 0)
            
            if symbol not in performance_data:
                performance_data[symbol] = {
                    'count': 0,
                    'total_profit': 0,
                    'wins': 0,
                    'losses': 0
                }
            
            performance_data[symbol]['count'] += 1
            performance_data[symbol]['total_profit'] += profit_pct
            
            if profit_pct > 0:
                performance_data[symbol]['wins'] += 1
            else:
                performance_data[symbol]['losses'] += 1
        
        # حساب معدل النجاح ومتوسط الربح
        for symbol, data in performance_data.items():
            if data['count'] > 0:
                data['win_rate'] = data['wins'] / data['count']
                data['avg_profit'] = data['total_profit'] / data['count']
            else:
                data['win_rate'] = 0
                data['avg_profit'] = 0
        
        # تحديد العملات ذات الأداء الجيد (معدل نجاح > 60% ومتوسط ربح إيجابي)
        performing_coins = set()
        blacklisted_coins = set()
        
        for symbol, data in performance_data.items():
            if data['count'] >= 3:  # على الأقل 3 صفقات للحصول على بيانات كافية
                if data['win_rate'] >= 0.6 and data['avg_profit'] > 0:
                    performing_coins.add(symbol)
                elif data['win_rate'] < 0.3 or (data['avg_profit'] < 0 and data['count'] >= 5):
                    blacklisted_coins.add(symbol)
        
        logger.info(f"تم تحديد {len(performing_coins)} عملة ذات أداء جيد و {len(blacklisted_coins)} عملة ذات أداء سيء")
    except Exception as e:
        logger.error(f"خطأ في تحديد العملات ذات الأداء الجيد: {e}")


def update_trading_settings() -> None:
    """
    تحديث إعدادات التداول بناءً على ظروف السوق
    """
    global market_conditions, last_settings_update
    
    try:
        current_time = time.time()
        
        # تحديث الإعدادات كل فترة محددة فقط
        if current_time - last_settings_update < SETTINGS_UPDATE_INTERVAL:
            return
        
        # تحديث تاريخ آخر تحديث
        last_settings_update = current_time
        
        # تحليل ظروف السوق
        market_conditions = analyze_market_conditions()
        
        # تحديد العملات ذات الأداء الجيد
        identify_performing_coins()
        
        # تحديث إعدادات التداول بناءً على ظروف السوق
        if market_conditions == 'bullish':
            # في السوق الصاعد، زيادة العدوانية في الدخول وتقليل العدوانية في الخروج
            trade_settings.update({
                'min_confidence': 0.6,            # خفض مستوى الثقة للدخول
                'min_profit': 0.5,                # خفض الحد الأدنى للربح المتوقع
                'waiting_period': 20,             # تقليل فترة الانتظار بين الصفقات
                'max_active_trades': 12,          # زيادة عدد الصفقات المفتوحة
                'quick_scan_interval': 5,         # مسح سريع كل 5 ثواني
                'scan_interval': 30               # مسح شامل كل 30 ثانية
            })
            logger.info("تم تحديث الإعدادات للسوق الصاعد - زيادة العدوانية في الدخول")
        elif market_conditions == 'bearish':
            # في السوق الهابط، زيادة الحذر في الدخول وزيادة العدوانية في الخروج
            trade_settings.update({
                'min_confidence': 0.75,           # زيادة مستوى الثقة للدخول
                'min_profit': 1.0,                # زيادة الحد الأدنى للربح المتوقع
                'waiting_period': 60,             # زيادة فترة الانتظار بين الصفقات
                'max_active_trades': 5,           # تقليل عدد الصفقات المفتوحة
                'quick_scan_interval': 15,        # إبطاء المسح السريع
                'scan_interval': 120              # إبطاء المسح الشامل
            })
            logger.info("تم تحديث الإعدادات للسوق الهابط - زيادة الحذر")
        elif market_conditions == 'volatile':
            # في السوق المتقلب، زيادة الحذر والتركيز على الفرص قصيرة الأجل
            trade_settings.update({
                'min_confidence': 0.7,            # مستوى ثقة متوسط
                'min_profit': 0.7,                # ربح متوقع معتدل
                'waiting_period': 45,             # فترة انتظار معتدلة
                'max_active_trades': 7,           # عدد صفقات معتدل
                'quick_profit_mode': True,        # تفعيل وضع الربح السريع
                'trailing_percentage': 0.5        # تتبع أكثر حساسية (0.5% بدلاً من 1%)
            })
            logger.info("تم تحديث الإعدادات للسوق المتقلب - زيادة الحذر مع التركيز على الفرص قصيرة الأجل")
        else:  # normal
            # في السوق العادي، إعدادات متوازنة
            trade_settings.update({
                'min_confidence': 0.65,           # مستوى ثقة متوازن
                'min_profit': 0.8,                # ربح متوقع متوازن
                'waiting_period': 30,             # فترة انتظار متوازنة
                'max_active_trades': 10,          # عدد صفقات متوازن
                'quick_scan_interval': 10,        # مسح سريع كل 10 ثواني
                'scan_interval': 60               # مسح شامل كل دقيقة
            })
            logger.info("تم تحديث الإعدادات للسوق العادي - إعدادات متوازنة")
        
        # تحديث قائمة العملات ذات الأولوية لتشمل العملات ذات الأداء الجيد
        priority_list = list(trade_settings['priority_symbols'])
        
        # إضافة العملات ذات الأداء الجيد
        for coin in performing_coins:
            if coin not in priority_list:
                priority_list.append(coin)
        
        # تحديث قائمة الأولوية
        trade_settings['priority_symbols'] = priority_list
        
        # تحديث القائمة السوداء
        trade_settings['blacklisted_symbols'] = list(blacklisted_coins)
        
        # تسجيل الإعدادات الجديدة
        logger.info(f"تم تحديث إعدادات التداول: حالة السوق = {market_conditions}")
        logger.info(f"عملات ذات أولوية: {len(priority_list)}, عملات محظورة: {len(blacklisted_coins)}")
    except Exception as e:
        logger.error(f"خطأ في تحديث إعدادات التداول: {e}")


def dynamic_trading_loop() -> None:
    """
    الحلقة الرئيسية للتداول الديناميكي
    """
    global dynamic_trader_running
    
    while dynamic_trader_running:
        try:
            # تحديث إعدادات التداول بناءً على ظروف السوق
            update_trading_settings()
            
            # انتظار قبل التحديث التالي
            time.sleep(60)  # فحص كل دقيقة
        except Exception as e:
            logger.error(f"خطأ في حلقة التداول الديناميكي: {e}")
            time.sleep(300)  # انتظار 5 دقائق في حالة الخطأ


def start_dynamic_trading() -> bool:
    """
    بدء التداول الديناميكي
    
    :return: True إذا تم البدء بنجاح
    """
    global dynamic_trader_running, dynamic_trader_thread
    
    if dynamic_trader_running:
        logger.warning("التداول الديناميكي قيد التشغيل بالفعل")
        return False
    
    # تحليل أولي لظروف السوق
    market_conditions = analyze_market_conditions()
    logger.info(f"بدء التداول الديناميكي - حالة السوق الحالية: {market_conditions}")
    
    # بدء التداول الآلي إذا لم يكن قيد التشغيل
    if not start_auto_trader():
        logger.error("فشل في بدء التداول الآلي")
        return False
    
    # بدء التداول الديناميكي
    dynamic_trader_running = True
    dynamic_trader_thread = threading.Thread(target=dynamic_trading_loop, daemon=True)
    dynamic_trader_thread.start()
    
    logger.info("تم بدء التداول الديناميكي")
    return True


def stop_dynamic_trading() -> bool:
    """
    إيقاف التداول الديناميكي
    
    :return: True إذا تم الإيقاف بنجاح
    """
    global dynamic_trader_running, dynamic_trader_thread
    
    if not dynamic_trader_running:
        logger.warning("التداول الديناميكي متوقف بالفعل")
        return False
    
    # إيقاف التداول الديناميكي
    dynamic_trader_running = False
    
    # انتظار إنهاء الخيط
    if dynamic_trader_thread:
        dynamic_trader_thread.join(timeout=1.0)
    
    # إيقاف التداول الآلي
    stop_auto_trader()
    
    logger.info("تم إيقاف التداول الديناميكي")
    return True


def get_market_insights() -> Dict[str, Any]:
    """
    الحصول على رؤى ومعلومات عن السوق
    
    :return: معلومات وإحصائيات عن السوق
    """
    try:
        return {
            'market_condition': market_conditions,
            'last_settings_update': datetime.fromtimestamp(last_settings_update).strftime('%Y-%m-%d %H:%M:%S') if last_settings_update > 0 else None,
            'performing_coins': list(performing_coins),
            'blacklisted_coins': list(blacklisted_coins),
            'trade_settings': trade_settings
        }
    except Exception as e:
        logger.error(f"خطأ في الحصول على رؤى السوق: {e}")
        return {
            'error': str(e)
        }