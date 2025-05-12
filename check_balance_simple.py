"""
سكريبت بسيط لفحص رصيد USDT فقط
"""
import logging
from app.mexc_api import get_account_balance

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_usdt_balance():
    try:
        # الحصول على رصيد USDT
        balances = get_account_balance()
        usdt_balance = 0
        
        for balance in balances.get('balances', []):
            if balance.get('asset') == 'USDT':
                usdt_balance = float(balance.get('free', 0))
                break
        
        print(f"رصيد USDT المتاح: {usdt_balance}$")
    except Exception as e:
        logger.error(f"خطأ أثناء فحص الرصيد: {e}")
        
if __name__ == "__main__":
    check_usdt_balance()