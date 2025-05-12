"""
سكريبت بسيط لمنع تداول XRPUSDT
"""

import os
import json
import time
import logging

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_backup():
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        backup_file = f"active_trades.json.backup.{int(time.time())}"
        os.system(f"cp active_trades.json {backup_file}")
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_file}")
    except Exception as e:
        logger.error(f"خطأ في إنشاء النسخة الاحتياطية: {e}")

def block_xrpusdt():
    """منع تداول XRPUSDT وإغلاق أي صفقات مفتوحة عليها"""
    try:
        # تحميل الصفقات
        if not os.path.exists('active_trades.json'):
            logger.warning("ملف الصفقات غير موجود")
            return 0
            
        with open('active_trades.json', 'r') as f:
            try:
                data = json.load(f)
                
                # تحويل إلى التنسيق الجديد إذا لزم الأمر
                if isinstance(data, list):
                    trades_data = {
                        'open': [t for t in data if t.get('status') == 'OPEN'],
                        'closed': [t for t in data if t.get('status') != 'OPEN']
                    }
                else:
                    trades_data = data
            except json.JSONDecodeError:
                logger.error("خطأ في تنسيق ملف الصفقات")
                return 0
        
        # معالجة الصفقات المفتوحة
        open_trades = trades_data.get('open', [])
        closed_trades = trades_data.get('closed', [])
        
        # البحث عن صفقات XRPUSDT
        xrp_trades = []
        other_trades = []
        
        for trade in open_trades:
            if trade.get('symbol', '').upper() == 'XRPUSDT':
                # تعديل حالة الصفقة وإغلاقها
                trade['status'] = 'closed'
                trade['exit_time'] = int(time.time() * 1000)
                trade['exit_reason'] = 'blocked_symbol'
                trade['enforced_close'] = True
                xrp_trades.append(trade)
            else:
                other_trades.append(trade)
        
        # تحديث القوائم
        closed_count = len(xrp_trades)
        if closed_count > 0:
            # إنشاء نسخة احتياطية
            create_backup()
            
            # تحديث الصفقات
            trades_data['open'] = other_trades
            trades_data['closed'].extend(xrp_trades)
            
            # حفظ التغييرات
            with open('active_trades.json', 'w') as f:
                json.dump(trades_data, f, indent=2)
                
            logger.info(f"تم إغلاق {closed_count} صفقة على XRPUSDT")
        else:
            logger.info("لا توجد صفقات مفتوحة على XRPUSDT")
            
        return closed_count
    except Exception as e:
        logger.error(f"خطأ في معالجة الصفقات: {e}")
        return 0

def main():
    """الدالة الرئيسية"""
    closed_count = block_xrpusdt()
    print(f"تم إغلاق {closed_count} صفقة على XRPUSDT")
    
    # إضافة XRPUSDT إلى القائمة السوداء
    try:
        from app.config import update_blacklist
        update_blacklist(['XRPUSDT'])
        print("تم إضافة XRPUSDT إلى القائمة السوداء")
    except:
        print("لم يتم العثور على وظيفة update_blacklist")
    
    return closed_count

if __name__ == "__main__":
    main()