# app/telegram_notify.py

import requests
import logging
import threading
import time
import datetime
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, BASE_CURRENCY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('telegram_notify')

# متغير عام للتحكم في تشغيل/إيقاف المؤقت الزمني
daily_report_timer_running = False
daily_report_thread = None

def send_telegram_message(message):
    """
    إرسال رسالة إلى التلغرام
    
    :param message: النص المراد إرساله
    :return: نتيجة الإرسال
    """
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        params = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to send telegram message: {response.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error sending telegram message: {e}")
        return False

def notify_trade_status(symbol, status, price=None, profit_loss=None, order_id=None, api_verified=True):
    """
    إرسال إشعار عن حالة التداول
    
    :param symbol: رمز العملة
    :param status: حالة التداول (شراء، بيع، وقف خسارة)
    :param price: سعر التنفيذ
    :param profit_loss: نسبة الربح أو الخسارة
    :param order_id: معرف الأمر (يظهر فقط للصفقات الحقيقية)
    :param api_verified: هل تم التحقق من الصفقة عبر API (افتراضياً نعم)
    """
    try:
        # تخطي الإشعار إذا لم يتم التحقق من الصفقة مع API
        if not api_verified:
            logger.warning(f"تجاهل إرسال إشعار لصفقة غير مؤكدة على المنصة: {symbol}")
            return False
        
        # إنشاء الرسالة مع معلومات إضافية حسب توفرها
        if price and profit_loss:
            message = f"<b>{status}</b>: {symbol} @ {price} | {profit_loss:+.2f}%"
        elif price:
            message = f"<b>{status}</b>: {symbol} @ {price}"
        else:
            message = f"<b>{status}</b>: {symbol}"
        
        # إضافة معرف الأمر للتحقق
        if order_id:
            message += f"\n<code>معرف الأمر: {order_id}</code>"
        
        # إرسال الإشعار
        return send_telegram_message(message)
    except Exception as e:
        logger.error(f"Error in notify_trade_status: {e}")
        return False

def notify_bot_status(status, message=None):
    """
    إرسال إشعار عن حالة البوت
    
    :param status: حالة البوت (تشغيل، إيقاف، تحذير، خطأ)
    :param message: رسالة إضافية
    :return: True إذا تم إرسال الإشعار بنجاح، False خلاف ذلك
    """
    try:
        if status == "start":
            emoji = "🟢"
            title = "تم تشغيل البوت"
        elif status == "stop":
            emoji = "🔴"
            title = "تم إيقاف البوت"
        elif status == "warning":
            emoji = "⚠️"
            title = "تحذير"
        elif status == "error":
            emoji = "❌"
            title = "خطأ"
        else:
            emoji = "ℹ️"
            title = status
            
        text = f"{emoji} <b>{title}</b>"
        if message:
            text += f"\n{message}"
        
        # إضافة الوقت والتاريخ لتمييز الإشعارات
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text += f"\n<i>الوقت: {current_time}</i>"
            
        result = send_telegram_message(text)
        logger.info(f"🔔 نتيجة إرسال إشعار حالة البوت ({status}): {result}")
        return result
    except Exception as e:
        logger.error(f"Error in notify_bot_status: {e}")
        return False

def notify_daily_summary(total_trades, profitable_trades, total_profit_loss, balance=None, active_trades=None):
    """
    إرسال ملخص يومي للأداء
    
    :param total_trades: عدد الصفقات الكلي
    :param profitable_trades: عدد الصفقات الرابحة
    :param total_profit_loss: إجمالي الربح أو الخسارة
    :param balance: الرصيد الحالي (اختياري)
    :param active_trades: قائمة الصفقات النشطة (اختياري)
    """
    try:
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        # التقرير اليومي باللغة العربية
        message = f"""<b>📊 التقرير اليومي لروبوت CJ</b>

<b>💹 ملخص أداء اليوم:</b>
• عدد الصفقات: <b>{total_trades}</b> صفقة
• الصفقات الرابحة: <b>{profitable_trades}</b> ({win_rate:.1f}%)
• الصفقات الخاسرة: <b>{total_trades - profitable_trades}</b> ({100 - win_rate:.1f}%)
• إجمالي نسبة الأرباح: <b>{total_profit_loss:+.2f}%</b>
"""
        
        # إضافة معلومات الرصيد إذا كانت متوفرة
        if balance:
            message += f"\n<b>💰 الرصيد الحالي:</b> <b>{balance}</b> USDT"
            
        # إضافة معلومات الصفقات النشطة إذا كانت متوفرة
        if active_trades and len(active_trades) > 0:
            message += "\n\n<b>📋 الصفقات النشطة الحالية:</b>"
            for trade in active_trades:
                symbol = trade.get('symbol', 'غير معروف')
                # استخدام entry_price بدلاً من price (تصحيح للتوافق مع بنية البيانات)
                entry_price = trade.get('entry_price', 0)
                
                # الحصول على السعر الحالي من API إذا لم يكن متوفراً
                current_price = trade.get('current_price', 0)
                if not current_price and symbol != 'غير معروف':
                    try:
                        from app.exchange_manager import get_current_price
                        price_result = get_current_price(symbol)
                        if price_result is not None:
                            try:
                                current_price = float(price_result)
                            except (ValueError, TypeError):
                                current_price = 0
                        else:
                            current_price = 0
                    except Exception as e:
                        logger.error(f"خطأ في الحصول على السعر الحالي: {e}")
                        current_price = 0
                
                # تسجيل معلومات التشخيص
                logger.debug(f"معلومات الصفقة النشطة: رمز={symbol}, سعر دخول={entry_price}, سعر حالي={current_price}")
                
                # حساب التغيير
                change = ((current_price - entry_price) / entry_price * 100) if entry_price and current_price else 0
                message += f"\n• {symbol}: {change:+.2f}% (سعر الدخول: {entry_price})"
        else:
            message += "\n\n<b>📋 الصفقات النشطة:</b> لا توجد صفقات نشطة حالياً"
            
        message += "\n\n<i>تم إنشاء هذا التقرير تلقائياً بواسطة روبوت CJ للتداول</i>"
        
        send_telegram_message(message)
        logger.info("تم إرسال التقرير اليومي بنجاح إلى تلجرام")
        return True
    except Exception as e:
        logger.error(f"حدث خطأ أثناء إرسال التقرير اليومي: {e}")
        return False


def generate_daily_report():
    """
    إنشاء وإرسال التقرير اليومي استناداً إلى البيانات الحالية
    """
    try:
        # استيراد الدوال اللازمة هنا لتجنب التضمين الدائري (circular import)
        from app.trade_executor import get_performance_stats, get_open_trades
        from app.mexc_api import get_balance
        
        # الحصول على الإحصائيات وبيانات التداول
        performance = get_performance_stats()
        open_trades = get_open_trades()
        
        # تحديث معلومات السعر الحالي لكل صفقة مفتوحة
        for trade in open_trades:
            try:
                symbol = trade.get('symbol')
                if symbol:
                    from app.exchange_manager import get_current_price
                    price_result = get_current_price(symbol)
                    
                    # التحقق من صحة النتيجة
                    if price_result is not None:
                        try:
                            # تحويل السعر إلى رقم عشري
                            current_price = float(price_result)
                            # حفظ السعر الحالي في القاموس
                            trade['current_price'] = current_price
                            
                            # حساب نسبة التغيير
                            entry_price = float(trade.get('entry_price', 0))
                            if entry_price > 0:
                                change_pct = (current_price - entry_price) / entry_price * 100
                                trade['change_pct'] = change_pct
                                
                                logger.debug(f"تم تحديث سعر {symbol}: {current_price} (تغيير: {change_pct:.2f}%)")
                        except (ValueError, TypeError) as conv_err:
                            logger.error(f"خطأ في تحويل سعر {symbol}: {conv_err}")
            except Exception as price_err:
                logger.error(f"خطأ في تحديث سعر العملة {trade.get('symbol', 'غير معروف')}: {price_err}")
        
        # محاولة الحصول على الرصيد الحالي
        try:
            balance = get_balance(BASE_CURRENCY)
            balance = round(float(balance), 2)
        except Exception as e:
            logger.error(f"خطأ في الحصول على الرصيد: {e}")
            balance = None
        
        # الحصول على الإحصائيات المطلوبة من كائن الأداء
        total_trades = performance.get('total_trades', 0)
        profit_trades = performance.get('profit_trades', 0)
        net_profit = performance.get('net_profit', 0)
        
        # سجل للتأكد من صحة البيانات قبل الإرسال
        logger.info(f"التقرير اليومي - صفقات مفتوحة: {len(open_trades)}")
        for trade in open_trades:
            logger.info(f"صفقة مفتوحة: {trade.get('symbol')} - سعر الدخول: {trade.get('entry_price')} - السعر الحالي: {trade.get('current_price')}")
        
        # إرسال التقرير
        notify_daily_summary(
            total_trades=total_trades,
            profitable_trades=profit_trades,
            total_profit_loss=net_profit,
            balance=balance,
            active_trades=open_trades
        )
        logger.info("تم إنشاء وإرسال التقرير اليومي بنجاح")
        return True
    except Exception as e:
        logger.error(f"حدث خطأ في إنشاء التقرير اليومي: {e}")
        return False


def start_daily_report_timer(target_hour=8):
    """
    بدء مؤقت لإرسال التقرير اليومي في الساعة المحددة
    
    :param target_hour: الساعة المستهدفة لإرسال التقرير (24 ساعة)
                        تم تعيين القيمة الافتراضية إلى 8 مساءً (20:00)
    """
    global daily_report_timer_running, daily_report_thread
    
    # إيقاف المؤقت السابق إذا كان يعمل
    if daily_report_timer_running and daily_report_thread:
        stop_daily_report_timer()
    
    daily_report_timer_running = True
    
    def timer_thread():
        logger.info(f"بدء مؤقت التقرير اليومي (الإرسال في الساعة {target_hour}:00)")
        while daily_report_timer_running:
            # الحصول على الوقت الحالي
            now = datetime.datetime.now()
            
            # حساب الوقت المتبقي حتى موعد التقرير التالي
            if now.hour < target_hour:
                # الموعد اليوم
                next_report = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            else:
                # الموعد غداً
                tomorrow = now + datetime.timedelta(days=1)
                next_report = tomorrow.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            
            # حساب الثواني المتبقية
            seconds_until_report = (next_report - now).total_seconds()
            
            # إرسال رسالة سجل للتوضيح
            report_time = next_report.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"التقرير التالي في {report_time} (بعد {seconds_until_report:.0f} ثانية)")
            
            # النوم حتى موعد التقرير التالي أو لمدة 60 ثانية للتحقق من التوقف
            sleep_duration = min(seconds_until_report, 60)
            time.sleep(sleep_duration)
            
            # التحقق من وقت الإرسال
            if seconds_until_report <= 60 and daily_report_timer_running:
                logger.info("حان وقت إرسال التقرير اليومي")
                generate_daily_report()
                # النوم لمدة دقيقة لتجنب الإرسال المتكرر
                time.sleep(60)
    
    # إنشاء وبدء الخيط
    daily_report_thread = threading.Thread(target=timer_thread, daemon=True)
    daily_report_thread.start()
    
    return True


def stop_daily_report_timer():
    """إيقاف مؤقت التقرير اليومي"""
    global daily_report_timer_running
    if daily_report_timer_running:
        daily_report_timer_running = False
        logger.info("تم إيقاف مؤقت التقرير اليومي")
    return True
