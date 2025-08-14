#!/bin/bash

# GPW Trading Advisor - Complete Startup Script
# This script starts the application and all automation services
# Author: GPW Trading Advisor Team
# Date: July 24, 2025

set -e  # Exit on any error

# Configuration
PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
VENV_PATH="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/run"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"
LOG_FILE="$LOG_DIR/startup_$(date +%Y%m%d_%H%M%S).log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}❌ $1${NC}" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}" | tee -a "$LOG_FILE"
}

# Function to check if a process is running
is_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# Function to stop a process
stop_process() {
    local name="$1"
    local pid_file="$PID_DIR/${name}.pid"
    
    if is_running "$pid_file"; then
        local pid=$(cat "$pid_file")
        log_info "Stopping $name (PID: $pid)"
        kill "$pid" 2>/dev/null || true
        sleep 2
        
        if kill -0 "$pid" 2>/dev/null; then
            log_warning "Force killing $name"
            kill -9 "$pid" 2>/dev/null || true
        fi
        
        rm -f "$pid_file"
        log_success "$name stopped"
    else
        log_info "$name is not running"
    fi
}

# Function to check Redis connection
check_redis() {
    log_info "Checking Redis connection..."
    
    if command -v redis-cli >/dev/null 2>&1; then
        if redis-cli ping > /dev/null 2>&1; then
            log_success "Redis is running"
            return 0
        else
            log_error "Redis is not responding"
            log_info "Please start Redis server: brew services start redis"
            return 1
        fi
    else
        log_error "Redis CLI not found"
        log_info "Please install Redis: brew install redis"
        return 1
    fi
}

# Function to start Django development server
start_django() {
    log_info "Starting Django development server..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Run migrations
    python manage.py migrate --no-input >> "$LOG_FILE" 2>&1
    
    # Collect static files
    python manage.py collectstatic --no-input >> "$LOG_FILE" 2>&1
    
    # Start Django server in background
    nohup python manage.py runserver 127.0.0.1:8000 > "$LOG_DIR/django.log" 2>&1 &
    echo $! > "$PID_DIR/django.pid"
    
    # Wait for server to start
    sleep 3
    
    if is_running "$PID_DIR/django.pid"; then
        log_success "Django server started on http://127.0.0.1:8000"
    else
        log_error "Failed to start Django server"
        return 1
    fi
}

# Function to start Celery Worker
start_celery_worker() {
    log_info "Starting Celery Worker..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Start Celery Worker in background
    nohup celery -A gpw_advisor worker --loglevel=info > "$LOG_DIR/celery_worker.log" 2>&1 &
    echo $! > "$PID_DIR/celery_worker.pid"
    
    # Wait for worker to start
    sleep 3
    
    if is_running "$PID_DIR/celery_worker.pid"; then
        log_success "Celery Worker started"
    else
        log_error "Failed to start Celery Worker"
        return 1
    fi
}

# Function to start Celery Beat (scheduler)
start_celery_beat() {
    log_info "Starting Celery Beat scheduler..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Start Celery Beat in background
    nohup celery -A gpw_advisor beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler > "$LOG_DIR/celery_beat.log" 2>&1 &
    echo $! > "$PID_DIR/celery_beat.pid"
    
    # Wait for beat to start
    sleep 3
    
    if is_running "$PID_DIR/celery_beat.pid"; then
        log_success "Celery Beat scheduler started"
    else
        log_error "Failed to start Celery Beat scheduler"
        return 1
    fi
}

# Function to start data collection automation
start_data_collection() {
    log_info "Starting data collection automation..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Create script for data collection
    cat > "$PROJECT_DIR/scripts/data_collection_daemon.sh" << 'EOF'
#!/bin/bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
source venv/bin/activate

while true; do
    echo "$(date): Starting data collection cycle"
    
    # Collect stock data
    python manage.py collect_stock_data >> logs/data_collection.log 2>&1
    
    # Sleep for 5 minutes
    sleep 300
done
EOF
    
    chmod +x "$PROJECT_DIR/scripts/data_collection_daemon.sh"
    
    # Start data collection in background
    nohup "$PROJECT_DIR/scripts/data_collection_daemon.sh" > "$LOG_DIR/data_collection_daemon.log" 2>&1 &
    echo $! > "$PID_DIR/data_collection.pid"
    
    log_success "Data collection automation started"
}

# Function to start signal generation automation
start_signal_automation() {
    log_info "Starting signal generation automation..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Create script for signal automation
    cat > "$PROJECT_DIR/scripts/signal_automation_daemon.sh" << 'EOF'
#!/bin/bash
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2
source venv/bin/activate

while true; do
    current_hour=$(date +%H)
    current_day=$(date +%u)  # 1=Monday, 7=Sunday
    
    # Only run during market hours (9-17) on weekdays (1-5)
    if [[ $current_day -le 5 && $current_hour -ge 9 && $current_hour -le 17 ]]; then
        echo "$(date): Starting signal generation cycle"
        
        # Calculate indicators
        python manage.py calculate_indicators >> logs/signal_automation.log 2>&1
        
        # Generate signals
        python manage.py generate_daily_signals --all-monitored >> logs/signal_automation.log 2>&1
        
        # Send notifications
        python manage.py generate_and_notify >> logs/signal_automation.log 2>&1
        
        echo "$(date): Signal generation cycle completed"
        
        # Sleep for 30 minutes during market hours
        sleep 1800
    else
        # Sleep for 1 hour outside market hours
        sleep 3600
    fi
done
EOF
    
    chmod +x "$PROJECT_DIR/scripts/signal_automation_daemon.sh"
    
    # Start signal automation in background
    nohup "$PROJECT_DIR/scripts/signal_automation_daemon.sh" > "$LOG_DIR/signal_automation_daemon.log" 2>&1 &
    echo $! > "$PID_DIR/signal_automation.pid"
    
    log_success "Signal automation started"
}

# Function to perform initial data setup
initial_data_setup() {
    log_info "Performing initial data setup..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Calculate today's indicators if not present
    python manage.py shell -c "
from apps.analysis.models import IndicatorValue
from datetime import date
today = date.today()
count = IndicatorValue.objects.filter(calculated_at__date=today).count()
if count < 100:
    print('Calculating initial indicators...')
    exit(1)
else:
    print(f'Found {count} indicators for today')
    exit(0)
" >> "$LOG_FILE" 2>&1
    
    if [[ $? -eq 1 ]]; then
        log_info "Calculating initial technical indicators..."
        python manage.py calculate_indicators >> "$LOG_FILE" 2>&1
        log_success "Initial indicators calculated"
    else
        log_success "Indicators already present"
    fi
    
    # Generate initial signals if needed
    python manage.py shell -c "
from apps.analysis.models import TradingSignal
from datetime import date
today = date.today()
count = TradingSignal.objects.filter(created_at__date=today).count()
if count == 0:
    print('Generating initial signals...')
    exit(1)
else:
    print(f'Found {count} signals for today')
    exit(0)
" >> "$LOG_FILE" 2>&1
    
    if [[ $? -eq 1 ]]; then
        log_info "Generating initial trading signals..."
        python manage.py generate_daily_signals --all-monitored >> "$LOG_FILE" 2>&1
        log_success "Initial signals generated"
    else
        log_success "Signals already present"
    fi
}

# Function to perform comprehensive health check
health_check() {
    log_info "Performing comprehensive health check..."
    
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    local health_status=0
    
    # Check Django server
    if curl -s http://127.0.0.1:8000 > /dev/null; then
        log_success "Django server is responding"
    else
        log_error "Django server is not responding"
        health_status=1
    fi
    
    # Check database connection
    python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('Database connection: OK')
except Exception as e:
    print(f'Database error: {e}')
    exit(1)
" >> "$LOG_FILE" 2>&1
    
    if [[ $? -eq 0 ]]; then
        log_success "Database connection is healthy"
    else
        log_error "Database connection failed"
        health_status=1
    fi
    
    # Check Telegram bot
    python manage.py shell -c "
import asyncio
from django.conf import settings
from telegram import Bot

async def test_bot():
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f'Telegram bot: @{me.username} - Active')
        return True
    except Exception as e:
        print(f'Telegram bot error: {e}')
        return False

result = asyncio.run(test_bot())
exit(0 if result else 1)
" >> "$LOG_FILE" 2>&1
    
    if [[ $? -eq 0 ]]; then
        log_success "Telegram bot is working"
    else
        log_warning "Telegram bot has issues (check logs)"
    fi
    
    # Check data freshness
    python manage.py shell -c "
from apps.scrapers.models import StockData
from datetime import date, timedelta
today = date.today()
yesterday = today - timedelta(days=1)

# Check today's data
today_count = StockData.objects.filter(created_at__date=today).count()
yesterday_count = StockData.objects.filter(created_at__date=yesterday).count()

print(f'Data today: {today_count}')
print(f'Data yesterday: {yesterday_count}')

if today_count > 1000:
    print('Data collection: OK')
    exit(0)
elif yesterday_count > 1000:
    print('Data collection: Recent data available')
    exit(0)
else:
    print('Data collection: No recent data')
    exit(1)
" >> "$LOG_FILE" 2>&1
    
    if [[ $? -eq 0 ]]; then
        log_success "Data collection is working"
    else
        log_warning "Data collection needs attention"
    fi
    
    # Check processes
    for process in django celery_worker celery_beat; do
        if is_running "$PID_DIR/${process}.pid"; then
            log_success "$process is running"
        else
            log_warning "$process is not running"
            health_status=1
        fi
    done
    
    # System summary
    log_info "=== SYSTEM SUMMARY ==="
    python manage.py shell -c "
from datetime import date
from apps.scrapers.models import StockData
from apps.analysis.models import IndicatorValue, TradingSignal
from apps.users.models import User

today = date.today()
print(f'Date: {today}')
print(f'Stock data entries today: {StockData.objects.filter(created_at__date=today).count()}')
print(f'Technical indicators today: {IndicatorValue.objects.filter(calculated_at__date=today).count()}')
print(f'Trading signals today: {TradingSignal.objects.filter(created_at__date=today).count()}')
print(f'Active users: {User.objects.filter(is_active=True).count()}')
print(f'Users with Telegram: {User.objects.filter(telegram_chat_id__isnull=False).count()}')
" | tee -a "$LOG_FILE"
    
    return $health_status
}

# Function to create monitoring script
create_monitoring_script() {
    log_info "Creating monitoring script..."
    
    cat > "$PROJECT_DIR/scripts/monitor_system.sh" << 'EOF'
#!/bin/bash

PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
PID_DIR="$PROJECT_DIR/run"

echo "=== GPW Trading Advisor System Status ==="
echo "Date: $(date)"
echo

# Check processes
for process in django celery_worker celery_beat; do
    pid_file="$PID_DIR/${process}.pid"
    if [[ -f "$pid_file" ]]; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "✅ $process: Running (PID: $pid)"
        else
            echo "❌ $process: Not running (stale PID file)"
            rm -f "$pid_file"
        fi
    else
        echo "❌ $process: Not running (no PID file)"
    fi
done

# Check Celery processes status
echo
echo "=== Celery Status ==="
cd "$PROJECT_DIR"
source venv/bin/activate
python -c "
import subprocess
import sys
try:
    result = subprocess.run(['celery', '-A', 'gpw_advisor', 'inspect', 'active'], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print('Celery workers are responsive')
    else:
        print('Celery workers not responding')
except:
    print('Could not check Celery status')
"

echo
echo "=== Recent Logs ==="
tail -5 "$PROJECT_DIR/logs/"*.log 2>/dev/null || echo "No recent logs"

echo
echo "=== Quick Health Check ==="
cd "$PROJECT_DIR"
source venv/bin/activate
python manage.py shell -c "
from datetime import date
from apps.analysis.models import TradingSignal
today = date.today()
signals = TradingSignal.objects.filter(created_at__date=today)
print(f'Signals today: {signals.count()}')
if signals.exists():
    print('Latest signals:')
    for s in signals[:3]:
        print(f'  - {s.stock.symbol}: {s.signal_type} (confidence: {s.confidence}%)')
"
EOF
    
    chmod +x "$PROJECT_DIR/scripts/monitor_system.sh"
    log_success "Monitoring script created at scripts/monitor_system.sh"
}

# Function to create stop script
create_stop_script() {
    log_info "Creating stop script..."
    
    cat > "$PROJECT_DIR/scripts/stop_system.sh" << 'EOF'
#!/bin/bash

PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
PID_DIR="$PROJECT_DIR/run"

echo "=== Stopping GPW Trading Advisor ==="

# Stop all processes
for process in django celery_worker celery_beat data_collection signal_automation; do
    pid_file="$PID_DIR/${process}.pid"
    if [[ -f "$pid_file" ]]; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping $process (PID: $pid)"
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                echo "Force killing $process"
                kill -9 "$pid"
            fi
        fi
        rm -f "$pid_file"
    fi
done

# Additional cleanup for Celery processes
echo "Cleaning up any remaining Celery processes..."
pkill -f "celery.*gpw_advisor" 2>/dev/null || true

echo "✅ All services stopped"
EOF
    
    chmod +x "$PROJECT_DIR/scripts/stop_system.sh"
    log_success "Stop script created at scripts/stop_system.sh"
}

# Main execution
main() {
    log_info "=== GPW Trading Advisor Startup Script ==="
    log_info "Starting comprehensive system initialization..."
    
    # Change to project directory
    cd "$PROJECT_DIR" || {
        log_error "Project directory not found: $PROJECT_DIR"
        exit 1
    }
    
    # Check if virtual environment exists
    if [[ ! -d "$VENV_PATH" ]]; then
        log_error "Virtual environment not found: $VENV_PATH"
        exit 1
    fi
    
    # Create necessary directories
    mkdir -p "$LOG_DIR" "$PID_DIR" "$PROJECT_DIR/scripts"
    
    # Check Redis availability (required for Celery)
    if ! check_redis; then
        log_error "Redis is required for Celery to work"
        exit 1
    fi
    
    # Stop any existing processes
    log_info "Stopping any existing processes..."
    for process in django data_collection signal_automation celery_worker celery_beat; do
        stop_process "$process"
    done
    
    # Start services
    log_info "Starting core services..."
    
    if start_django; then
        log_success "Django server started successfully"
    else
        log_error "Failed to start Django server"
        exit 1
    fi
    
    # Start Celery services
    if start_celery_worker; then
        log_success "Celery Worker started successfully"
    else
        log_error "Failed to start Celery Worker"
        exit 1
    fi
    
    if start_celery_beat; then
        log_success "Celery Beat scheduler started successfully"
    else
        log_error "Failed to start Celery Beat scheduler"
        exit 1
    fi
    
    # Perform initial data setup
    initial_data_setup
    
    # Start automation services (można wyłączyć - Celery je zastępuje)
    log_warning "Note: Legacy automation services disabled - using Celery schedulers instead"
    # start_data_collection
    # start_signal_automation
    
    # Create utility scripts
    create_monitoring_script
    create_stop_script
    
    # Perform comprehensive health check
    log_info "Performing final health check..."
    if health_check; then
        log_success "=== ALL SYSTEMS OPERATIONAL ==="
        log_info "Django server: http://127.0.0.1:8000"
        log_info "Monitoring: ./scripts/monitor_system.sh"
        log_info "Stop system: ./scripts/stop_system.sh"
        log_info "Logs directory: $LOG_DIR"
        
        # Send test notification
        log_info "Sending startup notification..."
        source "$VENV_PATH/bin/activate"
        python manage.py setup_notifications --test-telegram >> "$LOG_FILE" 2>&1 || log_warning "Test notification failed"
        
        log_success "🚀 GPW Trading Advisor is fully operational!"
    else
        log_warning "=== SYSTEM STARTED WITH WARNINGS ==="
        log_warning "Check logs for details: $LOG_FILE"
    fi
    
    log_info "Startup completed. Log file: $LOG_FILE"
}

# Handle script termination
trap 'log_error "Startup script interrupted"; exit 1' INT TERM

# Run main function
main "$@"
