# System Patterns: GPW Daily Trading Advisor

## Architectural Patterns

### Feature-Sliced Architecture
Each Django app represents a distinct business capability:

```
apps/
├── core/           # Shared utilities, base models, common services
├── users/          # User management, authentication, subscriptions
├── scrapers/       # Data collection from external sources
├── analysis/       # Technical analysis and signal generation
├── notifications/  # Message delivery and communication
├── tracking/       # Performance monitoring and reporting
└── dashboard/      # Administrative interface and user management
```

### Domain-Driven Design Principles
- **Bounded Contexts:** Each app has clear responsibility boundaries
- **Aggregate Roots:** User, Stock, Signal, Subscription as main entities
- **Value Objects:** Price data, technical indicators, risk parameters
- **Domain Services:** Signal generation, performance calculation, risk assessment

## Data Management Patterns

### Time-Series Data Handling
```python
# Price data with efficient querying
class StockPrice(models.Model):
    symbol = models.CharField(max_length=10, db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    open_price = models.DecimalField(max_digits=10, decimal_places=4)
    high_price = models.DecimalField(max_digits=10, decimal_places=4)
    low_price = models.DecimalField(max_digits=10, decimal_places=4)
    close_price = models.DecimalField(max_digits=10, decimal_places=4)
    volume = models.BigIntegerField()
    
    class Meta:
        indexes = [
            models.Index(fields=['symbol', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
        unique_together = ['symbol', 'timestamp']
```

### Event-Driven Architecture
```python
# Signal generation events
from django.dispatch import Signal

signal_generated = Signal()
price_alert_triggered = Signal()
subscription_expired = Signal()

# Event handlers
@receiver(signal_generated)
def send_trading_notification(sender, signal, **kwargs):
    NotificationTask.delay(signal.id)

@receiver(price_alert_triggered)
def handle_price_alert(sender, alert, **kwargs):
    PriceAlertTask.delay(alert.id)
```

### Repository Pattern for Data Access
```python
class StockPriceRepository:
    @staticmethod
    def get_latest_prices(symbols: List[str]) -> QuerySet:
        return StockPrice.objects.filter(
            symbol__in=symbols
        ).order_by('symbol', '-timestamp').distinct('symbol')
    
    @staticmethod
    def get_price_history(symbol: str, days: int) -> QuerySet:
        cutoff_date = timezone.now() - timedelta(days=days)
        return StockPrice.objects.filter(
            symbol=symbol,
            timestamp__gte=cutoff_date
        ).order_by('timestamp')
```

## Processing Patterns

### Strategy Pattern for Technical Analysis
```python
class TechnicalIndicator(ABC):
    @abstractmethod
    def calculate(self, prices: QuerySet) -> Dict:
        pass

class RSIIndicator(TechnicalIndicator):
    def __init__(self, period: int = 14):
        self.period = period
    
    def calculate(self, prices: QuerySet) -> Dict:
        # RSI calculation logic
        pass

class MACDIndicator(TechnicalIndicator):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
    
    def calculate(self, prices: QuerySet) -> Dict:
        # MACD calculation logic
        pass

# Usage
class SignalGenerator:
    def __init__(self):
        self.indicators = [
            RSIIndicator(period=14),
            MACDIndicator(),
            BollingerBandsIndicator(),
        ]
    
    def generate_signal(self, symbol: str) -> Signal:
        prices = StockPriceRepository.get_price_history(symbol, 30)
        indicator_results = [ind.calculate(prices) for ind in self.indicators]
        return self._evaluate_signals(indicator_results)
```

### Factory Pattern for Scrapers
```python
class ScraperFactory:
    _scrapers = {
        'stooq': StooqScraper,
        'espi': ESPIScraper,
        'financial_news': FinancialNewsScraper,
    }
    
    @classmethod
    def create_scraper(cls, scraper_type: str) -> BaseScraper:
        scraper_class = cls._scrapers.get(scraper_type)
        if not scraper_class:
            raise ValueError(f"Unknown scraper type: {scraper_type}")
        return scraper_class()

# Usage in Celery tasks
@celery_app.task
def scrape_stock_data(scraper_type: str, symbols: List[str]):
    scraper = ScraperFactory.create_scraper(scraper_type)
    return scraper.scrape_multiple(symbols)
```

### Observer Pattern for Notifications
```python
class NotificationManager:
    def __init__(self):
        self.observers = []
    
    def subscribe(self, observer: NotificationObserver):
        self.observers.append(observer)
    
    def notify(self, event: NotificationEvent):
        for observer in self.observers:
            if observer.should_handle(event):
                observer.handle(event)

class TelegramNotificationObserver:
    def should_handle(self, event: NotificationEvent) -> bool:
        return event.type in ['signal_generated', 'price_alert']
    
    def handle(self, event: NotificationEvent):
        TelegramSender.send_message(event.user, event.message)
```

## Error Handling Patterns

### Circuit Breaker for External Services
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitOpenException("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
```

### Retry Pattern with Exponential Backoff
```python
def retry_with_backoff(max_retries=3, base_delay=1, max_delay=60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise e
                    
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    time.sleep(delay)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
        return wrapper
    return decorator

# Usage
@retry_with_backoff(max_retries=3, base_delay=2)
def scrape_stock_price(symbol: str):
    # Scraping logic that may fail
    pass
```

## Performance Patterns

### Caching Strategy
```python
# Redis caching for frequently accessed data
class CachedStockPriceRepository:
    @staticmethod
    @cache.memoize(timeout=300)  # 5 minutes cache
    def get_latest_price(symbol: str) -> Decimal:
        return StockPrice.objects.filter(
            symbol=symbol
        ).latest('timestamp').close_price
    
    @staticmethod
    @cache.memoize(timeout=3600)  # 1 hour cache
    def get_daily_summary(symbol: str, date: datetime.date) -> Dict:
        prices = StockPrice.objects.filter(
            symbol=symbol,
            timestamp__date=date
        ).aggregate(
            open_price=models.Min('open_price'),
            high_price=models.Max('high_price'),
            low_price=models.Min('low_price'),
            close_price=models.Max('close_price'),
            volume=models.Sum('volume')
        )
        return prices
```

### Bulk Operations Pattern
```python
class BulkStockPriceService:
    @staticmethod
    def bulk_create_prices(price_data: List[Dict]) -> List[StockPrice]:
        price_objects = [
            StockPrice(**data) for data in price_data
        ]
        return StockPrice.objects.bulk_create(
            price_objects,
            batch_size=1000,
            ignore_conflicts=True
        )
    
    @staticmethod
    def bulk_update_signals(signals: List[Signal]) -> None:
        Signal.objects.bulk_update(
            signals,
            ['confidence', 'updated_at'],
            batch_size=500
        )
```

## Security Patterns

### Input Validation and Sanitization
```python
class StockSymbolValidator:
    VALID_PATTERN = re.compile(r'^[A-Z]{3,6}$')
    
    @classmethod
    def validate(cls, symbol: str) -> str:
        if not cls.VALID_PATTERN.match(symbol):
            raise ValidationError(f"Invalid stock symbol: {symbol}")
        return symbol.upper()

class RiskParameterValidator:
    @staticmethod
    def validate_percentage(value: float, min_val: float = 0.1, max_val: float = 10.0) -> float:
        if not min_val <= value <= max_val:
            raise ValidationError(f"Value must be between {min_val}% and {max_val}%")
        return value
```

### Rate Limiting Pattern
```python
class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
    
    def is_allowed(self, identifier: str) -> bool:
        now = time.time()
        user_requests = self.requests[identifier]
        
        # Remove old requests outside time window
        user_requests[:] = [req_time for req_time in user_requests 
                           if now - req_time < self.time_window]
        
        if len(user_requests) >= self.max_requests:
            return False
        
        user_requests.append(now)
        return True
```

## Integration Patterns

### Adapter Pattern for External APIs
```python
class TelegramAdapter:
    def __init__(self, bot_token: str):
        self.bot = telegram.Bot(token=bot_token)
    
    def send_trading_signal(self, chat_id: str, signal: Signal) -> bool:
        message = self._format_signal_message(signal)
        try:
            self.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False
    
    def _format_signal_message(self, signal: Signal) -> str:
        return f"""
🚀 *{signal.action.upper()} Signal*
📊 Stock: {signal.symbol}
💰 Price: {signal.current_price} PLN
📈 Confidence: {signal.confidence}%
⏰ Time: {signal.created_at.strftime('%H:%M')}
        """.strip()
```

This system architecture provides a robust foundation for the GPW Trading Advisor with clear separation of concerns, scalable patterns, and maintainable code structure.
