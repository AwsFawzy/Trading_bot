"""
سكريبت لتحديث جميع أهداف الربح في الصفقات الموجودة إلى 0.01%
"""
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_backup():
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    import shutil
    import os
    backup_file = f"active_trades.json.backup.{int(time.time())}"
    shutil.copy2("active_trades.json", backup_file)
    logger.info(f"تم إنشاء نسخة احتياطية: {backup_file}")
    return backup_file

def update_all_profit_targets():
    """تحديث جميع أهداف الربح إلى 0.01%"""
    create_backup()
    
    try:
        with open("active_trades.json", "r") as f:
            data = json.load(f)
        
        open_trades = data.get("open", [])
        updated_count = 0
        
        for trade in open_trades:
            # تحديث أهداف الربح
            if "take_profit_targets" in trade:
                old_targets = trade["take_profit_targets"]
                # حفظ حالة الأهداف المحققة إذا وجدت
                hit_status = [target.get("hit", False) for target in old_targets[:3]]
                
                # تعيين أهداف جديدة مع الحفاظ على حالة التحقق السابقة
                trade["take_profit_targets"] = [
                    {"percent": 0.01, "hit": hit_status[0] if len(hit_status) > 0 else False},
                    {"percent": 0.01, "hit": hit_status[1] if len(hit_status) > 1 else False},
                    {"percent": 0.01, "hit": hit_status[2] if len(hit_status) > 2 else False}
                ]
                updated_count += 1
        
        # حفظ البيانات المحدثة
        with open("active_trades.json", "w") as f:
            json.dump(data, f, indent=4)
        
        logger.info(f"✅ تم تحديث أهداف الربح لـ {updated_count} صفقة إلى 0.01%")
        return updated_count
    
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث أهداف الربح: {e}")
        return 0

if __name__ == "__main__":
    update_all_profit_targets()