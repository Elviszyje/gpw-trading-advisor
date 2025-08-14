#!/usr/bin/env python

import os
import sys
import django

# Setup Django
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from apps.core.models import NewsClassification, IndustrySentiment, StockSentiment

def main():
    print("=== Detailed Sentiment Analysis Results ===\n")
    
    classification = NewsClassification.objects.first()
    if not classification:
        print("No classifications found")
        return
        
    print(f"📰 Article: {classification.article.title[:80]}...")
    print(f"🤖 Provider: {classification.llm_provider.name}")
    print(f"📈 Overall Sentiment: {classification.sentiment} ({classification.sentiment_score})")
    print(f"🎯 Confidence: {classification.confidence_score}")
    print(f"💥 Market Impact: {classification.market_impact}")
    
    # Industry-specific sentiments
    industry_sentiments = classification.industry_sentiments.all()
    if industry_sentiments:
        print(f"\n🏭 INDUSTRY-SPECIFIC SENTIMENTS:")
        for ind_sent in industry_sentiments:
            print(f"  • {ind_sent.industry.name} ({ind_sent.industry.code})")
            print(f"    Sentiment: {ind_sent.sentiment} ({ind_sent.sentiment_score:+.2f})")
            print(f"    Confidence: {ind_sent.confidence_score:.2f}")
            print(f"    Reasoning: {ind_sent.reasoning[:100]}...")
            print()
    else:
        print(f"\n🏭 No industry-specific sentiments found")
    
    # Stock-specific sentiments
    stock_sentiments = classification.stock_sentiments.all()
    if stock_sentiments:
        print(f"📊 STOCK-SPECIFIC SENTIMENTS:")
        for stock_sent in stock_sentiments:
            print(f"  • {stock_sent.stock.symbol} - {stock_sent.stock.name}")
            print(f"    Sentiment: {stock_sent.sentiment} ({stock_sent.sentiment_score:+.2f})")
            print(f"    Confidence: {stock_sent.confidence_score:.2f}")
            print(f"    Relevance: {stock_sent.relevance_score:.2f}")
            print(f"    Reasoning: {stock_sent.reasoning[:100]}...")
            print()
    else:
        print(f"\n📊 No stock-specific sentiments found")
    
    print(f"\n💡 KEY INSIGHTS:")
    print(f"  Companies: {', '.join(classification.mentioned_companies)}")
    print(f"  Topics: {', '.join(classification.key_topics)}")
    print(f"  Processing Time: {classification.processing_time_ms}ms")

if __name__ == "__main__":
    main()
