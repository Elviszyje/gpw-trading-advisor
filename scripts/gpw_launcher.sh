#!/bin/bash

# GPW Trading Advisor Desktop Launcher
# This script provides a simple GUI for managing the GPW Trading Advisor

PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
SERVICE_SCRIPT="$PROJECT_DIR/scripts/gpw_service.sh"

# Function to show dialog
show_dialog() {
    local title="$1"
    local message="$2"
    
    if command -v osascript >/dev/null 2>&1; then
        osascript -e "display dialog \"$message\" with title \"$title\" buttons {\"OK\"} default button \"OK\""
    else
        echo "$title: $message"
    fi
}

# Function to show choice dialog
show_choice() {
    local title="$1"
    local message="$2"
    local choices="$3"
    
    if command -v osascript >/dev/null 2>&1; then
        choice=$(osascript -e "choose from list {$choices} with title \"$title\" with prompt \"$message\"")
        echo "$choice"
    else
        echo "start"  # Default choice
    fi
}

# Main menu
main_menu() {
    local choice
    choice=$(show_choice "GPW Trading Advisor" "Choose an action:" "\"Start System\", \"Stop System\", \"Check Status\", \"View Logs\", \"Health Check\", \"Test System\", \"Open Dashboard\"")
    
    case "$choice" in
        "Start System")
            show_dialog "GPW Trading Advisor" "Starting system... This may take a few minutes."
            "$SERVICE_SCRIPT" start > /tmp/gpw_output.log 2>&1
            if [[ $? -eq 0 ]]; then
                show_dialog "Success" "GPW Trading Advisor started successfully!"
            else
                show_dialog "Error" "Failed to start system. Check logs for details."
            fi
            ;;
        "Stop System")
            "$SERVICE_SCRIPT" stop > /tmp/gpw_output.log 2>&1
            show_dialog "GPW Trading Advisor" "System stopped."
            ;;
        "Check Status")
            "$SERVICE_SCRIPT" status > /tmp/gpw_output.log 2>&1
            show_dialog "System Status" "Status check completed. See terminal for details."
            ;;
        "View Logs")
            "$SERVICE_SCRIPT" logs > /tmp/gpw_output.log 2>&1
            show_dialog "Logs" "Logs displayed in terminal."
            ;;
        "Health Check")
            show_dialog "Health Check" "Running health check..."
            "$SERVICE_SCRIPT" health > /tmp/gpw_output.log 2>&1
            show_dialog "Health Check" "Health check completed. See terminal for details."
            ;;
        "Test System")
            show_dialog "Test System" "Running comprehensive test..."
            "$SERVICE_SCRIPT" test > /tmp/gpw_output.log 2>&1
            show_dialog "Test Complete" "System test completed. Check terminal for results."
            ;;
        "Open Dashboard")
            if command -v open >/dev/null 2>&1; then
                open "http://127.0.0.1:8000"
            else
                show_dialog "Dashboard" "Open http://127.0.0.1:8000 in your browser"
            fi
            ;;
        *)
            exit 0
            ;;
    esac
}

# Check if service script exists
if [[ ! -f "$SERVICE_SCRIPT" ]]; then
    show_dialog "Error" "GPW service script not found. Please run the startup script first."
    exit 1
fi

# Run main menu
main_menu
