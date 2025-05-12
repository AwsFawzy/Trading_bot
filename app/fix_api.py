"""
أداة إصلاح MEXC API وتحديث مفاتيح API
"""
import os
import hmac
import hashlib
import time
import requests
import json
from urllib.parse import urlencode

# الحصول على المفاتيح من متغيرات البيئة
API_KEY = os.environ.get("MEXC_API_KEY")
API_SECRET = os.environ.get("MEXC_API_SECRET")

BASE_URL = "https://api.mexc.com"

def check_and_fix_api():
    """
    التحقق من عمل مفاتيح API واختبار الاتصال بـ MEXC
    """
    if not API_KEY or not API_SECRET:
        print("❌ API_KEY or API_SECRET not found in environment variables")
        return False
    
    print(f"🔑 Using API_KEY: {API_KEY[:5]}...{API_KEY[-5:]}")
    print(f"🔒 Using API_SECRET: {API_SECRET[:5]}...")
    
    # ===================== اختبار جلب معلومات الحساب =====================
    print("\n🔍 Testing Account Endpoint...")
    account_data = get_account_info()
    
    if not account_data:
        print("❌ Could not get account data")
        return False
        
    print("✅ Successfully connected to account endpoint!")
    
    # طباعة الرصيد المتاح
    print("\n💰 Available Balances:")
    for balance in account_data.get('balances', []):
        if float(balance['free']) > 0 or float(balance['locked']) > 0:
            print(f"  • {balance['asset']}: {balance['free']} (free) / {balance['locked']} (locked)")
    
    # ===================== اختبار الصفقات المفتوحة =====================
    print("\n🔍 Testing Open Orders Endpoint...")
    open_orders = get_open_orders()
    
    if open_orders is None:
        print("❌ Could not get open orders")
        return False
        
    print(f"✅ Successfully connected to open orders endpoint! Found {len(open_orders)} open orders.")
    
    if open_orders:
        print("\n📊 Open Orders:")
        for order in open_orders:
            print(f"  • {order.get('symbol')}: {order.get('side')} {order.get('origQty')} @ {order.get('price')}")
    
    print("\n✅ All API tests passed successfully!")
    return True

def get_account_info():
    """
    الحصول على معلومات الحساب من MEXC API
    """
    timestamp = int(time.time() * 1000)
    
    params = {
        "timestamp": str(timestamp),
        "recvWindow": "5000"
    }
    
    query_string = urlencode(params)
    
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    url = f"{BASE_URL}/api/v3/account"
    headers = {"X-MEXC-APIKEY": API_KEY}
    
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(url, params=params, headers=headers)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return None
            
        return response.json()
    except Exception as e:
        print(f"Exception: {e}")
        return None

def get_open_orders():
    """
    الحصول على الصفقات المفتوحة من MEXC API
    """
    timestamp = int(time.time() * 1000)
    
    params = {
        "timestamp": str(timestamp),
        "recvWindow": "5000"
    }
    
    query_string = urlencode(params)
    
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    url = f"{BASE_URL}/api/v3/openOrders"
    headers = {"X-MEXC-APIKEY": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            if "No permission" in response.text:
                print("\n⚠️ PERMISSION ERROR: Your API key does not have the required permissions.")
                print("Please go to MEXC account settings > API Management and ensure READ and TRADE permissions are granted.")
            return None
            
        return response.json()
    except Exception as e:
        print(f"Exception: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 MEXC API TEST AND FIX UTILITY 🔧")
    print("=" * 60)
    check_and_fix_api()