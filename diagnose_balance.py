"""
ملف تشخيص لفهم مشكلة الرصيد في نظام التداول
"""
import json
import logging
import sys

# إعداد التسجيل
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('balance_debug.log')
    ]
)
logger = logging.getLogger('diagnose_balance')

try:
    # استيراد الدوال المطلوبة
    from app.config import BASE_CURRENCY
    from app.mexc_api import get_balance, get_account_balance, get_user_asset
    
    logger.info("✅ تم استيراد الدوال بنجاح")
except ImportError as e:
    logger.error(f"❌ خطأ في استيراد الدوال: {e}")
    sys.exit(1)

def diagnose_usdt_balance():
    """
    تشخيص مشكلة رصيد USDT بطريقة تفصيلية
    """
    logger.info("🔍 بدء تشخيص رصيد USDT...")
    
    # 1. استخدام دالة get_balance المباشرة
    try:
        direct_balance = get_balance(BASE_CURRENCY)
        logger.info(f"1️⃣ نتيجة get_balance: {direct_balance}")
        
        if direct_balance:
            logger.info(f"✅ عملة {BASE_CURRENCY} متوفرة برصيد: {direct_balance}")
        else:
            logger.warning(f"⚠️ get_balance لم تجد رصيد {BASE_CURRENCY}")
    except Exception as e:
        logger.error(f"❌ خطأ في get_balance: {e}")
    
    # 2. استخدام دالة get_account_balance للحصول على جميع الأرصدة
    try:
        account_balance = get_account_balance()
        logger.info(f"2️⃣ نتيجة get_account_balance: {account_balance}")
        
        # طباعة بنية البيانات كاملة للتحليل
        logger.info(f"🔍 نوع البيانات: {type(account_balance)}")
        
        # تحقق إذا كان قاموس
        if isinstance(account_balance, dict):
            logger.info(f"📊 مفاتيح القاموس: {account_balance.keys()}")
            
            # طريقة البحث الأولى: البحث المباشر عن USDT كمفتاح
            if BASE_CURRENCY in account_balance:
                usdt_data = account_balance[BASE_CURRENCY]
                logger.info(f"✅ عملة {BASE_CURRENCY} موجودة كمفتاح أساسي برصيد: {usdt_data}")
            else:
                logger.warning(f"⚠️ عملة {BASE_CURRENCY} غير موجودة كمفتاح أساسي")
            
            # طريقة البحث الثانية: البحث عن USDT في 'balances'
            if 'balances' in account_balance:
                balances = account_balance['balances']
                logger.info(f"🔍 عدد العناصر في 'balances': {len(balances)}")
                
                usdt_found = False
                for balance in balances:
                    if isinstance(balance, dict) and balance.get('asset') == BASE_CURRENCY:
                        usdt_found = True
                        usdt_amount = balance.get('free', 0)
                        logger.info(f"✅ عملة {BASE_CURRENCY} موجودة في 'balances' برصيد: {usdt_amount}")
                
                if not usdt_found:
                    logger.warning(f"⚠️ عملة {BASE_CURRENCY} غير موجودة في 'balances'")
        else:
            logger.warning(f"⚠️ بيانات الحساب ليست قاموس: {type(account_balance)}")
    except Exception as e:
        logger.error(f"❌ خطأ في get_account_balance: {e}")
    
    # 3. استخدام دالة get_user_asset للحصول على أصول المستخدم
    try:
        user_assets = get_user_asset()
        logger.info(f"3️⃣ نتيجة get_user_asset: {user_assets}")
        
        if isinstance(user_assets, list):
            usdt_found = False
            for asset in user_assets:
                if isinstance(asset, dict) and asset.get('asset') == BASE_CURRENCY:
                    usdt_found = True
                    usdt_amount = asset.get('free', 0)
                    logger.info(f"✅ عملة {BASE_CURRENCY} موجودة في أصول المستخدم برصيد: {usdt_amount}")
            
            if not usdt_found:
                logger.warning(f"⚠️ عملة {BASE_CURRENCY} غير موجودة في أصول المستخدم")
        else:
            logger.warning(f"⚠️ بيانات أصول المستخدم ليست قائمة: {type(user_assets)}")
    except Exception as e:
        logger.error(f"❌ خطأ في get_user_asset: {e}")
    
    # 4. توصيات لإصلاح المشكلة
    logger.info("\n🔧 توصيات الإصلاح:")
    logger.info("1️⃣. تعديل دالة execute_buy في trading_system.py للتعامل مع بنية البيانات الصحيحة")
    logger.info("2️⃣. تأكد من أن get_account_balance() تعيد البيانات بالتنسيق المتوقع")
    logger.info("3️⃣. في حالة عدم وجود USDT مباشرة، ابحث عنها في 'balances' إذا كانت موجودة")
    
def fix_recommendation():
    """
    توصية بالإصلاح المطلوب
    """
    logger.info("\n📝 توصية الإصلاح:")
    fix_code = """
    # الكود الحالي في trading_system.py - execute_buy
    try:
        logger.info("التحقق من رصيد USDT قبل تنفيذ عملية الشراء...")
        balance = get_account_balance()
        if not balance or 'USDT' not in balance:
            logger.error("❌ لم يتم العثور على رصيد USDT. تأكد من صلاحيات API.")
            return False, {"error": "لم يتم العثور على رصيد USDT"}
        
        initial_usdt_balance = float(balance['USDT'].get('free', 0))
        logger.info(f"💰 رصيد USDT المتاح: {initial_usdt_balance}")
    
    # الكود المقترح للإصلاح
    try:
        logger.info("التحقق من رصيد USDT قبل تنفيذ عملية الشراء...")
        balance = get_account_balance()
        
        # طريقة 1: إذا كان USDT موجود كمفتاح مباشر
        if balance and 'USDT' in balance:
            initial_usdt_balance = float(balance['USDT'].get('free', 0))
        # طريقة 2: إذا كان هناك قائمة 'balances'
        elif balance and 'balances' in balance:
            initial_usdt_balance = 0
            for asset in balance['balances']:
                if asset.get('asset') == 'USDT':
                    initial_usdt_balance = float(asset.get('free', 0))
                    break
        # طريقة 3: استخدام get_balance مباشرة
        else:
            direct_balance = get_balance('USDT')
            initial_usdt_balance = float(direct_balance) if direct_balance else 0
        
        if initial_usdt_balance <= 0:
            logger.error(f"❌ رصيد USDT غير كافٍ. متاح: {initial_usdt_balance}")
            return False, {"error": f"رصيد USDT غير كافٍ. متاح: {initial_usdt_balance}"}
            
        logger.info(f"💰 رصيد USDT المتاح: {initial_usdt_balance}")
    """
    
    logger.info(fix_code)

if __name__ == "__main__":
    logger.info("🚀 بدء تشخيص مشكلة الرصيد...")
    diagnose_usdt_balance()
    fix_recommendation()