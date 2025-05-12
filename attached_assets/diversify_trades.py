"""
برنامج تنفيذي لمنع تكرار التداولات
يجب تشغيله قبل كل تداول وبشكل دوري
"""

from symbol_blocker import enforce_diversification, get_active_symbols

def main():
    # تنفيذ التنويع وإصلاح الصفقات المكررة
    closed_count = enforce_diversification()
    print(f"تم إغلاق {closed_count} صفقة مكررة")
    
    # طباعة العملات النشطة بعد التنفيذ
    active_symbols = get_active_symbols()
    print(f"العملات المتداولة حالياً: {active_symbols}")
    
    if "XRPUSDT" in active_symbols:
        print("⚠️ تحذير: العملة XRPUSDT لا تزال نشطة!")
    else:
        print("✅ لا توجد صفقات XRPUSDT نشطة.")
    
    return True

if __name__ == "__main__":
    main()