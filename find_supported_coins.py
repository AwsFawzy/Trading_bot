"""
ملف للبحث عن العملات المدعومة في منصة MEXC
"""
import json
import logging
import sys

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('supported_coins.log')
    ]
)
logger = logging.getLogger('find_supported_coins')

try:
    # استيراد الدوال المطلوبة
    from app.mexc_api import get_exchange_info
    
    logger.info("✅ تم استيراد الدوال بنجاح")
except ImportError as e:
    logger.error(f"❌ خطأ في استيراد الدوال: {e}")
    sys.exit(1)

def find_supported_markets():
    """
    البحث عن الأسواق المدعومة في MEXC
    """
    logger.info("🔍 جاري البحث عن الأسواق المدعومة...")
    
    try:
        # جلب معلومات التبادل
        exchange_info = get_exchange_info()
        
        if not exchange_info or 'symbols' not in exchange_info:
            logger.error("❌ لا توجد معلومات عن الأسواق")
            return []
        
        # استخراج قائمة الرموز المدعومة
        symbols = exchange_info['symbols']
        logger.info(f"📊 تم العثور على {len(symbols)} رمز مدعوم")
        
        # فلترة الرموز التي تنتهي بـ USDT
        usdt_markets = []
        
        # طباعة بنية البيانات للتحليل
        if len(symbols) > 0:
            first_symbol = symbols[0]
            logger.info(f"نموذج لمعلومات الرمز: {json.dumps(first_symbol, indent=2)}")
        
        for symbol_info in symbols:
            symbol = symbol_info.get('symbol', '')
            status = symbol_info.get('status', '')
            
            if symbol.endswith('USDT'):
                # تخزين كمية أقل من البيانات للتبسيط
                usdt_markets.append({
                    'symbol': symbol,
                    'baseAsset': symbol_info.get('baseAsset', ''),
                    'quoteAsset': symbol_info.get('quoteAsset', ''),
                    'status': status
                })
        
        logger.info(f"📈 تم العثور على {len(usdt_markets)} سوق USDT مدعوم")
        
        # عرض أول 10 أسواق
        logger.info("أول 10 أسواق USDT مدعومة:")
        for i, market in enumerate(usdt_markets[:10], 1):
            logger.info(f"{i}. {market['symbol']} ({market['baseAsset']}/{market['quoteAsset']})")
        
        # حفظ القائمة الكاملة في ملف JSON
        with open('supported_markets.json', 'w') as f:
            json.dump({
                'total': len(usdt_markets),
                'markets': usdt_markets
            }, f, indent=2)
            
        logger.info("✅ تم حفظ القائمة الكاملة في ملف supported_markets.json")
        
        return usdt_markets
    except Exception as e:
        logger.error(f"❌ خطأ في البحث عن الأسواق المدعومة: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def find_popular_markets():
    """
    البحث عن الأسواق الشائعة في MEXC
    """
    # قائمة العملات الشائعة المحتملة
    popular_coins = [
        'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SHIB', 'LTC', 'DOT', 
        'TRX', 'ATOM', 'AVAX', 'NEAR', 'LINK', 'SOL', 'MATIC', 'OP', 'ARB'
    ]
    
    # جلب جميع الأسواق المدعومة
    all_markets = find_supported_markets()
    
    # فلترة العملات الشائعة
    popular_markets = []
    for market in all_markets:
        base_asset = market['baseAsset']
        if base_asset in popular_coins:
            popular_markets.append(market)
    
    logger.info(f"🌟 تم العثور على {len(popular_markets)} سوق شائع من أصل {len(all_markets)} سوق مدعوم")
    
    # عرض الأسواق الشائعة
    logger.info("الأسواق الشائعة المدعومة:")
    for i, market in enumerate(popular_markets, 1):
        logger.info(f"{i}. {market['symbol']} ({market['baseAsset']}/{market['quoteAsset']})")
    
    return popular_markets

if __name__ == "__main__":
    logger.info("🚀 بدء البحث عن العملات المدعومة...")
    popular_markets = find_popular_markets()
    
    if popular_markets:
        logger.info("✅ تم العثور على عملات مدعومة")
        
        # إنشاء قائمة JSON لاستخدامها في ملفات أخرى
        result = {
            'symbols': [market['symbol'] for market in popular_markets]
        }
        
        with open('popular_symbols.json', 'w') as f:
            json.dump(result, f, indent=2)
            
        logger.info(f"✅ تم حفظ {len(popular_markets)} رمز شائع في ملف popular_symbols.json")