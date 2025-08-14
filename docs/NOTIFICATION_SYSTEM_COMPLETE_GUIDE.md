# GPW Trading Advisor - Complete Notification System Guide

## Table of Contents
1. [System Overview](#system-overview)
2. [Problem Diagnosis](#problem-diagnosis)
3. [Solution Implementation](#solution-implementation)
4. [Daily Workflow Setup](#daily-workflow-setup)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Maintenance & Monitoring](#maintenance--monitoring)
7. [Technical Details](#technical-details)

---

## System Overview

The GPW Trading Advisor notification system consists of 4 main components:

```
Stock Data Collection → Technical Analysis → Signal Generation → Notifications
        ↓                      ↓                   ↓              ↓
   StockData Model    IndicatorValue Model   TradingSignal     Telegram/Email
   (Price feeds)      (RSI, MACD, etc.)     (BUY/SELL)        (User alerts)
```

### Key Components:
- **Data Collection**: Scrapes stock prices from stooq.pl
- **Technical Analysis**: Calculates indicators (MACD, RSI, Bollinger Bands)
- **Signal Generation**: Creates BUY/SELL recommendations based on indicators
- **Notification Service**: Sends alerts via Telegram and email

---

## Problem Diagnosis

### Original Issue (July 24, 2025)
**Symptom**: No Telegram notifications received despite data collection running

### Root Cause Analysis

#### ✅ Data Collection - Working
```bash
# Verification:
python manage.py shell -c "
from apps.scrapers.models import StockData
from datetime import date
print(f'Data entries today: {StockData.objects.filter(created_at__date=date.today()).count()}')
"
# Result: 113,765 entries collected
```

#### ❌ Technical Indicators - Missing
```bash
# Problem identified:
python manage.py shell -c "
from apps.analysis.models import IndicatorValue
from datetime import date
print(f'Indicators today: {IndicatorValue.objects.filter(calculated_at__date=date.today()).count()}')
"
# Result: 0 indicators (should be 1000+)
```

#### ❌ Signal Generation - Only HOLD signals
```bash
# Command output showed:
python manage.py generate_daily_signals --all-monitored
# Result: 9 HOLD signals, 0 BUY/SELL (due to missing indicators)
```

#### ✅ Telegram Bot - Working
```bash
# Test confirmed working:
python manage.py setup_notifications --test-telegram
# Result: Test message delivered successfully
```

### Summary
The notification pipeline was broken at step 2 (technical indicators), causing no actionable signals to be generated.

---

## Solution Implementation

### Step 1: Fix Technical Indicator Calculation

**Problem**: Indicators weren't being calculated automatically
**Solution**: Manual execution of indicator calculation

```bash
# Calculate missing indicators
python manage.py calculate_indicators

# Verify results
python manage.py shell -c "
from apps.analysis.models import IndicatorValue
from datetime import date
print(f'Indicators calculated: {IndicatorValue.objects.filter(calculated_at__date=date.today()).count()}')
"
# Expected result: 1000+ indicators
```

### Step 2: Generate Real Trading Signals

**Problem**: Only HOLD signals due to missing technical data
**Solution**: Regenerate signals with proper indicator data

```bash
# Generate signals with indicators available
python manage.py generate_daily_signals --all-monitored --show-details

# Expected output:
# 🟢 BUY Signals: 2-5
# 🔴 SELL Signals: 1-3  
# ⚪ HOLD Signals: 2-4
```

### Step 3: Create Complete Workflow Command

**Created**: `/apps/notifications/management/commands/generate_and_notify.py`

```bash
# Generate test signals and send notifications
python manage.py generate_and_notify --force-generate

# For production use (existing signals):
python manage.py generate_and_notify
```

### Step 4: User Configuration Verification

```bash
# Check user setup
python manage.py shell -c "
from apps.users.models import User
user = User.objects.filter(telegram_chat_id='7676229144').first()
print(f'User: {user.email}')
print(f'Active: {user.is_active}')  
print(f'Email notifications: {user.email_notifications}')
print(f'Telegram ID: {user.telegram_chat_id}')
"
```

**Required Configuration**:
- User email: `test@gpwtradingadvisor.com`
- Telegram chat ID: `7676229144`
- Email notifications: `True`
- Account status: `Active`

---

## Daily Workflow Setup

### Option 1: Manual Daily Execution

**Morning Routine (9:00 AM)**:
```bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
source venv/bin/activate

# Step 1: Calculate technical indicators
python manage.py calculate_indicators

# Step 2: Generate trading signals  
python manage.py generate_daily_signals --all-monitored

# Step 3: Send notifications
python manage.py generate_and_notify

# Step 4: Monitor results
python manage.py monitor_notifications
```

### Option 2: Automated Cron Job

**Setup crontab**:
```bash
# Edit crontab
crontab -e

# Add these lines:
# Daily workflow at 9 AM (weekdays only)
0 9 * * 1-5 /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2/scripts/daily_workflow.sh

# Real-time signals every 30 minutes during market hours
*/30 9-17 * * 1-5 cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2 && source venv/bin/activate && python manage.py calculate_indicators && python manage.py generate_daily_signals --all-monitored && python manage.py generate_and_notify
```

**Daily Workflow Script** (`/scripts/daily_workflow.sh`):
```bash
#!/bin/bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
source venv/bin/activate

echo "$(date): Starting GPW Trading Advisor daily workflow"

# Calculate indicators
python manage.py calculate_indicators

# Generate signals
python manage.py generate_daily_signals --all-monitored

# Send notifications
python manage.py generate_and_notify

echo "$(date): Daily workflow completed"
```

### Option 3: Complete Setup Command

```bash
# One-time setup and testing
python manage.py setup_notifications --test-telegram
```

---

## Troubleshooting Guide

### Issue 1: No Notifications Received

**Symptoms**: 
- Data collection working
- No Telegram messages

**Diagnosis Commands**:
```bash
# Check each component
python manage.py shell -c "
from datetime import date
from apps.scrapers.models import StockData
from apps.analysis.models import IndicatorValue, TradingSignal

today = date.today()
print(f'1. Data entries: {StockData.objects.filter(created_at__date=today).count()}')
print(f'2. Indicators: {IndicatorValue.objects.filter(calculated_at__date=today).count()}')
print(f'3. Signals: {TradingSignal.objects.filter(created_at__date=today).count()}')
"
```

**Solutions**:
- If indicators = 0: Run `python manage.py calculate_indicators`
- If signals = 0: Run `python manage.py generate_daily_signals --all-monitored`
- If notifications = 0: Run `python manage.py generate_and_notify --force-generate`

### Issue 2: Telegram Bot Not Working

**Test Bot Connection**:
```bash
python manage.py shell -c "
import asyncio
from django.conf import settings
from telegram import Bot

async def test_bot():
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    me = await bot.get_me()
    print(f'Bot: @{me.username}')
    
    result = await bot.send_message(
        chat_id='7676229144',
        text='Test message'
    )
    print(f'Message sent: {result.message_id}')

asyncio.run(test_bot())
"
```

**Common Issues**:
- Invalid token: Check `TELEGRAM_BOT_TOKEN` in settings
- Wrong chat ID: Verify `7676229144` is correct
- Bot blocked: Unblock @Rekomendacje_gp_bot in Telegram

### Issue 3: Only HOLD Signals Generated

**Symptoms**:
- Signals generated but all are HOLD
- No BUY/SELL recommendations

**Cause**: Missing or insufficient technical indicator data

**Solution**:
```bash
# Force recalculation of indicators
python manage.py calculate_indicators

# Verify sufficient data
python manage.py shell -c "
from apps.analysis.models import IndicatorValue
from apps.core.models import StockSymbol

symbols = StockSymbol.objects.filter(is_monitored=True)[:3]
for symbol in symbols:
    count = IndicatorValue.objects.filter(stock=symbol).count()
    print(f'{symbol.symbol}: {count} indicator values')
"
```

### Issue 4: Email Notifications Not Working

**Check Email Configuration**:
```bash
python manage.py shell -c "
from django.conf import settings
print(f'Email backend: {settings.EMAIL_BACKEND}')
print(f'SMTP host: {getattr(settings, \"EMAIL_HOST\", \"Not set\")}')
print(f'From email: {getattr(settings, \"DEFAULT_FROM_EMAIL\", \"Not set\")}')
"
```

**Test Email Sending**:
```bash
python manage.py shell -c "
from django.core.mail import send_mail
result = send_mail(
    'Test Subject',
    'Test message',
    'from@example.com',
    ['test@gpwtradingadvisor.com'],
    fail_silently=False
)
print(f'Email sent: {result}')
"
```

### Issue 5: User Configuration Problems

**Check User Setup**:
```bash
python manage.py shell -c "
from apps.users.models import User

users = User.objects.filter(is_active=True)
print(f'Active users: {users.count()}')

for user in users:
    print(f'Email: {user.email}')
    print(f'  Telegram ID: {getattr(user, \"telegram_chat_id\", \"None\")}')
    print(f'  Email notifications: {getattr(user, \"email_notifications\", \"None\")}')
"
```

**Fix User Configuration**:
```bash
python manage.py shell -c "
from apps.users.models import User

user = User.objects.filter(email='test@gpwtradingadvisor.com').first()
if user:
    user.telegram_chat_id = '7676229144'
    user.email_notifications = True
    user.is_active = True
    user.save()
    print('User configuration updated')
"
```

---

## Maintenance & Monitoring

### Daily Monitoring Commands

**Check System Status**:
```bash
# Quick status check
python manage.py monitor_notifications

# Detailed analysis
python manage.py shell -c "
from datetime import date, timedelta
from apps.analysis.models import TradingSignal
from apps.notifications.models import Notification

today = date.today()
yesterday = today - timedelta(days=1)

print(f'Signals today: {TradingSignal.objects.filter(created_at__date=today).count()}')
print(f'Signals yesterday: {TradingSignal.objects.filter(created_at__date=yesterday).count()}')
print(f'Notifications today: {Notification.objects.filter(sent_at__date=today).count()}')
"
```

**Performance Analytics**:
```bash
# Check signal accuracy over time
python manage.py analyze_signal_performance

# View recommendation dashboard
# Navigate to: http://localhost:8000/analysis/recommendations/
```

### Weekly Maintenance

**Every Monday**:
```bash
# Clean up old data (optional)
python manage.py shell -c "
from datetime import date, timedelta
from apps.analysis.models import TradingSignal

# Delete signals older than 30 days
cutoff = date.today() - timedelta(days=30)
old_signals = TradingSignal.objects.filter(created_at__date__lt=cutoff)
print(f'Would delete {old_signals.count()} old signals')
# old_signals.delete()  # Uncomment to actually delete
"

# Update technical indicators configuration
python manage.py shell -c "
from apps.analysis.models import TechnicalIndicator
indicators = TechnicalIndicator.objects.all()
print(f'Active indicators: {indicators.count()}')
for ind in indicators:
    print(f'- {ind.name}: {ind.indicator_type}')
"
```

### Log Monitoring

**Important Log Files**:
- Django logs: Check for notification service errors
- Telegram errors: TelegramError exceptions
- Database errors: Connection and query issues

**Key Log Messages to Monitor**:
```
INFO Telegram bot initialized successfully
INFO Email sent successfully to user@email.com
ERROR Failed to send signal alert to user
WARNING No indicator data available for [SYMBOL]
```

---

## Technical Details

### Database Schema

**Key Models**:
```python
# TradingSignal fields
- stock: ForeignKey to StockSymbol
- signal_type: 'buy', 'sell', 'hold'
- confidence: Decimal (0-100)
- price_at_signal: Decimal
- target_price: Decimal
- stop_loss_price: Decimal
- is_sent: Boolean
- sent_at: DateTime

# User notification fields  
- email_notifications: Boolean
- telegram_chat_id: CharField
- is_active: Boolean

# IndicatorValue fields
- stock: ForeignKey to StockSymbol
- indicator: ForeignKey to TechnicalIndicator  
- value: Decimal
- calculated_at: DateTime
```

### API Endpoints

**Notification System URLs**:
```
/analysis/recommendations/          # Dashboard
/analysis/recommendations/details/  # Signal details
/analysis/learning/                 # ML analytics
```

### Configuration Files

**Key Settings**:
```python
# settings.py
TELEGRAM_BOT_TOKEN = '7865747632:AAG5pY6yzx0YupiVXXjkCQjTecoLHvmOLP4'
DEFAULT_FROM_EMAIL = 'noreply@gpwtradingadvisor.com'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Chat ID for notifications
TELEGRAM_CHAT_ID = '7676229144'
```

### Dependencies

**Python Packages**:
```
python-telegram-bot>=20.0
django>=4.2
psycopg2-binary
celery  # For async processing
redis   # For task queue
```

---

## Quick Reference

### Essential Commands
```bash
# Daily workflow
python manage.py calculate_indicators
python manage.py generate_daily_signals --all-monitored  
python manage.py generate_and_notify

# Testing
python manage.py setup_notifications --test-telegram
python manage.py generate_and_notify --force-generate --dry-run

# Monitoring  
python manage.py monitor_notifications
python manage.py analyze_signal_performance

# Debugging
python manage.py shell -c "[diagnosis commands]"
```

### File Locations
```
/apps/notifications/enhanced_notification_service.py  # Main service
/apps/notifications/management/commands/              # Management commands
/templates/notifications/                             # Email/Telegram templates
/scripts/daily_workflow.sh                            # Automation script
```

### Support Contacts
- **System Admin**: Check Django logs
- **Telegram Issues**: @Rekomendacje_gp_bot status
- **Email Issues**: SMTP configuration
- **Signal Issues**: Technical indicator calculation

---

**Last Updated**: July 24, 2025  
**Status**: ✅ Fully Operational  
**Next Review**: July 31, 2025
