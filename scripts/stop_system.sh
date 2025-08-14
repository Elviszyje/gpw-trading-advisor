#!/bin/bash

PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
PID_DIR="$PROJECT_DIR/run"

echo "=== Stopping GPW Trading Advisor ==="

# Stop all processes
for process in django data_collection signal_automation; do
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

echo "✅ All services stopped"
