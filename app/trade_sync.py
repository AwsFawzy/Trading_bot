"""
مزامنة الصفقات المحلية مع الصفقات الحقيقية على المنصة
يحل مشكلة وجود صفقات وهمية في الملف المحلي لا توجد على المنصة
"""

import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Any

from app.utils import load_json_data, save_json_data
from app.config import MEXC_API_KEY, MEXC_API_SECRET
from app.exchange_manager import get_open_orders, get_recent_trades

logger = logging.getLogger(__name__)

def get_real_mexc_trades():
    """
    الحصول على الصفقات الحقيقية من منصة MEXC
    
    :return: قائمة بالصفقات المفتوحة الحقيقية
    """
    if not MEXC_API_KEY or not MEXC_API_SECRET:
        logger.error("لم يتم تكوين مفاتيح API")
        return []
    
    try:
        # الحصول على الصفقات المفتوحة
        open_orders = get_open_orders() or []
        
        # الحصول على آخر الصفقات المنفذة للتحقق من الصفقات المحلية
        recent_trades = get_recent_trades(limit=50) or []
        
        # جمع المعلومات
        return {
            "open_orders": open_orders,
            "recent_trades": recent_trades
        }
    except Exception as e:
        logger.error(f"خطأ في الحصول على الصفقات الحقيقية: {e}")
        return {"open_orders": [], "recent_trades": []}


def verify_and_remove_phantom_trades():
    """
    تحقق من وجود صفقات وهمية (غير موجودة فعلياً على المنصة) وإزالتها
    
    :return: عدد الصفقات الوهمية التي تمت إزالتها
    """
    trades = load_json_data("active_trades.json", [])
    logger.info(f"تحميل {len(trades)} صفقة من ملف active_trades.json")
    
    if not trades:
        return 0
    
    # الحصول على البيانات الحقيقية من المنصة
    api_data = get_real_mexc_trades()
    api_order_ids = []
    
    # التعامل بشكل آمن مع البيانات - التحقق من أن api_data هو قاموس
    if isinstance(api_data, dict) and "open_orders" in api_data:
        api_order_ids = [order.get("orderId") for order in api_data["open_orders"] if isinstance(order, dict)]
    elif isinstance(api_data, list):
        # في حالة عاد قائمة بدلاً من قاموس
        api_order_ids = [order.get("orderId") for order in api_data if isinstance(order, dict)]
    
    # تحويل البيانات إلى مجموعة للبحث السريع
    api_order_ids_set = set(api_order_ids)
    
    # إعداد القائمة النهائية
    valid_trades = []
    phantom_trades = []
    
    for trade in trades:
        if trade.get("status") != "OPEN":
            # الصفقات المغلقة تبقى كما هي
            valid_trades.append(trade)
            continue
        
        order_id = trade.get("orderId")
        
        # إذا كان الأمر موجوداً في المنصة، فهو صالح
        if order_id in api_order_ids_set:
            valid_trades.append(trade)
        else:
            # تحقق إضافي من خلال البيانات الإضافية
            if trade.get("metadata", {}).get("api_confirmed", False):
                # إذا تم تأكيد الصفقة سابقاً من API، نحتفظ بها
                valid_trades.append(trade)
            else:
                # هذه صفقة وهمية
                phantom_trades.append(trade)
                logger.warning(f"صفقة وهمية: {trade.get('symbol')} - {order_id}")
    
    # تحديث الملف إذا وجدت صفقات وهمية
    if phantom_trades:
        logger.info(f"تم العثور على {len(phantom_trades)} صفقة وهمية وسيتم إزالتها")
        save_json_data("active_trades.json", valid_trades)
        
        # نسخ احتياطي للصفقات الوهمية للتحقق
        backup_file = f"phantom_trades_{int(time.time())}.json"
        with open(backup_file, "w") as f:
            json.dump(phantom_trades, f, indent=2)
        logger.info(f"تم حفظ نسخة احتياطية من الصفقات الوهمية في: {backup_file}")
    
    return len(phantom_trades)


def clean_all_phantom_trades():
    """
    إزالة جميع الصفقات الوهمية وإعادة ضبط الملف مع الصفقات الحقيقية فقط
    
    :return: عدد الصفقات المتبقية بعد التنظيف
    """
    removed_count = verify_and_remove_phantom_trades()
    
    if removed_count > 0:
        logger.info(f"تم إزالة {removed_count} صفقة وهمية بنجاح")
    else:
        logger.info("لم يتم العثور على أي صفقات وهمية")
    
    # عرض الصفقات المتبقية
    remaining_trades = load_json_data("active_trades.json", [])
    open_count = len([t for t in remaining_trades if t.get("status") == "OPEN"])
    
    logger.info(f"بعد التنظيف: {open_count} صفقة مفتوحة من أصل {len(remaining_trades)}")
    
    return len(remaining_trades)


def add_real_trade_to_file(trade_data: Dict[str, Any]):
    """
    إضافة صفقة حقيقية إلى ملف الصفقات
    
    :param trade_data: بيانات الصفقة
    :return: True إذا تمت الإضافة بنجاح
    """
    if not trade_data or "symbol" not in trade_data:
        logger.error("بيانات الصفقة غير صالحة")
        return False
    
    trades = load_json_data("active_trades.json", [])
    
    # تأكد من أن الصفقة غير موجودة بالفعل
    order_id = trade_data.get("orderId")
    existing = next((t for t in trades if t.get("orderId") == order_id), None)
    
    if existing:
        logger.info(f"الصفقة بمعرف {order_id} موجودة بالفعل في الملف")
        return False
    
    # إضافة البيانات الإضافية
    if "metadata" not in trade_data:
        trade_data["metadata"] = {}
    
    trade_data["metadata"]["api_confirmed"] = True
    trade_data["metadata"]["added_at"] = datetime.now().timestamp()
    
    # إضافة الصفقة وحفظ الملف
    trades.append(trade_data)
    save_json_data("active_trades.json", trades)
    
    logger.info(f"تمت إضافة صفقة حقيقية جديدة: {trade_data.get('symbol')} - {order_id}")
    
    return True


# تنفيذ تنظيف فوري عند استيراد الوحدة
try:
    count = clean_all_phantom_trades()
    logger.info(f"تم تنظيف ملف الصفقات. المتبقي: {count} صفقة")
except Exception as e:
    logger.error(f"خطأ أثناء تنظيف الصفقات الوهمية: {e}")