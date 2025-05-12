#!/usr/bin/env python3
"""
مهمة يومية للتأكد من تنويع الصفقات ومنع وجود صفقات مكررة
تنفذ آليًا كل 24 ساعة أو عند إعادة تشغيل البوت
"""
import json
import os
import time
import logging
from datetime import datetime, timedelta

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_backup(filename='active_trades.json'):
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    if os.path.exists(filename):
        timestamp = int(time.time())
        backup_file = f"{filename}.backup.{timestamp}"
        with open(filename, 'r') as src, open(backup_file, 'w') as dst:
            dst.write(src.read())
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_file}")
        return True
    return False

def enforce_trade_diversity(filename='active_trades.json'):
    """إجبار التنويع بإغلاق الصفقات المكررة"""
    # إنشاء نسخة احتياطية أولاً
    create_backup(filename)
    
    try:
        # تحميل الصفقات
        with open(filename, 'r') as f:
            trades = json.load(f)
        
        logger.info(f"إجمالي الصفقات: {len(trades)}")
        logger.info(f"الصفقات المفتوحة: {len([t for t in trades if t.get('status') == 'OPEN'])}")
        
        # استخراج الصفقات المفتوحة والمغلقة
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        closed_trades = [t for t in trades if t.get('status') != 'OPEN']
        
        # حساب العملات الفريدة
        symbols = {}
        for trade in open_trades:
            symbol = trade.get('symbol')
            if symbol not in symbols:
                symbols[symbol] = []
            symbols[symbol].append(trade)
        
        logger.info(f"العملات الفريدة المفتوحة: {list(symbols.keys())}")
        
        # الاحتفاظ بأحدث صفقة فقط لكل عملة
        kept_trades = []
        for symbol, symbol_trades in symbols.items():
            # التأكد من وجود صفقة واحدة فقط لكل عملة
            if len(symbol_trades) > 1:
                logger.warning(f"⚠️ وجدنا {len(symbol_trades)} صفقة مفتوحة لـ {symbol}. سيتم الاحتفاظ بواحدة فقط.")
                
                # فرز الصفقات حسب التاريخ (الأحدث أولًا)
                symbol_trades.sort(key=lambda x: int(x.get('timestamp', 0)), reverse=True)
                
                # الاحتفاظ بأحدث صفقة فقط
                kept_trades.append(symbol_trades[0])
                
                # إغلاق بقية الصفقات
                for t in symbol_trades[1:]:
                    t['status'] = 'CLOSED_BY_ENFORCER'
                    t['close_reason'] = 'إغلاق تلقائي لتنفيذ التنويع الإلزامي'
                    t['close_timestamp'] = int(time.time() * 1000)
                    t['close_price'] = t.get('entry_price', 0)  # إغلاق بنفس سعر الدخول (لا ربح ولا خسارة)
                    closed_trades.append(t)
                    logger.info(f"✅ تم إغلاق صفقة مكررة لـ {symbol} (معرف: {t.get('id')})")
            else:
                # إذا كانت هناك صفقة واحدة فقط، احتفظ بها
                kept_trades.append(symbol_trades[0])
        
        # تجميع الصفقات المحفوظة والمغلقة
        fixed_trades = kept_trades + closed_trades
        
        logger.info(f"الصفقات بعد التنفيذ: {len(fixed_trades)}")
        logger.info(f"الصفقات المفتوحة بعد التنفيذ: {len([t for t in fixed_trades if t.get('status') == 'OPEN'])}")
        
        # حفظ الصفقات المصححة
        with open(filename, 'w') as f:
            json.dump(fixed_trades, f, indent=2)
        
        logger.info("✅ تم تنفيذ التنويع الإلزامي للصفقات بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ حدث خطأ أثناء تنفيذ التنويع: {e}")
        return False

if __name__ == "__main__":
    enforce_trade_diversity()