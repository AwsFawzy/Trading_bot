#!/bin/bash

# سكريبت لإعادة تشغيل البوت عند انقطاع الإنترنت أو توقف البوت
# Copyright (c) 2025

echo "$(date) - محاولة إعادة تشغيل البوت..."

# التأكد من وجود ملف السجلات
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/restart_bot.log"

if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi

# تسجيل محاولة إعادة التشغيل
echo "$(date) - بدء محاولة إعادة تشغيل البوت" >> "$LOG_FILE"

# الانتظار 10 ثوانٍ للتأكد من إغلاق العمليات السابقة
sleep 10

# محاولة إيقاف البوت
python -c "from app.trading_bot import stop_bot; stop_bot()" >> "$LOG_FILE" 2>&1

# الانتظار 5 ثوانٍ للتأكد من إيقاف العمليات
sleep 5

# محاولة تشغيل البوت من جديد
python -c "from app.trading_bot import start_bot; start_bot()" >> "$LOG_FILE" 2>&1

# قم بإرسال إشعار تيليجرام
python -c "from app.telegram_notify import send_telegram_message; send_telegram_message('✅ تم إعادة تشغيل البوت آلياً عن طريق سكريبت الإعادة الآلية')" >> "$LOG_FILE" 2>&1

echo "$(date) - اكتملت محاولة إعادة تشغيل البوت" >> "$LOG_FILE"

# نهاية السكريبت
exit 0