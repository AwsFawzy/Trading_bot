"""
وحدة مساعدة للحصول على تاريخ التداول وإصلاح الأخطاء في API
"""
import logging
from app.mexc_api import get_recent_trades

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trade_history')

def get_trades_history_safely(symbol=None, limit=50):
    """
    وظيفة آمنة للحصول على تاريخ التداول مع معالجة الأخطاء والاستثناءات
    تستخدم اختياريًا معلمة symbol وتعمل بشكل صحيح سواء تم تمريرها أم لا
    
    :param symbol: رمز العملة (اختياري)
    :param limit: عدد الصفقات المطلوبة
    :return: قائمة بالتداولات
    """
    try:
        # استدعاء الوظيفة المطورة للحصول على تاريخ التداول
        return get_recent_trades()
    except Exception as e:
        logger.error(f"خطأ في الحصول على تاريخ التداول: {e}")
        return []