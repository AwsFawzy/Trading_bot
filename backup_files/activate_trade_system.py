"""
أداة سريعة لتنشيط نظام التداول المحسن حسب الحاجة
تساعد على إدارة البوت بطريقة مباشرة وسهلة
"""

import argparse
import logging
import sys
import time
import json
import os

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_active_trades():
    """الحصول على الصفقات النشطة حالياً"""
    try:
        if not os.path.exists('active_trades.json'):
            logger.info("ملف الصفقات غير موجود")
            return []
            
        with open('active_trades.json', 'r') as f:
            data = json.load(f)
            
        if isinstance(data, dict) and 'open' in data:
            return data['open']
        elif isinstance(data, list):
            return [t for t in data if t.get('status') == 'OPEN']
        else:
            logger.warning(f"صيغة غير متوقعة لملف الصفقات: {type(data)}")
            return []
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الصفقات: {e}")
        return []

def check_api_connectivity():
    """التحقق من الاتصال بواجهة برمجة التطبيقات"""
    try:
        from app.mexc_api import get_exchange_info
        
        # محاولة جلب معلومات السوق
        info = get_exchange_info()
        
        if info and isinstance(info, dict) and 'symbols' in info:
            symbol_count = len(info['symbols'])
            logger.info(f"تم الاتصال بنجاح، عدد العملات: {symbol_count}")
            return True
        else:
            logger.error(f"فشل الاتصال، استجابة غير صالحة: {info}")
            return False
    except Exception as e:
        logger.error(f"خطأ في الاتصال بواجهة برمجة التطبيقات: {e}")
        return False

def clean_fake_trades():
    """تنظيف الصفقات الوهمية التي لا تحتوي على بيانات حقيقية أو غير موجودة على المنصة"""
    try:
        # استخدام الوظيفة المحسنة من وحدة clean_trades
        try:
            logger.info("محاولة استخدام وظيفة التنظيف المتقدمة...")
            from app.clean_trades import clean_fake_trades as enhanced_clean_fake_trades
            result = enhanced_clean_fake_trades()
            
            logger.info(f"✅ تم تنظيف {result['cleaned_count']} صفقة وهمية باستخدام الوظيفة المحسنة")
            logger.info(f"الصفقات المفتوحة المتبقية: {result['current_count']} من أصل {result['original_count']}")
            
            return True
        except ImportError as ie:
            logger.warning(f"⚠️ لم يتم العثور على وحدة clean_trades المحسنة: {ie}")
            logger.warning("سيتم استخدام الطريقة التقليدية للتنظيف...")
        except Exception as advanced_error:
            logger.error(f"❌ فشل استخدام وظيفة التنظيف المتقدمة: {advanced_error}")
            
        # الطريقة التقليدية في حال فشل الوظيفة المحسنة
        if not os.path.exists('active_trades.json'):
            logger.warning("ملف الصفقات غير موجود")
            return False
            
        # إنشاء نسخة احتياطية
        backup_name = f"active_trades.json.backup.{int(time.time())}"
        os.system(f"cp active_trades.json {backup_name}")
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
        
        # قراءة الملف
        with open('active_trades.json', 'r') as f:
            data = json.load(f)
            
        if isinstance(data, dict) and 'open' in data:
            # فلترة الصفقات الوهمية
            old_count = len(data['open'])
            
            # الاحتفاظ فقط بالصفقات الحقيقية
            data['open'] = [
                t for t in data['open'] 
                if (t.get('entry_price', 0) > 0) and 
                   (t.get('quantity', 0) > 0) and 
                   not (t.get('metadata', {}).get('test_trade', False)) and
                   not (t.get('test_trade', False)) and 
                   (t.get('api_executed', True))
            ]
            
            new_count = len(data['open'])
            removed = old_count - new_count
            
            # حفظ البيانات المنظفة
            with open('active_trades.json', 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"تم تنظيف {removed} صفقة وهمية، ولم يتبق سوى {new_count} صفقة حقيقية")
            return True
        else:
            logger.warning(f"صيغة غير متوقعة لملف الصفقات: {type(data)}")
            return False
    except Exception as e:
        logger.error(f"خطأ في تنظيف الصفقات الوهمية: {e}")
        return False

def reset_all_trades():
    """إعادة ضبط جميع الصفقات"""
    try:
        if os.path.exists('active_trades.json'):
            # إنشاء نسخة احتياطية
            backup_name = f"active_trades.json.backup.{int(time.time())}"
            os.system(f"cp active_trades.json {backup_name}")
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
            
            # إنشاء ملف جديد
            with open('active_trades.json', 'w') as f:
                json.dump({'open': [], 'closed': []}, f, indent=2)
                
            logger.info("تم إعادة ضبط ملف الصفقات")
            return True
        else:
            logger.warning("ملف الصفقات غير موجود")
            return False
    except Exception as e:
        logger.error(f"خطأ في إعادة ضبط الصفقات: {e}")
        return False

def activate_continuous_trader():
    """تنشيط خدمة التداول المستمر"""
    try:
        from app.continuous_trader import start_trader, get_trader_status
        
        # التحقق من حالة التشغيل الحالية
        status = get_trader_status()
        
        if status['status'] == 'running':
            logger.info("خدمة التداول المستمر قيد التشغيل بالفعل")
            return True
        
        # تشغيل الخدمة
        success = start_trader()
        
        if success:
            logger.info("تم تنشيط خدمة التداول المستمر بنجاح")
        else:
            logger.error("فشل تنشيط خدمة التداول المستمر")
            
        return success
    except Exception as e:
        logger.error(f"خطأ في تنشيط خدمة التداول المستمر: {e}")
        return False

def run_fix_and_diversify():
    """تشغيل سكريبت إصلاح وتنويع الصفقات"""
    try:
        import subprocess
        
        # تشغيل السكريبت
        result = subprocess.run(['python', 'fix_and_diversify.py'], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"تم تنفيذ سكريبت الإصلاح والتنويع بنجاح: {result.stdout}")
            return True
        else:
            logger.error(f"فشل تنفيذ سكريبت الإصلاح والتنويع: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"خطأ في تشغيل سكريبت الإصلاح والتنويع: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    # إعداد محلل المعاملات
    parser = argparse.ArgumentParser(description='أداة تنشيط نظام التداول')
    parser.add_argument('--check', action='store_true', help='التحقق من اتصال API')
    parser.add_argument('--trades', action='store_true', help='عرض الصفقات النشطة')
    parser.add_argument('--reset', action='store_true', help='إعادة ضبط الصفقات')
    parser.add_argument('--clean', action='store_true', help='تنظيف الصفقات الوهمية')
    parser.add_argument('--start', action='store_true', help='تشغيل خدمة التداول المستمر')
    parser.add_argument('--diversify', action='store_true', help='إصلاح وتنويع الصفقات')
    parser.add_argument('--full', action='store_true', help='تنفيذ عملية كاملة: إعادة ضبط، تنويع، تشغيل')
    
    args = parser.parse_args()
    
    if args.check:
        # التحقق من اتصال API
        connected = check_api_connectivity()
        print(f"حالة الاتصال بواجهة برمجة التطبيقات: {'متصل ✓' if connected else 'غير متصل ✗'}")
        
    elif args.trades:
        # عرض الصفقات النشطة
        trades = get_active_trades()
        print(f"الصفقات النشطة ({len(trades)}):")
        for trade in trades:
            symbol = trade.get('symbol', 'غير معروف')
            entry_price = trade.get('entry_price', 0)
            timestamp = trade.get('timestamp', 0)
            
            # تحويل الطابع الزمني إلى تاريخ مقروء
            from datetime import datetime
            date_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'غير معروف'
            
            print(f"  - {symbol}: سعر الدخول={entry_price}, التاريخ={date_str}")
            
    elif args.reset:
        # إعادة ضبط الصفقات
        reset_all_trades()
        print("تم إعادة ضبط الصفقات")
        
    elif args.clean:
        # تنظيف الصفقات الوهمية
        clean_fake_trades()
        print("تم تنظيف الصفقات الوهمية")
        
    elif args.start:
        # تشغيل خدمة التداول المستمر
        activate_continuous_trader()
        print("تم تنشيط خدمة التداول المستمر")
        
    elif args.diversify:
        # إصلاح وتنويع الصفقات
        run_fix_and_diversify()
        print("تم تنفيذ عملية الإصلاح والتنويع")
        
    elif args.full:
        # تنفيذ عملية كاملة
        print("تنفيذ عملية كاملة...")
        
        # 1. إعادة ضبط الصفقات
        print("1. إعادة ضبط الصفقات...")
        reset_all_trades()
        
        # 2. إصلاح وتنويع الصفقات
        print("2. إصلاح وتنويع الصفقات...")
        run_fix_and_diversify()
        
        # 3. تشغيل خدمة التداول المستمر
        print("3. تشغيل خدمة التداول المستمر...")
        activate_continuous_trader()
        
        print("تم تنفيذ العملية الكاملة بنجاح")
        
    else:
        # عرض التعليمات
        parser.print_help()
        print("\nمثال:")
        print("  python activate_trade_system.py --check")
        print("  python activate_trade_system.py --trades")
        print("  python activate_trade_system.py --full")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nتم إلغاء التشغيل")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطأ في تشغيل الأداة: {e}")
        print(f"خطأ في تشغيل الأداة: {e}")
        sys.exit(1)