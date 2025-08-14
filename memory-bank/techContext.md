# Technical Context: GPW Daily Trading Advisor

## Technology Stack

### Core Framework
**Django 5.0+**
- Latest stable version for robust web framework
- Built-in admin interface for user management
- ORM for database interactions
- Management commands for schedulers
- REST framework for potential API expansion

### Database
**PostgreSQL 15+**
- High-performance relational database
- Excellent support for time-series data
- JSONB fields for flexible data storage
- Strong consistency for financial data
- Advanced indexing for fast queries

### Web Scraping & Data Collection
**Selenium WebDriver**
- Chrome/Firefox headless browsers
- JavaScript-heavy site compatibility (stooq.pl)
- Robust element waiting and error handling
- Concurrent browser instances for scalability

**Additional Libraries:**
- `requests` for RSS/API data collection
- `BeautifulSoup4` for HTML parsing
- `feedparser` for RSS feeds (ESPI/EBI)

### Message Queue & Task Scheduling
**Celery + Redis**
- Distributed task queue for background jobs
- Redis as message broker and cache
- Periodic tasks for data collection
- Result backend for task monitoring

**Alternative: Celery + RabbitMQ**
- More robust message broker for production
- Better persistence and reliability
- Advanced routing capabilities

### External Integrations
**Telegram Bot API**
- `python-telegram-bot` library
- Webhook or polling modes
- Rich message formatting support
- Error handling and retry logic

### Development & Deployment
**Development Tools:**
- Docker for containerization
- docker-compose for local development
- pytest for testing
- black/isort for code formatting
- flake8 for linting

**Production Considerations:**
- Gunicorn/uWSGI as WSGI server
- Nginx for reverse proxy
- PostgreSQL with connection pooling
- Redis cluster for high availability
- Monitoring with Sentry

## Architecture Overview

### Django Project Structure
```
gpw_advisor/
├── config/                 # Django settings
├── apps/
│   ├── core/              # Shared utilities
│   ├── users/             # User management & subscriptions
│   ├── scrapers/          # Data collection
│   ├── analysis/          # Technical analysis engine
│   ├── notifications/     # Telegram integration
│   ├── tracking/          # Performance monitoring
│   └── dashboard/         # Admin interface
├── data/                  # Data storage helpers
├── scripts/               # Management commands
└── tests/                 # Test suites
```

### Database Schema Design

#### Core Tables
- `users_user` - User accounts and preferences
- `users_subscription` - Subscription management
- `scrapers_stockprice` - Time-series price data
- `scrapers_espinews` - ESPI/EBI communications
- `scrapers_financialnews` - Financial news articles
- `analysis_signal` - Generated trading signals
- `tracking_recommendation` - Performance tracking
- `notifications_message` - Message delivery log

#### Indexing Strategy
- Time-based indexes for price data
- Composite indexes for user-specific queries
- Full-text search indexes for news content

### Data Flow Architecture

#### Real-time Data Pipeline
```
stooq.pl → Selenium Scraper → PostgreSQL → Analysis Engine → Signal Generation → Telegram
```

#### News Processing Pipeline
```
ESPI/EBI RSS → Parser → Sentiment Analysis → Stock Correlation → Alert Generation
```

#### Performance Tracking Pipeline
```
Generated Signals → Price Monitoring → P&L Calculation → Performance Reports
```

### Concurrency & Performance

#### Multi-threading Strategy
- Separate threads for each data source
- ThreadPoolExecutor for concurrent scraping
- Django channels for real-time updates
- Async views for non-blocking operations

#### Celery Task Organization
- `scrapers.tasks` - Data collection tasks
- `analysis.tasks` - Technical analysis tasks
- `notifications.tasks` - Message delivery tasks
- `tracking.tasks` - Performance calculation tasks

#### Caching Strategy
- Redis for frequently accessed data
- Django cache framework for computed results
- Query optimization with select_related/prefetch_related

## Development Environment

### Local Setup Requirements
```bash
# Core dependencies
Python 3.11+
PostgreSQL 15+
Redis 7+
Chrome/Firefox browser

# Python packages
Django 5.0+
psycopg2-binary
celery[redis]
selenium
python-telegram-bot
pandas
numpy
ta (technical analysis)
```

### Configuration Management
- Environment-based settings (development/staging/production)
- Secrets management with environment variables
- Database connection pooling configuration
- Logging configuration for debugging and monitoring

### Testing Strategy
- Unit tests for business logic
- Integration tests for external APIs
- Selenium tests for scraping reliability
- Performance tests for concurrent operations
- Mock external services for consistent testing

## Deployment Considerations

### Infrastructure Requirements
- **CPU:** Multi-core for concurrent processing
- **RAM:** 8GB+ for browser instances and data processing
- **Storage:** SSD for database performance
- **Network:** Stable connection for real-time data

### Monitoring & Observability
- Application performance monitoring (APM)
- Database query performance tracking
- External API response time monitoring
- User notification delivery metrics
- Error rate and alert thresholds

### Security Considerations
- Environment variable secret management
- Database connection encryption
- API rate limiting and authentication
- User data privacy compliance
- Secure Telegram token handling

### Scalability Planning
- Horizontal scaling with multiple worker instances
- Database read replicas for query optimization
- Message queue clustering for high availability
- CDN for static assets if web interface is added
- Auto-scaling based on user load
