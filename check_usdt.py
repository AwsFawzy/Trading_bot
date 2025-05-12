"""
سكريبت بسيط لفحص رصيد USDT والعملات
"""
import json
import logging
from app.mexc_api import get_account_balances

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_balance():
    try:
        # الحصول على جميع الأرصدة
        balances = get_account_balances()
        
        # البحث عن رصيد USDT
        usdt_balance = 0
        for balance in balances.get('balances', []):
            if balance.get('asset') == 'USDT':
                usdt_balance = float(balance.get('free', 0))
                
        print(f"رصيد USDT المتاح: {usdt_balance}$")
        
        # عرض العملات التي لديها رصيد
        print("\nالعملات ذات الرصيد:")
        for balance in balances.get('balances', []):
            free_balance = float(balance.get('free', 0))
            if free_balance > 0:
                asset = balance.get('asset', '')
                print(f"  {asset}: {free_balance}")
                
    except Exception as e:
        logger.error(f"خطأ أثناء فحص الرصيد: {e}")

if __name__ == "__main__":
    check_balance()