"""
ملف للتحقق من رصيد USDT في المنصة
"""
import logging
from app.mexc_api import get_balance, get_account_balance
from app.config import BASE_CURRENCY

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('check_balance')

def check_usdt_balance():
    """التحقق من رصيد USDT بعدة طرق"""
    print("🔍 التحقق من رصيد USDT في المنصة...")
    
    # الطريقة الأولى: استخدام دالة get_balance
    try:
        usdt_balance = get_balance(BASE_CURRENCY)
        print(f"📊 رصيد USDT (طريقة 1): {usdt_balance}")
    except Exception as e:
        print(f"❌ خطأ في الحصول على الرصيد (طريقة 1): {e}")
    
    # الطريقة الثانية: استخدام معلومات الحساب
    try:
        account_data = get_account_balance()
        print(f"📋 معلومات الحساب الكاملة:")
        print(account_data)
        
        # البحث عن USDT في الأرصدة
        if account_data and 'balances' in account_data:
            balances = account_data['balances']
            for balance in balances:
                if balance.get('asset') == BASE_CURRENCY:
                    print(f"💰 رصيد {BASE_CURRENCY} وجد في معلومات الحساب: {balance}")
        else:
            print(f"⚠️ لم يتم العثور على 'balances' في معلومات الحساب، أو المعلومات فارغة: {account_data}")
    except Exception as e:
        print(f"❌ خطأ في الحصول على معلومات الحساب: {e}")

if __name__ == "__main__":
    check_usdt_balance()