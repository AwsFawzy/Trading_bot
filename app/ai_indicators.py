import logging
import os
import time
import numpy as np
from datetime import datetime, timedelta

# إعداد المسجل
logger = logging.getLogger(__name__)

# مخزن مؤقت للتنبؤات
prediction_cache = {}

# فحص الـ API_KEY
try:
    from app.config import API_KEY as OPENAI_API_KEY
except ImportError:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def has_openai_key():
    """
    التحقق من وجود مفتاح OpenAI API
    
    :return: True إذا كان المفتاح موجود، False خلاف ذلك
    """
    return OPENAI_API_KEY is not None and len(OPENAI_API_KEY) > 10

def generate_market_insights(symbol=None):
    """
    توليد نصائح وتحليلات باستخدام الذكاء الاصطناعي
    
    :param symbol: رمز العملة (اختياري)
    :return: التحليل والنصائح
    """
    if not has_openai_key():
        logger.warning("مفتاح OpenAI API غير متوفر. لا يمكن توليد تحليلات الذكاء الاصطناعي.")
        return {"error": "مفتاح OpenAI API غير متوفر"}
    
    try:
        # التحقق من الذاكرة المؤقتة أولاً (صالحة لمدة 2 ساعة)
        cache_key = f"insights_{symbol if symbol else 'market'}"
        if cache_key in prediction_cache:
            cache_time, cache_value = prediction_cache[cache_key]
            if time.time() - cache_time < 7200:  # 2 ساعة = 7200 ثانية
                return cache_value
        
        # جمع بيانات السوق
        from app.market_analyzer import get_market_sentiment, analyze_market_cycles
        
        market_sentiment = get_market_sentiment()
        market_cycles = analyze_market_cycles()
        
        # جمع بيانات عن العملة المحددة (إذا تم تحديدها)
        coin_data = {}
        if symbol:
            from app.market_analyzer import get_price_change_24h, predict_next_move
            from app.exchange_manager import get_current_price
            
            coin_data = {
                "symbol": symbol,
                "price_change_24h": get_price_change_24h(symbol),
                "current_price": get_current_price(symbol),
                "prediction": predict_next_move(symbol)
            }
        
        # إعداد البيانات للتحليل
        analysis_data = {
            "market_sentiment": market_sentiment,
            "market_phase": market_cycles.get("market_phase"),
            "btc_change_24h": market_cycles.get("btc_change_24h"),
            "request_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "coin_data": coin_data
        }
        
        # استدعاء OpenAI API لتحليل البيانات
        try:
            import json
            from openai import OpenAI
            
            # إنشاء عميل OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            # تحضير الرسالة بناءً على البيانات المتاحة
            if symbol:
                prompt = f"""
                أنت خبير في أسواق العملات الرقمية. قم بتحليل البيانات التالية عن عملة {symbol}:
                
                - سعر العملة الحالي: {coin_data.get('current_price')}
                - تغير السعر خلال 24 ساعة: {coin_data.get('price_change_24h')}%
                - توقع الحركة القادمة: {coin_data.get('prediction').get('direction')} (ثقة: {coin_data.get('prediction').get('confidence')})
                
                معلومات السوق العامة:
                - حالة السوق: {analysis_data.get('market_phase')}
                - مؤشر المشاعر السوقية: {analysis_data.get('market_sentiment')}
                - تغير بيتكوين خلال 24 ساعة: {analysis_data.get('btc_change_24h')}%
                
                قدم:
                1. تحليل موجز للوضع الحالي لهذه العملة
                2. نصائح محددة للتداول (شراء/بيع/انتظار)
                3. مستويات سعرية مهمة للمراقبة
                
                قدم الإجابة بتنسيق JSON مع المفاتيح: analysis, recommendation, key_levels
                """
            else:
                prompt = f"""
                أنت خبير في أسواق العملات الرقمية. قم بتحليل البيانات التالية عن السوق:
                
                - حالة السوق: {analysis_data.get('market_phase')}
                - مؤشر المشاعر السوقية: {analysis_data.get('market_sentiment')}
                - تغير بيتكوين خلال 24 ساعة: {analysis_data.get('btc_change_24h')}%
                
                قدم:
                1. تحليل موجز للوضع الحالي للسوق
                2. نصائح عامة للتداول في هذه الظروف
                3. قطاعات أو عملات يجب مراقبتها في هذه الفترة
                
                قدم الإجابة بتنسيق JSON مع المفاتيح: analysis, recommendation, sectors_to_watch
                """
            
            # استدعاء API
            response = client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "أنت مستشار تداول محترف متخصص في أسواق العملات الرقمية."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            # استخراج الرد
            if response and response.choices and len(response.choices) > 0:
                result = json.loads(response.choices[0].message.content)
                
                # تخزين في الذاكرة المؤقتة
                prediction_cache[cache_key] = (time.time(), result)
                
                return result
            else:
                return {"error": "فشل في الحصول على رد من OpenAI"}
        
        except Exception as api_error:
            logger.error(f"خطأ في استدعاء OpenAI API: {api_error}")
            return {"error": f"خطأ في استدعاء OpenAI API: {str(api_error)}"}
    
    except Exception as e:
        logger.error(f"خطأ في توليد تحليلات السوق: {e}")
        return {"error": f"خطأ في توليد تحليلات السوق: {str(e)}"}

def predict_optimal_trading_params(symbol):
    """
    التنبؤ بالمعلمات المثلى للتداول (مثل وقف الخسارة وهدف الربح) بناءً على التحليل الذكي
    
    :param symbol: رمز العملة
    :return: المعلمات المقترحة
    """
    if not has_openai_key():
        logger.warning("مفتاح OpenAI API غير متوفر. لا يمكن التنبؤ بمعلمات التداول المثلى.")
        return None
    
    try:
        # التحقق من الذاكرة المؤقتة أولاً (صالحة لمدة 1 ساعة)
        cache_key = f"params_{symbol}"
        if cache_key in prediction_cache:
            cache_time, cache_value = prediction_cache[cache_key]
            if time.time() - cache_time < 3600:  # 1 ساعة = 3600 ثانية
                return cache_value
        
        # جمع البيانات اللازمة
        from app.risk_manager import get_volatility
        from app.market_analyzer import get_price_change_24h, predict_next_move
        
        volatility = get_volatility(symbol)
        price_change_24h = get_price_change_24h(symbol)
        next_move = predict_next_move(symbol)
        
        # تحليل البيانات التقنية أولاً
        if volatility is not None:
            # حساب مستويات جني الأرباح ووقف الخسارة بناءً على التقلب
            take_profit = min(max(0.002, volatility / 2), 0.05)  # بين 0.2% و5%
            take_profit_2 = take_profit * 2
            take_profit_3 = take_profit * 3
            
            stop_loss = min(max(0.005, volatility), 0.03)  # بين 0.5% و3%
            
            # التكيف مع التنبؤ بالحركة القادمة
            if next_move.get('direction') == 'هبوط' and next_move.get('confidence') > 0.6:
                # تخفيض حد الربح وزيادة وقف الخسارة في حالة التنبؤ بالهبوط
                take_profit = take_profit * 0.8
                stop_loss = stop_loss * 1.2
            elif next_move.get('direction') == 'صعود' and next_move.get('confidence') > 0.6:
                # زيادة حد الربح وتخفيض وقف الخسارة في حالة التنبؤ بالصعود
                take_profit = take_profit * 1.2
                stop_loss = stop_loss * 0.8
            
            # إنشاء المعلمات المقترحة
            params = {
                "symbol": symbol,
                "take_profit": round(take_profit, 4),
                "take_profit_2": round(take_profit_2, 4),
                "take_profit_3": round(take_profit_3, 4),
                "stop_loss": round(stop_loss, 4),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "based_on": {
                    "volatility": volatility,
                    "price_change_24h": price_change_24h,
                    "predicted_direction": next_move.get('direction'),
                    "prediction_confidence": next_move.get('confidence')
                }
            }
            
            # تخزين في الذاكرة المؤقتة
            prediction_cache[cache_key] = (time.time(), params)
            
            return params
        else:
            logger.warning(f"بيانات التقلب غير متوفرة لـ {symbol}")
            return None
    
    except Exception as e:
        logger.error(f"خطأ في التنبؤ بمعلمات التداول المثلى: {e}")
        return None