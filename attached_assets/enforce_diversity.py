#!/usr/bin/env python
"""
أداة الإصلاح النهائي لمشكلة تكرار الصفقات على نفس العملة
سيتم تشغيلها تلقائياً عند بدء البوت وقبل كل صفقة جديدة
تقوم بالإبقاء على صفقة واحدة فقط لكل عملة وإغلاق البقية
"""

import json
import os
import time
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_backup(filename='active_trades.json'):
    """إنشاء نسخة احتياطية من ملف الصفقات"""
    try:
        backup_name = f"{filename}.backup.{int(time.time())}"
        with open(filename, 'r') as f:
            content = f.read()
        with open(backup_name, 'w') as f:
            f.write(content)
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_name}")
        return True
    except Exception as e:
        logger.error(f"خطأ في إنشاء نسخة احتياطية: {e}")
        return False

def enforce_trade_diversity(filename='active_trades.json', max_per_symbol=1):
    """
    فرض التنويع بشكل صارم عن طريق إغلاق الصفقات المكررة
    والإبقاء على صفقة واحدة فقط لكل عملة
    """
    # إنشاء نسخة احتياطية أولاً
    create_backup(filename)
    
    try:
        # تحميل الصفقات
        with open(filename, 'r') as f:
            trades = json.load(f)
        
        total_trades = len(trades)
        logger.info(f"إجمالي الصفقات: {total_trades}")
        
        # حساب الصفقات المفتوحة
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        logger.info(f"الصفقات المفتوحة: {len(open_trades)}")
        
        # حساب العملات الفريدة
        unique_symbols = list(set([t.get('symbol') for t in open_trades if t.get('symbol')]))
        logger.info(f"العملات الفريدة المفتوحة: {unique_symbols}")
        
        # للتأكد من وجود صفقة واحدة فقط لكل عملة
        for symbol in unique_symbols:
            symbol_trades = [t for t in trades if t.get('symbol') == symbol and t.get('status') == 'OPEN']
            if len(symbol_trades) > max_per_symbol:
                logger.warning(f"⚠️ وجدنا {len(symbol_trades)} صفقة مفتوحة لـ {symbol}. سيتم الاحتفاظ بواحدة فقط.")
                
                # فرز الصفقات حسب سعر الشراء للاحتفاظ بأفضلها
                symbol_trades.sort(key=lambda x: float(x.get('entry_price', 0)))
                
                # الاحتفاظ بالصفقة الأولى فقط وإغلاق البقية
                for i, trade in enumerate(symbol_trades):
                    if i >= max_per_symbol:
                        # إيجاد الصفقة في القائمة الأصلية وتحديثها
                        for j, t in enumerate(trades):
                            if t.get('id') == trade.get('id'):
                                trades[j]['status'] = 'CLOSED'
                                trades[j]['close_price'] = trade.get('entry_price')
                                trades[j]['close_time'] = int(time.time() * 1000)
                                trades[j]['profit'] = "0.0"
                                trades[j]['profit_percentage'] = "0.0"
                                logger.info(f"✅ تم إغلاق صفقة مكررة لـ {symbol} (معرف: {trade.get('id')})")
        
        # حفظ التغييرات
        with open(filename, 'w') as f:
            json.dump(trades, f, indent=2)
        
        logger.info(f"الصفقات بعد التنفيذ: {len(trades)}")
        logger.info(f"الصفقات المفتوحة بعد التنفيذ: {len([t for t in trades if t.get('status') == 'OPEN'])}")
        print("✅ تم تنفيذ التنويع الإلزامي للصفقات بنجاح")
        return True
    
    except Exception as e:
        logger.error(f"خطأ في تنفيذ التنويع: {e}")
        return False

def fix_symbol_trades(symbol, filename='active_trades.json'):
    """
    إصلاح الصفقات لعملة محددة بإغلاق جميع الصفقات المكررة
    """
    create_backup(filename)
    
    try:
        with open(filename, 'r') as f:
            trades = json.load(f)
        
        symbol_trades = [t for t in trades if t.get('symbol') == symbol and t.get('status') == 'OPEN']
        if len(symbol_trades) <= 1:
            logger.info(f"لا توجد صفقات مكررة لـ {symbol}")
            return True
        
        logger.warning(f"وجدنا {len(symbol_trades)} صفقة مفتوحة لـ {symbol}. سيتم الاحتفاظ بواحدة فقط.")
        
        # ترتيب الصفقات حسب السعر للاحتفاظ بأفضلها
        symbol_trades.sort(key=lambda x: float(x.get('entry_price', 0)))
        
        # الاحتفاظ بالصفقة الأولى فقط وإغلاق البقية
        for i, trade in enumerate(symbol_trades):
            if i >= 1:  # إغلاق كل شيء بعد الصفقة الأولى
                # البحث عن الصفقة في القائمة الرئيسية وتحديثها
                for j, t in enumerate(trades):
                    if t.get('id') == trade.get('id'):
                        trades[j]['status'] = 'CLOSED'
                        trades[j]['close_price'] = trade.get('entry_price')
                        trades[j]['close_time'] = int(time.time() * 1000)
                        trades[j]['profit'] = "0.0"
                        trades[j]['profit_percentage'] = "0.0"
                        logger.info(f"✅ تم إغلاق صفقة مكررة لـ {symbol} (معرف: {trade.get('id')})")
        
        # حفظ التغييرات
        with open(filename, 'w') as f:
            json.dump(trades, f, indent=2)
        
        print(f"✅ تم إصلاح صفقات {symbol} بنجاح")
        return True
    
    except Exception as e:
        logger.error(f"خطأ في إصلاح صفقات {symbol}: {e}")
        return False

if __name__ == "__main__":
    print("== أداة إصلاح تنويع الصفقات ==")
    
    if len(sys.argv) > 1:
        # إذا تم تمرير رمز العملة كوسيط
        symbol = sys.argv[1]
        print(f"معالجة صفقات {symbol} فقط...")
        fix_symbol_trades(symbol)
    else:
        # معالجة كل العملات
        print("معالجة جميع العملات...")
        enforce_trade_diversity()