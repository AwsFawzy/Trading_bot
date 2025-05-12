"""
برنامج لإضافة وظيفة cron تلقائياً لتنفيذ فحص التنويع كل ساعة
"""

import os
import subprocess
import sys

def add_cron_job():
    """إضافة وظيفة cron لتشغيل برنامج التنويع كل ساعة"""
    # الحصول على المسار الحالي
    current_dir = os.getcwd()
    
    # إنشاء الأمر المطلوب إضافته إلى crontab
    cron_command = f"0 * * * * cd {current_dir} && python cron_enforce_diversity.py >> diversity_cron.log 2>&1"
    
    # التحقق من وجود المهمة بالفعل
    try:
        check_result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        
        # إذا كانت المهمة موجودة بالفعل
        if cron_command in check_result.stdout:
            print("وظيفة cron موجودة بالفعل")
            return True
            
        # إذا كانت المهمة غير موجودة
        current_crontab = check_result.stdout
        
        # إضافة المهمة الجديدة
        new_crontab = current_crontab.strip() + "\n" + cron_command + "\n"
        
        # إنشاء ملف مؤقت
        with open("temp_crontab", "w") as f:
            f.write(new_crontab)
            
        # تثبيت crontab الجديد
        subprocess.run(["crontab", "temp_crontab"], check=True)
        
        # حذف الملف المؤقت
        os.remove("temp_crontab")
        
        print("تمت إضافة وظيفة cron بنجاح")
        return True
    except Exception as e:
        print(f"خطأ في إضافة وظيفة cron: {e}")
        return False

def main():
    print("جاري إضافة وظيفة cron لتنفيذ فحص التنويع كل ساعة...")
    success = add_cron_job()
    
    if success:
        print("✅ تمت إضافة وظيفة cron بنجاح")
    else:
        print("❌ فشل في إضافة وظيفة cron")
        
    # إنشاء ملف لتسجيل وقت آخر تنفيذ
    with open("last_diversity_check.txt", "w") as f:
        f.write("تم تثبيت وظيفة التنويع الآلي\n")
        
    return success

if __name__ == "__main__":
    main()