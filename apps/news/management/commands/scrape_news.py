"""
Django command to scrape financial news from RSS feeds and news portals
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.news.models import NewsSource, NewsArticleModel
from apps.core.models import StockSymbol
from apps.news.utils.deduplication import news_deduplicator
from apps.core.utils.stock_detection import stock_symbol_detector
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin
import re

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape financial news from RSS feeds and news portals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            help='Specific source to scrape (if not provided, scrapes all active sources)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum number of articles to scrape per source (default: 50)',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=7,
            help='Number of days back to scrape articles (default: 7)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('🗞️  STARTING NEWS SCRAPING'))
        self.stdout.write('=' * 50)
        
        source_filter = options.get('source')
        limit = options.get('limit', 50)
        days_back = options.get('days_back', 7)
        
        # Get active news sources
        sources = NewsSource.objects.filter(is_active=True)
        if source_filter:
            sources = sources.filter(name__icontains=source_filter)
            
        if not sources.exists():
            self.stdout.write(self.style.ERROR('❌ No active news sources found'))
            return
            
        total_scraped = 0
        total_saved = 0
        
        for source in sources:
            self.stdout.write(f'\n📰 Scraping: {source.name} ({source.type})')
            
            try:
                scraped, saved = self.scrape_source(source, limit, days_back)
                total_scraped += scraped
                total_saved += saved
                
                self.stdout.write(
                    f'   ✅ Found: {scraped}, Saved: {saved} new articles'
                )
                
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

    def scrape_source(self, source: NewsSource, limit: int, days_back: int) -> tuple:
        """Scrape a single news source"""
        
        if source.type == 'rss':
            return self.scrape_rss_feed(source, limit, days_back)
        elif source.type == 'html':
            return self.scrape_html_portal(source, limit, days_back)
        else:
            self.stdout.write(f'   ⚠️  Unknown source type: {source.type}')
            return 0, 0

    def scrape_rss_feed(self, source: NewsSource, limit: int, days_back: int) -> tuple:
        """Scrape RSS feed"""
        
        try:
            # Parse RSS feed
            feed = feedparser.parse(source.url)
            
            if not feed.entries:
                self.stdout.write(f'   ⚠️  No entries found in RSS feed')
                return 0, 0
                
            cutoff_date = timezone.now() - timedelta(days=days_back)
            scraped_count = 0
            saved_count = 0
            
            for entry in feed.entries[:limit]:
                scraped_count += 1
                
                # Parse published date
                published_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed and isinstance(entry.published_parsed, tuple):
                    try:
                        published_date = timezone.make_aware(
                            datetime(*entry.published_parsed[:6])
                        )
                    except (TypeError, ValueError):
                        pass
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed and isinstance(entry.updated_parsed, tuple):
                    try:
                        published_date = timezone.make_aware(
                            datetime(*entry.updated_parsed[:6])
                        )
                    except (TypeError, ValueError):
                        pass
                        
                if not published_date:
                    published_date = timezone.now()
                
                # Skip old articles
                if published_date < cutoff_date:
                    continue
                    
                # Check if article already exists (enhanced duplicate detection)
                article_url = str(entry.link) if hasattr(entry, 'link') else ""
                if not article_url:
                    continue
                
                # Extract basic content for duplicate detection
                title = str(entry.title) if hasattr(entry, 'title') else ""
                summary = ""
                if hasattr(entry, 'summary') and isinstance(entry.summary, str):
                    summary = self.clean_html(entry.summary)
                
                # Enhanced duplicate detection
                is_dup, existing_article, detection_method = news_deduplicator.is_duplicate(
                    url=article_url,
                    title=title,
                    content=summary,
                    source_id=source.pk
                )
                
                if is_dup:
                    self.stdout.write(f"   🔄 Skipped duplicate: {title[:50]}... (detected by: {detection_method})")
                    continue
                    
                # Extract content
                content = ""
                summary = ""
                
                if hasattr(entry, 'summary') and isinstance(entry.summary, str):
                    summary = self.clean_html(entry.summary)
                    
                if hasattr(entry, 'content') and entry.content and len(entry.content) > 0:
                    content_item = entry.content[0]
                    if hasattr(content_item, 'value'):
                        content = self.clean_html(str(content_item.value))
                elif hasattr(entry, 'description') and isinstance(entry.description, str):
                    content = self.clean_html(entry.description)
                else:
                    content = summary
                    
                # Try to fetch full content if available
                if not content or len(content) < 100:
                    full_content = self.fetch_article_content(article_url)
                    if full_content:
                        content = full_content
                
                # Extract stock symbols using enhanced detector
                text_for_symbols = ""
                title = str(entry.title) if hasattr(entry, 'title') else ""
                text_for_symbols = title + " " + summary + " " + content
                stock_symbols = stock_symbol_detector.get_simple_symbol_list(text_for_symbols)
                
                # Create article
                article = NewsArticleModel.objects.create(
                    title=title[:255] if title else 'No Title',
                    content=content or summary or '',  # Use content or summary as fallback
                    url=article_url,
                    published_date=published_date,
                    source=source,  # Pass NewsSource object, not string
                )
                
                # Add stock symbol relationships
                for symbol_code in stock_symbols:
                    try:
                        symbol = StockSymbol.objects.get(symbol=symbol_code)
                        article.mentioned_stocks.add(symbol)
                    except StockSymbol.DoesNotExist:
                        pass
                        
                saved_count += 1
                
                # Rate limiting
                time.sleep(0.5)
                
            return scraped_count, saved_count
            
        except Exception as e:
            logger.error(f'Error scraping RSS feed {source.url}: {e}', exc_info=True)
            raise

    def scrape_html_portal(self, source: NewsSource, limit: int, days_back: int) -> tuple:
        """Scrape HTML news portal"""
        
        try:
            response = requests.get(source.url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # This is basic implementation - would need specific selectors for each portal
            article_links = soup.find_all('a', href=True)
            
            scraped_count = 0
            saved_count = 0
            cutoff_date = timezone.now() - timedelta(days=days_back)
            
            for link_elem in article_links[:limit]:
                # Check if this is a valid BeautifulSoup Tag element
                if not hasattr(link_elem, 'get_text') or not hasattr(link_elem, 'get'):
                    continue
                    
                if not self.is_financial_article(link_elem.get_text()):
                    continue
                    
                # Safely get href attribute
                try:
                    if hasattr(link_elem, 'get') and hasattr(link_elem, 'name'):
                        href = link_elem.get('href')  # type: ignore
                    else:
                        continue
                except (AttributeError, TypeError):
                    continue
                    
                if not href:
                    continue
                    
                article_url = urljoin(source.url, str(href))
                
                # Enhanced duplicate detection for HTML scraping
                title = link_elem.get_text() if hasattr(link_elem, 'get_text') else ""
                is_dup, existing_article, detection_method = news_deduplicator.is_duplicate(
                    url=article_url,
                    title=title,
                    content="",  # Content will be fetched later
                    source_id=source.pk
                )
                
                if is_dup:
                    self.stdout.write(f"   🔄 Skipped duplicate: {title[:50]}... (detected by: {detection_method})")
                    continue
                    
                scraped_count += 1
                
                # Fetch article content
                article_content = self.fetch_article_content(article_url)
                if not article_content:
                    continue
                    
                # Extract title from link text or fetch from page
                title = link_elem.get_text().strip()
                if not title:
                    title = self.extract_title_from_url(article_url)
                    
                # Create article
                article = NewsArticleModel.objects.create(
                    title=title[:255],
                    content=article_content,
                    url=article_url,
                    published_date=timezone.now(),  # Would need better date extraction
                    source=source,  # Pass NewsSource object, not string
                )
                
                saved_count += 1
                time.sleep(1)  # Rate limiting
                
            return scraped_count, saved_count
            
        except Exception as e:
            logger.error(f'Error scraping HTML portal {source.url}: {e}', exc_info=True)
            raise

    def fetch_article_content(self, url: str) -> str:
        """Fetch full article content from URL"""
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                elem.decompose()
                
            # Try common article content selectors
            content_selectors = [
                '.article-content', '.content', '.post-content',
                '[itemprop="articleBody"]', '.entry-content',
                'article', '.article', '.post'
            ]
            
            content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(strip=True)
                    break
                    
            if not content:
                # Fallback to main content area
                main = soup.find('main') or soup.find('body')
                if main:
                    content = main.get_text(strip=True)
                    
            return content[:10000]  # Limit content length
            
        except Exception as e:
            logger.debug(f'Failed to fetch content from {url}: {e}')
            return ""

    def extract_stock_symbols(self, text: str) -> List[str]:
        """Extract Polish stock symbols from text (legacy method)"""
        return stock_symbol_detector.get_simple_symbol_list(text)

    def is_financial_article(self, text: str) -> bool:
        """Check if article is likely financial/stock related"""
        
        financial_keywords = [
            'akcje', 'giełda', 'gpw', 'spółka', 'wig', 'notowania',
            'dividenda', 'wyniki', 'finansowe', 'raport', 'akcjonariusz',
            'inwestor', 'kapitał', 'obligacje', 'fundusz'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in financial_keywords)

    def extract_title_from_url(self, url: str) -> str:
        """Extract title from article URL page"""
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            title_elem = soup.find('title') or soup.find('h1')
            
            return title_elem.get_text().strip() if title_elem else 'Untitled Article'
            
        except Exception:
            return 'Untitled Article'

    def clean_html(self, html_content: str) -> str:
        """Clean HTML content and return plain text"""
        
        if not html_content:
            return ""
            
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text().strip()
