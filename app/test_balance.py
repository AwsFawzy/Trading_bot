"""
أداة اختبار للحصول على رصيد الحساب من MEXC API
"""
import os
import hmac
import hashlib
import time
import requests
import json
from urllib.parse import urlencode

BASE_URL = "https://api.mexc.com"

def get_balance():
    """
    اختبار الحصول على رصيد الحساب
    """
    api_key = os.environ.get("MEXC_API_KEY")
    api_secret = os.environ.get("MEXC_API_SECRET")
    
    if not api_key or not api_secret:
        print("API_KEY or API_SECRET not found in environment variables")
        return
    
    print(f"Using API_KEY: {api_key[:5]}...")
    print(f"Using API_SECRET: {api_secret[:5]}...")
    
    # الحصول على الوقت الحالي
    timestamp = int(time.time() * 1000)
    
    # إنشاء بارامترات الطلب
    params = {
        "timestamp": str(timestamp),
        "recvWindow": "5000"
    }
    
    # إنشاء سلسلة الاستعلام
    query_string = urlencode(params)
    
    # توقيع سلسلة الاستعلام
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # إضافة التوقيع إلى البارامترات
    params['signature'] = signature
    
    # تنفيذ الطلب
    url = f"{BASE_URL}/api/v3/account"
    headers = {"X-MEXC-APIKEY": api_key}
    
    print(f"Request URL: {url}")
    print(f"Request headers: {headers}")
    print(f"Full URL with params: {url}?{urlencode(params)}")
    
    try:
        response = requests.get(url, params=params, headers=headers)
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            # تحويل النص إلى كائن JSON
            data = response.json()
            # طباعة الرصيد بتنسيق أفضل
            print("\nBalances:")
            for balance in data.get('balances', []):
                if float(balance['free']) > 0 or float(balance['locked']) > 0:
                    print(f"- {balance['asset']}: {balance['free']} (free) / {balance['locked']} (locked)")
    except Exception as e:
        print(f"Error during request: {e}")

if __name__ == "__main__":
    get_balance()