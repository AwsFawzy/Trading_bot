"""
وحدة مراقبة السوق المتخصصة لتحديد فرص الربح اليومية
تعمل بشكل منفصل عن البوت الرئيسي وتركز على تحليل عميق للسوق
"""
import logging
import threading
import time
from typing import List, Dict, Any, Tuple
import os
import json
from datetime import datetime, timedelta

from app.exchange_manager import get_klines, get_all_symbols_24h_data, get_current_price
from app.ai_model import predict_trend, predict_potential_profit, analyze_market_sentiment
from app.utils import get_timestamp_str, load_json_data, save_json_data
from app.candlestick_patterns import detect_candlestick_patterns, get_entry_signal
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# متغيرات عالمية
monitor_running = False
monitor_thread = None
market_opportunities = []  # فرص السوق المكتشفة
daily_reports = []  # تقارير يومية لحركة الأسعار

# العملات ذات الأولوية العالية للمراقبة (تركيز على العملات الرئيسية والنشطة)
HIGH_PRIORITY_COINS = [
    'DOGEUSDT',    # دوجكوين - التركيز الرئيسي
    'BTCUSDT',     # بيتكوين - مؤشر اتجاه السوق
    'ETHUSDT',     # إيثريوم - مؤشر اتجاه السوق
    'BNBUSDT',     # بينانس كوين
    'SHIBUSDT',    # شيبا
    'SOLUSDT',     # سولانا
    'TRXUSDT',     # ترون
    'XRPUSDT',     # ريبل
    'MATICUSDT',   # بوليجون
    'LTCUSDT',     # لايتكوين
]

# معايير اكتشاف الفرص
MIN_POTENTIAL_PROFIT = 0.8  # الحد الأدنى للربح المحتمل (%)
MAX_RISK_REWARD_RATIO = 2.0  # نسبة العائد إلى المخاطرة
MIN_CONFIDENCE_SCORE = 0.65  # الحد الأدنى لدرجة الثقة (0-1)

class MarketOpportunity:
    """فئة تمثل فرصة تداول في السوق"""
    
    def __init__(self, symbol: str, entry_price: float, potential_profit: float, 
                 confidence: float, reason: str, timeframe: str):
        self.symbol = symbol
        self.entry_price = entry_price
        self.potential_profit = potential_profit
        self.confidence = confidence
        self.reason = reason
        self.timeframe = timeframe
        self.timestamp = datetime.now()
        self.realized = False
        self.take_profit_price = round(entry_price * (1 + potential_profit/100), 8)
        self.stop_loss_price = round(entry_price * (1 - (potential_profit/100)/MAX_RISK_REWARD_RATIO), 8)
        self.volume_24h = 0
        self.pattern_info = {}
        
    def to_dict(self) -> Dict[str, Any]:
        """تحويل الفرصة إلى قاموس"""
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'potential_profit': self.potential_profit,
            'confidence': self.confidence,
            'reason': self.reason,
            'timeframe': self.timeframe,
            'timestamp': self.timestamp.timestamp(),
            'date': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'take_profit_price': self.take_profit_price,
            'stop_loss_price': self.stop_loss_price,
            'realized': self.realized,
            'volume_24h': self.volume_24h,
            'pattern_info': self.pattern_info
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketOpportunity':
        """إنشاء فرصة من قاموس"""
        opportunity = cls(
            symbol=data.get('symbol', ''),
            entry_price=data.get('entry_price', 0.0),
            potential_profit=data.get('potential_profit', 0.0),
            confidence=data.get('confidence', 0.0),
            reason=data.get('reason', ''),
            timeframe=data.get('timeframe', '')
        )
        opportunity.timestamp = datetime.fromtimestamp(data.get('timestamp', 0))
        opportunity.realized = data.get('realized', False)
        opportunity.take_profit_price = data.get('take_profit_price')
        opportunity.stop_loss_price = data.get('stop_loss_price')
        opportunity.volume_24h = data.get('volume_24h', 0)
        opportunity.pattern_info = data.get('pattern_info', {})
        return opportunity


def analyze_price_action(symbol: str) -> Dict[str, Any]:
    """
    تحليل حركة السعر لعملة محددة عبر إطارات زمنية متعددة
    
    :param symbol: رمز العملة
    :return: نتائج التحليل
    """
    results = {
        'symbol': symbol,
        'price': get_current_price(symbol),
        'timestamp': get_timestamp_str(),
        'timeframes': {},
        'summary': {}
    }
    
    # إطارات زمنية متعددة للتحليل الشامل
    timeframes = {
        '5m': {'limit': 60, 'description': 'قصير المدى'},  # آخر 5 ساعات
        '15m': {'limit': 48, 'description': 'متوسط المدى'}, # آخر 12 ساعة
        '1h': {'limit': 24, 'description': 'طويل المدى'},   # آخر 24 ساعة
    }
    
    # جمع بيانات جميع الإطارات الزمنية
    for tf, tf_info in timeframes.items():
        try:
            tf_value = tf if tf != '1h' else '60m'  # تصحيح الفاصل الزمني لـ MEXC API
            klines = get_klines(symbol, tf_value, tf_info['limit'])
            if not klines:
                continue
                
            # تحليل شامل للإطار الزمني
            trend = predict_trend(klines)
            potential_profit = predict_potential_profit(klines)
            
            # تحليل أنماط الشموع
            patterns = detect_candlestick_patterns(klines)
            
            # تحليل الشعور العام للسوق
            sentiment = analyze_market_sentiment(klines)
            
            # حساب قوة الاتجاه والثقة
            trend_strength = 0.5  # قيمة افتراضية
            if patterns.get('strength'):
                trend_strength = patterns.get('strength')
            
            # تخزين النتائج لهذا الإطار الزمني
            results['timeframes'][tf] = {
                'trend': trend,
                'potential_profit': potential_profit,
                'patterns': patterns,
                'sentiment': sentiment,
                'trend_strength': trend_strength
            }
        except Exception as e:
            logger.error(f"خطأ في تحليل الإطار الزمني {tf} للعملة {symbol}: {e}")
    
    # تلخيص النتائج عبر جميع الإطارات الزمنية
    if results['timeframes']:
        # حساب الاتجاه الإجمالي
        trend_votes = {'up': 0, 'down': 0, 'neutral': 0}
        weighted_profit = 0
        confidence = 0
        timeframe_weights = {'5m': 0.2, '15m': 0.3, '1h': 0.5}  # وزن كل إطار زمني
        
        for tf, tf_data in results['timeframes'].items():
            if tf_data['trend'] in trend_votes:
                trend_votes[tf_data['trend']] += int(timeframe_weights.get(tf, 0.3) * 100) / 100
            weighted_profit += tf_data['potential_profit'] * timeframe_weights.get(tf, 0.3)
            
            # بناء درجة الثقة
            if tf_data['sentiment'].get('sentiment') in ['bullish', 'strongly_bullish']:
                confidence += 0.2 * timeframe_weights.get(tf, 0.3)
            
            if tf_data['patterns'].get('direction') == 'bullish':
                confidence += 0.3 * timeframe_weights.get(tf, 0.3)
            
            if tf_data['trend'] == 'up':
                confidence += 0.2 * timeframe_weights.get(tf, 0.3)
        
        # تحديد الاتجاه الإجمالي
        if trend_votes['up'] > trend_votes['down'] + trend_votes['neutral']:
            overall_trend = 'up'
        elif trend_votes['down'] > trend_votes['up'] + trend_votes['neutral']:
            overall_trend = 'down'
        else:
            overall_trend = 'neutral'
        
        # تخزين الملخص
        results['summary'] = {
            'overall_trend': overall_trend,
            'weighted_profit': weighted_profit,
            'confidence': min(confidence, 1.0),  # لا تتجاوز 1.0
            'suitable_for_trading': overall_trend == 'up' and weighted_profit >= MIN_POTENTIAL_PROFIT/100 and confidence >= MIN_CONFIDENCE_SCORE
        }
        
        # إضافة سبب مناسب للتداول
        if results['summary']['suitable_for_trading']:
            reasons = []
            for tf, tf_data in results['timeframes'].items():
                if tf_data['trend'] == 'up':
                    reasons.append(f"{tf} اتجاه صاعد")
                if tf_data['patterns'].get('pattern_names'):
                    patterns_found = tf_data['patterns'].get('pattern_names', [])
                    if patterns_found:
                        reasons.append(f"{tf} {', '.join(patterns_found[:2])}")
            
            results['summary']['trading_reason'] = ' | '.join(reasons[:3]) if reasons else "تحليل فني إيجابي"
    
    return results


def scan_for_opportunities() -> List[MarketOpportunity]:
    """
    فحص شامل للعملات الرئيسية والأكثر نشاطاً للعثور على فرص تداول مربحة
    
    :return: قائمة بفرص التداول
    """
    opportunities = []
    
    # الحصول على معلومات السوق
    market_data = get_all_symbols_24h_data()
    if not market_data:
        logger.error("فشل في الحصول على بيانات السوق")
        return opportunities
    
    # تصفية العملات ذات النشاط العالي
    active_symbols = {}
    high_priority_symbols = {s: {'priority': True} for s in HIGH_PRIORITY_COINS}
    
    for symbol_data in market_data:
        symbol = symbol_data.get('symbol', '')
        
        # فقط العملات المقترنة بـ USDT
        if not symbol.endswith('USDT'):
            continue
            
        # إضافة البيانات إلى القاموس
        is_high_priority = symbol in high_priority_symbols
        
        # حساب نقاط التصنيف
        volume = float(symbol_data.get('quoteVolume', 0))
        price = float(symbol_data.get('lastPrice', 0))
        change_pct = float(symbol_data.get('priceChangePercent', 0))
        
        # نقاط التصنيف تعتمد على الحجم والسعر وحركة السعر
        score = volume / 1000000  # نقطة لكل مليون دولار
        
        # إذا كان التغير اليومي إيجابياً، زيادة النقاط
        if change_pct > 0:
            score += change_pct * 0.1
        
        # إضافة العملة إلى القائمة مع معلوماتها
        active_symbols[symbol] = {
            'price': price,
            'volume': volume,
            'change_pct': change_pct,
            'score': score,
            'high_priority': is_high_priority
        }
    
    # ترتيب العملات حسب الأولوية أولاً ثم النقاط
    sorted_symbols = sorted(
        active_symbols.items(),
        key=lambda x: (not x[1]['high_priority'], -x[1]['score'])
    )
    
    # تحليل أفضل 30 عملة فقط (جميع العملات ذات الأولوية + أعلى العملات نقاطاً)
    symbols_to_analyze = sorted_symbols[:30]
    
    logger.info(f"تحليل {len(symbols_to_analyze)} عملة بحثاً عن فرص تداول...")
    
    # تحليل كل عملة بعمق
    for symbol_tuple in symbols_to_analyze:
        symbol = symbol_tuple[0]
        symbol_info = symbol_tuple[1]
        
        try:
            # تحليل شامل متعدد الإطارات الزمنية
            analysis = analyze_price_action(symbol)
            
            # التحقق من ملاءمة العملة للتداول
            if analysis['summary'].get('suitable_for_trading', False):
                # إنشاء فرصة جديدة
                opportunity = MarketOpportunity(
                    symbol=symbol,
                    entry_price=analysis['price'],
                    potential_profit=analysis['summary']['weighted_profit'] * 100,  # تحويل إلى نسبة مئوية
                    confidence=analysis['summary']['confidence'],
                    reason=analysis['summary'].get('trading_reason', 'تحليل فني'),
                    timeframe=max(analysis['timeframes'].keys(), key=lambda k: analysis['timeframes'][k]['trend_strength'])
                )
                
                # إضافة معلومات إضافية
                opportunity.volume_24h = symbol_info['volume']
                
                # إضافة معلومات الأنماط من جميع الإطارات الزمنية
                for tf, tf_data in analysis['timeframes'].items():
                    if 'patterns' in tf_data and tf_data['patterns'].get('pattern_names'):
                        opportunity.pattern_info[tf] = tf_data['patterns'].get('pattern_names', [])
                
                opportunities.append(opportunity)
                logger.info(f"تم العثور على فرصة تداول لـ {symbol} - الربح المحتمل: {opportunity.potential_profit:.2f}%")
        except Exception as e:
            logger.error(f"خطأ في تحليل العملة {symbol}: {e}")
    
    # ترتيب الفرص حسب الثقة والربح المحتمل
    sorted_opportunities = sorted(
        opportunities,
        key=lambda x: (x.confidence * x.potential_profit),
        reverse=True
    )
    
    return sorted_opportunities


def save_opportunities(opportunities: List[MarketOpportunity]):
    """
    حفظ فرص التداول في ملف
    
    :param opportunities: قائمة بفرص التداول
    """
    try:
        # تحويل الفرص إلى قواميس
        opportunities_dict = [opp.to_dict() for opp in opportunities]
        
        # حفظ الفرص في ملف
        save_json_data(opportunities_dict, 'market_opportunities.json')
        logger.info(f"تم حفظ {len(opportunities)} فرصة تداول في market_opportunities.json")
    except Exception as e:
        logger.error(f"خطأ في حفظ فرص التداول: {e}")


def load_opportunities() -> List[MarketOpportunity]:
    """
    تحميل فرص التداول من ملف
    
    :return: قائمة بفرص التداول
    """
    try:
        # تحميل الفرص من ملف
        opportunities_dict = load_json_data('market_opportunities.json', [])
        
        # تحويل القواميس إلى فرص
        opportunities = [MarketOpportunity.from_dict(opp) for opp in opportunities_dict]
        
        logger.info(f"تم تحميل {len(opportunities)} فرصة تداول من market_opportunities.json")
        return opportunities
    except Exception as e:
        logger.error(f"خطأ في تحميل فرص التداول: {e}")
        return []


def generate_daily_market_report() -> Dict[str, Any]:
    """
    إنشاء تقرير يومي شامل عن حالة السوق وأداء العملات المختلفة
    
    :return: تقرير السوق
    """
    report = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'timestamp': datetime.now().timestamp(),
        'market_summary': {},
        'top_performers': [],
        'trading_opportunities': [],
        'high_priority_coins': {}
    }
    
    try:
        # الحصول على معلومات السوق
        market_data = get_all_symbols_24h_data()
        if not market_data:
            logger.error("فشل في الحصول على بيانات السوق للتقرير اليومي")
            return report
        
        # حساب متوسط التغير في السوق
        total_change_pct = 0
        positive_count = 0
        negative_count = 0
        usdt_pairs_count = 0
        
        # قائمة للعملات ذات الأداء الأفضل
        all_coins = []
        
        for symbol_data in market_data:
            symbol = symbol_data.get('symbol', '')
            
            # فقط العملات المقترنة بـ USDT
            if not symbol.endswith('USDT'):
                continue
                
            usdt_pairs_count += 1
            change_pct = float(symbol_data.get('priceChangePercent', 0))
            total_change_pct += change_pct
            
            if change_pct > 0:
                positive_count += 1
            elif change_pct < 0:
                negative_count += 1
            
            # حفظ معلومات العملة
            all_coins.append({
                'symbol': symbol,
                'price': float(symbol_data.get('lastPrice', 0)),
                'change_pct': change_pct,
                'volume': float(symbol_data.get('quoteVolume', 0))
            })
            
            # تتبع العملات ذات الأولوية
            if symbol in HIGH_PRIORITY_COINS:
                report['high_priority_coins'][symbol] = {
                    'price': float(symbol_data.get('lastPrice', 0)),
                    'change_pct': change_pct,
                    'volume': float(symbol_data.get('quoteVolume', 0))
                }
        
        # ملخص السوق
        report['market_summary'] = {
            'average_change': total_change_pct / usdt_pairs_count if usdt_pairs_count > 0 else 0,
            'positive_coins': positive_count,
            'negative_coins': negative_count,
            'total_coins': usdt_pairs_count,
            'market_sentiment': 'bullish' if positive_count > negative_count else 'bearish',
            'strength': abs(positive_count - negative_count) / usdt_pairs_count if usdt_pairs_count > 0 else 0
        }
        
        # ترتيب العملات حسب التغير اليومي
        all_coins.sort(key=lambda x: x['change_pct'], reverse=True)
        
        # إضافة أفضل 10 عملات
        report['top_performers'] = all_coins[:10]
        
        # إضافة فرص التداول
        opportunities = scan_for_opportunities()
        report['trading_opportunities'] = [opp.to_dict() for opp in opportunities[:5]]
        
        # حفظ التقرير اليومي
        save_json_data(report, f'daily_report_{report["date"]}.json')
        
        # إضافة التقرير إلى قائمة التقارير اليومية
        global daily_reports
        daily_reports.append(report)
        
        # إرسال ملخص التقرير عبر تيليجرام
        send_telegram_report(report)
        
        logger.info(f"تم إنشاء تقرير يومي للسوق: {report['date']}")
        return report
    except Exception as e:
        logger.error(f"خطأ في إنشاء التقرير اليومي: {e}")
        return report


def send_telegram_report(report: Dict[str, Any]):
    """
    إرسال ملخص التقرير اليومي عبر تيليجرام
    
    :param report: التقرير اليومي
    """
    try:
        from app.telegram_notify import send_telegram_message
        
        market_summary = report['market_summary']
        
        # بناء رسالة الملخص
        message = f"📊 تقرير السوق اليومي ({report['date']})\n\n"
        message += f"🔹 حالة السوق: {'📈 صاعد' if market_summary['market_sentiment'] == 'bullish' else '📉 هابط'}\n"
        message += f"🔹 متوسط التغير: {market_summary['average_change']:.2f}%\n"
        message += f"🔹 العملات الإيجابية: {market_summary['positive_coins']} ({market_summary['positive_coins']/market_summary['total_coins']*100:.1f}%)\n"
        message += f"🔹 العملات السلبية: {market_summary['negative_coins']} ({market_summary['negative_coins']/market_summary['total_coins']*100:.1f}%)\n\n"
        
        # أفضل العملات أداءً
        message += "🏆 أفضل العملات أداءً اليوم:\n"
        for i, coin in enumerate(report['top_performers'][:5]):
            message += f"{i+1}. {coin['symbol']}: {coin['change_pct']:.2f}% بحجم ${coin['volume']/1000000:.1f}M\n"
        
        # فرص التداول
        message += "\n💰 أفضل فرص التداول:\n"
        for i, opp in enumerate(report['trading_opportunities'][:3]):
            message += f"{i+1}. {opp['symbol']} - ربح محتمل: {opp['potential_profit']:.2f}%\n"
            message += f"   السبب: {opp['reason']}\n"
        
        # العملات ذات الأولوية
        message += "\n🔍 العملات ذات الأولوية:\n"
        for symbol, data in list(report['high_priority_coins'].items())[:5]:
            message += f"• {symbol}: {data['change_pct']:.2f}% بسعر {data['price']}\n"
        
        # إرسال الرسالة
        send_telegram_message(message)
        logger.info("تم إرسال تقرير السوق اليومي عبر تيليجرام")
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير السوق عبر تيليجرام: {e}")


def monitor_market(interval=1800):
    """
    مراقبة السوق بشكل مستمر والبحث عن فرص جديدة
    
    :param interval: الفاصل الزمني بين عمليات الفحص (بالثواني)
    """
    global market_opportunities, monitor_running
    
    while monitor_running:
        try:
            logger.info("بدء فحص السوق بحثاً عن فرص جديدة...")
            
            # البحث عن فرص جديدة
            new_opportunities = scan_for_opportunities()
            
            # تحديث قائمة الفرص
            market_opportunities = new_opportunities
            
            # حفظ الفرص
            save_opportunities(market_opportunities)
            
            # توليد تقرير يومي إذا كان وقت التقرير (الساعة 8 مساءً)
            now = datetime.now()
            if now.hour == 20 and now.minute < 30:  # بين الساعة 8:00 و 8:30 مساءً
                generate_daily_market_report()
            
            # فحص الفرص الحالية ومعرفة إذا تم تحقيقها
            check_opportunity_status()
            
            logger.info(f"تم العثور على {len(market_opportunities)} فرصة تداول جديدة")
            logger.info(f"انتظار {interval//60} دقيقة قبل الفحص التالي...")
            
            # انتظار الفاصل الزمني المحدد
            time.sleep(interval)
        except Exception as e:
            logger.error(f"خطأ في مراقبة السوق: {e}")
            time.sleep(300)  # انتظار 5 دقائق في حالة حدوث خطأ


def check_opportunity_status():
    """
    فحص حالة الفرص المكتشفة مسبقاً ومعرفة إذا تم تحقيقها
    """
    global market_opportunities
    
    for opportunity in market_opportunities:
        if opportunity.realized:
            continue
            
        try:
            # الحصول على السعر الحالي
            current_price = get_current_price(opportunity.symbol)
            if not current_price:
                continue
                
            # التحقق مما إذا تم تحقيق هدف الربح
            if current_price >= opportunity.take_profit_price:
                opportunity.realized = True
                logger.info(f"تم تحقيق هدف الربح للعملة {opportunity.symbol} - ربح {opportunity.potential_profit:.2f}%")
                
                # إرسال إشعار عن تحقيق الهدف
                from app.telegram_notify import send_telegram_message
                message = f"🎯 تم تحقيق هدف الربح!\n"
                message += f"العملة: {opportunity.symbol}\n"
                message += f"سعر الدخول: {opportunity.entry_price}\n"
                message += f"سعر الخروج: {current_price}\n"
                message += f"الربح: {opportunity.potential_profit:.2f}%\n"
                message += f"الإطار الزمني: {opportunity.timeframe}\n"
                send_telegram_message(message)
            
            # التحقق مما إذا تم تفعيل وقف الخسارة
            elif current_price <= opportunity.stop_loss_price:
                opportunity.realized = True
                loss_pct = (current_price - opportunity.entry_price) / opportunity.entry_price * 100
                logger.info(f"تم تفعيل وقف الخسارة للعملة {opportunity.symbol} - خسارة {loss_pct:.2f}%")
                
                # إرسال إشعار عن تفعيل وقف الخسارة
                from app.telegram_notify import send_telegram_message
                message = f"⚠️ تم تفعيل وقف الخسارة!\n"
                message += f"العملة: {opportunity.symbol}\n"
                message += f"سعر الدخول: {opportunity.entry_price}\n"
                message += f"سعر الخروج: {current_price}\n"
                message += f"الخسارة: {loss_pct:.2f}%\n"
                message += f"الإطار الزمني: {opportunity.timeframe}\n"
                send_telegram_message(message)
        except Exception as e:
            logger.error(f"خطأ في فحص حالة الفرصة للعملة {opportunity.symbol}: {e}")
    
    # حفظ الفرص بعد التحديث
    save_opportunities(market_opportunities)


def start_market_monitor(interval=1800):
    """
    بدء مراقبة السوق في خيط منفصل
    
    :param interval: الفاصل الزمني بين عمليات الفحص (بالثواني)
    """
    global monitor_running, monitor_thread, market_opportunities
    
    if monitor_running:
        logger.warning("مراقبة السوق قيد التشغيل بالفعل")
        return False
    
    # تحميل الفرص السابقة
    market_opportunities = load_opportunities()
    
    # بدء المراقبة
    monitor_running = True
    monitor_thread = threading.Thread(target=monitor_market, args=(interval,), daemon=True)
    monitor_thread.start()
    
    logger.info(f"تم بدء مراقبة السوق (الفاصل الزمني: {interval//60} دقيقة)")
    return True


def stop_market_monitor():
    """
    إيقاف مراقبة السوق
    
    :return: True إذا تم الإيقاف بنجاح
    """
    global monitor_running, monitor_thread
    
    if not monitor_running:
        logger.warning("مراقبة السوق متوقفة بالفعل")
        return False
    
    # إيقاف المراقبة
    monitor_running = False
    
    # انتظار إنهاء الخيط
    if monitor_thread:
        monitor_thread.join(timeout=1.0)
    
    logger.info("تم إيقاف مراقبة السوق")
    return True


def get_latest_opportunities(limit=10) -> List[Dict[str, Any]]:
    """
    الحصول على أحدث فرص التداول
    
    :param limit: عدد الفرص المطلوبة
    :return: قائمة بالفرص
    """
    global market_opportunities
    
    # ترتيب الفرص حسب التاريخ (الأحدث أولاً)
    sorted_opportunities = sorted(
        market_opportunities,
        key=lambda x: x.timestamp,
        reverse=True
    )
    
    # إرجاع الفرص المطلوبة
    return [opp.to_dict() for opp in sorted_opportunities[:limit]]


def get_best_opportunities(limit=10) -> List[Dict[str, Any]]:
    """
    الحصول على أفضل فرص التداول
    
    :param limit: عدد الفرص المطلوبة
    :return: قائمة بالفرص
    """
    global market_opportunities
    
    # ترتيب الفرص حسب الثقة والربح المحتمل
    sorted_opportunities = sorted(
        market_opportunities,
        key=lambda x: (x.confidence * x.potential_profit),
        reverse=True
    )
    
    # إرجاع الفرص المطلوبة
    return [opp.to_dict() for opp in sorted_opportunities[:limit]]


def get_opportunity_details(symbol: str) -> Dict[str, Any]:
    """
    الحصول على تفاصيل فرصة تداول لعملة محددة
    
    :param symbol: رمز العملة
    :return: تفاصيل الفرصة
    """
    global market_opportunities
    
    # البحث عن الفرصة
    opportunity = next((opp for opp in market_opportunities if opp.symbol == symbol), None)
    
    if opportunity:
        # إرجاع تفاصيل الفرصة
        details = opportunity.to_dict()
        
        # إضافة تحليل إضافي
        try:
            analysis = analyze_price_action(symbol)
            details['analysis'] = analysis
        except Exception as e:
            logger.error(f"خطأ في الحصول على تحليل إضافي للعملة {symbol}: {e}")
        
        return details
    else:
        return {'error': f'لم يتم العثور على فرصة للعملة {symbol}'}


def get_market_summary() -> Dict[str, Any]:
    """
    الحصول على ملخص حالة السوق
    
    :return: ملخص السوق
    """
    try:
        # الحصول على معلومات السوق
        market_data = get_all_symbols_24h_data()
        if not market_data:
            logger.error("فشل في الحصول على بيانات السوق للملخص")
            return {}
        
        # حساب متوسط التغير في السوق
        total_change_pct = 0
        positive_count = 0
        negative_count = 0
        usdt_pairs_count = 0
        
        # معلومات العملات ذات الأولوية
        high_priority_coins = {}
        
        for symbol_data in market_data:
            symbol = symbol_data.get('symbol', '')
            
            # فقط العملات المقترنة بـ USDT
            if not symbol.endswith('USDT'):
                continue
                
            usdt_pairs_count += 1
            change_pct = float(symbol_data.get('priceChangePercent', 0))
            total_change_pct += change_pct
            
            if change_pct > 0:
                positive_count += 1
            elif change_pct < 0:
                negative_count += 0
            
            # تتبع العملات ذات الأولوية
            if symbol in HIGH_PRIORITY_COINS:
                high_priority_coins[symbol] = {
                    'price': float(symbol_data.get('lastPrice', 0)),
                    'change_pct': change_pct,
                    'volume': float(symbol_data.get('quoteVolume', 0))
                }
        
        # ملخص السوق
        summary = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'average_change': total_change_pct / usdt_pairs_count if usdt_pairs_count > 0 else 0,
            'positive_coins': positive_count,
            'negative_coins': negative_count,
            'total_coins': usdt_pairs_count,
            'market_sentiment': 'bullish' if positive_count > negative_count else 'bearish',
            'strength': abs(positive_count - negative_count) / usdt_pairs_count if usdt_pairs_count > 0 else 0,
            'high_priority_coins': high_priority_coins
        }
        
        return summary
    except Exception as e:
        logger.error(f"خطأ في الحصول على ملخص السوق: {e}")
        return {}


def get_market_monitor_status() -> Dict[str, Any]:
    """
    الحصول على حالة مراقب السوق
    
    :return: حالة المراقب
    """
    global monitor_running, market_opportunities
    
    return {
        'running': monitor_running,
        'opportunities_count': len(market_opportunities),
        'unrealized_opportunities': len([opp for opp in market_opportunities if not opp.realized]),
        'realized_opportunities': len([opp for opp in market_opportunities if opp.realized]),
        'last_scan': market_opportunities[0].timestamp.strftime('%Y-%m-%d %H:%M:%S') if market_opportunities else None
    }


# بدء مراقبة السوق عند استيراد الوحدة
# start_market_monitor(interval=1800)  # مراقبة كل 30 دقيقة