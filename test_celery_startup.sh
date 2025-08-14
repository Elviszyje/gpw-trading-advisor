#!/bin/bash

# Test funkcji Celery z startup script

PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"
VENV_PATH="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/run"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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
        return 0
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
        return 0
    else
        log_error "Failed to start Celery Beat scheduler"
        return 1
    fi
}

# Main test
echo "=== Test funkcji Celery ==="
mkdir -p "$LOG_DIR" "$PID_DIR"

if start_celery_worker; then
    log_success "✅ Celery Worker test passed"
else
    log_error "❌ Celery Worker test failed"
    exit 1
fi

if start_celery_beat; then
    log_success "✅ Celery Beat test passed"
else
    log_error "❌ Celery Beat test failed"
    exit 1
fi

echo ""
log_success "🎉 All Celery functions working!"

# Show status
echo ""
echo "=== Status ==="
for process in celery_worker celery_beat; do
    pid_file="$PID_DIR/${process}.pid"
    if is_running "$pid_file"; then
        pid=$(cat "$pid_file")
        log_success "$process: Running (PID: $pid)"
    else
        log_error "$process: Not running"
    fi
done

echo ""
echo "=== Logs ==="
echo "Worker log: tail -f $LOG_DIR/celery_worker.log"
echo "Beat log: tail -f $LOG_DIR/celery_beat.log"
