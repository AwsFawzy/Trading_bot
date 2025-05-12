"""
نظام منع تكرار الصفقات على نفس العملة
يقوم هذا النظام بمنع تكرار الصفقات على نفس العملة بشكل صارم وحازم
ومراقبة وإصلاح أي محاولات لفتح صفقات جديدة على عملات متداولة بالفعل

تم تصميم هذا النظام كطبقة أمان إضافية وأخيرة بعد عدة طبقات أخرى
من الآليات الوقائية التي تمنع تكرار الصفقات.
"""

import os
import json
import logging
import time
import threading
import random
from typing import List, Set, Dict, Any

logger = logging.getLogger(__name__)

# قائمة العملات البديلة للتداول إذا لم تكن هناك خيارات أخرى
ALTERNATIVE_COINS = [
    'BTCUSDT',  # بيتكوين
    'ETHUSDT',  # إيثريوم
    'BNBUSDT',  # بينانس كوين
    'ADAUSDT',  # كاردانو
    'DOGEUSDT',  # دوجكوين
    'DOTUSDT',  # بولكادوت
    'SOLUSDT',  # سولانا
    'AVAXUSDT',  # افالانش
    'MATICUSDT',  # بوليجون
    'LINKUSDT',  # تشينلينك
    'LTCUSDT',  # لايتكوين
    'BCHUSDT',  # بيتكوين كاش
    'ATOMUSDT',  # كوزموس
    'UNIUSDT',  # يونيسواب
    'VETUSDT',  # فيتشين
    'ICPUSDT',  # إنترنت كمبيوتر
    'FILUSDT',  # فايلكوين
    'ETCUSDT',  # إيثريوم كلاسيك
    'TRXUSDT',  # ترون
    'XLMUSDT',  # ستيلر
]

# قفل لضمان عمليات آمنة عند التحقق من الصفقات المفتوحة وتعديلها
trades_lock = threading.Lock()

def get_active_trades_file_path() -> str:
    """
    الحصول على مسار ملف الصفقات النشطة
    
    :return: مسار ملف الصفقات النشطة
    """
    return os.path.join(os.getcwd(), 'active_trades.json')

def create_backup(filename='active_trades.json'):
    """
    إنشاء نسخة احتياطية من ملف الصفقات
    
    :param filename: اسم الملف المراد عمل نسخة احتياطية منه
    """
    try:
        backup_name = f"{filename}.backup.{int(time.time())}"
        os.system(f"cp {filename} {backup_name}")
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")

def load_active_trades() -> Dict[str, List[Dict[str, Any]]]:
    """
    تحميل الصفقات النشطة من الملف
    
    :return: قاموس يحتوي على الصفقات المفتوحة والمغلقة
    """
    file_path = get_active_trades_file_path()
    
    with trades_lock:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    return json.load(file)
            else:
                return {"open": [], "closed": []}
        except Exception as e:
            logger.error(f"خطأ في تحميل الصفقات النشطة: {e}")
            return {"open": [], "closed": []}

def save_active_trades(trades_data: Dict[str, List[Dict[str, Any]]]):
    """
    حفظ الصفقات النشطة في الملف
    
    :param trades_data: قاموس يحتوي على الصفقات المفتوحة والمغلقة
    """
    file_path = get_active_trades_file_path()
    
    with trades_lock:
        try:
            # إنشاء نسخة احتياطية قبل الحفظ
            create_backup()
            
            with open(file_path, 'w') as file:
                json.dump(trades_data, file, indent=2)
                
            logger.info(f"تم حفظ {len(trades_data.get('open', []))} صفقة مفتوحة و {len(trades_data.get('closed', []))} صفقة مغلقة")
        except Exception as e:
            logger.error(f"خطأ في حفظ الصفقات النشطة: {e}")

def get_currently_traded_symbols() -> Set[str]:
    """
    الحصول على مجموعة العملات المتداولة حالياً
    
    :return: مجموعة تحتوي على رموز العملات المتداولة حالياً
    """
    trades_data = load_active_trades()
    open_trades = trades_data.get('open', [])
    
    # استخراج الرموز من الصفقات المفتوحة
    symbols = {trade.get('symbol', '').upper() for trade in open_trades if trade.get('symbol')}
    
    # إضافة XRPUSDT لمنعها تماماً بغض النظر عن حالتها
    symbols.add('XRPUSDT')
    
    return symbols

def is_symbol_traded(symbol: str) -> bool:
    """
    التحقق مما إذا كانت العملة متداولة بالفعل
    
    :param symbol: رمز العملة
    :return: True إذا كانت العملة متداولة بالفعل
    """
    return symbol.upper() in get_currently_traded_symbols()

def enforce_trade_diversity() -> int:
    """
    فرض التنوع في الصفقات بإغلاق الصفقات المكررة على نفس العملة
    
    :return: عدد الصفقات المغلقة
    """
    with trades_lock:
        trades_data = load_active_trades()
        open_trades = trades_data.get('open', [])
        closed_trades = trades_data.get('closed', [])
        
        # العملات التي تم التعامل معها بالفعل
        processed_symbols = set()
        # الصفقات التي سيتم الاحتفاظ بها
        trades_to_keep = []
        # الصفقات التي سيتم إغلاقها
        trades_to_close = []
        
        # فرز الصفقات حسب التاريخ (الأحدث أولاً)
        open_trades.sort(key=lambda x: x.get('enter_time', 0), reverse=True)
        
        for trade in open_trades:
            symbol = trade.get('symbol', '').upper()
            
            # تخطي الصفقات التي لا تحتوي على رمز
            if not symbol:
                trades_to_keep.append(trade)
                continue
            
            # إذا كانت العملة لم تتم معالجتها بعد، احتفظ بالصفقة
            if symbol not in processed_symbols:
                processed_symbols.add(symbol)
                trades_to_keep.append(trade)
            # إذا كانت العملة قد تمت معالجتها، أغلق الصفقة
            else:
                # تحديث حالة الصفقة وإضافة سبب الإغلاق
                trade['status'] = 'closed'
                trade['exit_time'] = int(time.time() * 1000)
                trade['exit_price'] = trade.get('current_price', trade.get('enter_price', 0))
                trade['exit_reason'] = 'enforced_diversity'
                trade['profit_loss_percent'] = 0
                trade['enforced_close'] = True
                
                trades_to_close.append(trade)
                logger.warning(f"⚠️ إغلاق صفقة مكررة على {symbol} (ID: {trade.get('id')})")
        
        # تحديث قوائم الصفقات
        trades_data['open'] = trades_to_keep
        trades_data['closed'].extend(trades_to_close)
        
        # حفظ التغييرات
        save_active_trades(trades_data)
        
        # عدد الصفقات المغلقة
        closed_count = len(trades_to_close)
        
        if closed_count > 0:
            logger.warning(f"🔴 تم إغلاق {closed_count} صفقة مكررة لفرض التنويع")
        
        return closed_count

def is_trade_allowed(symbol: str) -> bool:
    """
    التحقق مما إذا كان مسموحاً بفتح صفقة على عملة معينة
    مع تطبيق جميع قواعد الحماية المتعددة
    
    :param symbol: رمز العملة
    :return: True إذا كان مسموحاً بفتح صفقة، False إذا لم يكن
    """
    # تطبيق قاعدة التنويع أولاً
    enforce_trade_diversity()
    
    # كما أن XRPUSDT ممنوعة بشكل دائم نظراً للمشاكل السابقة
    if symbol.upper() == 'XRPUSDT':
        logger.warning(f"🔴 العملة {symbol} ممنوعة بشكل دائم من التداول")
        return False
    
    # التحقق مما إذا كانت العملة متداولة بالفعل
    if is_symbol_traded(symbol):
        logger.warning(f"🔴 العملة {symbol} متداولة بالفعل")
        return False
    
    return True

def recommend_diverse_trade_targets(count: int = 5) -> List[str]:
    """
    توصية بعملات متنوعة للتداول بناءً على العملات المتداولة حالياً
    
    :param count: عدد العملات الموصى بها
    :return: قائمة بالعملات الموصى بها للتداول
    """
    # الحصول على العملات المتداولة حالياً
    traded_symbols = get_currently_traded_symbols()
    
    # العملات المتاحة للتداول (غير المتداولة حالياً)
    available_symbols = [s for s in ALTERNATIVE_COINS if s not in traded_symbols]
    
    # إذا لم تكن هناك عملات متاحة، استخدام قائمة العملات البديلة بالكامل
    if not available_symbols:
        available_symbols = ALTERNATIVE_COINS.copy()
    
    # خلط العملات المتاحة لضمان التنوع
    random.shuffle(available_symbols)
    
    # اختيار عدد محدد من العملات
    return available_symbols[:count]

def get_trade_allocation(balance: float) -> float:
    """
    حساب مبلغ التداول لكل صفقة مع توزيع متساوٍ على 5 صفقات
    
    :param balance: الرصيد الإجمالي المتاح للتداول
    :return: مبلغ التداول لكل صفقة
    """
    # يتم تقسيم الرصيد على 5 صفقات مختلفة
    return round(balance / 5, 2)

def reset_traded_symbols():
    """
    إعادة تعيين قائمة العملات المتداولة عن طريق إغلاق جميع الصفقات المفتوحة
    تُستخدم في حالات الطوارئ فقط
    
    :return: عدد الصفقات المغلقة
    """
    with trades_lock:
        trades_data = load_active_trades()
        open_trades = trades_data.get('open', [])
        closed_trades = trades_data.get('closed', [])
        
        # تحديث حالة جميع الصفقات المفتوحة
        for trade in open_trades:
            trade['status'] = 'closed'
            trade['exit_time'] = int(time.time() * 1000)
            trade['exit_price'] = trade.get('current_price', trade.get('enter_price', 0))
            trade['exit_reason'] = 'emergency_reset'
            trade['profit_loss_percent'] = 0
            trade['enforced_close'] = True
        
        # تحديث قوائم الصفقات
        closed_trades.extend(open_trades)
        trades_data['open'] = []
        trades_data['closed'] = closed_trades
        
        # حفظ التغييرات
        save_active_trades(trades_data)
        
        # عدد الصفقات المغلقة
        closed_count = len(open_trades)
        
        if closed_count > 0:
            logger.warning(f"🔴 تم إغلاق {closed_count} صفقة في عملية إعادة تعيين الطوارئ")
        
        return closed_count

# تطبيق التنويع عند استيراد الملف
enforce_trade_diversity()