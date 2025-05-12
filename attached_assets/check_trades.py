#!/usr/bin/env python3
import json

# تحميل الصفقات النشطة
with open('active_trades.json', 'r') as f:
    trades = json.load(f)

# حساب الصفقات المفتوحة
open_trades = [t for t in trades if t.get('status') == 'OPEN']
symbols = set([t.get('symbol') for t in open_trades])

print(f"صفقات مفتوحة: {len(open_trades)}")
print(f"عملات فريدة: {len(symbols)}")
print(f"العملات: {symbols}")

# عرض تفاصيل كل عملة
for symbol in symbols:
    symbol_trades = [t for t in open_trades if t.get('symbol') == symbol]
    print(f"\nالعملة {symbol}: {len(symbol_trades)} صفقة")
    for i, trade in enumerate(symbol_trades):
        print(f"  {i+1}. معرف: {trade.get('id')}, سعر الدخول: {trade.get('entry_price')}")