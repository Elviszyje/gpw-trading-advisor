# GPW Trading Advisor - Technical Troubleshooting Checklist

## 🚨 When Notifications Stop Working

### Emergency Checklist (5 Minutes)

**□ Step 1: Quick Status Check**
```bash
python manage.py shell -c "
from datetime import date, timedelta
from apps.scrapers.models import StockData
from apps.analysis.models import IndicatorValue, TradingSignal

today = date.today()
print('=== SYSTEM STATUS ===')
print(f'Date: {today}')
print(f'Data collected: {StockData.objects.filter(created_at__date=today).count()}')
print(f'Indicators calculated: {IndicatorValue.objects.filter(calculated_at__date=today).count()}') 
print(f'Signals generated: {TradingSignal.objects.filter(created_at__date=today).count()}')
print(f'Signals sent: {TradingSignal.objects.filter(created_at__date=today, is_sent=True).count()}')
"
```

**□ Step 2: Test Telegram Bot**
```bash
python manage.py setup_notifications --test-telegram
```

**□ Step 3: Check User Configuration**  
```bash
python manage.py shell -c "
from apps.users.models import User
user = User.objects.filter(telegram_chat_id='7676229144').first()
print(f'User found: {user.email if user else \"NO USER\"}')
if user:
    print(f'Active: {user.is_active}')
    print(f'Email notifications: {user.email_notifications}')
"
```

### Common Issues & Fixes

**Issue**: No data collected (count = 0)
```bash
# Check scraper status
python manage.py check_scrapers
# Restart data collection if needed
python manage.py collect_stock_data
```

**Issue**: No indicators calculated (count = 0)  
```bash
# Force calculate indicators
python manage.py calculate_indicators
```

**Issue**: No signals generated (count = 0)
```bash
# Generate signals manually
python manage.py generate_daily_signals --all-monitored --show-details
```

**Issue**: Signals generated but not sent (is_sent = False)
```bash
# Send notifications for unsent signals
python manage.py generate_and_notify
```

**Issue**: Telegram bot not responding
```bash
# Check bot token and connection
python manage.py shell -c "
from django.conf import settings
from telegram import Bot
import asyncio

async def check_bot():
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f'✅ Bot active: @{me.username}')
        return True
    except Exception as e:
        print(f'❌ Bot error: {e}')
        return False

asyncio.run(check_bot())
"
```

---

## 🔧 Diagnostic Commands

### Full System Diagnostic
```bash
python manage.py shell -c "
import os
from django.conf import settings
from datetime import date, timedelta

print('=== GPW TRADING ADVISOR DIAGNOSTIC ===')
print(f'Date: {date.today()}')
print(f'Working directory: {os.getcwd()}')
print(f'Django debug: {settings.DEBUG}')
print(f'Database: {settings.DATABASES[\"default\"][\"NAME\"]}')
print(f'Telegram token: {\"SET\" if hasattr(settings, \"TELEGRAM_BOT_TOKEN\") else \"MISSING\"}')

# Check database connections
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('✅ Database connection: OK')
except Exception as e:
    print(f'❌ Database error: {e}')

# Check models
from apps.scrapers.models import StockData
from apps.analysis.models import TradingSignal, IndicatorValue
from apps.users.models import User

today = date.today()
yesterday = today - timedelta(days=1)

print(f'\\n=== DATA STATUS ===')
print(f'Stock symbols: {StockData.objects.values(\"stock\").distinct().count()}')
print(f'Data today: {StockData.objects.filter(created_at__date=today).count()}')
print(f'Data yesterday: {StockData.objects.filter(created_at__date=yesterday).count()}')
print(f'Indicators today: {IndicatorValue.objects.filter(calculated_at__date=today).count()}')
print(f'Signals today: {TradingSignal.objects.filter(created_at__date=today).count()}')
print(f'Active users: {User.objects.filter(is_active=True).count()}')
print(f'Users with Telegram: {User.objects.filter(telegram_chat_id__isnull=False).count()}')
"
```

### Performance Check
```bash
python manage.py shell -c "
from datetime import date, timedelta
from apps.analysis.models import TradingSignal

# Check signal performance over last 7 days
start_date = date.today() - timedelta(days=7)
signals = TradingSignal.objects.filter(created_at__date__gte=start_date)

total = signals.count()
buy_signals = signals.filter(signal_type='buy').count()
sell_signals = signals.filter(signal_type='sell').count()
hold_signals = signals.filter(signal_type='hold').count()
sent_signals = signals.filter(is_sent=True).count()

print(f'=== 7-DAY SIGNAL PERFORMANCE ===')
print(f'Total signals: {total}')
print(f'BUY signals: {buy_signals} ({buy_signals/total*100:.1f}%)' if total else 'BUY signals: 0')
print(f'SELL signals: {sell_signals} ({sell_signals/total*100:.1f}%)' if total else 'SELL signals: 0')  
print(f'HOLD signals: {hold_signals} ({hold_signals/total*100:.1f}%)' if total else 'HOLD signals: 0')
print(f'Sent notifications: {sent_signals} ({sent_signals/total*100:.1f}%)' if total else 'Sent: 0')

# Daily breakdown
for i in range(7):
    check_date = date.today() - timedelta(days=i)
    day_signals = signals.filter(created_at__date=check_date)
    print(f'{check_date}: {day_signals.count()} signals')
"
```

### Network & Connectivity Test
```bash
python manage.py shell -c "
import requests
from telegram import Bot
from django.conf import settings
import asyncio

print('=== CONNECTIVITY TEST ===')

# Test internet connection
try:
    response = requests.get('https://www.google.com', timeout=5)
    print(f'✅ Internet: {response.status_code}')
except Exception as e:
    print(f'❌ Internet: {e}')

# Test Telegram API
async def test_telegram_api():
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f'✅ Telegram API: @{me.username}')
        return True
    except Exception as e:
        print(f'❌ Telegram API: {e}')
        return False

asyncio.run(test_telegram_api())

# Test database
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT version()')
        version = cursor.fetchone()[0]
    print(f'✅ Database: PostgreSQL {version[:20]}...')
except Exception as e:
    print(f'❌ Database: {e}')
"
```

---

## 🚑 Emergency Recovery Procedures

### Scenario 1: Complete System Failure
```bash
# 1. Restart everything
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
source venv/bin/activate

# 2. Check dependencies
pip install -r requirements.txt

# 3. Database migration check
python manage.py migrate

# 4. Rebuild indicators
python manage.py calculate_indicators

# 5. Generate fresh signals
python manage.py generate_daily_signals --all-monitored

# 6. Test notifications
python manage.py setup_notifications --test-telegram
```

### Scenario 2: Telegram Bot Stopped Working
```bash
# 1. Check bot status
python manage.py shell -c "
import asyncio
from telegram import Bot
from django.conf import settings

async def check_bot():
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        me = await bot.get_me()
        print(f'Bot status: @{me.username} - Active')
    except Exception as e:
        print(f'Bot error: {e}')
        if 'Unauthorized' in str(e):
            print('Solution: Check TELEGRAM_BOT_TOKEN in settings')
        elif 'Network' in str(e):
            print('Solution: Check internet connection')

asyncio.run(check_bot())
"

# 2. Test direct message
python manage.py shell -c "
import asyncio
from telegram import Bot
from django.conf import settings

async def test_message():
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        result = await bot.send_message('7676229144', 'Emergency test message')
        print(f'Message sent successfully: {result.message_id}')
    except Exception as e:
        print(f'Message failed: {e}')

asyncio.run(test_message())
"
```

### Scenario 3: No Signals Being Generated
```bash
# 1. Check monitored stocks
python manage.py shell -c "
from apps.core.models import StockSymbol
monitored = StockSymbol.objects.filter(is_monitored=True, is_active=True)
print(f'Monitored stocks: {monitored.count()}')
for stock in monitored:
    print(f'- {stock.symbol}')
"

# 2. Force regenerate all technical data
python manage.py shell -c "
from apps.analysis.models import IndicatorValue
from datetime import date
today = date.today()
IndicatorValue.objects.filter(calculated_at__date=today).delete()
print('Cleared today indicators - will recalculate')
"

python manage.py calculate_indicators
python manage.py generate_daily_signals --all-monitored --show-details
```

### Scenario 4: Database Issues
```bash
# 1. Check database connection
python manage.py dbshell

# 2. Check table status
python manage.py shell -c "
from django.db import connection
tables = ['analysis_tradingsignal', 'analysis_indicatorvalue', 'scrapers_stockdata']
with connection.cursor() as cursor:
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'{table}: {count} records')
"

# 3. Run migrations
python manage.py migrate

# 4. Check for corruption
python manage.py check
```

---

## 📞 Escalation Procedures

### Level 1: User Issues (5 minutes)
- Run quick diagnostic
- Test Telegram bot
- Check user configuration

### Level 2: Data Issues (15 minutes)  
- Check data collection
- Recalculate indicators
- Regenerate signals

### Level 3: System Issues (30 minutes)
- Database connectivity
- Django settings
- Server resources

### Level 4: Infrastructure Issues (Contact Support)
- Network connectivity
- Server hardware
- External API failures

---

## 📋 Maintenance Log Template

```
Date: [DATE]
Issue: [DESCRIPTION]
Symptoms: [WHAT USER REPORTED]
Diagnosis: [COMMANDS RUN AND RESULTS]
Solution: [WHAT FIXED IT]
Prevention: [HOW TO AVOID IN FUTURE]
Time to resolve: [MINUTES]
```

**Example Entry**:
```
Date: 2025-07-24
Issue: No notifications received
Symptoms: Data collection working but no Telegram messages
Diagnosis: IndicatorValue.objects.filter(calculated_at__date=today).count() returned 0
Solution: Ran python manage.py calculate_indicators
Prevention: Add to daily cron job
Time to resolve: 10 minutes
```

---

**Last Updated**: July 24, 2025  
**Emergency Contact**: Check Django logs first, then run diagnostic commands above
