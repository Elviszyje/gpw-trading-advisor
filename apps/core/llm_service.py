"""
LLM Service for AI-powered news analysis and classification
Supports both OpenAI and OLLAMA providers
"""

import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from apps.core.models import LLMProvider, Industry, NewsClassification, StockSymbol, IndustrySentiment, StockSentiment
from apps.core.utils.ai_parser import ai_response_parser
import requests
import openai

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for AI-powered news analysis using multiple LLM providers
    """
    
    def __init__(self):
        self.active_providers = LLMProvider.objects.filter(is_active=True)
        self.openai_client = None
        
    def get_available_provider(self, provider_type: Optional[str] = None) -> Optional[LLMProvider]:
        """Get available LLM provider"""
        providers = self.active_providers
        
        if provider_type:
            providers = providers.filter(provider_type=provider_type)
            
        # Check availability
        for provider in providers:
            if self.check_provider_availability(provider):
                return provider
                
        return None
        
    def check_provider_availability(self, provider: LLMProvider) -> bool:
        """Check if LLM provider is available"""
        try:
            if provider.provider_type == 'openai':
                return self._check_openai_availability(provider)
            elif provider.provider_type == 'ollama':
                return self._check_ollama_availability(provider)
            else:
                return False
        except Exception as e:
            logger.error(f"Error checking provider {provider.name}: {e}")
            return False
            
    def _check_openai_availability(self, provider: LLMProvider) -> bool:
        """Check OpenAI availability"""
        if not provider.api_key:
            return False
            
        try:
            if not self.openai_client:
                self.openai_client = openai.OpenAI(api_key=provider.api_key)
                
            # Simple test request
            response = self.openai_client.chat.completions.create(
                model=provider.model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            
            provider.is_available = True
            provider.last_check = timezone.now()
            provider.save()
            
            return True
            
        except Exception as e:
            logger.warning(f"OpenAI provider {provider.name} not available: {e}")
            provider.is_available = False
            provider.last_check = timezone.now()
            provider.save()
            return False
            
    def _check_ollama_availability(self, provider: LLMProvider) -> bool:
        """Check OLLAMA availability"""
        try:
            response = requests.get(
                f"{provider.api_url.rstrip('/api/chat')}/api/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                
                is_available = any(provider.model_name in name for name in model_names)
                
                provider.is_available = is_available
                provider.last_check = timezone.now()
                provider.save()
                
                return is_available
            else:
                provider.is_available = False
                provider.last_check = timezone.now()
                provider.save()
                return False
                
        except Exception as e:
            logger.warning(f"OLLAMA provider {provider.name} not available: {e}")
            provider.is_available = False
            provider.last_check = timezone.now()
            provider.save()
            return False
    
    def analyze_news_article(self, article, provider: Optional[LLMProvider] = None, max_retries: int = 2) -> Optional[NewsClassification]:
        """
        Analyze news article using AI for sentiment, industry classification, and stock correlation
        
        Args:
            article: NewsArticleModel instance
            provider: Optional specific LLM provider
            max_retries: Maximum number of retry attempts
        """
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            if not provider:
                provider = self.get_available_provider()
                
            if not provider:
                logger.error("No available LLM provider for news analysis")
                return None
                
            try:
                start_time = time.time()
                
                # Prepare prompt
                prompt = self._create_analysis_prompt(article)
                
                # Get AI response
                if provider.provider_type == 'openai':
                    ai_response = self._analyze_with_openai(prompt, provider)
                elif provider.provider_type == 'ollama':
                    ai_response = self._analyze_with_ollama(prompt, provider)
                else:
                    logger.error(f"Unsupported provider type: {provider.provider_type}")
                    return None
                    
                if not ai_response:
                    last_error = f"No AI response from {provider.name}"
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                        time.sleep(1)  # Brief pause before retry
                        continue
                    else:
                        return None
                    
                processing_time = int((time.time() - start_time) * 1000)
                
                # Parse AI response and create classification
                classification = self._create_classification_from_response(
                    article, provider, ai_response, processing_time
                )
                
                if classification:
                    logger.info(f"Successfully analyzed article on attempt {attempt + 1}")
                    return classification
                else:
                    last_error = "Failed to create classification from AI response"
                    if attempt < max_retries:
                        logger.warning(f"Classification creation failed on attempt {attempt + 1}, retrying...")
                        time.sleep(1)
                        continue
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error analyzing article (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    time.sleep(2)  # Longer pause for exceptions
                    continue
        
        logger.error(f"Failed to analyze article after {max_retries + 1} attempts. Last error: {last_error}")
        return None
            
    def _create_analysis_prompt(self, article) -> str:
        """Create AI prompt for news analysis"""
        
        # Get ALL industries and stocks for comprehensive analysis
        industries = list(Industry.objects.values_list('name', 'code', 'keywords'))
        stocks = list(StockSymbol.objects.values_list('symbol', 'name'))
        
        prompt = f"""
Przeanalizuj poniższy artykuł finansowy z perspektywy INWESTORA GIEŁDOWEGO i zwróć odpowiedź w formacie JSON.

ARTYKUŁ:
Tytuł: {article.title}
Treść: {article.content[:2000]}
Źródło: {article.source.name}

WSZYSTKIE DOSTĘPNE BRANŻE:
{chr(10).join([f"- {name} ({code}): {', '.join(keywords[:5])}" for name, code, keywords in industries])}

WSZYSTKIE SPÓŁKI GPW:
{chr(10).join([f"- {symbol}: {name}" for symbol, name in stocks[:30]])}

ZADANIA ANALIZY Z PERSPEKTYWY INWESTORA:
1. Oceń OGÓLNY sentyment artykułu z perspektywy inwestora giełdowego (-1 do 1)
2. Określ poziom pewności analizy (0 do 1)
3. Zidentyfikuj branże, których dotyczy artykuł
4. Oceń wpływ na całość rynku (minimal/low/medium/high/very_high)
5. NAJWAŻNIEJSZE: Dla każdej istotnej branży podaj osobny sentyment inwestycyjny
6. NAJWAŻNIEJSZE: Dla każdej istotnej spółki podaj osobny sentyment inwestycyjny
7. Wyciągnij kluczowe podmioty (firmy, osoby, lokalizacje)
8. Podsumuj główne tematy inwestycyjne

UWAGA: Ten sam artykuł może być pozytywny dla jednej branży, a negatywny dla innej!
Przykład: "Wzrost cen ropy" = pozytywny dla branży paliwowej, negatywny dla linii lotniczych.

ODPOWIEDŹ (tylko JSON):
{{
  "overall_sentiment": "positive|negative|neutral|very_positive|very_negative",
  "overall_sentiment_score": 0.7,
  "confidence_score": 0.85,
  "market_impact": "medium",
  "general_summary": "Ogólne podsumowanie artykułu z perspektywy inwestora...",
  "general_reasoning": "Ogólne uzasadnienie klasyfikacji...",
  
  "industry_analysis": [
    {{
      "industry_code": "BANK",
      "sentiment": "positive",
      "sentiment_score": 0.8,
      "confidence": 0.9,
      "reasoning": "Dlaczego ten artykuł jest pozytywny/negatywny dla banków..."
    }},
    {{
      "industry_code": "FUEL",
      "sentiment": "negative", 
      "sentiment_score": -0.6,
      "confidence": 0.7,
      "reasoning": "Dlaczego ten artykuł jest negatywny dla branży paliwowej..."
    }}
  ],
  
  "stock_analysis": [
    {{
      "stock_symbol": "PKN",
      "sentiment": "positive",
      "sentiment_score": 0.9,
      "confidence": 0.95,
      "relevance": 0.8,
      "reasoning": "Dlaczego ta wiadomość jest pozytywna dla PKN Orlen..."
    }},
    {{
      "stock_symbol": "PKO",
      "sentiment": "neutral",
      "sentiment_score": 0.1,
      "confidence": 0.6,
      "relevance": 0.3,
      "reasoning": "Dlaczego ta wiadomość ma neutralny wpływ na PKO BP..."
    }}
  ],
  
  "mentioned_companies": ["PKN ORLEN", "PKO BP"],
  "mentioned_people": ["Jan Kowalski"],
  "mentioned_locations": ["Warszawa", "Płock"],
  "key_topics": ["zyski", "dywidenda", "inwestycje"],
  "key_phrases": ["rekordowe zyski", "wzrost dywidendy"]
}}

WAŻNE: 
- Analizuj z perspektywy inwestora giełdowego (czy to wpłynie pozytywnie/negatywnie na cenę akcji)
- Uwzględnij tylko branże i spółki ISTOTNE dla tego artykułu
- Jeden artykuł może mieć różne sentymenty dla różnych branż/spółek
- Podaj konkretne uzasadnienie dla każdego sentymentu
"""
        
        return prompt
        
    def _analyze_with_openai(self, prompt: str, provider: LLMProvider) -> Optional[Dict]:
        """Analyze using OpenAI"""
        try:
            if not self.openai_client:
                self.openai_client = openai.OpenAI(api_key=provider.api_key)
                
            response = self.openai_client.chat.completions.create(
                model=provider.model_name,
                messages=[
                    {"role": "system", "content": "Jesteś ekspertem analizy rynku finansowego. Zawsze odpowiadaj w poprawnym formacie JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=provider.max_tokens,
                temperature=provider.temperature
            )
            
            content = response.choices[0].message.content
            
            # Update token usage
            if hasattr(response, 'usage') and response.usage:
                provider.total_tokens_used += response.usage.total_tokens
                provider.save()
            
            return {"content": content, "tokens_used": getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') and response.usage else 0}
            
        except Exception as e:
            logger.error(f"OpenAI analysis error: {e}")
            return None
            
    def _analyze_with_ollama(self, prompt: str, provider: LLMProvider) -> Optional[Dict]:
        """Analyze using OLLAMA"""
        try:
            payload = {
                "model": provider.model_name,
                "messages": [
                    {"role": "system", "content": "Jesteś ekspertem analizy rynku finansowego. Zawsze odpowiadaj w poprawnym formacie JSON."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": provider.temperature,
                    "num_predict": provider.max_tokens
                }
            }
            
            response = requests.post(
                provider.api_url,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('message', {}).get('content', '')
                
                return {"content": content, "tokens_used": len(content.split())}
            else:
                logger.error(f"OLLAMA error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"OLLAMA analysis error: {e}")
            return None
            
    def _create_classification_from_response(
        self, 
        article, 
        provider: LLMProvider, 
        ai_response: Dict, 
        processing_time: int
    ) -> Optional[NewsClassification]:
        """Create NewsClassification from AI response"""
        
        try:
            content = ai_response.get('content', '')
            tokens_used = ai_response.get('tokens_used', 0)
            
            # Parse JSON from AI response using enhanced parser
            analysis_data = ai_response_parser.parse_ai_response(content)
            
            if not analysis_data:
                logger.error(f"Failed to parse AI response after all attempts: {content[:200]}...")
                return None
                
            # Create classification with new format
            classification = NewsClassification.objects.create(
                article=article,
                llm_provider=provider,
                sentiment=analysis_data.get('overall_sentiment'),
                sentiment_score=analysis_data.get('overall_sentiment_score'),
                confidence_score=analysis_data.get('confidence_score'),
                market_impact=analysis_data.get('market_impact'),
                mentioned_companies=analysis_data.get('mentioned_companies', []),
                mentioned_people=analysis_data.get('mentioned_people', []),
                mentioned_locations=analysis_data.get('mentioned_locations', []),
                key_topics=analysis_data.get('key_topics', []),
                ai_summary=analysis_data.get('general_summary', ''),
                ai_reasoning=analysis_data.get('general_reasoning', ''),
                key_phrases=analysis_data.get('key_phrases', []),
                processing_time_ms=processing_time,
                tokens_used=tokens_used
            )
            
            # Process industry-specific sentiments
            industry_analysis = analysis_data.get('industry_analysis', [])
            for industry_data in industry_analysis:
                try:
                    industry = Industry.objects.get(code=industry_data.get('industry_code'))
                    
                    IndustrySentiment.objects.create(
                        classification=classification,
                        industry=industry,
                        sentiment=industry_data.get('sentiment'),
                        sentiment_score=industry_data.get('sentiment_score', 0.0),
                        confidence_score=industry_data.get('confidence', 0.0),
                        reasoning=industry_data.get('reasoning', '')
                    )
                    
                    # Also add to detected industries for backward compatibility
                    classification.detected_industries.add(industry)
                    
                except Industry.DoesNotExist:
                    logger.warning(f"Industry {industry_data.get('industry_code')} not found")
            
            # Process stock-specific sentiments  
            stock_analysis = analysis_data.get('stock_analysis', [])
            for stock_data in stock_analysis:
                try:
                    stock = StockSymbol.objects.get(symbol=stock_data.get('stock_symbol'))
                    
                    StockSentiment.objects.create(
                        classification=classification,
                        stock=stock,
                        sentiment=stock_data.get('sentiment'),
                        sentiment_score=stock_data.get('sentiment_score', 0.0),
                        confidence_score=stock_data.get('confidence', 0.0),
                        reasoning=stock_data.get('reasoning', ''),
                        relevance_score=stock_data.get('relevance', 0.0)
                    )
                    
                    # Also add to article mentioned stocks for backward compatibility
                    article.mentioned_stocks.add(stock)
                    
                except StockSymbol.DoesNotExist:
                    logger.warning(f"Stock {stock_data.get('stock_symbol')} not found")
            
            # Set primary industry (first one with highest sentiment)
            if industry_analysis:
                primary_industry_data = max(industry_analysis, key=lambda x: x.get('sentiment_score', 0))
                try:
                    primary_industry = Industry.objects.get(code=primary_industry_data.get('industry_code'))
                    classification.primary_industry = primary_industry
                    classification.save()
                except Industry.DoesNotExist:
                    pass
                    
            return classification
            
        except Exception as e:
            logger.error(f"Error creating classification: {e}")
            return None


# Convenience function for easy use
def analyze_article_with_ai(article) -> Optional[NewsClassification]:
    """Convenience function to analyze article with AI"""
    service = LLMService()
    return service.analyze_news_article(article)
