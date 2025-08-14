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
