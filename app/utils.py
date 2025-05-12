# app/utils.py
import time
import json
import os
import datetime
from functools import wraps
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('utils')

def format_price(price, decimals=4):
    """
    تنسيق رقم السعر بعدد محدد من الخانات العشرية
    
    :param price: السعر
    :param decimals: عدد الخانات العشرية
    :return: السعر المنسق
    """
    try:
        return round(float(price), decimals)
    except (ValueError, TypeError):
        return 0.0

def calculate_percentage_change(entry_price, current_price):
    """
    حساب نسبة التغيير في السعر
    
    :param entry_price: سعر الدخول
    :param current_price: السعر الحالي
    :return: نسبة التغيير
    """
    try:
        return ((current_price - entry_price) / entry_price) * 100
    except ZeroDivisionError:
        return 0

def truncate_float(value, decimals=4):
    """
    تقريب الرقم العشري للأسفل بعدد محدد من الخانات
    
    :param value: القيمة
    :param decimals: عدد الخانات العشرية
    :return: القيمة المقربة
    """
    try:
        str_value = f"{value:.10f}"
        return float(str_value[:str_value.find('.') + decimals + 1])
    except (ValueError, TypeError):
        return 0.0

def get_trade_status(entry_price, current_price):
    """
    الحصول على حالة الصفقة (ربح/خسارة)
    
    :param entry_price: سعر الدخول
    :param current_price: السعر الحالي
    :return: حالة الصفقة
    """
    change = calculate_percentage_change(entry_price, current_price)
    if change > 0:
        return "ربح"
    elif change < 0:
        return "خسارة"
    return "بدون تغيير"

def save_json_data(file_path, data):
    """
    حفظ البيانات بتنسيق JSON في ملف
    
    :param file_path: مسار الملف
    :param data: البيانات المراد حفظها
    :return: True في حالة النجاح، False في حالة الفشل
    """
    try:
        # التأكد من أن المسار هو سلسلة نصية وليس كائن
        if not isinstance(file_path, (str, bytes, os.PathLike)):
            logger.error(f"Invalid file path: expected string or path-like object, got {type(file_path)}")
            return False
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON data to {file_path}: {e}")
        return False

def load_json_data(file_path, default=None):
    """
    تحميل البيانات من ملف JSON
    
    :param file_path: مسار الملف
    :param default: القيمة الافتراضية إذا فشل التحميل
    :return: البيانات المحملة أو القيمة الافتراضية
    """
    if default is None:
        default = {}
        
    try:
        if not os.path.exists(file_path):
            return default
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON data from {file_path}: {e}")
        return default

def get_timestamp_str():
    """
    الحصول على الوقت الحالي كسلسلة نصية
    
    :return: سلسلة نصية تمثل الوقت الحالي
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def retry(max_retries=3, delay=1):
    """
    ديكوريتور لإعادة محاولة تنفيذ الدالة عدة مرات في حالة فشلها
    
    :param max_retries: أقصى عدد من المحاولات
    :param delay: التأخير بين المحاولات بالثواني
    :return: ديكوريتور
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    logger.warning(f"Retry {retries}/{max_retries} for {func.__name__}: {e}")
                    time.sleep(delay)
        return wrapper
    return decorator

def format_timestamp(timestamp_ms):
    """
    تحويل الطابع الزمني بالمللي ثانية إلى تاريخ ووقت مقروء
    
    :param timestamp_ms: الطابع الزمني بالمللي ثانية
    :return: سلسلة نصية تمثل التاريخ والوقت
    """
    try:
        timestamp_sec = timestamp_ms / 1000
        dt = datetime.datetime.fromtimestamp(timestamp_sec)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "غير متاح"
        
def calculate_total_profit():
    """
    حساب إجمالي الربح المحقق من جميع الصفقات المغلقة
    
    :return: الربح الإجمالي بالدولار والنسبة المئوية
    """
    try:
        trades = load_trades()
        
        total_profit_dollar = 0
        total_profit_pct = 0
        num_profitable_trades = 0
        num_closed_trades = 0
        
        for trade in trades:
            if trade.get('status') != 'CLOSED':
                continue
                
            # زيادة عدد الصفقات المغلقة
            num_closed_trades += 1
            
            entry_price = float(trade.get('entry_price', 0))
            close_price = float(trade.get('close_price', 0))
            quantity = float(trade.get('quantity', 0))
            
            # إذا كانت جميع البيانات اللازمة متوفرة
            if entry_price > 0 and close_price > 0 and quantity > 0:
                trade_profit_dollar = (close_price - entry_price) * quantity
                
                # إضافة الربح إلى الإجمالي
                total_profit_dollar += trade_profit_dollar
                
                # حساب نسبة الربح المئوية
                profit_pct = ((close_price - entry_price) / entry_price) * 100
                total_profit_pct += profit_pct
                
                # التحقق مما إذا كانت الصفقة مربحة
                if trade_profit_dollar > 0:
                    num_profitable_trades += 1
            
            # أو استخدام profit_pct المخزن مباشرة إذا كان متوفرًا
            elif trade.get('profit_pct') is not None:
                profit_pct = float(trade.get('profit_pct', 0))
                total_profit_pct += profit_pct
                
                # التحقق مما إذا كانت الصفقة مربحة
                if profit_pct > 0:
                    num_profitable_trades += 1
        
        # حساب متوسط الربح بالنسبة المئوية (إذا كان هناك صفقات مغلقة)
        avg_profit_pct = total_profit_pct / num_closed_trades if num_closed_trades > 0 else 0
        
        # حساب نسبة الصفقات المربحة
        win_rate = (num_profitable_trades / num_closed_trades * 100) if num_closed_trades > 0 else 0
        
        # تنسيق النتائج
        profit_statistics = {
            'total_profit_dollar': round(total_profit_dollar, 2),
            'avg_profit_pct': round(avg_profit_pct, 2),
            'win_rate': round(win_rate, 2),
            'num_profitable_trades': num_profitable_trades,
            'num_closed_trades': num_closed_trades
        }
        
        return profit_statistics
    except Exception as e:
        logger.error(f"خطأ في حساب الربح الإجمالي: {e}")
        return {
            'total_profit_dollar': 0,
            'avg_profit_pct': 0,
            'win_rate': 0,
            'num_profitable_trades': 0,
            'num_closed_trades': 0
        }

def load_trades():
    """
    تحميل الصفقات من ملف JSON
    
    :return: قائمة بالصفقات المحملة
    """
    return load_json_data('active_trades.json', [])
