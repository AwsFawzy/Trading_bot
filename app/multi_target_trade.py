"""
نظام الأهداف المتعددة للتداول
يقسم كل صفقة إلى أجزاء متعددة ويضع هدف ربح مختلف لكل جزء
"""

import logging
import json
import math
from typing import Dict, List, Tuple, Any
from datetime import datetime
from app.utils import load_json_data, save_json_data

logger = logging.getLogger(__name__)

# إعدادات افتراضية للنظام متعدد الأهداف
DEFAULT_TARGETS = {
    "target1": {"profit_pct": 0.005, "quantity_pct": 0.40},  # أول 40% بهدف ربح 0.5%
    "target2": {"profit_pct": 0.01, "quantity_pct": 0.30},   # 30% التالية بهدف ربح 1%
    "target3": {"profit_pct": 0.02, "quantity_pct": 0.30}    # آخر 30% بهدف ربح 2%
}


def setup_multi_target_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    """
    إعداد صفقة متعددة الأهداف
    
    :param trade: بيانات الصفقة الأساسية
    :return: بيانات الصفقة مع إعدادات الأهداف المتعددة
    """
    # نسخة عميقة من الصفقة لتجنب تغيير الأصل
    enriched_trade = dict(trade)
    
    # إضافة كامل معلومات الصفقة الأصلية
    if "id" not in enriched_trade and "timestamp" in enriched_trade:
        enriched_trade["id"] = str(enriched_trade["timestamp"])
    
    total_quantity = float(enriched_trade.get("quantity", 0))
    entry_price = float(enriched_trade.get("entry_price", 0))
    
    # إضافة معلومات الأهداف المتعددة إذا لم تكن موجودة
    if "targets" not in enriched_trade:
        targets = {}
        
        for target_name, target_info in DEFAULT_TARGETS.items():
            profit_pct = target_info["profit_pct"]
            quantity_pct = target_info["quantity_pct"]
            
            # حساب الكمية والأسعار لكل هدف
            target_quantity = round(total_quantity * quantity_pct, 8)
            target_price = round(entry_price * (1 + profit_pct), 8)
            
            targets[target_name] = {
                "price": target_price,
                "quantity": target_quantity,
                "profit_pct": profit_pct,
                "executed": False,
                "executed_price": None,
                "executed_time": None
            }
        
        enriched_trade["targets"] = targets
    
    return enriched_trade


def update_trade_with_targets(trade_id: str) -> bool:
    """
    تحديث صفقة موجودة بإضافة أهداف متعددة
    
    :param trade_id: معرف الصفقة
    :return: True إذا تم التحديث بنجاح
    """
    trades = load_json_data("active_trades.json", [])
    updated = False
    
    for i, trade in enumerate(trades):
        current_id = trade.get("id", str(trade.get("timestamp", "")))
        
        if current_id == trade_id:
            # تأكد من وجود معرف للصفقة
            if "id" not in trade:
                trade["id"] = current_id
            
            # إضافة أهداف متعددة إذا لم تكن موجودة
            if "targets" not in trade:
                updated_trade = setup_multi_target_trade(trade)
                trades[i] = updated_trade
                updated = True
    
    if updated:
        save_json_data("active_trades.json", trades)
        logger.info(f"تم تحديث الصفقة {trade_id} بأهداف متعددة")
    else:
        logger.warning(f"لم يتم العثور على الصفقة {trade_id}")
    
    return updated


def check_target_hit(trade: Dict[str, Any], current_price: float) -> List[str]:
    """
    التحقق من تحقيق أي من أهداف الصفقة
    
    :param trade: بيانات الصفقة
    :param current_price: السعر الحالي
    :return: قائمة بالأهداف المحققة
    """
    logger.debug(f"فحص الأهداف للصفقة: {trade.get('symbol', 'unknown')}, السعر الحالي: {current_price}")
    
    if not isinstance(trade, dict):
        logger.error(f"خطأ: الصفقة ليست قاموس، بل: {type(trade)}")
        return []
        
    if "targets" not in trade or not isinstance(trade["targets"], dict):
        logger.debug(f"لا توجد أهداف في الصفقة أو targets ليس قاموس: {type(trade.get('targets', None))}")
        return []
    
    hit_targets = []
    
    try:
        entry_price = float(trade.get("entry_price", 0))
        
        # التعامل مع الهيكل الجديد للأهداف
        # فحص الأهداف السعرية
        if "price_targets" in trade["targets"] and isinstance(trade["targets"]["price_targets"], dict):
            if current_price >= float(trade["targets"]["price_targets"].get("target1", 0)):
                hit_targets.append("price_targets")
                
        # يمكن إضافة فحص إضافي للأهداف الأخرى إذا لزم الأمر
        if "quantity_distribution" in trade["targets"] and isinstance(trade["targets"]["quantity_distribution"], dict):
            if current_price >= float(trade.get("entry_price", 0)) * 1.005:  # تحقق من زيادة السعر بنسبة 0.5% على الأقل
                hit_targets.append("quantity_distribution")
                
    except Exception as e:
        logger.error(f"خطأ في فحص الأهداف: {e}")
    
    return hit_targets


def execute_target_sell(trade_id: str, target_name: str, current_price: float = None) -> bool:
    """
    تنفيذ بيع هدف معين
    
    :param trade_id: معرف الصفقة
    :param target_name: اسم الهدف
    :param current_price: السعر الحالي (اختياري)
    :return: True إذا تم التنفيذ بنجاح
    """
    logger.debug(f"تنفيذ هدف بيع للصفقة: {trade_id}, الهدف: {target_name}, السعر: {current_price}")
    trades = load_json_data("active_trades.json", [])
    executed = False
    
    if not isinstance(trades, list):
        logger.error(f"خطأ: trades ليس قائمة، بل: {type(trades)}")
        return False
        
    for i, trade in enumerate(trades):
        if not isinstance(trade, dict):
            logger.error(f"خطأ في موضع {i}: الصفقة ليست قاموس، بل: {type(trade)}")
            continue
            
        current_id = trade.get("id", str(trade.get("timestamp", "")))
        logger.debug(f"مقارنة ID: {current_id} مع {trade_id}")
        
        if current_id == trade_id:
            logger.debug(f"تم العثور على الصفقة المناسبة في الموضع {i}")
            
            # التحقق من وجود الأهداف في الصفقة
            if "targets" not in trade or not isinstance(trade["targets"], dict):
                logger.warning(f"لا توجد أهداف في الصفقة {trade_id}")
                return False
            
            # تحديد كمية البيع بناءً على نوع الهدف
            target_quantity = 0
            symbol = trade.get("symbol")
            
            if target_name == "price_targets" and "quantity_distribution" in trade["targets"]:
                # استخدام كمية الهدف الأول كعينة
                if isinstance(trade["targets"]["quantity_distribution"], dict):
                    # جمع كل الكميات المتاحة
                    for qty_key, qty_val in trade["targets"]["quantity_distribution"].items():
                        target_quantity += float(qty_val) if isinstance(qty_val, (int, float, str)) else 0
            
            if target_quantity <= 0:
                logger.warning(f"كمية غير صالحة {target_quantity} للهدف {target_name} للصفقة {trade_id}")
                return False
            
            # تنفيذ أمر البيع
            try:
                if not symbol:
                    logger.error(f"رمز العملة غير متوفر في الصفقة {trade_id}")
                    return False
                    
                if current_price is None:
                    # الحصول على السعر الحالي من API
                    from app.exchange_manager import get_current_price
                    current_price = float(get_current_price(symbol))
                
                # تنفيذ البيع
                from app.exchange_manager import execute_market_sell
                sell_result = execute_market_sell(symbol, target_quantity)
                
                if sell_result and "orderId" in sell_result:
                    # إضافة الهدف إلى قائمة الأهداف المكتملة إذا لم تكن موجودة
                    if "completed_targets" not in trade["targets"]:
                        trade["targets"]["completed_targets"] = []
                    
                    if target_name not in trade["targets"]["completed_targets"]:
                        trade["targets"]["completed_targets"].append(target_name)
                    
                    # إغلاق الصفقة إذا تم تنفيذ جميع الأهداف
                    completed_targets = len(trade["targets"]["completed_targets"])
                    all_executed = completed_targets >= 2  # إذا تم تنفيذ هدفين على الأقل، نعتبر الصفقة مكتملة
                    
                    if all_executed:
                        trade["status"] = "CLOSED"
                        trade["exit_price"] = current_price
                        trade["exit_time"] = datetime.now().timestamp()
                        
                        # حساب الربح النهائي
                        entry_price = float(trade.get("entry_price", 0))
                        total_quantity = float(trade.get("quantity", 0))
                        profit_pct = (current_price - entry_price) / entry_price * 100
                        
                        trade["profit_pct"] = profit_pct
                        trade["profit_usdt"] = (current_price - entry_price) * total_quantity
                        
                        # إضافة العملة إلى فترة الراحة
                        from app.enforce_diversity import add_coin_to_cooldown
                        if symbol:
                            add_coin_to_cooldown(symbol, hours=2)  # فترة راحة لمدة ساعتين
                    
                    # حفظ التغييرات
                    trades[i] = trade
                    save_json_data("active_trades.json", trades)
                    executed = True
                    
                    # سجل العملية
                    logger.info(f"✅ تم تنفيذ بيع الهدف {target_name} للصفقة {trade_id} بسعر {current_price}")
                    if all_executed:
                        logger.info(f"🎯 تم إغلاق الصفقة {trade_id} بربح {profit_pct:.2f}%")
                else:
                    logger.error(f"❌ فشل تنفيذ بيع الهدف {target_name} للصفقة {trade_id}")
            
            except Exception as e:
                logger.error(f"خطأ أثناء تنفيذ بيع الهدف {target_name} للصفقة {trade_id}: {e}")
            
            break
    
    return executed


def get_remaining_quantity(trade: Dict[str, Any]) -> float:
    """
    حساب الكمية المتبقية في الصفقة بعد تنفيذ بعض الأهداف
    
    :param trade: بيانات الصفقة
    :return: الكمية المتبقية
    """
    if "targets" not in trade:
        return float(trade.get("quantity", 0))
    
    # التعامل مع الهيكل الجديد للأهداف
    if "quantity_distribution" in trade["targets"] and isinstance(trade["targets"]["quantity_distribution"], dict):
        # فحص قائمة الأهداف المكتملة
        completed_targets = trade["targets"].get("completed_targets", [])
        
        # إذا كان هناك هدف مكتمل، افترض أنه تم بيع نصف الكمية
        if "price_targets" in completed_targets:
            return float(trade.get("quantity", 0)) * 0.5
        
        # إذا كانت كل الأهداف مكتملة، لا يوجد كمية متبقية
        if len(completed_targets) >= 2:
            return 0
            
        # لم يتم تنفيذ أي هدف، إرجاع الكمية الكاملة
        return float(trade.get("quantity", 0))
    
    # في حالة استخدام الهيكل القديم (للتوافق مع الإصدارات السابقة)
    remaining = 0
    for target_name, target_info in trade["targets"].items():
        if isinstance(target_info, dict) and not target_info.get("executed", False):
            remaining += float(target_info.get("quantity", 0))
    
    return remaining


def update_all_trades_with_targets():
    """
    تحديث جميع الصفقات المفتوحة بنظام الأهداف المتعددة
    """
    trades = load_json_data("active_trades.json", [])
    updated_count = 0
    
    for i, trade in enumerate(trades):
        if trade.get("status") == "OPEN" and "targets" not in trade:
            updated_trade = setup_multi_target_trade(trade)
            trades[i] = updated_trade
            updated_count += 1
    
    if updated_count > 0:
        save_json_data("active_trades.json", trades)
        logger.info(f"تم تحديث {updated_count} صفقة بنظام الأهداف المتعددة")
    
    return updated_count


# تنفيذ التحديث عند استيراد الوحدة
try:
    count = update_all_trades_with_targets()
    if count > 0:
        logger.info(f"تم تحديث {count} صفقة بنظام الأهداف المتعددة عند البدء")
except Exception as e:
    logger.error(f"خطأ أثناء تحديث الصفقات بنظام الأهداف المتعددة: {e}")