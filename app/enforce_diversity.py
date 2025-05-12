#!/usr/bin/env python
"""
نظام صارم لفرض تنويع الصفقات على عملات مختلفة
هذا النظام مدمج مباشرة في جميع نقاط تنفيذ الصفقات
"""

import json
import os
import time
import logging
import subprocess
from typing import List, Tuple, Dict, Set

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
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

def get_open_trades_per_symbol() -> Dict[str, int]:
    """
    الحصول على عدد الصفقات المفتوحة لكل عملة
    
    :return: قاموس يحتوي على العملات وعدد صفقاتها المفتوحة
    """
    try:
        with open('active_trades.json', 'r') as f:
            trades = json.load(f)
            
        # حساب الصفقات المفتوحة لكل رمز
        open_trades_count = {}
        for trade in trades:
            if trade.get('status') == 'OPEN' and trade.get('symbol'):
                symbol = trade.get('symbol')
                if symbol in open_trades_count:
                    open_trades_count[symbol] += 1
                else:
                    open_trades_count[symbol] = 1
                    
        return open_trades_count
    except Exception as e:
        logger.error(f"خطأ في حساب الصفقات المفتوحة: {e}")
        return {}

def get_unique_traded_symbols() -> Set[str]:
    """
    الحصول على مجموعة العملات المتداولة
    
    :return: مجموعة العملات المتداولة حاليًا
    """
    try:
        with open('active_trades.json', 'r') as f:
            trades = json.load(f)
            
        # الحصول على مجموعة العملات المتداولة
        unique_symbols = set([
            trade.get('symbol') for trade in trades 
            if trade.get('status') == 'OPEN' and trade.get('symbol')
        ])
        
        return unique_symbols
    except Exception as e:
        logger.error(f"خطأ في الحصول على العملات المتداولة: {e}")
        return set()

def is_trade_allowed(symbol: str, max_per_symbol: int = 1) -> Tuple[bool, str]:
    """
    التحقق مما إذا كان مسموحًا بفتح صفقة جديدة على العملة
    
    :param symbol: رمز العملة
    :param max_per_symbol: الحد الأقصى للصفقات المفتوحة لكل عملة
    :return: (مسموح, السبب)
    """
    if not symbol:
        return False, "لم يتم تحديد رمز العملة"
        
    # الحصول على عدد الصفقات المفتوحة لكل عملة
    open_trades_count = get_open_trades_per_symbol()
    
    # التحقق مما إذا كان مسموحًا بفتح صفقة جديدة على العملة
    if symbol in open_trades_count and open_trades_count[symbol] >= max_per_symbol:
        return False, f"لقد وصلت للحد الأقصى من الصفقات المفتوحة لـ {symbol} ({max_per_symbol})"
    
    # يمكن فتح صفقة جديدة
    return True, "مسموح بفتح صفقة جديدة"

def enforce_diversity_for_candidates(candidates: List[str]) -> List[str]:
    """
    فرض التنويع على قائمة العملات المرشحة للتداول
    
    :param candidates: قائمة برموز العملات المرشحة
    :return: قائمة بالعملات المسموح التداول عليها بعد تطبيق قواعد التنويع
    """
    if not candidates:
        return []
    
    # العملات المتداولة حاليًا
    traded_symbols = get_unique_traded_symbols()
    
    # استبعاد العملات المتداولة حاليًا
    allowed_candidates = [symbol for symbol in candidates if symbol not in traded_symbols]
    
    logger.info(f"تطبيق قواعد التنويع: من {len(candidates)} إلى {len(allowed_candidates)} مرشح")
    logger.info(f"العملات المتداولة حاليًا: {traded_symbols}")
    logger.info(f"العملات المرشحة المسموح بها: {allowed_candidates}")
    
    return allowed_candidates

def clean_duplicate_trades(max_per_symbol: int = 1):
    """
    تنظيف الصفقات المكررة
    
    :param max_per_symbol: الحد الأقصى للصفقات المفتوحة لكل عملة
    """
    # إنشاء نسخة احتياطية أولاً
    create_backup()
    
    try:
        with open('active_trades.json', 'r') as f:
            trades = json.load(f)
            
        # حساب الصفقات المفتوحة لكل رمز
        symbols_trades = {}
        for trade in trades:
            if trade.get('status') == 'OPEN' and trade.get('symbol'):
                symbol = trade.get('symbol')
                if symbol not in symbols_trades:
                    symbols_trades[symbol] = []
                symbols_trades[symbol].append(trade)
                
        # الاحتفاظ بالحد الأقصى المسموح به من الصفقات لكل عملة
        changes_made = False
        for symbol, symbol_trades in symbols_trades.items():
            if len(symbol_trades) > max_per_symbol:
                logger.warning(f"العملة {symbol} لديها {len(symbol_trades)} صفقة مفتوحة. سيتم الاحتفاظ بـ {max_per_symbol} فقط.")
                
                # ترتيب الصفقات حسب وقت الإنشاء (أحدث الصفقات أولاً)
                symbol_trades.sort(key=lambda x: int(x.get('id', 0)), reverse=True)
                
                # إغلاق الصفقات الزائدة
                for i, trade in enumerate(symbol_trades):
                    if i >= max_per_symbol:
                        # البحث عن الصفقة في القائمة الأصلية وإغلاقها
                        for j, t in enumerate(trades):
                            if t.get('id') == trade.get('id'):
                                trades[j]['status'] = 'CLOSED'
                                trades[j]['close_price'] = trade.get('entry_price')
                                trades[j]['close_time'] = int(time.time() * 1000)
                                trades[j]['profit'] = "0.0"
                                trades[j]['profit_percentage'] = "0.0"
                                logger.info(f"✅ تم إغلاق صفقة مكررة لـ {symbol} (معرف: {trade.get('id')})")
                                changes_made = True
        
        # حفظ التغييرات إذا تم إجراء أي تغييرات
        if changes_made:
            with open('active_trades.json', 'w') as f:
                json.dump(trades, f, indent=2)
            logger.info("✅ تم تنظيف الصفقات المكررة بنجاح")
        else:
            logger.info("✓ لا توجد صفقات مكررة للتنظيف")
            
        # طباعة إحصائيات بعد التنظيف
        open_trades = len([t for t in trades if t.get('status') == 'OPEN'])
        unique_symbols = len(set([t.get('symbol') for t in trades if t.get('status') == 'OPEN' and t.get('symbol')]))
        
        logger.info(f"الصفقات المفتوحة: {open_trades}")
        logger.info(f"العملات الفريدة: {unique_symbols}")
        
        return True
    except Exception as e:
        logger.error(f"خطأ في تنظيف الصفقات المكررة: {e}")
        return False

def get_candidate_for_diversity():
    """
    الحصول على مرشح للتنويع
    يبحث عن عملات جديدة لم يتم التداول عليها بعد
    
    :return: قائمة العملات المرشحة للتنويع
    """
    try:
        # الحصول على جميع العملات المتاحة
        all_symbols = []
        with open('app/config.py', 'r') as f:
            for line in f:
                if "SUPPORTED_SYMBOLS = [" in line or "DEFAULT_SYMBOLS = [" in line:
                    start = line.find('[')
                    end = line.find(']')
                    if start != -1 and end != -1:
                        symbols_str = line[start+1:end].strip()
                        symbols = [s.strip().strip('"\'') for s in symbols_str.split(',') if s.strip()]
                        all_symbols.extend(symbols)
        
        # العملات المتداولة حاليًا
        traded_symbols = get_unique_traded_symbols()
        
        # العملات غير المتداولة حاليًا
        untrade_symbols = [s for s in all_symbols if s not in traded_symbols]
        
        # استبعاد العملات غير المناسبة
        filtered_symbols = []
        for symbol in untrade_symbols:
            if symbol not in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:  # العملات المستبعدة لأسباب مختلفة
                filtered_symbols.append(symbol)
                
        return filtered_symbols
    except Exception as e:
        logger.error(f"خطأ في الحصول على مرشح للتنويع: {e}")
        return []

def recommend_untrade_symbols():
    """
    اقتراح عملات غير متداولة للتنويع
    
    :return: قائمة بأفضل العملات غير المتداولة حاليًا
    """
    symbols = get_candidate_for_diversity()
    
    # ترتيب العملات بطريقة عشوائية للتنويع
    import random
    random.shuffle(symbols)
    
    return symbols[:10]  # إعادة أفضل 10 عملات