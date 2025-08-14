#!/usr/bin/env python

import os
import sys
import django

# Setup Django
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from apps.news.models import NewsArticleModel
from apps.core.models import NewsClassification

def main():
    print("=== News Analysis Status ===")
    
    total = NewsArticleModel.objects.count()
    analyzed = NewsClassification.objects.count()
    unanalyzed = NewsArticleModel.objects.filter(ai_classification__isnull=True).count()

    print(f"Total articles: {total}")
    print(f"Analyzed articles: {analyzed}") 
    print(f"Unanalyzed articles: {unanalyzed}")

    if unanalyzed > 0:
        print(f"\nFirst unanalyzed article:")
        article = NewsArticleModel.objects.filter(ai_classification__isnull=True).first()
        print(f"ID {article.id}: {article.title}")
        print(f"Content preview: {article.content[:200]}...")
    
    print(f"\nRunning AI analysis command...")
    
if __name__ == "__main__":
    main()
