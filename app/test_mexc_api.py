"""
أداة اختبار بسيطة لتوقيع طلب API لمنصة MEXC
"""
import hmac
import hashlib
import time
from urllib.parse import urlencode
import requests
import os

# BASE_URL
BASE_URL = "https://api.mexc.com"

def test_signature(api_key, api_secret):
    """
    اختبار توقيع الطلب باستخدام المفاتيح المقدمة
    """
    # الحصول على الوقت الحالي
    timestamp = int(time.time() * 1000)
    
    # إنشاء بارامترات الطلب
    params = {
        "timestamp": str(timestamp),
        "recvWindow": "5000"
    }
    
    # طباعة بارامترات الطلب
    print(f"Request parameters: {params}")
    
    # إنشاء سلسلة الاستعلام
    query_string = urlencode(params)
    
    # طباعة سلسلة الاستعلام
    print(f"Query string: {query_string}")
    
    # توقيع سلسلة الاستعلام
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # طباعة التوقيع
    print(f"Signature: {signature}")
    
    # إضافة التوقيع إلى البارامترات
    params['signature'] = signature
    
    # طباعة العنوان والرأس للطلب
    url = f"{BASE_URL}/api/v3/account"
    headers = {"X-MEXC-APIKEY": api_key}
    
    print(f"Request URL: {url}")
    print(f"Request headers: {headers}")
    print(f"Full URL with params: {url}?{urlencode(params)}")
    
    # تنفيذ الطلب
    try:
        response = requests.get(url, params=params, headers=headers)
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
    except Exception as e:
        print(f"Error during request: {e}")

if __name__ == "__main__":
    # الحصول على مفاتيح API من متغيرات البيئة
    api_key = os.environ.get("MEXC_API_KEY")
    api_secret = os.environ.get("MEXC_API_SECRET")
    
    if not api_key or not api_secret:
        print("API_KEY or API_SECRET not found in environment variables")
        exit(1)
    
    # طباعة جزء من المفاتيح
    print(f"Using API_KEY: {api_key[:5]}...")
    print(f"Using API_SECRET: {api_secret[:5]}...")
    
    # اختبار التوقيع
    test_signature(api_key, api_secret)