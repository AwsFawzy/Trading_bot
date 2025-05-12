# app/config.py
import os
import logging

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('config')

# الرموز التي لا تدعم واجهة API - تم تقليص القائمة بشكل كبير
API_UNSUPPORTED_SYMBOLS = [
    'SHELLUSDT',     # مشاكل API مع هذه العملة
    'GRIFFAINUSDT',  # مشاكل API مع هذه العملة
    'ITUSDT',        # عملة وهمية أو لديها مشاكل مع API
    'POPCATUSDT'     # عملة وهمية أو لديها مشاكل مع API
]

# العملات ذات التداول العالي للتركيز عليها (تفضيلية)
# تم توسيع القائمة لتشمل المزيد من العملات لضمان تنوع الفرص
HIGH_VOLUME_SYMBOLS = [
    # عملات رئيسية ذات حجم تداول مرتفع جداً
    'BTCUSDT',      # بيتكوين - أعلى حجم تداول
    'ETHUSDT',      # إيثريوم - ثاني أعلى حجم تداول
    'SOLUSDT',      # سولانا - حجم تداول عالي
    'DOGEUSDT',     # دوجكوين - حجم تداول عالي ونشاط مستمر
    'BNBUSDT',      # بينانس كوين - حجم تداول عالي
    
    # عملات ذات حجم تداول جيد وتقلبات مناسبة للأرباح القصيرة
    'XRPUSDT',      # ريبل - حجم تداول عالي
    'MATICUSDT',    # بوليجون - حجم تداول عالي
    'AVAXUSDT',     # أفالانش - حجم تداول جيد
    'ADAUSDT',      # كاردانو - حجم تداول جيد
    'TRXUSDT',      # ترون - حجم تداول عالي
    
    # عملات إضافية ذات نشاط وتقلبات مناسبة
    'SHIBUSDT',     # شيبا اينو - نشاط تداول مرتفع
    'LINKUSDT',     # تشين لينك - تقلبات معتدلة وفرص جيدة
    'DOTUSDT',      # بولكادوت - فرص تداول متكررة
    'ATOMUSDT',     # كوزموس - تقلبات جيدة للتداول قصير المدى
    'LTCUSDT',      # لايتكوين - حجم تداول ثابت
    'FILUSDT',      # فايلكوين - تقلبات جيدة
    'UNIUSDT',      # يونيسواب - حركة سعرية نشطة
    'APTUSDT',      # أبتوس - عملة حديثة نسبياً بتقلبات جيدة
    'STXUSDT',      # ستاكس - فرص تداول قصيرة مربحة
    'NEARUSDT',     # نير - تقلبات سعرية جيدة
    'INJUSDT',      # انجكتيف - حركة سوق نشطة
]

# عدد العملات المراد فحصها في كل دورة - للتنويع وعدم التركيز على عملة واحدة
LIMIT_COINS_SCAN = 25  # زيادة كبيرة لضمان تنوع الفرص ومنع التركيز على عملة واحدة

# إعدادات جديدة لضمان تنويع العملات
ENFORCE_COIN_DIVERSITY = True  # تفعيل آلية إجبار التنويع بين العملات
MAX_TRADES_PER_COIN = 1  # الحد الأقصى للصفقات المسموح بها على نفس العملة في وقت واحد
COOLDOWN_AFTER_TRADE = 7200  # فترة إلزامية بعد بيع عملة قبل إعادة الشراء (بالثواني) - ساعتين

# العملات الأساسية والمستهدفة
BASE_CURRENCY = "USDT"  # العملة الأساسية المستخدمة في التداول
MAX_ACTIVE_TRADES = 10    # الحد الأقصى للصفقات النشطة في نفس الوقت - تم تعديله إلى 10 صفقات لزيادة حركة التداول
TOTAL_RISK_CAPITAL_RATIO = 1.0  # تخصيص 100% من رأس المال للتداول - تم تغييره من 80% إلى 100% حسب طلب المستخدم
AUTO_TRADING_ENABLED = True  # تفعيل وضع التداول التلقائي بشكل دائم

# إعدادات التخزين المؤقت
CACHE_EXPIRY = 600  # مدة التخزين المؤقت الافتراضية بالثواني (10 دقائق)

# إعدادات لكل صفقة
RISK_CAPITAL_RATIO = 0.01  # تخصيص 1% من رأس المال لكل صفقة

# إعدادات الأهداف المتعددة للصفقات - نظام جديد محسن
TAKE_PROFIT = 0.005  # 0.5% هدف الربح الأول (تم زيادته من 0.2% لتحقيق ربح أفضل)
TAKE_PROFIT_2 = 0.01  # 1% هدف الربح الثاني
TAKE_PROFIT_3 = 0.02  # 2% هدف الربح الثالث

# نسب توزيع الكمية على الأهداف
TP1_QUANTITY_RATIO = 0.4  # 40% من الكمية تُباع عند الهدف الأول
TP2_QUANTITY_RATIO = 0.3  # 30% من الكمية تُباع عند الهدف الثاني
TP3_QUANTITY_RATIO = 0.3  # 30% من الكمية تُباع عند الهدف الثالث

# إعدادات وقف الخسارة
STOP_LOSS = 0.01  # 1% وقف خسارة - وفق الاستراتيجية المطلوبة
SMART_STOP_LOSS = True  # تفعيل وقف الخسارة الذكي
SMART_STOP_THRESHOLD = 0.02  # 2% عتبة وقف الخسارة الذكي

# إعدادات البيع المبكر والحد الأدنى
MIN_PROFIT_TO_SELL = 0.005  # الحد الأدنى للربح (0.5%) للبيع المبكر
MAX_TRADE_HOLD_TIME = 4  # أقصى وقت للاحتفاظ بالصفقة (بالساعات) قبل البيع الإلزامي

# إعدادات تحسين الأداء
SCAN_INTERVAL = 300  # فحص السوق كل 5 دقائق (بدلاً من كل دقيقة) - 300 ثانية
CACHE_EXPIRY = 600  # صلاحية البيانات المخزنة مؤقتًا بالثواني (10 دقائق)
LIMIT_COINS_SCAN = 50  # الحد الأقصى لعدد العملات للفحص في كل دورة
API_RATE_LIMIT = 0.2  # حد للطلبات API (5 طلبات في الثانية)

# قائمة العملات ذات حجم التداول المرتفع (تحديث بتاريخ 09-05-2025)
HIGH_VOLUME_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", 
    "DOGEUSDT", "AVAXUSDT", "SHIBUSDT", "ADAUSDT", "DOTUSDT",
    "LDOUSDT", "NEARUSDT", "MATICUSDT", "LINKUSDT", "ATOMUSDT",
    "LTCUSDT", "APTUSDT", "FILUSDT", "UNIUSDT", "TRXUSDT",
    "TONUSDT", "JTOAUSDT", "ETCUSDT", "VETUSDT", "STXUSDT",
    "ARBUSDT", "IMXUSDT", "INJUSDT", "FLOKIUSDT", "RUNEUSDT"
]

# استراتيجية تعدد الإطارات الزمنية
USE_MULTI_TIMEFRAME = True  # استخدام استراتيجية تعدد الإطارات الزمنية
TIMEFRAMES = {
    "trend": "1h",    # لتحديد الاتجاه العام
    "signal": "15m",  # لتحديد مناطق الدعم/المقاومة
    "entry": "5m"     # لتحديد نقاط الدخول والخروج الدقيقة
}

# الحد الأدنى لمبلغ الصفقة بالدولار
MIN_TRADE_AMOUNT = 1.0  # تم تخفيض الحد الأدنى لمبلغ الصفقة إلى $1.0 مؤقتاً بسبب الرصيد الحالي

# وقت الإنتظار بالساعات قبل إغلاق صفقة غير مربحة
TIME_STOP_LOSS_HOURS = 2  # تم تقليله من 4 ساعات إلى 2 ساعات لتحرير رأس المال بشكل أسرع
MAX_TRADE_HOLD_TIME = 4  # الحد الأقصى للاحتفاظ بالصفقة بالساعات حتى لو كانت في خسارة - تم تقليله من 8 إلى 4

# حد الخسارة اليومي
DAILY_LOSS_LIMIT = 0.05  # 5% من رأس المال كحد أقصى للخسارة اليومية

# الحد الأدنى للربح المطلوب للبيع
MIN_PROFIT_TO_SELL = 0.0001  # 0.01% الحد الأدنى للربح المطلوب للبيع

# الحد الأدنى للربح المتوقع لبدء صفقة جديدة
MIN_PROFIT_THRESHOLD = 0.0001  # 0.01% الحد الأدنى للربح المتوقع - تم تخفيضه لزيادة عدد الفرص

# الخسارة عندما يتجاوز السعر حد البيع
STOP_LOSS_MARGIN = 0.01  # الوقف عند 1% إذا كانت الصفقة خاسرة

# المنصة النشطة (MEXC فقط)
ACTIVE_EXCHANGE = "MEXC"

# معلومات API الخاصة بمنصة MEXC
# الحصول على مفاتيح API من متغيرات البيئة بشكل مباشر، بدون قيم افتراضية
API_KEY = os.environ.get("MEXC_API_KEY")
API_SECRET = os.environ.get("MEXC_API_SECRET")

# طباعة جزء من المفاتيح للتحقق (دون كشف المعلومات الحساسة)
logger.info(f"MEXC_API_KEY configured: {'Yes' if API_KEY else 'No'}")
logger.info(f"MEXC_API_SECRET configured: {'Yes' if API_SECRET else 'No'}")
if API_KEY and len(API_KEY) > 10:
    logger.info(f"MEXC_API_KEY starts with: {API_KEY[:5]}... and ends with ...{API_KEY[-5:]}")
    # تحقق من الحالة المجهزة بشكل مسبق
    if API_KEY.startswith("API_KEY") or API_KEY.startswith("api_key"):
        logger.error("WARNING: API Key appears to be invalid, starts with 'API_KEY'")
        logger.error("Please update your API keys from MEXC in the API settings")

# إعدادات التلجرام
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8129105671:AAEW5tgtdAI9GDKyuEFMMN2Wg7q0Stq6aqY")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1336248130")

# تم نقل إعدادات وقف الخسارة الزمني إلى الأعلى

# إعدادات وقف الخسارة التراكمي
DAILY_LOSS_LIMIT = 0.03  # 3% كحد أقصى للخسارة اليومية

# إعدادات فترات المراقبة
MONITOR_INTERVAL_SECONDS = 15  # فترة تحديث مراقبة الصفقات (تم تقليلها لزيادة الاستجابة)

def update_api_keys(new_api_key, new_api_secret):
    """
    تحديث مفاتيح API الخاصة بـ MEXC في وقت التشغيل
    
    :param new_api_key: مفتاح API الجديد
    :param new_api_secret: سر API الجديد
    :return: True في حالة النجاح
    """
    global API_KEY, API_SECRET
    
    # تنظيف المفاتيح (إزالة المسافات وأي أحرف غير مرغوب فيها)
    if new_api_key is not None:
        new_api_key = new_api_key.strip()
    if new_api_secret is not None:
        new_api_secret = new_api_secret.strip()
    
    # التحقق من تنسيق المفاتيح
    if len(new_api_key) < 5 or len(new_api_secret) < 5:
        logger.error("المفاتيح التي تم إدخالها قصيرة جدًا أو غير صالحة")
        return False
        
    # التحقق من الكلمات المفتاحية التي لا ينبغي أن تكون في المفاتيح
    invalid_keywords = ["API_KEY", "api_key", "API_SECRET", "api_secret", "MEXC_API"]
    for keyword in invalid_keywords:
        if keyword in new_api_key or keyword in new_api_secret:
            logger.error(f"المفتاح يحتوي على كلمة محجوزة غير صالحة: {keyword}")
            return False
    
    # تسجيل المعلومات الحالية لتصحيح الأخطاء
    if API_KEY and len(API_KEY) > 6:
        logger.info(f"Current API_KEY before update: {API_KEY[:3]}...{API_KEY[-3:]}")
    else:
        logger.info("Current API_KEY before update: Not configured")
    
    # تحديث المتغيرات العالمية
    API_KEY = new_api_key
    API_SECRET = new_api_secret
    
    # تحديث متغيرات البيئة
    os.environ["MEXC_API_KEY"] = new_api_key
    os.environ["MEXC_API_SECRET"] = new_api_secret
    
    # تأكيد التحديث
    logger.info(f"Updated API_KEY: {new_api_key[:3]}...{new_api_key[-3:] if len(new_api_key) > 6 else ''}")
    logger.info("تم تحديث مفاتيح MEXC API بنجاح")
    
    # إعادة تحميل وحدات API
    try:
        import sys
        import importlib
        if 'app.mexc_api' in sys.modules:
            importlib.reload(sys.modules['app.mexc_api'])
            logger.info("تم إعادة تحميل وحدة mexc_api بنجاح")
    except Exception as e:
        logger.error(f"فشل في إعادة تحميل وحدة mexc_api: {e}")
        
    return True


# تم إزالة دوال OKX

# إضافة SYSTEM_SETTINGS للاستخدام في نظام التداول الموحد
SYSTEM_SETTINGS = {
    'blacklisted_symbols': API_UNSUPPORTED_SYMBOLS,
    'max_trades': MAX_ACTIVE_TRADES,
    'total_capital': 25.0,  # إجمالي رأس المال المخصص للتداول (5 صفقات * 5 دولار)
    'per_trade_amount': 5.0,  # المبلغ المخصص لكل صفقة (5 دولار)
    'min_profit': TAKE_PROFIT,  # الحد الأدنى للربح
    'multi_tp_targets': [TAKE_PROFIT, TAKE_PROFIT_2, TAKE_PROFIT_3],  # أهداف الربح المتعددة
    'tp_quantity_ratios': [TP1_QUANTITY_RATIO, TP2_QUANTITY_RATIO, TP3_QUANTITY_RATIO],  # نسب الكمية لكل هدف
    'max_loss': abs(STOP_LOSS),  # الحد الأقصى للخسارة
    'max_hold_hours': TIME_STOP_LOSS_HOURS,  # الحد الأقصى لوقت الاحتفاظ بالصفقة
    'trade_cycle_interval': 300,  # فترة دورة التداول بالثواني (5 دقائق) - تم تقليله من 15 دقيقة لجعل البوت أكثر نشاطاً
    'enforce_diversity': ENFORCE_COIN_DIVERSITY,  # فرض تنويع العملات
    'prioritized_coins': HIGH_VOLUME_SYMBOLS  # العملات ذات الأولوية
}
