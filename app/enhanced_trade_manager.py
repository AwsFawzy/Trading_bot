"""
مدير صفقات محسن لإدارة الصفقات وبيعها بشكل أفضل
يعالج مشاكل عدم البيع وعدم التنويع
"""

import os
import json
import time
import logging
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# العملات المفضلة للتنويع - عند عدم وجود فرص تداول عالية الجودة
DIVERSE_COINS = [
    'BTCUSDT',     # بيتكوين
    'ETHUSDT',     # إيثريوم
    'DOGEUSDT',    # دوج كوين
    'SOLUSDT',     # سولانا
    'BNBUSDT',     # بينانس كوين
    'MATICUSDT',   # بوليجون
    'AVAXUSDT',    # أفالانش
    'LINKUSDT',    # تشينلينك
    'TRXUSDT',     # ترون
    'LTCUSDT',     # لايتكوين
    'ADAUSDT',     # كاردانو
    'ETCUSDT',     # إيثريوم كلاسيك
    'DOTUSDT',     # بولكادوت
    'FILUSDT',     # فايلكوين
    'ATOMUSDT',    # كوزموس
]

# العملات المحظورة بشكل دائم
BANNED_COINS = ['XRPUSDT']

def load_trades():
    """تحميل الصفقات من الملف"""
    try:
        if os.path.exists('active_trades.json'):
            with open('active_trades.json', 'r') as f:
                data = json.load(f)
            
            # تحويل البيانات إلى التنسيق الصحيح إذا لزم الأمر
            if isinstance(data, dict) and 'open' in data and 'closed' in data:
                return data
            elif isinstance(data, list):
                return {
                    'open': [t for t in data if t.get('status') == 'OPEN'],
                    'closed': [t for t in data if t.get('status') != 'OPEN']
                }
            else:
                logger.warning(f"صيغة غير متوقعة لملف الصفقات: {type(data)}")
                return {'open': [], 'closed': []}
        
        return {'open': [], 'closed': []}
    except Exception as e:
        logger.error(f"خطأ في تحميل الصفقات: {e}")
        return {'open': [], 'closed': []}

def save_trades(data):
    """حفظ الصفقات في الملف"""
    try:
        # إنشاء نسخة احتياطية
        backup_name = f"active_trades.json.backup.{int(time.time())}"
        if os.path.exists('active_trades.json'):
            os.system(f"cp active_trades.json {backup_name}")
        
        # حفظ البيانات
        with open('active_trades.json', 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"تم حفظ {len(data.get('open', []))} صفقة مفتوحة و {len(data.get('closed', []))} صفقة مغلقة")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصفقات: {e}")
        return False

def get_traded_symbols():
    """الحصول على العملات المتداولة حالياً"""
    data = load_trades()
    open_trades = data.get('open', [])
    
    # استخراج رموز العملات
    symbols = set()
    for trade in open_trades:
        symbol = trade.get('symbol', '')
        if symbol:
            symbols.add(symbol.upper())
    
    return symbols

def is_symbol_allowed(symbol):
    """التحقق ما إذا كان مسموحاً بتداول العملة"""
    # منع العملات المحظورة
    if symbol.upper() in BANNED_COINS:
        return False, f"العملة {symbol} محظورة نهائياً"
    
    # التحقق من عدم وجود صفقات مفتوحة على نفس العملة
    traded_symbols = get_traded_symbols()
    if symbol.upper() in traded_symbols:
        return False, f"توجد صفقة مفتوحة بالفعل على {symbol}"
    
    return True, "مسموح بالتداول"

def select_diverse_coins(count=5):
    """اختيار عملات متنوعة للتداول"""
    # الحصول على العملات المتداولة حالياً
    traded_symbols = get_traded_symbols()
    
    # استبعاد العملات المتداولة حالياً والعملات المحظورة
    available_coins = [
        coin for coin in DIVERSE_COINS 
        if coin not in traded_symbols and coin not in BANNED_COINS
    ]
    
    # خلط العملات المتاحة لضمان التنويع العشوائي
    random.shuffle(available_coins)
    
    # اختيار العدد المطلوب من العملات
    selected_coins = available_coins[:count]
    
    logger.info(f"تم اختيار {len(selected_coins)} عملة للتنويع: {selected_coins}")
    return selected_coins

def force_sell_stale_trades(max_hours=12):
    """
    بيع الصفقات التي مضى عليها وقت طويل
    
    :param max_hours: الحد الأقصى للساعات قبل البيع القسري
    :return: عدد الصفقات التي تم بيعها
    """
    try:
        from app.trade_logic import close_trade
        
        data = load_trades()
        open_trades = data.get('open', [])
        closed_trades = data.get('closed', [])
        
        current_time = int(time.time() * 1000)
        max_time_ms = max_hours * 60 * 60 * 1000  # تحويل الساعات إلى ميلي ثانية
        
        sold_count = 0
        
        for trade in list(open_trades):  # استخدام نسخة من القائمة للتمكن من الحذف أثناء التكرار
            enter_time = trade.get('timestamp', current_time)
            time_diff = current_time - enter_time
            
            if time_diff > max_time_ms:
                logger.warning(f"بيع إجباري للصفقة المفتوحة منذ {time_diff/(60*60*1000):.1f} ساعة: {trade.get('symbol')}")
                
                # محاولة البيع
                try:
                    symbol = trade.get('symbol')
                    quantity = trade.get('quantity')
                    
                    # التأكد من وجود رمز وكمية صالحة
                    if not symbol or not quantity:
                        logger.error(f"صفقة بدون رمز أو كمية: {trade}")
                        continue
                    
                    # تنفيذ البيع
                    success = close_trade(symbol, quantity)
                    
                    if success:
                        # تحديث حالة الصفقة
                        trade['status'] = 'closed'
                        trade['exit_time'] = current_time
                        trade['exit_reason'] = 'forced_sell_stale'
                        
                        # نقل الصفقة من المفتوحة إلى المغلقة
                        open_trades.remove(trade)
                        closed_trades.append(trade)
                        
                        sold_count += 1
                        logger.info(f"تم بيع {symbol} بنجاح")
                    else:
                        logger.error(f"فشل بيع {symbol}")
                except Exception as e:
                    logger.error(f"خطأ في بيع {trade.get('symbol')}: {e}")
        
        # حفظ التغييرات إذا تم بيع أي صفقة
        if sold_count > 0:
            data['open'] = open_trades
            data['closed'] = closed_trades
            save_trades(data)
            
        return sold_count
    except Exception as e:
        logger.error(f"خطأ في بيع الصفقات القديمة: {e}")
        return 0

def check_profitable_trades():
    """
    التحقق من الصفقات المربحة وبيعها
    
    :return: عدد الصفقات المربحة التي تم بيعها
    """
    try:
        from app.trade_logic import close_trade
        from app.mexc_api import get_current_price
        
        data = load_trades()
        open_trades = data.get('open', [])
        closed_trades = data.get('closed', [])
        
        sold_count = 0
        
        for trade in list(open_trades):  # استخدام نسخة من القائمة للتمكن من الحذف أثناء التكرار
            symbol = trade.get('symbol')
            entry_price = trade.get('entry_price', 0)
            quantity = trade.get('quantity', 0)
            
            # التأكد من وجود بيانات صالحة
            if not symbol or not entry_price or not quantity:
                continue
            
            # الحصول على السعر الحالي
            current_price = get_current_price(symbol)
            if not current_price:
                continue
                
            # حساب نسبة الربح
            profit_percent = (current_price - entry_price) / entry_price * 100
            
            # شروط البيع - تم تخفيف الشروط لضمان البيع
            min_profit = 0.1  # 0.1% ربح على الأقل
            max_loss = -1.0  # -1% خسارة كحد أقصى
            
            if profit_percent >= min_profit or profit_percent <= max_loss:
                reason = "ربح" if profit_percent >= min_profit else "خسارة"
                logger.info(f"بيع صفقة {symbol} بنسبة {reason} {profit_percent:.2f}%")
                
                # تنفيذ البيع
                success = close_trade(symbol, quantity)
                
                if success:
                    # تحديث حالة الصفقة
                    trade['status'] = 'closed'
                    trade['exit_time'] = int(time.time() * 1000)
                    trade['exit_price'] = current_price
                    trade['exit_reason'] = 'profit_target' if profit_percent >= min_profit else 'stop_loss'
                    trade['profit_loss_percent'] = profit_percent
                    
                    # نقل الصفقة من المفتوحة إلى المغلقة
                    open_trades.remove(trade)
                    closed_trades.append(trade)
                    
                    sold_count += 1
                    logger.info(f"تم بيع {symbol} بنجاح")
                else:
                    logger.error(f"فشل بيع {symbol}")
        
        # حفظ التغييرات إذا تم بيع أي صفقة
        if sold_count > 0:
            data['open'] = open_trades
            data['closed'] = closed_trades
            save_trades(data)
            
        return sold_count
    except Exception as e:
        logger.error(f"خطأ في بيع الصفقات المربحة: {e}")
        return 0

def diversify_trades(capital=30, max_trades=5):
    """
    تنويع الصفقات عن طريق اختيار عملات متنوعة
    
    :param capital: رأس المال المتاح للتداول
    :param max_trades: الحد الأقصى لعدد الصفقات
    :return: عدد الصفقات الجديدة التي تم فتحها
    """
    try:
        from app.trade_logic import execute_buy
        from app.mexc_api import get_current_price
        
        # الحصول على العملات المتداولة حالياً
        traded_symbols = get_traded_symbols()
        
        # إذا كان عدد العملات المتداولة وصل للحد الأقصى
        if len(traded_symbols) >= max_trades:
            logger.info(f"تم الوصول للحد الأقصى من العملات المتداولة: {len(traded_symbols)}/{max_trades}")
            return 0
        
        # اختيار عملات متنوعة
        available_spots = max_trades - len(traded_symbols)
        diverse_coins = select_diverse_coins(available_spots)
        
        # مبلغ كل صفقة
        per_trade_amount = capital / max_trades
        
        # فتح صفقات جديدة
        opened_count = 0
        
        for coin in diverse_coins:
            # التحقق إذا كان مسموحاً بتداول العملة
            allowed, reason = is_symbol_allowed(coin)
            if not allowed:
                logger.warning(f"تجاهل العملة {coin}: {reason}")
                continue
            
            # الحصول على السعر الحالي
            price = get_current_price(coin)
            if not price:
                logger.warning(f"لم يتم الحصول على سعر العملة {coin}")
                continue
            
            # تنفيذ الشراء
            logger.info(f"محاولة شراء {coin} بمبلغ {per_trade_amount} دولار")
            success = execute_buy(coin, per_trade_amount, price)
            
            if success:
                opened_count += 1
                logger.info(f"تم شراء {coin} بنجاح")
            else:
                logger.error(f"فشل شراء {coin}")
        
        return opened_count
    except Exception as e:
        logger.error(f"خطأ في تنويع الصفقات: {e}")
        return 0

def manage_all_trades():
    """
    إدارة شاملة للصفقات: بيع القديمة، بيع المربحة، تنويع الصفقات
    
    :return: إحصائيات العمليات
    """
    stats = {
        'stale_trades_sold': 0,
        'profitable_trades_sold': 0,
        'new_trades_opened': 0
    }
    
    # بيع الصفقات القديمة
    stats['stale_trades_sold'] = force_sell_stale_trades(max_hours=12)
    
    # بيع الصفقات المربحة
    stats['profitable_trades_sold'] = check_profitable_trades()
    
    # تنويع الصفقات
    stats['new_trades_opened'] = diversify_trades(capital=30, max_trades=5)
    
    logger.info(f"إحصائيات إدارة الصفقات: {stats}")
    return stats