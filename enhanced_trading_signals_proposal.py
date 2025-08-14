"""
PROPOZYCJA: Enhanced Daily Trading Signals z integracją newsów
Rozszerzenie istniejącego DailyTradingSignalGenerator o analizę sentymentu
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, time, timedelta, date
from django.utils import timezone
from django.db.models import Q, Avg
import logging

# Importy z istniejącego systemu
from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData, NewsArticleModel
from apps.analysis.models import TechnicalIndicator, IndicatorValue, TradingSignal
from apps.core.models import NewsClassification, StockSentiment
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator

logger = logging.getLogger(__name__)


class EnhancedDailyTradingSignalGenerator(DailyTradingSignalGenerator):
    """
    Rozszerzony generator sygnałów łączący analizę techniczną z analizą sentymentu.
    
    NOWE FUNKCJE:
    - Analiza sentymentu newsów z ostatnich 7 dni
    - Boost/penalty na podstawie wysokiego impactu newsów  
    - Filtrowanie sygnałów przy bardzo negatywnych newsach
    - Zwiększenie pewności przy pozytywnych newsach
    """
    
    # Nowe progi dla analizy sentymentu
    NEWS_SENTIMENT_BOOST_THRESHOLD = 0.5    # Powyżej tego sentymentu = boost
    NEWS_SENTIMENT_PENALTY_THRESHOLD = -0.5  # Poniżej tego = penalty
    HIGH_IMPACT_NEWS_MULTIPLIER = 1.5        # Mnożnik dla high/very_high impact
    NEWS_CONFIDENCE_BOOST = Decimal('15.0')   # Boost pewności za pozytywne newsy
    NEWS_CONFIDENCE_PENALTY = Decimal('20.0') # Penalty za negatywne newsy
    
    def generate_signals_for_stock(
        self, 
        stock: StockSymbol, 
        trading_session: Optional[TradingSession] = None
    ) -> Dict[str, Any]:
        """
        ROZSZERZONA wersja generatora z analizą newsów.
        """
        # 1. Najpierw wygeneruj bazowy sygnał (istniejąca logika)
        base_result = super().generate_signals_for_stock(stock, trading_session)
        
        # 2. Analizuj newsy dla tej akcji
        news_analysis = self._analyze_stock_news_sentiment(stock)
        
        # 3. Zastosuj modyfikacje na podstawie newsów
        enhanced_result = self._apply_news_analysis_to_signal(base_result, news_analysis, stock)
        
        # 4. Dodaj informacje o newsach do wyniku
        enhanced_result['news_analysis'] = news_analysis
        
        return enhanced_result
    
    def _analyze_stock_news_sentiment(self, stock: StockSymbol) -> Dict[str, Any]:
        """
        Analizuje sentiment newsów dla danej akcji z ostatnich 7 dni.
        """
        try:
            # Okres analizy - ostatnie 7 dni
            start_date = timezone.now().date() - timedelta(days=7)
            end_date = timezone.now().date()
            
            # Znajdź newsy mentionujące tę akcję
            stock_news = NewsArticleModel.objects.filter(
                stock_symbols__contains=[stock.symbol],
                published_date__date__range=[start_date, end_date]
            ).prefetch_related('ai_classification')
            
            if not stock_news.exists():
                return {
                    'sentiment_score': 0.0,
                    'confidence': 0.0,
                    'news_count': 0,
                    'impact_level': 'minimal',
                    'recent_news': [],
                    'summary': 'No recent news found'
                }
            
            # Analizuj klasyfikacje AI
            classifications = []
            high_impact_news = 0
            very_recent_news = 0  # Z ostatnich 24h
            
            cutoff_recent = timezone.now().date() - timedelta(days=1)
            
            for news in stock_news:
                try:
                    classification = news.ai_classification
                    if classification:
                        # Waga na podstawie ważności i aktualności
                        days_old = (end_date - news.published_date.date()).days
                        recency_weight = max(0.1, 1.0 - (days_old / 7.0))
                        
                        # Boost dla high impact news
                        impact_weight = 1.0
                        if classification.market_impact in ['high', 'very_high']:
                            impact_weight = self.HIGH_IMPACT_NEWS_MULTIPLIER
                            high_impact_news += 1
                        
                        # Sprawdź czy jest specific sentiment dla tej akcji
                        stock_specific_sentiment = None
                        try:
                            stock_sentiment = StockSentiment.objects.get(
                                classification=classification,
                                stock=stock
                            )
                            stock_specific_sentiment = stock_sentiment.sentiment_score
                        except StockSentiment.DoesNotExist:
                            stock_specific_sentiment = classification.sentiment_score
                        
                        if news.published_date.date() >= cutoff_recent:
                            very_recent_news += 1
                            
                        classifications.append({
                            'sentiment_score': stock_specific_sentiment or 0.0,
                            'confidence': classification.confidence_score or 0.0,
                            'impact': classification.market_impact,
                            'weight': recency_weight * impact_weight,
                            'title': news.title[:60] + '...',
                            'date': news.published_date.date()
                        })
                        
                except Exception as e:
                    logger.warning(f"Error processing news classification: {e}")
                    continue
            
            if not classifications:
                return {
                    'sentiment_score': 0.0,
                    'confidence': 0.0,
                    'news_count': len(stock_news),
                    'impact_level': 'minimal',
                    'recent_news': [],
                    'summary': f'{len(stock_news)} news articles found but none analyzed by AI'
                }
            
            # Oblicz ważoną średnią sentymentu
            total_weighted_sentiment = sum(c['sentiment_score'] * c['weight'] for c in classifications)
            total_weight = sum(c['weight'] for c in classifications)
            weighted_sentiment = total_weighted_sentiment / total_weight if total_weight > 0 else 0.0
            
            # Średnia pewność
            avg_confidence = sum(c['confidence'] for c in classifications) / len(classifications)
            
            # Określ ogólny poziom wpływu
            if high_impact_news >= 2:
                impact_level = 'very_high'
            elif high_impact_news >= 1:
                impact_level = 'high'
            elif very_recent_news >= 2:
                impact_level = 'medium'  
            else:
                impact_level = 'low'
            
            # Ostatnie 3 newsy dla kontekstu
            recent_news = sorted(classifications, key=lambda x: x['date'], reverse=True)[:3]
            
            # Podsumowanie
            if weighted_sentiment > 0.3:
                sentiment_desc = "Positive"
            elif weighted_sentiment < -0.3:
                sentiment_desc = "Negative"  
            else:
                sentiment_desc = "Neutral"
                
            summary = f"{sentiment_desc} sentiment ({weighted_sentiment:.2f}) from {len(classifications)} analyzed articles"
            
            return {
                'sentiment_score': weighted_sentiment,
                'confidence': avg_confidence,
                'news_count': len(classifications),
                'impact_level': impact_level,
                'high_impact_count': high_impact_news,
                'very_recent_count': very_recent_news,
                'recent_news': recent_news,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error analyzing news sentiment for {stock.symbol}: {e}")
            return {
                'sentiment_score': 0.0,
                'confidence': 0.0,
                'news_count': 0,
                'impact_level': 'minimal',
                'recent_news': [],
                'summary': f'Error analyzing news: {str(e)}'
            }
    
    def _apply_news_analysis_to_signal(
        self, 
        base_signal: Dict[str, Any], 
        news_analysis: Dict[str, Any],
        stock: StockSymbol
    ) -> Dict[str, Any]:
        """
        Modyfikuje bazowy sygnał na podstawie analizy newsów.
        """
        enhanced_signal = base_signal.copy()
        
        sentiment_score = news_analysis['sentiment_score']
        news_confidence = news_analysis['confidence'] 
        impact_level = news_analysis['impact_level']
        
        # Nie modyfikuj sygnałów HOLD z zerową pewnością - brak danych technicznych
        if base_signal.get('confidence', 0) == 0:
            enhanced_signal['news_impact'] = 'No impact on technical analysis - insufficient data'
            return enhanced_signal
        
        original_confidence = float(base_signal.get('confidence', 0))
        original_signal = base_signal.get('signal', 'HOLD')
        
        confidence_modification = 0
        signal_modification = None
        impact_explanation = []
        
        # === SCENARIO 1: POZYTYWNE NEWSY ===
        if sentiment_score > self.NEWS_SENTIMENT_BOOST_THRESHOLD and news_confidence > 0.6:
            
            # Zwiększ pewność dla sygnałów BUY
            if original_signal == 'BUY':
                boost = self.NEWS_CONFIDENCE_BOOST
                if impact_level in ['high', 'very_high']:
                    boost *= 1.5  # Extra boost dla high-impact news
                confidence_modification = float(boost)
                impact_explanation.append(f"News sentiment boost (+{boost}% confidence)")
                
            # Zamień SELL na HOLD przy bardzo pozytywnych newsach
            elif original_signal == 'SELL' and sentiment_score > 0.7 and impact_level in ['high', 'very_high']:
                signal_modification = 'HOLD'
                confidence_modification = -10  # Zmniejsz pewność SELL
                impact_explanation.append("Strong positive news overrides SELL signal")
                
            # Zamień HOLD na WEAK_BUY przy bardzo pozytywnych newsach wysokiego impactu
            elif original_signal == 'HOLD' and sentiment_score > 0.8 and impact_level == 'very_high':
                signal_modification = 'BUY'
                confidence_modification = 40  # Umiarkowana pewność
                impact_explanation.append("Very positive high-impact news generates BUY signal")
        
        # === SCENARIO 2: NEGATYWNE NEWSY ===
        elif sentiment_score < self.NEWS_SENTIMENT_PENALTY_THRESHOLD and news_confidence > 0.6:
            
            # Zmniejsz pewność dla sygnałów BUY lub zamień na HOLD
            if original_signal == 'BUY':
                penalty = self.NEWS_CONFIDENCE_PENALTY
                if impact_level in ['high', 'very_high']:
                    penalty *= 1.5
                    
                # Bardzo negatywne newsy = zamień BUY na HOLD
                if sentiment_score < -0.7 and impact_level in ['high', 'very_high']:
                    signal_modification = 'HOLD'
                    confidence_modification = -penalty
                    impact_explanation.append("Strong negative news overrides BUY signal")
                else:
                    confidence_modification = -float(penalty)
                    impact_explanation.append(f"Negative news penalty (-{penalty}% confidence)")
            
            # Zwiększ pewność dla sygnałów SELL
            elif original_signal == 'SELL':
                boost = self.NEWS_CONFIDENCE_BOOST
                if impact_level in ['high', 'very_high']:
                    boost *= 1.5
                confidence_modification = float(boost)
                impact_explanation.append(f"Negative news confirms SELL (+{boost}% confidence)")
                
            # Zamień HOLD na SELL przy bardzo negatywnych newsach
            elif original_signal == 'HOLD' and sentiment_score < -0.8 and impact_level == 'very_high':
                signal_modification = 'SELL'
                confidence_modification = 40
                impact_explanation.append("Very negative high-impact news generates SELL signal")
        
        # === SCENARIO 3: WYSOKIEJ WICHTOŚCI NEWSY (niezależnie od sentymentu) ===
        if impact_level == 'very_high' and news_confidence > 0.8:
            confidence_modification += 5  # Małe dodatkowe boost za wysoką jakość informacji
            impact_explanation.append("High-quality news information boost")
        
        # Zastosuj modyfikacje
        if signal_modification:
            enhanced_signal['signal'] = signal_modification
            enhanced_signal['signal_modified_by_news'] = True
            
        if confidence_modification != 0:
            new_confidence = original_confidence + confidence_modification
            enhanced_signal['confidence'] = max(0, min(100, new_confidence))  # 0-100%
            enhanced_signal['confidence_modified_by_news'] = confidence_modification
            
        # Dodaj wyjaśnienia
        if impact_explanation:
            existing_reason = enhanced_signal.get('reason', '')
            news_reason = ' | '.join(impact_explanation)
            enhanced_signal['reason'] = f"{existing_reason} | {news_reason}"
            
        enhanced_signal['news_impact'] = impact_explanation if impact_explanation else ['No significant news impact']
        
        return enhanced_signal
    
    def generate_comprehensive_analysis(
        self, 
        stock: StockSymbol, 
        trading_session: Optional[TradingSession] = None
    ) -> Dict[str, Any]:
        """
        Kompleksowa analiza łącząca wszystkie dostępne źródła informacji.
        """
        # Generuj rozszerzony sygnał
        signal_result = self.generate_signals_for_stock(stock, trading_session)
        
        # Dodaj dodatkowe szczegóły
        comprehensive_result = {
            **signal_result,
            'analysis_type': 'comprehensive_with_news',
            'data_sources': [],
            'analysis_timestamp': timezone.now(),
        }
        
        # Określ źródła danych
        if signal_result.get('indicators'):
            comprehensive_result['data_sources'].append('technical_analysis')
            
        if signal_result.get('news_analysis', {}).get('news_count', 0) > 0:
            comprehensive_result['data_sources'].append('news_sentiment')
            
        comprehensive_result['data_sources_count'] = len(comprehensive_result['data_sources'])
        
        return comprehensive_result


# === PRZYKŁAD UŻYCIA ===
"""
# Inicjalizacja rozszerzonego generatora
enhanced_generator = EnhancedDailyTradingSignalGenerator()

# Generowanie sygnału z analizą newsów
stock = StockSymbol.objects.get(symbol='PKN')
result = enhanced_generator.generate_signals_for_stock(stock)

# Wynik będzie zawierał:
{
    'signal': 'BUY',  # Może być zmodyfikowane przez newsy
    'confidence': 75,  # Może być zwiększone/zmniejszone przez newsy  
    'reason': 'Bullish convergence | News sentiment boost (+15% confidence)',
    'news_analysis': {
        'sentiment_score': 0.6,
        'summary': 'Positive sentiment (0.60) from 3 analyzed articles',
        'impact_level': 'high'
    },
    'news_impact': ['News sentiment boost (+15% confidence)'],
    'signal_modified_by_news': False,
    'confidence_modified_by_news': 15
}
"""
