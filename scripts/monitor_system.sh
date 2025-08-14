#!/bin/bash

PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
PID_DIR="$PROJECT_DIR/run"

echo "=== GPW Trading Advisor System Status ==="
echo "Date: $(date)"
echo

# Check processes
for process in django data_collection signal_automation; do
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
