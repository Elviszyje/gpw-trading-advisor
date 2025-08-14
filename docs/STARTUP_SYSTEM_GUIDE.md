# GPW Trading Advisor - Startup Scripts Documentation

## 🚀 Complete Startup & Automation System

I've created a comprehensive startup system for your GPW Trading Advisor that will:

1. **Start the Django application**
2. **Launch all automation services**  
3. **Perform health checks**
4. **Set up monitoring**
5. **Send test notifications**

## 📁 Scripts Created

### 1. Main Startup Script: `scripts/startup.sh`
**Purpose**: Complete system initialization
**Features**:
- Starts Django development server on http://127.0.0.1:8000
- Launches data collection automation (every 5 minutes)
- Starts signal generation automation (every 30 minutes during market hours)
- Performs comprehensive health checks
- Creates monitoring and stop scripts
- Sends startup notification to Telegram

### 2. Service Manager: `scripts/gpw_service.sh`  
**Purpose**: systemctl-style service management
**Commands**:
```bash
./scripts/gpw_service.sh start     # Start all services
./scripts/gpw_service.sh stop      # Stop all services  
./scripts/gpw_service.sh restart   # Restart all services
./scripts/gpw_service.sh status    # Show service status
./scripts/gpw_service.sh logs      # Show recent logs
./scripts/gpw_service.sh health    # Perform health check
./scripts/gpw_service.sh test      # Run comprehensive test
```

### 3. Desktop Launcher: `scripts/gpw_launcher.sh`
**Purpose**: macOS GUI launcher with dialog boxes
**Features**:
- Start/stop system with GUI dialogs
- Check status and view logs
- Run health checks and tests
- Open web dashboard

## 🎯 Quick Start

### Step 1: Make Scripts Executable
```bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
chmod +x scripts/*.sh
```

### Step 2: Start the System
```bash
# Option A: Full startup (recommended first time)
./scripts/startup.sh

# Option B: Service manager
./scripts/gpw_service.sh start

# Option C: GUI launcher (macOS)
./scripts/gpw_launcher.sh
```

### Step 3: Verify Everything Works
```bash
# Check status
./scripts/gpw_service.sh status

# View dashboard
open http://127.0.0.1:8000

# Run health check
./scripts/gpw_service.sh health
```

## 🔄 What Happens During Startup

### Phase 1: Environment Setup
- ✅ Validates project directory and virtual environment
- ✅ Creates log and PID directories
- ✅ Stops any existing processes

### Phase 2: Django Server
- ✅ Runs database migrations
- ✅ Collects static files
- ✅ Starts Django on http://127.0.0.1:8000

### Phase 3: Initial Data Setup
- ✅ Calculates technical indicators if missing
- ✅ Generates initial trading signals if needed

### Phase 4: Automation Services
- ✅ **Data Collection Daemon**: Collects stock prices every 5 minutes
- ✅ **Signal Automation Daemon**: Generates signals every 30 minutes during market hours (9 AM - 5 PM, weekdays)

### Phase 5: Health Check
- ✅ Tests Django server response
- ✅ Verifies database connection
- ✅ Tests Telegram bot connection
- ✅ Checks data freshness
- ✅ Validates all processes are running

### Phase 6: Final Setup
- ✅ Creates monitoring script (`scripts/monitor_system.sh`)
- ✅ Creates stop script (`scripts/stop_system.sh`)  
- ✅ Sends test Telegram notification
- ✅ Displays system summary

## 📊 Monitoring & Management

### Real-time Monitoring
```bash
# Quick status check
./scripts/gpw_service.sh status

# Detailed monitoring
./scripts/monitor_system.sh

# Watch logs in real-time
tail -f logs/django.log
tail -f logs/signal_automation_daemon.log
```

### Log Files Location
```
logs/
├── startup_YYYYMMDD_HHMMSS.log     # Startup logs
├── django.log                       # Django server logs
├── data_collection_daemon.log       # Data collection logs
├── signal_automation_daemon.log     # Signal automation logs
└── data_collection.log              # Manual data collection
```

### Process Management
```bash
# All processes are tracked with PID files in:
run/
├── django.pid
├── data_collection.pid
└── signal_automation.pid
```

## 🔧 Automation Details

### Data Collection Automation
- **Frequency**: Every 5 minutes
- **Purpose**: Continuously collect stock price data
- **Command**: `python manage.py collect_stock_data`

### Signal Generation Automation  
- **Frequency**: Every 30 minutes during market hours (9 AM - 5 PM, Mon-Fri)
- **Outside market hours**: Every 1 hour (minimal activity)
- **Process**:
  1. Calculate technical indicators
  2. Generate trading signals
  3. Send notifications for new signals

### Market Hours Detection
- **Active**: Monday-Friday, 9:00 AM - 5:00 PM
- **Weekend**: Minimal processing
- **After hours**: Reduced frequency

## 🚨 Emergency Procedures

### If System Becomes Unresponsive
```bash
# Force stop everything
./scripts/gpw_service.sh stop

# Check for hung processes
ps aux | grep python | grep manage.py

# Restart fresh
./scripts/gpw_service.sh start
```

### If Notifications Stop Working
```bash
# Quick diagnostic
./scripts/gpw_service.sh health

# Test notifications
./scripts/gpw_service.sh test

# Check Telegram bot
python manage.py setup_notifications --test-telegram
```

### If Data Collection Stops
```bash
# Check data collection status
./scripts/gpw_service.sh status

# View data collection logs
tail -20 logs/data_collection_daemon.log

# Manual data collection test
python manage.py collect_stock_data
```

## 📱 Expected Notifications

After startup, you should receive:

1. **Startup notification**: Confirms system is operational
2. **Morning signals**: Daily trading recommendations (9:00-9:30 AM)
3. **Intraday signals**: Additional signals during market hours
4. **Error alerts**: If any system issues occur

## 🎯 Desktop Integration (macOS)

### Create Desktop Shortcut
```bash
# Create app bundle
mkdir -p ~/Desktop/GPW\ Trading\ Advisor.app/Contents/MacOS

# Copy launcher
cp scripts/gpw_launcher.sh ~/Desktop/GPW\ Trading\ Advisor.app/Contents/MacOS/

# Make executable  
chmod +x ~/Desktop/GPW\ Trading\ Advisor.app/Contents/MacOS/gpw_launcher.sh
```

### Add to Dock
1. Drag `GPW Trading Advisor.app` to your Dock
2. Right-click → Options → Keep in Dock

## 📋 Daily Workflow

### Automatic (Recommended)
- System runs continuously
- Data collected every 5 minutes
- Signals generated every 30 minutes during market hours
- Notifications sent immediately

### Manual Trigger
```bash
# Force generate signals now
python manage.py calculate_indicators
python manage.py generate_daily_signals --all-monitored
python manage.py generate_and_notify
```

## 🔍 Troubleshooting

### Common Issues

**Port 8000 already in use**:
```bash
./scripts/gpw_service.sh stop
lsof -ti:8000 | xargs kill
./scripts/gpw_service.sh start
```

**Virtual environment issues**:
```bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Database connection errors**:
```bash
python manage.py migrate
python manage.py check --database default
```

**Telegram bot not working**:
```bash
# Check settings
python manage.py shell -c "from django.conf import settings; print(settings.TELEGRAM_BOT_TOKEN)"

# Test manually
python manage.py setup_notifications --test-telegram
```

## ✅ Success Indicators

System is working correctly when:

- ✅ Django server responds at http://127.0.0.1:8000
- ✅ All 3 processes show as "Running" in status
- ✅ Recent data in database (1000+ entries per day)
- ✅ Technical indicators calculated daily
- ✅ Trading signals generated (2-10 per day typical)
- ✅ Telegram notifications received
- ✅ Dashboard shows live data

## 📞 Support

### Self-Diagnosis
```bash
./scripts/gpw_service.sh health
./scripts/gpw_service.sh test
```

### Log Analysis
```bash
./scripts/gpw_service.sh logs
```

### Manual Reset
```bash
./scripts/gpw_service.sh stop
rm -rf run/*.pid
./scripts/startup.sh
```

---

**Ready to start? Run: `./scripts/startup.sh`** 🚀
