#!/usr/bin/env python

import os
import sys
import django

# Setup Django
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from apps.core.models import NewsClassification
from apps.news.models import NewsArticleModel

def main():
    print("=== AI Classification Results ===")
    
    classification = NewsClassification.objects.first()
    if not classification:
        print("No classifications found")
        return
        
    print(f"Article: {classification.article.title}")
    print(f"Provider: {classification.llm_provider.name}")
    print(f"Sentiment: {classification.sentiment} ({classification.sentiment_score})")
    print(f"Confidence: {classification.confidence_score}")
    print(f"Market Impact: {classification.market_impact}")
    print(f"Processing Time: {classification.processing_time_ms}ms")
    print(f"Tokens Used: {classification.tokens_used}")

    print(f"\nMentioned Companies: {classification.mentioned_companies}")
    print(f"Key Topics: {classification.key_topics}")
    print(f"Key Phrases: {classification.key_phrases}")

    print(f"\nAI Summary: {classification.ai_summary[:200]}...")
    print(f"\nAI Reasoning: {classification.ai_reasoning[:200]}...")

    if classification.detected_industries.exists():
        industries = list(classification.detected_industries.all())
        print(f"\nDetected Industries: {[ind.name for ind in industries]}")
        
    if classification.article.mentioned_stocks.exists():
        stocks = list(classification.article.mentioned_stocks.all())
        print(f"Related Stocks: {[stock.symbol for stock in stocks]}")

if __name__ == "__main__":
    main()
