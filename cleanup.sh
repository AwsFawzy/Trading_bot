#!/bin/bash
# سكريبت لتنظيف الملفات غير الضرورية بعد توحيد النظام

# إنشاء مجلد للنسخ الاحتياطية إذا لم يكن موجودًا
mkdir -p backup_files

# قائمة بالملفات التي سيتم نقلها إلى المجلد الاحتياطي
FILES_TO_MOVE=(
    activate_trade_system.py
    add_missing_trades.py
    block_xrpusdt.py
    check_real_trades.py
    check_trades.py
    clean_trades_file.py
    close_and_open_new_trades.py
    cron_enforce_diversity.py
    daily_enforcer.py
    diversify_runner.py
    diversify_trades.py
    enforce_diversity.py
    find_all_trades.py
    fix_and_diversify.py
    fix_trades.py
    force_fix.py
    forced_sell.py
    health_check.py
    install_cron.py
    monitor_real_trades.py
    run_auto_trade.py
    run_before_trade.py
    run_trade_manager.py
    start_bot_only.py
    stop_bot.py
    symbol_blocker.py
    update_real_trades.py
    verify_and_clean_trades.py
)

# نقل كل ملف إلى مجلد النسخ الاحتياطية
for file in "${FILES_TO_MOVE[@]}"; do
    if [ -f "$file" ]; then
        echo "نقل $file إلى مجلد النسخ الاحتياطية..."
        mv "$file" backup_files/
    else
        echo "$file غير موجود"
    fi
done

echo "تم الانتهاء من تنظيف الملفات"