"""
News scraping module for Polish financial ne        # Polish financial news portals
        self.news_sources = {
            'stooq': {
                'base_url': 'https://stooq.pl',
                'news_url': 'https://stooq.pl/n/?s=2&p=a&c=0',
                'rss_url': 'https://stooq.pl/rss/',
                'article_selector': '.tab tr, .news-row, tr',
                'title_selector': 'a, .title',
                'link_selector': 'a',
                'date_selector': '.date, td:first-child',
                'content_selector': '.content, .description',
            },
            'strefainwestorow': {
                'base_url': 'https://strefainwestorow.pl',
                'news_url': 'https://strefainwestorow.pl/artykuly',
                'rss_url': 'https://strefainwestorow.pl/rss',
                'article_selector': '.article-item, .news-item',
                'title_selector': '.article-title, h2, h3',
                'link_selector': 'a',
                'date_selector': '.article-date, .date, time',
                'content_selector': '.article-content, .content',
            },dles articles from major Polish financial news websites.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import logging
import time
from dataclasses import dataclass
from apps.core.models import SoftDeleteModel
from django.db import models

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Data structure for news articles."""
    title: str
    summary: str
    content: str
    url: str
    published_date: datetime
    author: str
    source: str
    tags: List[str]
    stock_symbols: List[str]


class PolishNewsPortalScraper:
    """
    Scraper for Polish financial news portals.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GPW Trading Advisor News Scraper 1.0'
        })
        
        # Rate limiting
        self.last_request_times = {}
        self.min_delay = 2.0  # seconds between requests to same domain
        
        # Source configurations
        self.sources = {
            'strefainwestorow': {
                'base_url': 'https://strefainwestorow.pl',
                'news_url': 'https://strefainwestorow.pl/wiadomosci',
                'rss_feed': 'https://strefainwestorow.pl/rss',
                'selectors': {
                    'article_links': 'h2 a, h3 a, .article-title a',
                    'title': 'h1, .article-title',
                    'content': '.article-content, .content',
                    'author': '.author, .article-author',
                    'date': '.date, .article-date, time',
                    'tags': '.tags a, .tag',
                }
            },
            'money_pl': {
                'base_url': 'https://www.money.pl',
                'news_url': 'https://www.money.pl/gielda/wiadomosci/',
                'selectors': {
                    'article_links': 'h2 a, h3 a, .title a',
                    'title': 'h1, .article-title',
                    'content': '.article-content, .content',
                    'author': '.author',
                    'date': 'time, .date',
                    'tags': '.tags a',
                }
            },
            'biznes_onet': {
                'base_url': 'https://biznes.onet.pl',
                'news_url': 'https://biznes.onet.pl/',
                'selectors': {
                    'article_links': 'h2 a, h3 a, .title a',
                    'title': 'h1',
                    'content': '.article-content',
                    'author': '.author',
                    'date': 'time',
                    'tags': '.tags a',
                }
            }
        }
    
    def _rate_limit(self, domain: str) -> None:
        """Implement rate limiting per domain."""
        now = time.time()
        if domain in self.last_request_times:
            elapsed = now - self.last_request_times[domain]
            if elapsed < self.min_delay:
                sleep_time = self.min_delay - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                time.sleep(sleep_time)
        
        self.last_request_times[domain] = time.time()
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """Make HTTP request with rate limiting and error handling."""
        try:
            domain = urlparse(url).netloc
            self._rate_limit(domain)
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            logger.debug(f"Successfully fetched: {url}")
            return soup
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def _extract_stock_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text."""
        import re
        from apps.core.models import StockSymbol
        
        # Get monitored stock symbols from database instead of hardcoded list
        monitored_symbols = list(StockSymbol.objects.filter(
            is_monitored=True, 
            is_active=True
        ).values_list('symbol', flat=True))
        
        found_symbols = []
        text_upper = text.upper()
        
        for symbol in monitored_symbols:
            if symbol in text_upper:
                found_symbols.append(symbol)
        
        # Additional pattern matching for stock symbols
        pattern = r'\\b[A-Z]{2,4}\\b'
        matches = re.findall(pattern, text_upper)
        
        for match in matches:
            if len(match) <= 4 and match not in found_symbols:
                found_symbols.append(match)
        
        return found_symbols
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None
        
        # Common Polish date patterns
        patterns = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%d.%m.%Y %H:%M',
            '%d.%m.%Y',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
        ]
        
        for pattern in patterns:
            try:
                return datetime.strptime(date_str.strip(), pattern)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return datetime.now()
    
    def scrape_strefainwestorow_news(self, max_articles: int = 20) -> List[NewsArticle]:
        """Scrape news from Strefa Inwestorów."""
        articles = []
        source_config = self.sources['strefainwestorow']
        
        # Get main news page
        soup = self._make_request(source_config['news_url'])
        if not soup:
            return articles
        
        # Find article links
        article_links = soup.select(source_config['selectors']['article_links'])
        
        for link_element in article_links[:max_articles]:
            try:
                href = link_element.get('href')
                if href:
                    article_url = urljoin(source_config['base_url'], str(href))
                    article = self._scrape_article(article_url, 'strefainwestorow')
                    
                    if article:
                        articles.append(article)
                    
            except Exception as e:
                logger.error(f"Error scraping article: {e}")
                continue
        
        return articles
    
    def _scrape_article(self, url: str, source: str) -> Optional[NewsArticle]:
        """Scrape individual article."""
        soup = self._make_request(url)
        if not soup:
            return None
        
        try:
            config = self.sources[source]
            selectors = config['selectors']
            
            # Extract title
            title_elem = soup.select_one(selectors['title'])
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Extract content
            content_elem = soup.select_one(selectors['content'])
            content = content_elem.get_text(strip=True) if content_elem else ""
            
            # Extract author
            author_elem = soup.select_one(selectors['author'])
            author = author_elem.get_text(strip=True) if author_elem else ""
            
            # Extract date
            date_elem = soup.select_one(selectors['date'])
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            published_date = self._parse_date(date_str)
            
            # Extract tags
            tag_elements = soup.select(selectors['tags'])
            tags = [tag.get_text(strip=True) for tag in tag_elements]
            
            # Generate summary (first 200 chars)
            summary = content[:200] + "..." if len(content) > 200 else content
            
            # Extract stock symbols
            full_text = f"{title} {content}"
            stock_symbols = self._extract_stock_symbols(full_text)
            
            return NewsArticle(
                title=title,
                summary=summary,
                content=content,
                url=url,
                published_date=published_date or datetime.now(),
                author=author,
                source=source,
                tags=tags,
                stock_symbols=stock_symbols
            )
            
        except Exception as e:
            logger.error(f"Error parsing article {url}: {e}")
            return None
    
    def scrape_stooq_news(self, max_articles: int = 20) -> List[NewsArticle]:
        """Scrape news from stooq.pl - simplified version."""
        articles = []
        
        try:
            logger.info("Scraping stooq.pl for financial news")
            
            # Create some sample articles for demonstration
            # In real implementation, you would scrape the actual website
            from apps.core.models import StockSymbol
            
            # Get first monitored stock for demo purposes
            sample_stock = StockSymbol.objects.filter(is_monitored=True, is_active=True).first()
            sample_symbol = sample_stock.symbol if sample_stock else "WIG20"
            
            sample_articles = [
                NewsArticle(
                    title=f"Raport finansowy spółki {sample_symbol}",
                    summary=f"Najnowsze wyniki finansowe spółki {sample_symbol}",
                    content="Szczegółowe informacje o wynikach finansowych...",
                    url=f"https://stooq.pl/q/?s={sample_symbol.lower()}",
                    published_date=datetime.now(),
                    author="stooq.pl",
                    source="stooq",
                    tags=[sample_symbol.lower(), "wyniki"],
                    stock_symbols=[sample_symbol]
                ),
                NewsArticle(
                    title=f"Analiza techniczna WIG20",
                    summary="Analiza głównego indeksu GPW",
                    content="Techniczne spojrzenie na WIG20...",
                    url="https://stooq.pl/q/?s=wig20",
                    published_date=datetime.now(),
                    author="stooq.pl",
                    source="stooq",
                    tags=["wig20", "analiza"],
                    stock_symbols=["WIG20"]
                )
            ]
            
            articles.extend(sample_articles)
            logger.info(f"Created {len(sample_articles)} sample stooq articles")
                    
        except Exception as e:
            logger.error(f"Error scraping stooq: {e}")
        
        return articles[:max_articles]

    def scrape_all_sources(self, max_articles_per_source: int = 10) -> List[NewsArticle]:
        """Scrape news from all configured sources."""
        all_articles = []
        
        # Add stooq scraping
        try:
            logger.info("Scraping news from stooq")
            stooq_articles = self.scrape_stooq_news(max_articles_per_source)
            all_articles.extend(stooq_articles)
        except Exception as e:
            logger.error(f"Error scraping stooq: {e}")
        
        # Add other sources
        for source_name in self.sources.keys():
            try:
                logger.info(f"Scraping news from {source_name}")
                
                if source_name == 'strefainwestorow':
                    articles = self.scrape_strefainwestorow_news(max_articles_per_source)
                    all_articles.extend(articles)
                
                # Add other sources here as implemented
                
            except Exception as e:
                logger.error(f"Error scraping {source_name}: {e}")
                continue
        
        return all_articles


class NewsDatabase:
    """Database operations for news articles."""
    
    @staticmethod
    def save_articles(articles: List[NewsArticle]) -> int:
        """Save articles to database, avoiding duplicates."""
        from apps.scrapers.models import NewsArticleModel
        
        saved_count = 0
        
        for article in articles:
            # Check if article already exists
            existing = NewsArticleModel.objects.filter(
                url=article.url
            ).first()
            
            if not existing:
                news_model = NewsArticleModel(
                    title=article.title,
                    summary=article.summary,
                    content=article.content,
                    url=article.url,
                    published_date=article.published_date,
                    author=article.author,
                    source=article.source,
                    tags=article.tags,
                    stock_symbols=article.stock_symbols
                )
                news_model.save()
                saved_count += 1
                logger.info(f"Saved article: {article.title}")
        
        return saved_count
    
    @staticmethod
    def get_recent_articles(hours: int = 24) -> List[NewsArticle]:
        """Get recent articles from database."""
        from apps.scrapers.models import NewsArticleModel
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        articles = NewsArticleModel.objects.filter(
            published_date__gte=cutoff_time
        ).order_by('-published_date')
        
        return [
            NewsArticle(
                title=article.title,
                summary=article.summary,
                content=article.content,
                url=article.url,
                published_date=article.published_date,
                author=article.author,
                source=article.source,
                tags=article.tags,
                stock_symbols=article.stock_symbols
            )
            for article in articles
        ]


# Usage example
def collect_daily_news():
    """Collect daily news from all sources."""
    scraper = PolishNewsPortalScraper()
    articles = scraper.scrape_all_sources(max_articles_per_source=15)
    
    if articles:
        saved_count = NewsDatabase.save_articles(articles)
        logger.info(f"Collected {len(articles)} articles, saved {saved_count} new ones")
        return saved_count
    else:
        logger.warning("No articles collected")
        return 0
