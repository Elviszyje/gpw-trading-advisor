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
