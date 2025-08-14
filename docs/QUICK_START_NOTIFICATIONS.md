# GPW Trading Advisor - Quick Start Guide

## 🚀 Get Notifications Working in 5 Minutes

### Step 1: Test Everything is Working
```bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
source venv/bin/activate
python manage.py setup_notifications --test-telegram
```
**Expected**: You should receive a test message on Telegram

### Step 2: Generate Today's Signals & Notifications
```bash
# Complete daily workflow
python manage.py calculate_indicators
python manage.py generate_daily_signals --all-monitored
python manage.py generate_and_notify --force-generate
```
**Expected**: You should receive trading signal notifications

### Step 3: Verify Results
```bash
python manage.py shell -c "
from apps.analysis.models import TradingSignal
from datetime import date
signals = TradingSignal.objects.filter(created_at__date=date.today())
print(f'Signals today: {signals.count()}')
for s in signals:
    print(f'- {s.stock.symbol}: {s.signal_type} (sent: {s.is_sent})')
"
```

---

## 📅 Daily Automation Setup

### Option A: Manual (Recommended for Testing)
Run this every morning at 9 AM:
```bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2 && source venv/bin/activate && python manage.py calculate_indicators && python manage.py generate_daily_signals --all-monitored && python manage.py generate_and_notify
```

### Option B: Automatic (Set and Forget)
```bash
# Add to crontab (run: crontab -e)
0 9 * * 1-5 /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2/scripts/daily_workflow.sh

# Make script executable
chmod +x /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2/scripts/daily_workflow.sh
```

---

## 🔍 Troubleshooting (If No Notifications)

### Check 1: Data Collection
```bash
python manage.py shell -c "
from apps.scrapers.models import StockData
from datetime import date
print(f'Data collected today: {StockData.objects.filter(created_at__date=date.today()).count()}')
"
```
**Should be**: 50,000+ entries

### Check 2: Technical Indicators  
```bash
python manage.py shell -c "
from apps.analysis.models import IndicatorValue
from datetime import date
print(f'Indicators today: {IndicatorValue.objects.filter(calculated_at__date=date.today()).count()}')
"
```
**Should be**: 1,000+ entries  
**If 0**: Run `python manage.py calculate_indicators`

### Check 3: Trading Signals
```bash
python manage.py shell -c "
from apps.analysis.models import TradingSignal
from datetime import date
signals = TradingSignal.objects.filter(created_at__date=date.today())
print(f'Signals today: {signals.count()}')
print(f'BUY signals: {signals.filter(signal_type=\"buy\").count()}')
print(f'SELL signals: {signals.filter(signal_type=\"sell\").count()}')
"
```
**Should be**: 3-10 total signals with some BUY/SELL  
**If only HOLD**: Technical indicators missing - run step 2 above

### Check 4: User Configuration
```bash
python manage.py shell -c "
from apps.users.models import User
user = User.objects.filter(telegram_chat_id='7676229144').first()
if user:
    print(f'User: {user.email} (Active: {user.is_active})')
    print(f'Email notifications: {user.email_notifications}')
else:
    print('ERROR: No user configured with Telegram ID')
"
```

### Check 5: Telegram Bot
```bash
python manage.py shell -c "
import asyncio
from telegram import Bot
from django.conf import settings

async def test():
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    me = await bot.get_me()
    print(f'Bot: @{me.username}')
    await bot.send_message('7676229144', 'Test message')
    print('Test message sent!')

asyncio.run(test())
"
```

---

## 📊 Monitoring Dashboard

### View Signal Performance
1. Start Django server: `python manage.py runserver`
2. Open: http://localhost:8000/analysis/recommendations/
3. Check accuracy, ROI, and learning analytics

### Daily Status Check
```bash
python manage.py monitor_notifications
```

---

## 🛠️ Advanced Commands

### Force Generate Test Signals
```bash
python manage.py generate_and_notify --force-generate
```

### Dry Run (See What Would Happen)
```bash
python manage.py generate_and_notify --dry-run
```

### Full System Test
```bash
python manage.py test_30min_notifications
```

### Reset Today's Signals (for testing)
```bash
python manage.py shell -c "
from apps.analysis.models import TradingSignal
from datetime import date
TradingSignal.objects.filter(created_at__date=date.today()).update(is_sent=False, sent_at=None)
print('Reset signals for testing')
"
```

---

## 📞 Emergency Contacts

**If nothing works**:
1. Check Django logs for errors
2. Verify Telegram bot @Rekomendacje_gp_bot is not blocked
3. Confirm internet connection
4. Check PostgreSQL database is running

**System Status**:
- ✅ Data collection: Active
- ✅ Telegram bot: @Rekomendacje_gp_bot  
- ✅ User: test@gpwtradingadvisor.com
- ✅ Chat ID: 7676229144

---

## 📋 Expected Daily Flow

**9:00 AM**: System calculates technical indicators  
**9:05 AM**: Trading signals generated (2-8 signals typical)  
**9:06 AM**: Telegram notifications sent for BUY/SELL signals  
**Throughout day**: Additional signals if market conditions change  
**5:00 PM**: Daily summary (optional)

**Sample Notification**:
```
🎯 GPW Trading Signal

Stock: PKO
Action: BUY
Confidence: 78.5%
Price: 25.50 PLN
Target: 27.00 PLN
Stop Loss: 24.00 PLN

Generated: 09:06:23
```

---

**Last Updated**: July 24, 2025  
**Next Steps**: Run the quick test above to verify everything works!
