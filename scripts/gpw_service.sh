#!/bin/bash

# GPW Trading Advisor Service Manager
# Usage: ./gpw_service.sh {start|stop|restart|status|logs|health}

PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
STARTUP_SCRIPT="$PROJECT_DIR/scripts/startup.sh"
STOP_SCRIPT="$PROJECT_DIR/scripts/stop_system.sh"
MONITOR_SCRIPT="$PROJECT_DIR/scripts/monitor_system.sh"
LOG_DIR="$PROJECT_DIR/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo "GPW Trading Advisor Service Manager"
    echo "Usage: $0 {start|stop|restart|status|logs|health|test}"
    echo ""
    echo "Commands:"
    echo "  start   - Start all GPW services"
    echo "  stop    - Stop all GPW services"
    echo "  restart - Restart all GPW services"
    echo "  status  - Show service status"
    echo "  logs    - Show recent logs"
    echo "  health  - Perform health check"
    echo "  test    - Run comprehensive test"
    exit 1
}

print_header() {
    echo -e "${BLUE}=== GPW Trading Advisor Service Manager ===${NC}"
    echo "Date: $(date)"
    echo ""
}

start_services() {
    echo -e "${GREEN}🚀 Starting GPW Trading Advisor...${NC}"
    
    if [[ ! -f "$STARTUP_SCRIPT" ]]; then
        echo -e "${RED}❌ Startup script not found: $STARTUP_SCRIPT${NC}"
        exit 1
    fi
    
    chmod +x "$STARTUP_SCRIPT"
    "$STARTUP_SCRIPT"
}

stop_services() {
    echo -e "${YELLOW}🛑 Stopping GPW Trading Advisor...${NC}"
    
    if [[ -f "$STOP_SCRIPT" ]]; then
        chmod +x "$STOP_SCRIPT"
        "$STOP_SCRIPT"
    else
        echo -e "${YELLOW}⚠️  Stop script not found, stopping manually...${NC}"
        
        # Manual stop
        PID_DIR="$PROJECT_DIR/run"
        for process in django celery_worker celery_beat data_collection signal_automation; do
            pid_file="$PID_DIR/${process}.pid"
            if [[ -f "$pid_file" ]]; then
                pid=$(cat "$pid_file")
                if kill -0 "$pid" 2>/dev/null; then
                    echo "Stopping $process (PID: $pid)"
                    kill "$pid" 2>/dev/null || true
                    sleep 2
                    if kill -0 "$pid" 2>/dev/null; then
                        kill -9 "$pid" 2>/dev/null || true
                    fi
                fi
                rm -f "$pid_file"
            fi
        done
        
        # Additional cleanup for Celery processes
        echo "Cleaning up any remaining Celery processes..."
        pkill -f "celery.*gpw_advisor" 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✅ Services stopped${NC}"
}

show_status() {
    echo -e "${BLUE}📊 Service Status${NC}"
    
    if [[ -f "$MONITOR_SCRIPT" ]]; then
        chmod +x "$MONITOR_SCRIPT"
        "$MONITOR_SCRIPT"
    else
        echo -e "${YELLOW}⚠️  Monitor script not found, checking manually...${NC}"
        
        PID_DIR="$PROJECT_DIR/run"
        for process in django celery_worker celery_beat data_collection signal_automation; do
            pid_file="$PID_DIR/${process}.pid"
            if [[ -f "$pid_file" ]]; then
                pid=$(cat "$pid_file")
                if kill -0 "$pid" 2>/dev/null; then
                    echo -e "${GREEN}✅ $process: Running (PID: $pid)${NC}"
                else
                    echo -e "${RED}❌ $process: Not running (stale PID)${NC}"
                fi
            else
                echo -e "${RED}❌ $process: Not running${NC}"
            fi
        done
    fi
}

show_logs() {
    echo -e "${BLUE}📝 Recent Logs${NC}"
    
    if [[ -d "$LOG_DIR" ]]; then
        echo "=== Startup Logs ==="
        ls -la "$LOG_DIR"/startup_*.log 2>/dev/null | tail -3
        echo ""
        
        latest_startup_log=$(ls -t "$LOG_DIR"/startup_*.log 2>/dev/null | head -1)
        if [[ -f "$latest_startup_log" ]]; then
            echo "=== Latest Startup Log (last 20 lines) ==="
            tail -20 "$latest_startup_log"
            echo ""
        fi
        
        echo "=== Django Logs ==="
        if [[ -f "$LOG_DIR/django.log" ]]; then
            tail -10 "$LOG_DIR/django.log"
        else
            echo "No Django logs found"
        fi
        
        echo ""
        echo "=== Data Collection Logs ==="
        if [[ -f "$LOG_DIR/data_collection_daemon.log" ]]; then
            tail -5 "$LOG_DIR/data_collection_daemon.log"
        else
            echo "No data collection logs found"
        fi
        
        echo ""
        echo "=== Signal Automation Logs ==="
        if [[ -f "$LOG_DIR/signal_automation_daemon.log" ]]; then
            tail -5 "$LOG_DIR/signal_automation_daemon.log"
        else
            echo "No signal automation logs found"
        fi
    else
        echo -e "${RED}❌ Log directory not found: $LOG_DIR${NC}"
    fi
}

health_check() {
    echo -e "${BLUE}🔍 Health Check${NC}"
    
    cd "$PROJECT_DIR" || {
        echo -e "${RED}❌ Cannot access project directory${NC}"
        return 1
    }
    
    source venv/bin/activate 2>/dev/null || {
        echo -e "${RED}❌ Cannot activate virtual environment${NC}"
        return 1
    }
    
    # Check Django
    if curl -s http://127.0.0.1:8000 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Django server responding${NC}"
    else
        echo -e "${RED}❌ Django server not responding${NC}"
    fi
    
    # Quick database check
    python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('✅ Database: Connected')
except Exception as e:
    print(f'❌ Database: {e}')
"
    
    # Quick data check
    python manage.py shell -c "
from datetime import date, timedelta
from apps.scrapers.models import StockData
from apps.analysis.models import TradingSignal

today = date.today()
yesterday = today - timedelta(days=1)

data_today = StockData.objects.filter(created_at__date=today).count()
data_yesterday = StockData.objects.filter(created_at__date=yesterday).count()
signals_today = TradingSignal.objects.filter(created_at__date=today).count()

print(f'📊 Data today: {data_today}')
print(f'📊 Data yesterday: {data_yesterday}')
print(f'📊 Signals today: {signals_today}')

if data_today > 100 or data_yesterday > 100:
    print('✅ Data collection: Recent data available')
else:
    print('⚠️  Data collection: No recent data')
"
    
    # Telegram test
    echo ""
    echo -e "${BLUE}🤖 Testing Telegram Bot...${NC}"
    python manage.py shell -c "
import asyncio
from django.conf import settings
from telegram import Bot

async def quick_test():
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f'✅ Telegram: @{me.username} is active')
        return True
    except Exception as e:
        print(f'❌ Telegram: {e}')
        return False

asyncio.run(quick_test())
"
}

run_comprehensive_test() {
    echo -e "${BLUE}🧪 Running Comprehensive Test${NC}"
    
    cd "$PROJECT_DIR" || {
        echo -e "${RED}❌ Cannot access project directory${NC}"
        return 1
    }
    
    source venv/bin/activate
    
    echo "1. Testing notification system..."
    python manage.py setup_notifications --test-telegram
    
    echo ""
    echo "2. Generating test signals..."
    python manage.py generate_and_notify --force-generate --dry-run
    
    echo ""
    echo "3. System monitoring test..."
    python manage.py monitor_notifications
    
    echo ""
    echo -e "${GREEN}✅ Comprehensive test completed${NC}"
}

case "$1" in
    start)
        print_header
        start_services
        ;;
    stop)
        print_header
        stop_services
        ;;
    restart)
        print_header
        stop_services
        echo ""
        sleep 3
        start_services
        ;;
    status)
        print_header
        show_status
        ;;
    logs)
        print_header
        show_logs
        ;;
    health)
        print_header
        health_check
        ;;
    test)
        print_header
        run_comprehensive_test
        ;;
    *)
        usage
        ;;
esac
