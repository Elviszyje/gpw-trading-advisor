#!/bin/bash

# GPW Trading Advisor Daily Workflow
# This script runs the complete daily workflow for signal generation and notifications

echo "🚀 Starting GPW Trading Advisor Daily Workflow - $(date)"
echo "=================================================="

# Navigate to project directory
cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2

# Activate virtual environment
source venv/bin/activate

echo "📊 Step 1: Calculate Technical Indicators"
python manage.py calculate_indicators

echo "📈 Step 2: Generate Daily Trading Signals"  
python manage.py generate_daily_signals --all-monitored

echo "📱 Step 3: Send Signal Notifications"
python manage.py generate_and_notify

echo "✅ Daily workflow completed - $(date)"
echo "Check Telegram for notifications!"
