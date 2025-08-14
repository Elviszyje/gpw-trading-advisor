"""
Simplified Django command to scrape financial news from RSS feeds
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.news.models import NewsSource, NewsArticleModel
from apps.core.models import StockSymbol
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import time
from typing import List
from urllib.parse import urljoin
import re

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape financial news from RSS feeds'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            help='Specific source to scrape',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Maximum number of articles to scrape per source',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('🗞️  STARTING NEWS SCRAPING'))
        self.stdout.write('=' * 50)
        
        source_filter = options.get('source')
        limit = options.get('limit', 20)
        
        # Get active RSS news sources
        sources = NewsSource.objects.filter(is_active=True, type='rss')
        if source_filter:
            sources = sources.filter(name__icontains=source_filter)
            
        if not sources.exists():
            self.stdout.write(self.style.ERROR('❌ No active RSS sources found'))
            return
            
        total_scraped = 0
        total_saved = 0
        
        for source in sources:
            self.stdout.write(f'\n📰 Scraping: {source.name}')
            self.stdout.write(f'   URL: {source.url}')
            
            try:
                scraped, saved = self.scrape_rss_source(source, limit)
                total_scraped += scraped
                total_saved += saved
                
                self.stdout.write(
                    f'   ✅ Found: {scraped}, Saved: {saved} new articles'
                )
                
                # Update last scraped time
                source.last_scraped = timezone.now()
                source.save()
                
                # Rate limiting between sources
                time.sleep(2)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Error scraping {source.name}: {e}')
                )
                logger.error(f'Error scraping {source.name}: {e}', exc_info=True)
                
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f'🎉 SCRAPING COMPLETE: {total_scraped} found, {total_saved} saved'
            )
        )

    def scrape_rss_source(self, source: NewsSource, limit: int) -> tuple:
        """Scrape RSS feed source"""
        
        try:
            # Parse RSS feed
            self.stdout.write(f'   📡 Fetching RSS: {source.url}')
            feed = feedparser.parse(source.url)
            
            if not feed.entries:
                self.stdout.write(f'   ⚠️  No entries found in RSS feed')
                return 0, 0
                
            self.stdout.write(f'   📄 Found {len(feed.entries)} entries in feed')
            
            scraped_count = 0
            saved_count = 0
            cutoff_date = timezone.now() - timedelta(days=7)
            
            for entry in feed.entries[:limit]:
                scraped_count += 1
                
                # Get basic info
                title = getattr(entry, 'title', 'No Title')
                link = getattr(entry, 'link', '')
                
                if not link:
                    continue
                    
                # Check if article already exists
                if NewsArticleModel.objects.filter(url=link).exists():
                    continue
                
                # Parse published date safely
                published_date = timezone.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        if isinstance(entry.published_parsed, tuple) and len(entry.published_parsed) >= 6:
                            published_date = timezone.make_aware(
                                datetime(*entry.published_parsed[:6])
                            )
                    except (TypeError, ValueError):
                        pass
                
                # Skip old articles
                if published_date < cutoff_date:
                    continue
                    
                # Extract content
                summary = ''
                content = ''
                
                if hasattr(entry, 'summary'):
                    summary = self.clean_html(str(entry.summary))
                    
                if hasattr(entry, 'content') and entry.content:
                    try:
                        content = self.clean_html(str(entry.content[0].value))
                    except (IndexError, AttributeError):
                        pass
                        
                if not content and hasattr(entry, 'description'):
                    content = self.clean_html(str(entry.description))
                    
                if not content:
                    content = summary
                
                # Extract stock symbols
                text_for_symbols = f"{title} {summary} {content}"
                stock_symbols = self.extract_stock_symbols(text_for_symbols)
                
                # Create article
                try:
                    article = NewsArticleModel.objects.create(
                        title=title[:500],  # Model has max_length=500
                        content=content,
                        url=link,
                        published_date=published_date,
                        source=source,  # ForeignKey to NewsSource instance
                    )
                    
                    # Add stock symbol relationships
                    for symbol_code in stock_symbols:
                        try:
                            symbol = StockSymbol.objects.get(symbol=symbol_code)
                            article.mentioned_stocks.add(symbol)
                        except StockSymbol.DoesNotExist:
                            pass
                            
                    saved_count += 1
                    
                    if saved_count <= 3:  # Show first few titles
                        self.stdout.write(f'      💾 {title[:60]}...')
                    
                except Exception as e:
                    self.stdout.write(f'      ❌ Error saving article: {e}')
                    continue
                
                # Rate limiting
                time.sleep(0.5)
                
            return scraped_count, saved_count
            
        except Exception as e:
            logger.error(f'Error scraping RSS feed {source.url}: {e}', exc_info=True)
            raise

    def extract_stock_symbols(self, text: str) -> List[str]:
        """Extract Polish stock symbols from text"""
        
        if not text:
            return []
            
        symbols = set()
        
        # Get all known symbols from database
        all_symbols = list(StockSymbol.objects.values_list('symbol', flat=True))
        
        for symbol in all_symbols:
            # Look for symbol mentions (case insensitive)
            pattern = r'\b' + re.escape(symbol) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                symbols.add(symbol)
                
        return list(symbols)

    def clean_html(self, html_content: str) -> str:
        """Clean HTML content and return plain text"""
        
        if not html_content:
            return ""
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text().strip()
        except Exception:
            return str(html_content).strip()
