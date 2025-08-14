#!/bin/bash
# scripts/monitor.sh - System monitoring and alerting script

set -e

# Configuration
LOG_FILE="/var/log/gpw-advisor/monitor.log"
HEALTH_URL="http://localhost:8000/health/"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}"
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=85
ALERT_THRESHOLD_DISK=90

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to send Telegram notification
send_telegram_alert() {
    local message="$1"
    
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="🚨 GPW Advisor Alert: $message" \
            -d parse_mode="Markdown" > /dev/null
    fi
}

# Function to check application health
check_app_health() {
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")
    
    if [ "$status_code" = "200" ]; then
        log "✅ Application health check: OK"
        return 0
    else
        log "❌ Application health check: FAILED (HTTP $status_code)"
        send_telegram_alert "Application health check failed (HTTP $status_code)"
        return 1
    fi
}

# Function to check Docker containers
check_containers() {
    log "🐳 Checking Docker containers..."
    
    local failed_containers=()
    local containers=("gpw2-web-1" "gpw2-celery-1" "gpw2-celery-beat-1" "gpw2-db-1" "gpw2-redis-1")
    
    for container in "${containers[@]}"; do
        if ! docker container inspect "$container" --format '{{.State.Status}}' 2>/dev/null | grep -q "running"; then
            failed_containers+=("$container")
        fi
    done
    
    if [ ${#failed_containers[@]} -eq 0 ]; then
        log "✅ All containers are running"
        return 0
    else
        local failed_list=$(printf ", %s" "${failed_containers[@]}")
        failed_list=${failed_list:2}  # Remove leading ", "
        log "❌ Failed containers: $failed_list"
        send_telegram_alert "Containers not running: $failed_list"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "💻 Checking system resources..."
    
    # CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    cpu_usage=${cpu_usage%.*}  # Remove decimal part
    
    if [ "$cpu_usage" -gt "$ALERT_THRESHOLD_CPU" ]; then
        log "⚠️  High CPU usage: ${cpu_usage}%"
        send_telegram_alert "High CPU usage: ${cpu_usage}% (threshold: ${ALERT_THRESHOLD_CPU}%)"
    else
        log "✅ CPU usage: ${cpu_usage}%"
    fi
    
    # Memory usage
    local memory_info=$(free | grep Mem)
    local total_mem=$(echo $memory_info | awk '{print $2}')
    local used_mem=$(echo $memory_info | awk '{print $3}')
    local memory_usage=$(( used_mem * 100 / total_mem ))
    
    if [ "$memory_usage" -gt "$ALERT_THRESHOLD_MEMORY" ]; then
        log "⚠️  High memory usage: ${memory_usage}%"
        send_telegram_alert "High memory usage: ${memory_usage}% (threshold: ${ALERT_THRESHOLD_MEMORY}%)"
    else
        log "✅ Memory usage: ${memory_usage}%"
    fi
    
    # Disk usage
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | cut -d'%' -f1)
    
    if [ "$disk_usage" -gt "$ALERT_THRESHOLD_DISK" ]; then
        log "⚠️  High disk usage: ${disk_usage}%"
        send_telegram_alert "High disk usage: ${disk_usage}% (threshold: ${ALERT_THRESHOLD_DISK}%)"
    else
        log "✅ Disk usage: ${disk_usage}%"
    fi
}

# Function to check database connectivity
check_database() {
    log "🗄️  Checking database connectivity..."
    
    if docker-compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
        log "✅ Database connection: OK"
        
        # Check database size
        local db_size=$(docker-compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT pg_size_pretty(pg_database_size('$POSTGRES_DB'));" | xargs)
        log "📊 Database size: $db_size"
        
        return 0
    else
        log "❌ Database connection: FAILED"
        send_telegram_alert "Database connection failed"
        return 1
    fi
}

# Function to check Redis connectivity
check_redis() {
    log "🔴 Checking Redis connectivity..."
    
    if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
        log "✅ Redis connection: OK"
        
        # Check Redis memory usage
        local redis_memory=$(docker-compose exec -T redis redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
        log "📊 Redis memory usage: $redis_memory"
        
        return 0
    else
        log "❌ Redis connection: FAILED"
        send_telegram_alert "Redis connection failed"
        return 1
    fi
}

# Function to check Celery workers
check_celery() {
    log "⚙️  Checking Celery workers..."
    
    local active_workers=$(docker-compose exec -T celery celery -A gpw_advisor inspect active | grep -c "gpw_advisor" || echo "0")
    
    if [ "$active_workers" -gt 0 ]; then
        log "✅ Celery workers: $active_workers active"
        return 0
    else
        log "❌ Celery workers: No active workers found"
        send_telegram_alert "No active Celery workers found"
        return 1
    fi
}

# Function to check log file sizes
check_log_sizes() {
    log "📋 Checking log file sizes..."
    
    local logs_dir="logs"
    if [ -d "$logs_dir" ]; then
        find "$logs_dir" -name "*.log" -size +100M -exec ls -lh {} \; | while read -r line; do
            log "⚠️  Large log file: $line"
        done
    fi
}

# Function to cleanup old logs
cleanup_logs() {
    log "🧹 Cleaning up old logs..."
    
    # Remove logs older than 30 days
    find logs -name "*.log" -mtime +30 -delete 2>/dev/null || true
    
    # Rotate large log files
    find logs -name "*.log" -size +50M -exec mv {} {}.old \; -exec touch {} \; 2>/dev/null || true
    
    log "✅ Log cleanup completed"
}

# Function to generate system report
generate_report() {
    log "📊 Generating system report..."
    
    local report_file="logs/system-report-$(date +%Y-%m-%d_%H-%M-%S).txt"
    
    {
        echo "GPW Trading Advisor System Report"
        echo "Generated: $(date)"
        echo "=================================="
        echo
        
        echo "Docker Containers:"
        docker-compose ps
        echo
        
        echo "System Resources:"
        echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')"
        echo "Memory Usage:"
        free -h
        echo
        echo "Disk Usage:"
        df -h
        echo
        
        echo "Application Health:"
        curl -s "$HEALTH_URL" | jq . 2>/dev/null || echo "Health check failed"
        echo
        
        echo "Recent Logs (last 20 lines):"
        tail -20 "$LOG_FILE"
        
    } > "$report_file"
    
    log "📄 System report generated: $report_file"
}

# Function to perform full health check
health_check() {
    log "🔍 Starting comprehensive health check..."
    
    local issues=0
    
    check_app_health || ((issues++))
    check_containers || ((issues++))
    check_database || ((issues++))
    check_redis || ((issues++))
    check_celery || ((issues++))
    check_system_resources
    check_log_sizes
    
    if [ "$issues" -eq 0 ]; then
        log "✅ All health checks passed"
    else
        log "❌ $issues health check(s) failed"
        send_telegram_alert "$issues health check(s) failed - please investigate"
    fi
    
    return $issues
}

# Function to restart unhealthy services
auto_restart() {
    log "🔄 Checking for services that need restart..."
    
    if ! check_app_health; then
        log "🔄 Restarting web service..."
        docker-compose restart web
        sleep 10
        
        if check_app_health; then
            log "✅ Web service restarted successfully"
            send_telegram_alert "Web service was automatically restarted and is now healthy"
        else
            log "❌ Web service restart failed"
            send_telegram_alert "Web service restart failed - manual intervention required"
        fi
    fi
}

# Main function
main() {
    case "${1:-health-check}" in
        "health-check"|"check")
            health_check
            ;;
        "monitor")
            # Continuous monitoring mode
            while true; do
                health_check
                sleep 300  # Check every 5 minutes
            done
            ;;
        "restart")
            auto_restart
            ;;
        "report")
            generate_report
            ;;
        "cleanup")
            cleanup_logs
            ;;
        "alert")
            send_telegram_alert "${2:-Test alert}"
            ;;
        *)
            echo "Usage: $0 {health-check|monitor|restart|report|cleanup|alert [message]}"
            echo
            echo "Commands:"
            echo "  health-check  - Run comprehensive health check (default)"
            echo "  monitor       - Run continuous monitoring (every 5 minutes)"
            echo "  restart       - Auto-restart unhealthy services"
            echo "  report        - Generate system report"
            echo "  cleanup       - Clean up old log files"
            echo "  alert         - Send test alert"
            echo
            echo "Examples:"
            echo "  $0 health-check"
            echo "  $0 monitor"
            echo "  $0 alert 'System maintenance starting'"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
