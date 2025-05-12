"""
وحدة التداول الآلي التي تحدد الفرص وتدخل بشكل تلقائي
تعتمد على تحليل متخصص من مراقب السوق وتنفذ الصفقات بناءً على معايير محددة
"""
import logging
import threading
import time
from typing import List, Dict, Any
from datetime import datetime

from app.market_monitor import get_best_opportunities, analyze_price_action
from app.trade_executor import get_open_trades, close_trade
from app.capital_manager import get_position_size, is_within_daily_loss_limit, calculate_per_trade_capital
from app.mexc_api import get_current_price, get_account_balance
from app.utils import load_json_data, save_json_data, get_timestamp_str
from app.config import MAX_ACTIVE_TRADES, TAKE_PROFIT, STOP_LOSS
from app.candlestick_patterns import detect_candlestick_patterns, get_entry_signal
from app.telegram_notify import send_telegram_message
from app.trade_diversifier import get_trade_diversity_metrics
from app.symbol_enforcer_hook import is_trade_allowed, enforce_diversity
# استبدال دالة can_trade_coin القديمة بأكثر تطوراً

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('auto_trader')

# متغيرات عالمية
auto_trader_running = False
auto_trader_thread = None
trade_settings = {
    'min_confidence': 0.65,           # خفض الحد الأدنى لدرجة الثقة لاقتناص المزيد من الفرص
    'min_profit': 0.5,                # خفض الحد الأدنى للربح المحتمل (0.5% بدلاً من 1%)
    'max_active_trades': 10,          # زيادة الحد الأقصى للصفقات المفتوحة
    'priority_symbols': [             # العملات ذات الأولوية الموسعة
        'DOGEUSDT',                   # دوجكوين - أولوية قصوى
        'BTCUSDT',                    # بيتكوين
        'ETHUSDT',                    # إيثريوم
        'SHIBUSDT',                   # شيبا إينو
        'SOLUSDT',                    # سولانا
        'XRPUSDT',                    # ريبل
        'TRXUSDT',                    # ترون
        'MATICUSDT',                  # بوليجون
        'LTCUSDT',                    # لايتكوين
        'ADAUSDT'                     # كاردانو
    ],
    'blacklisted_symbols': [],        # العملات المحظورة
    'waiting_period': 30,             # تقليل فترة الانتظار بين الصفقات (30 ثانية بدلاً من دقيقة)
    'auto_approve': True,             # الموافقة التلقائية على الصفقات
    'use_market_orders': True,        # استخدام أوامر السوق للتنفيذ الفوري
    'confirm_patterns': True,         # تأكيد أنماط الشموع قبل الدخول
    'min_volume': 500000,             # خفض الحد الأدنى لحجم التداول لاقتناص المزيد من الفرص
    'max_continuous_operation': True, # تشغيل مستمر بدون توقف
    'reinvest_profits': True,         # إعادة استثمار الأرباح تلقائياً
    'rapid_scanning': True,           # تفعيل المسح السريع للسوق
    'scan_interval': 60,              # فترة المسح الشامل (60 ثانية)
    'quick_scan_interval': 10,        # فترة المسح السريع (10 ثواني للعملات ذات الأولوية)
    'dynamic_tp_sl': True,            # استخدام أهداف ربح ووقف خسارة ديناميكية
    'quick_profit_mode': True         # وضع الربح السريع (خروج جزئي عند تحقق ربح صغير)
}

# تاريخ آخر صفقة
last_trade_timestamp = 0

def can_open_new_trade(symbol: str) -> bool:
    """
    التحقق مما إذا كان يمكن فتح صفقة جديدة مع تطبيق استراتيجية التنويع المحسنة
    تستخدم نظام trade_diversifier.py الجديد والأكثر صرامة
    
    :param symbol: رمز العملة
    :return: True إذا كان يمكن فتح صفقة جديدة
    """
    global last_trade_timestamp
    
    try:
        # التحقق من وقت آخر صفقة
        current_time = time.time()
        time_since_last_trade = current_time - last_trade_timestamp
        
        if time_since_last_trade < trade_settings['waiting_period']:
            logger.info(f"تجاهل الصفقة لـ {symbol} - لم تمض فترة الانتظار المطلوبة ({time_since_last_trade:.0f}s من أصل {trade_settings['waiting_period']}s)")
            return False
        
        # التحقق مما إذا كانت العملة محظورة
        if symbol in trade_settings['blacklisted_symbols']:
            logger.info(f"تجاهل الصفقة لـ {symbol} - موجودة في القائمة السوداء")
            return False
        
        # الحصول على الصفقات المفتوحة
        open_trades = get_open_trades()
        
        # التحقق من عدد الصفقات المفتوحة
        if len(open_trades) >= trade_settings['max_active_trades']:
            logger.info(f"تجاهل الصفقة لـ {symbol} - وصلنا للحد الأقصى من الصفقات المفتوحة ({len(open_trades)}/{trade_settings['max_active_trades']})")
            return False
        
        # ===== استخدام نظام التنويع الجديد المحسن =====
        # التحقق من قواعد التنويع باستخدام trade_diversifier
        allowed, reason = is_trade_allowed(symbol)
        if not allowed:
            logger.warning(f"تجاهل الصفقة لـ {symbol} - {reason}")
            return False
            
        # فحص إضافي للتأكيد
        diversity_metrics = get_trade_diversity_metrics()
        logger.info(f"حالة التنويع الحالية: {diversity_metrics}")
        
        # ستظهر الإحصائيات كل مرة للتأكد من التطبيق الصحيح
        if symbol in diversity_metrics['coins_distribution']:
            logger.error(f"⛔ منع الصفقة بشكل إلزامي! - {symbol} متداولة بالفعل. التنويع مطلوب!")
            return False
        
        # التحقق من حد الخسارة اليومي
        if not is_within_daily_loss_limit():
            logger.info(f"تجاهل الصفقة لـ {symbol} - تم الوصول إلى حد الخسارة اليومي")
            return False
        
        # التحقق من رصيد الحساب
        usdt_balance = get_account_balance().get('USDT', 0)
        per_trade_capital = calculate_per_trade_capital()
        
        if usdt_balance < per_trade_capital:
            logger.info(f"تجاهل الصفقة لـ {symbol} - رصيد USDT غير كافٍ (المتاح: {usdt_balance}, المطلوب: {per_trade_capital})")
            return False
        
        logger.info(f"✅ السماح بفتح صفقة جديدة لـ {symbol} - متوافقة مع قواعد التنويع!")
        return True
    except Exception as e:
        logger.error(f"خطأ في التحقق من إمكانية فتح صفقة جديدة: {e}")
        return False


def should_enter_trade(opportunity: Dict[str, Any]) -> bool:
    """
    التحقق مما إذا كان يجب الدخول في صفقة استناداً إلى الفرصة المقدمة
    
    :param opportunity: فرصة التداول
    :return: True إذا كان يجب الدخول في الصفقة
    """
    try:
        symbol = opportunity.get('symbol')
        confidence = opportunity.get('confidence', 0)
        potential_profit = opportunity.get('potential_profit', 0)
        
        # تطبيق التنويع أولاً ثم فحص ما إذا كان مسموحًا بفتح صفقة
        enforce_diversity()
        
        # منع XRPUSDT نهائياً
        if symbol and symbol.upper() == 'XRPUSDT':
            logger.warning(f"تجاهل الصفقة لـ XRPUSDT - عملة محظورة نهائياً")
            return False
        
        # فحص ما إذا كان مسموحًا بفتح صفقة جديدة وفقًا لقواعد التنويع
        allowed = is_trade_allowed(symbol)
        if not allowed:
            logger.warning(f"تجاهل الصفقة لـ {symbol} - تعارض مع قواعد التنويع")
            return False
            
        # التحقق من عدد الصفقات المفتوحة لهذه العملة - التأكد مرة ثانية
        from app.utils import load_json_data
        trades = load_json_data('active_trades.json', [])
        open_trades_for_symbol = [t for t in trades if t.get('symbol') == symbol and t.get('status') == 'OPEN']
        
        if len(open_trades_for_symbol) >= 1:  # قيود صارمة - عملة واحدة فقط لكل صفقة
            logger.warning(f"تجاهل الصفقة لـ {symbol} - توجد بالفعل صفقة مفتوحة لهذه العملة")
            return False
        
        # التحقق من الحد الأدنى للثقة والربح المحتمل
        if confidence < trade_settings['min_confidence']:
            logger.info(f"تجاهل الصفقة لـ {symbol} - الثقة منخفضة جداً ({confidence:.2f} < {trade_settings['min_confidence']})")
            return False
        
        if potential_profit < trade_settings['min_profit']:
            logger.info(f"تجاهل الصفقة لـ {symbol} - الربح المحتمل منخفض جداً ({potential_profit:.2f}% < {trade_settings['min_profit']}%)")
            return False
        
        # التحقق من حجم التداول
        volume_24h = opportunity.get('volume_24h', 0)
        if volume_24h < trade_settings['min_volume']:
            logger.info(f"تجاهل الصفقة لـ {symbol} - حجم التداول منخفض جداً ({volume_24h:.0f} < {trade_settings['min_volume']})")
            return False
        
        # إذا كان التأكيد على أنماط الشموع مطلوباً
        if trade_settings['confirm_patterns']:
            # تحليل إضافي للشموع
            try:
                # الحصول على بيانات الشموع من مختلف الإطارات الزمنية
                from app.mexc_api import get_klines
                klines_5m = get_klines(symbol, interval='5m', limit=30)
                klines_15m = get_klines(symbol, interval='15m', limit=30)
                klines_1h = get_klines(symbol, interval='60m', limit=24)
                
                if klines_5m and klines_15m and klines_1h:
                    # الحصول على إشارة الدخول من تحليل الشموع
                    has_signal, trend, signal_strength, signal_info = get_entry_signal(klines_1h, klines_15m, klines_5m)
                    
                    if not has_signal or trend != 'up' or signal_strength < 0.7:
                        logger.info(f"تجاهل الصفقة لـ {symbol} - لم يتم تأكيد إشارة الدخول (إشارة: {has_signal}, اتجاه: {trend}, قوة: {signal_strength:.2f})")
                        return False
                    
                    logger.info(f"تم تأكيد إشارة الدخول لـ {symbol} - اتجاه: {trend}, قوة: {signal_strength:.2f}")
            except Exception as e:
                logger.error(f"خطأ في تحليل الشموع لـ {symbol}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"خطأ في تقييم فرصة تداول: {e}")
        return False


def execute_trade(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    """
    تنفيذ صفقة بناءً على فرصة
    
    :param opportunity: فرصة التداول
    :return: نتيجة التنفيذ
    """
    global last_trade_timestamp
    
    try:
        symbol = opportunity.get('symbol')
        entry_price = opportunity.get('entry_price')
        reason = opportunity.get('reason', 'تحليل فني إيجابي')
        
        # الحصول على حجم المركز المناسب
        quantity = get_position_size(symbol)
        
        # حساب أسعار الربح والخسارة
        take_profit_price = entry_price * (1 + TAKE_PROFIT)
        stop_loss_price = entry_price * (1 - STOP_LOSS)
        
        # تنفيذ الصفقة
        if trade_settings['use_market_orders']:
            result = execute_market_buy(symbol, quantity)
        else:
            result = execute_limit_buy(symbol, quantity, entry_price)
        
        # تحديث وقت آخر صفقة
        last_trade_timestamp = time.time()
        
        # إرسال إشعار عن الصفقة الجديدة
        trade_message = f"🔔 تم فتح صفقة جديدة!\n"
        trade_message += f"العملة: {symbol}\n"
        trade_message += f"السعر: {entry_price}\n"
        trade_message += f"الكمية: {quantity}\n"
        trade_message += f"هدف الربح: {take_profit_price:.8f}\n"
        trade_message += f"وقف الخسارة: {stop_loss_price:.8f}\n"
        trade_message += f"السبب: {reason}\n"
        send_telegram_message(trade_message)
        
        logger.info(f"تم تنفيذ صفقة جديدة: {symbol} بسعر {entry_price} وكمية {quantity}")
        
        # إضافة معلومات إضافية للنتيجة
        result['opportunity'] = opportunity
        
        return result
    except Exception as e:
        logger.error(f"خطأ في تنفيذ صفقة: {e}")
        return {'error': str(e)}


def scan_and_trade():
    """
    فحص الفرص وتنفيذ الصفقات تلقائياً مع تطبيق صارم لقواعد التنويع
    """
    global auto_trader_running
    import json
    
    # متغيرات لتتبع الوقت
    last_full_scan = 0
    last_quick_scan = 0
    
    # قائمة العملات التي تم فحصها في المسح السريع
    recently_scanned = set()
    
    while auto_trader_running:
        try:
            current_time = time.time()
            
            # تحديد نوع المسح (شامل أو سريع)
            if trade_settings['rapid_scanning']:
                # مسح شامل كل 60 ثانية (أو حسب الإعدادات)
                run_full_scan = (current_time - last_full_scan) >= trade_settings['scan_interval']
                
                # مسح سريع للعملات ذات الأولوية كل 10 ثواني (أو حسب الإعدادات)
                run_quick_scan = (current_time - last_quick_scan) >= trade_settings['quick_scan_interval']
            else:
                # إذا كان المسح السريع معطلاً، استخدم المسح الشامل فقط
                run_full_scan = True
                run_quick_scan = False
            
            # المسح الشامل - فحص جميع الفرص
            if run_full_scan:
                logger.info("بدء المسح الشامل للفرص...")
                
                # الحصول على أفضل الفرص (عدد أكبر لزيادة الاحتمالات)
                opportunities = get_best_opportunities(limit=30)
                
                if opportunities:
                    # تحضير قائمة مجموعة متنوعة من العملات لزيادة التنوع
                    # تطبيق قواعد التنويع من خلال نظام trade_diversifier.py الجديد
                    from app.trade_diversifier import enforce_diversity
                    
                    # استخراج رموز العملات من الفرص
                    candidate_symbols = [opp.get('symbol') for opp in opportunities if opp.get('symbol')]
                    
                    # تطبيق آلية التنويع على الفرص باستخدام النظام الجديد
                    diverse_symbols = enforce_diversity(candidate_symbols)
                    
                    # فلترة الفرص لتقتصر على العملات المتنوعة فقط
                    diverse_opportunities = [opp for opp in opportunities if opp.get('symbol') in diverse_symbols]
                    
                    logger.info(f"بعد تطبيق قواعد التنويع: {len(diverse_opportunities)} فرصة متاحة من أصل {len(opportunities)}")
                    
                    # فحص كل فرصة والدخول إذا كانت تستوفي المعايير
                    for opportunity in diverse_opportunities:
                        if not auto_trader_running:
                            break
                            
                        symbol = opportunity.get('symbol')
                        
                        logger.info(f"[مسح شامل] فحص فرصة لـ {symbol} - ثقة: {opportunity.get('confidence', 0):.2f}, ربح محتمل: {opportunity.get('potential_profit', 0):.2f}%")
                        
                        # إضافة العملة للقائمة المفحوصة مؤخراً
                        recently_scanned.add(symbol)
                        
                        # محاولة فتح صفقة
                        process_opportunity(opportunity)
                else:
                    logger.info("لم يتم العثور على فرص تداول في المسح الشامل")
                
                # تحديث وقت آخر مسح شامل
                last_full_scan = current_time
            
            # المسح السريع - فحص العملات ذات الأولوية فقط
            elif run_quick_scan and trade_settings['rapid_scanning']:
                logger.info("بدء المسح السريع للعملات ذات الأولوية...")
                
                # فحص العملات ذات الأولوية فقط
                from app.market_monitor import analyze_price_action
                
                # فحص كل عملة من العملات ذات الأولوية
                for symbol in trade_settings['priority_symbols']:
                    if not auto_trader_running:
                        break
                    
                    # تجاهل العملات التي تم فحصها مؤخراً في المسح الشامل
                    if symbol in recently_scanned:
                        continue
                        
                    try:
                        # تحليل العملة
                        analysis = analyze_price_action(symbol)
                        
                        # التحقق مما إذا كانت مناسبة للتداول
                        if analysis['summary'].get('suitable_for_trading', False):
                            logger.info(f"[مسح سريع] عثر على فرصة لـ {symbol}")
                            
                            # إنشاء كائن الفرصة
                            opportunity = {
                                'symbol': symbol,
                                'entry_price': analysis['price'],
                                'potential_profit': analysis['summary']['weighted_profit'] * 100,
                                'confidence': analysis['summary']['confidence'],
                                'reason': analysis['summary'].get('trading_reason', 'تحليل فني إيجابي'),
                                'timeframe': max(analysis['timeframes'].keys(), key=lambda k: analysis['timeframes'][k]['trend_strength'])
                            }
                            
                            # محاولة فتح صفقة
                            process_opportunity(opportunity)
                    except Exception as e:
                        logger.error(f"خطأ في تحليل العملة {symbol} في المسح السريع: {e}")
                
                # تحديث وقت آخر مسح سريع
                last_quick_scan = current_time
                
                # مسح قائمة العملات المفحوصة مؤخراً بشكل دوري
                if len(recently_scanned) > 50:
                    recently_scanned.clear()
            
            # انتظار قصير بين دورات المسح
            time.sleep(1)
        except Exception as e:
            logger.error(f"خطأ في حلقة المسح والتداول: {e}")
            time.sleep(30)  # انتظار في حالة حدوث خطأ


def process_opportunity(opportunity):
    """
    معالجة فرصة تداول محددة وفتح صفقة إذا كانت مناسبة
    
    :param opportunity: فرصة التداول
    :return: نتيجة المعالجة
    """
    try:
        symbol = opportunity.get('symbol')
        
        # التحقق من إمكانية فتح صفقة جديدة
        if not can_open_new_trade(symbol):
            return False
        
        # التحقق مما إذا كان يجب الدخول في الصفقة
        if not should_enter_trade(opportunity):
            return False
        
        # تنفيذ الصفقة
        result = execute_trade(opportunity)
        
        if 'error' in result:
            logger.error(f"فشل تنفيذ الصفقة لـ {symbol}: {result['error']}")
            return False
        else:
            logger.info(f"تم تنفيذ الصفقة بنجاح لـ {symbol}")
            
            # إعادة حساب أسعار العملات بسرعة بعد فتح صفقة جديدة
            # لتحديث معلومات وقف الخسارة وأخذ الربح
            threading.Thread(target=lambda: manage_open_trades(), daemon=True).start()
            
            return True
    except Exception as e:
        logger.error(f"خطأ في معالجة فرصة التداول لـ {opportunity.get('symbol', 'غير معروف')}: {e}")
        return False


def manage_open_trades():
    """
    إدارة الصفقات المفتوحة (أخذ الربح / وقف الخسارة) مع خيارات متقدمة للبيع الذكي
    """
    try:
        # الحصول على الصفقات المفتوحة
        open_trades = get_open_trades()
        
        # إضافة إعدادات البيع المتقدمة
        sell_settings = {
            'trailing_take_profit': True,  # تفعيل وقف الربح المتحرك
            'trailing_percentage': 1.0,    # نسبة التتبع للوقف المتحرك (%)
            'partial_profit_taking': True, # بيع جزئي للأرباح
            'partial_take_profit': 0.8,    # نسبة من هدف الربح للبيع الجزئي (80%)
            'partial_sell_ratio': 0.5,     # نسبة الكمية للبيع الجزئي (50%)
            'exit_on_trend_reversal': True, # خروج عند انعكاس الاتجاه
        }
        
        for trade in open_trades:
            symbol = trade.get('symbol')
            entry_price = trade.get('entry_price', trade.get('price', 0))
            quantity = float(trade.get('quantity', 0))
            
            # التجاهل إذا كان السعر أو الكمية غير صالحة
            if not entry_price or entry_price <= 0 or not quantity or quantity <= 0:
                continue
                
            # الحصول على معلومات الصفقة الإضافية (للتتبع)
            trade_meta = trade.get('metadata', {})
            if not trade_meta:
                trade['metadata'] = {
                    'highest_price': entry_price,
                    'trailing_stop': 0,
                    'partial_take_executed': False
                }
                trade_meta = trade['metadata']
            
            # الحصول على السعر الحالي
            current_price = get_current_price(symbol)
            if not current_price:
                continue
            
            # حساب التغيير النسبي
            price_change_pct = ((current_price - entry_price) / entry_price) * 100
            
            # حساب أسعار أخذ الربح ووقف الخسارة الأساسية
            take_profit_price = entry_price * (1 + TAKE_PROFIT)
            stop_loss_price = entry_price * (1 - STOP_LOSS)
            
            # تحديث أعلى سعر تم الوصول إليه (للتتبع)
            if current_price > trade_meta.get('highest_price', 0):
                trade_meta['highest_price'] = current_price
                
                # تحديث وقف الربح المتحرك إذا كان مفعلاً
                if sell_settings['trailing_take_profit']:
                    trailing_stop_price = current_price * (1 - sell_settings['trailing_percentage']/100)
                    # تحديث وقف الربح المتحرك فقط إذا كان أعلى من القيمة السابقة
                    if trailing_stop_price > trade_meta.get('trailing_stop', 0):
                        trade_meta['trailing_stop'] = trailing_stop_price
                        logger.info(f"تحديث وقف الربح المتحرك لـ {symbol}: {trailing_stop_price:.8f}")
            
            # حساب سعر البيع الجزئي إذا كان مفعلاً
            partial_take_profit_price = entry_price * (1 + TAKE_PROFIT * sell_settings['partial_take_profit'])
            
            # بيع جزئي عند الوصول لنسبة من هدف الربح
            if (sell_settings['partial_profit_taking'] and 
                current_price >= partial_take_profit_price and 
                not trade_meta.get('partial_take_executed', False)):
                
                # تنفيذ بيع جزئي
                partial_quantity = quantity * sell_settings['partial_sell_ratio']
                
                try:
                    # إغلاق جزء من الصفقة
                    from app.mexc_api import execute_market_sell
                    sell_result = execute_market_sell(symbol, partial_quantity)
                    
                    if 'error' not in sell_result:
                        logger.info(f"تم تنفيذ بيع جزئي للعملة {symbol} - الكمية: {partial_quantity}, الربح: {price_change_pct:.2f}%")
                        
                        # تحديث معلومات الصفقة
                        trade['quantity'] = quantity - partial_quantity
                        trade_meta['partial_take_executed'] = True
                        
                        # إرسال إشعار
                        message = f"💰 تم تنفيذ بيع جزئي!\n"
                        message += f"العملة: {symbol}\n"
                        message += f"سعر الدخول: {entry_price}\n"
                        message += f"سعر البيع الجزئي: {current_price}\n"
                        message += f"الكمية المباعة: {partial_quantity}\n"
                        message += f"الربح: {price_change_pct:.2f}%\n"
                        message += f"الكمية المتبقية: {trade['quantity']}\n"
                        send_telegram_message(message)
                    else:
                        logger.error(f"فشل تنفيذ البيع الجزئي للعملة {symbol}: {sell_result.get('error')}")
                except Exception as e:
                    logger.error(f"خطأ في تنفيذ البيع الجزئي للعملة {symbol}: {e}")
            
            # فحص انعكاس الاتجاه إذا كان مفعلاً
            trend_reversal_detected = False
            if sell_settings['exit_on_trend_reversal'] and price_change_pct > 1.0:
                try:
                    # فحص انعكاس الاتجاه باستخدام تحليل الشموع
                    from app.mexc_api import get_klines
                    from app.ai_model import identify_trend_reversal
                    
                    # الحصول على بيانات الشموع
                    klines_5m = get_klines(symbol, interval='5m', limit=10)
                    
                    if klines_5m and len(klines_5m) >= 3:
                        trend_reversal_detected = identify_trend_reversal(klines_5m)
                        
                        if trend_reversal_detected:
                            logger.info(f"تم اكتشاف انعكاس الاتجاه للعملة {symbol} - البيع للحفاظ على الربح")
                except Exception as e:
                    logger.error(f"خطأ في فحص انعكاس الاتجاه للعملة {symbol}: {e}")
            
            # التحقق من شروط البيع المختلفة:
            
            # 1. هدف الربح الأساسي
            if current_price >= take_profit_price:
                logger.info(f"تم الوصول إلى هدف الربح للعملة {symbol} - الربح: {price_change_pct:.2f}%")
                
                # إغلاق الصفقة
                close_result = close_trade(trade, 'take_profit')
                
                # إرسال إشعار
                profit_message = f"🎯 تم الوصول إلى هدف الربح!\n"
                profit_message += f"العملة: {symbol}\n"
                profit_message += f"سعر الدخول: {entry_price}\n"
                profit_message += f"سعر الخروج: {current_price}\n"
                profit_message += f"الربح: {price_change_pct:.2f}%\n"
                send_telegram_message(profit_message)
            
            # 2. وقف الربح المتحرك (إذا كان مفعلاً وتم تعيين قيمة له)
            elif (sell_settings['trailing_take_profit'] and 
                  trade_meta.get('trailing_stop', 0) > 0 and 
                  current_price <= trade_meta['trailing_stop'] and 
                  current_price > entry_price):
                
                logger.info(f"تم تفعيل وقف الربح المتحرك للعملة {symbol} - الربح: {price_change_pct:.2f}%")
                
                # إغلاق الصفقة
                close_result = close_trade(trade, 'trailing_stop')
                
                # إرسال إشعار
                message = f"📈 تم تفعيل وقف الربح المتحرك!\n"
                message += f"العملة: {symbol}\n"
                message += f"سعر الدخول: {entry_price}\n"
                message += f"أعلى سعر: {trade_meta['highest_price']}\n"
                message += f"سعر الخروج: {current_price}\n"
                message += f"الربح: {price_change_pct:.2f}%\n"
                send_telegram_message(message)
            
            # 3. بيع عند اكتشاف انعكاس الاتجاه (إذا كان مفعلاً)
            elif trend_reversal_detected and price_change_pct > 0:
                logger.info(f"البيع بسبب انعكاس الاتجاه للعملة {symbol} - الربح: {price_change_pct:.2f}%")
                
                # إغلاق الصفقة
                close_result = close_trade(trade, 'trend_reversal')
                
                # إرسال إشعار
                message = f"🔄 بيع بسبب انعكاس الاتجاه!\n"
                message += f"العملة: {symbol}\n"
                message += f"سعر الدخول: {entry_price}\n"
                message += f"سعر الخروج: {current_price}\n"
                message += f"الربح: {price_change_pct:.2f}%\n"
                send_telegram_message(message)
            
            # 4. وقف الخسارة الأساسي
            elif current_price <= stop_loss_price:
                logger.info(f"تم تفعيل وقف الخسارة للعملة {symbol} - الخسارة: {price_change_pct:.2f}%")
                
                # إغلاق الصفقة
                close_result = close_trade(trade, 'stop_loss')
                
                # إرسال إشعار
                loss_message = f"⚠️ تم تفعيل وقف الخسارة!\n"
                loss_message += f"العملة: {symbol}\n"
                loss_message += f"سعر الدخول: {entry_price}\n"
                loss_message += f"سعر الخروج: {current_price}\n"
                loss_message += f"الخسارة: {price_change_pct:.2f}%\n"
                send_telegram_message(loss_message)
    except Exception as e:
        logger.error(f"خطأ في إدارة الصفقات المفتوحة: {e}")


def auto_trading_loop():
    """
    حلقة التداول الآلي - تدمج البحث عن الفرص وإدارة الصفقات
    """
    global auto_trader_running
    
    while auto_trader_running:
        try:
            # إدارة الصفقات المفتوحة
            manage_open_trades()
            
            # فحص وتنفيذ صفقات جديدة
            scan_and_trade()
            
            # انتظار فترة قصيرة قبل الدورة التالية
            time.sleep(10)
        except Exception as e:
            logger.error(f"خطأ في حلقة التداول الآلي: {e}")
            time.sleep(30)


def start_auto_trader():
    """
    بدء التداول الآلي
    
    :return: True إذا تم البدء بنجاح
    """
    global auto_trader_running, auto_trader_thread
    
    if auto_trader_running:
        logger.warning("التداول الآلي قيد التشغيل بالفعل")
        return False
    
    # بدء التداول الآلي
    auto_trader_running = True
    auto_trader_thread = threading.Thread(target=auto_trading_loop, daemon=True)
    auto_trader_thread.start()
    
    logger.info("تم بدء التداول الآلي")
    
    # إرسال إشعار
    status_message = f"🤖 تم بدء التداول الآلي!\n"
    status_message += f"وقت البدء: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    status_message += f"الحد الأقصى للصفقات المفتوحة: {trade_settings['max_active_trades']}\n"
    status_message += f"الحد الأدنى للثقة: {trade_settings['min_confidence']}\n"
    status_message += f"الحد الأدنى للربح المحتمل: {trade_settings['min_profit']}%\n"
    send_telegram_message(status_message)
    
    return True


def stop_auto_trader():
    """
    إيقاف التداول الآلي
    
    :return: True إذا تم الإيقاف بنجاح
    """
    global auto_trader_running, auto_trader_thread
    
    if not auto_trader_running:
        logger.warning("التداول الآلي متوقف بالفعل")
        return False
    
    # إيقاف التداول الآلي
    auto_trader_running = False
    
    # انتظار إنهاء الخيط
    if auto_trader_thread:
        auto_trader_thread.join(timeout=1.0)
    
    logger.info("تم إيقاف التداول الآلي")
    
    # إرسال إشعار
    status_message = f"🛑 تم إيقاف التداول الآلي!\n"
    status_message += f"وقت الإيقاف: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    send_telegram_message(status_message)
    
    return True


def get_auto_trader_status():
    """
    الحصول على حالة التداول الآلي
    
    :return: حالة التداول الآلي
    """
    global auto_trader_running, last_trade_timestamp
    
    return {
        'running': auto_trader_running,
        'settings': trade_settings,
        'last_trade_time': datetime.fromtimestamp(last_trade_timestamp).strftime('%Y-%m-%d %H:%M:%S') if last_trade_timestamp > 0 else None,
        'time_since_last_trade': time.time() - last_trade_timestamp if last_trade_timestamp > 0 else 0
    }


def update_auto_trader_settings(new_settings: Dict[str, Any]):
    """
    تحديث إعدادات التداول الآلي
    
    :param new_settings: الإعدادات الجديدة
    :return: الإعدادات المحدثة
    """
    global trade_settings
    
    try:
        # تحديث الإعدادات
        for key, value in new_settings.items():
            if key in trade_settings:
                trade_settings[key] = value
        
        logger.info(f"تم تحديث إعدادات التداول الآلي: {trade_settings}")
        return trade_settings
    except Exception as e:
        logger.error(f"خطأ في تحديث إعدادات التداول الآلي: {e}")
        return trade_settings