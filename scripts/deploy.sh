#!/bin/bash
# scripts/deploy.sh - Production deployment script

set -e

echo "🚀 Starting GPW Trading Advisor deployment..."

# Configuration
PROJECT_NAME="gpw-trading-advisor"
BACKUP_DIR="backups/$(date +%Y-%m-%d_%H-%M-%S)"
LOG_FILE="/var/log/${PROJECT_NAME}/deploy.log"

# Create directories
mkdir -p logs backups

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check if service is healthy
check_service_health() {
    local service=$1
    local max_attempts=30
    local attempt=1
    
    log "Checking health of $service..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec $service sh -c 'exit 0' 2>/dev/null; then
            log "$service is healthy"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts - $service not ready yet..."
        sleep 5
        ((attempt++))
    done
    
    log "❌ $service failed to become healthy"
    return 1
}

# Function to run database backup
backup_database() {
    if docker-compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; then
        log "Creating database backup..."
        mkdir -p "$BACKUP_DIR"
        
        docker-compose exec -T db pg_dump \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            --clean --create --if-exists \
            > "$BACKUP_DIR/database.sql"
            
        log "Database backup created: $BACKUP_DIR/database.sql"
    else
        log "⚠️  Database not accessible, skipping backup"
    fi
}

# Function to restore from backup
restore_database() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        log "❌ Backup file not found: $backup_file"
        return 1
    fi
    
    log "Restoring database from $backup_file..."
    docker-compose exec -T db psql \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        < "$backup_file"
        
    log "Database restored successfully"
}

# Function to deploy application
deploy() {
    log "Starting deployment process..."
    
    # Pull latest changes
    log "Pulling latest code..."
    git pull origin main
    
    # Backup current state
    backup_database
    
    # Build new images
    log "Building Docker images..."
    docker-compose build --no-cache
    
    # Stop services gracefully
    log "Stopping services..."
    docker-compose down --remove-orphans
    
    # Start database first
    log "Starting database..."
    docker-compose up -d db redis
    
    # Wait for database to be ready
    check_service_health db
    check_service_health redis
    
    # Run migrations
    log "Running database migrations..."
    docker-compose run --rm web python manage.py migrate
    
    # Collect static files
    log "Collecting static files..."
    docker-compose run --rm web python manage.py collectstatic --noinput
    
    # Start all services
    log "Starting all services..."
    docker-compose up -d
    
    # Wait for services to be healthy
    check_service_health web
    
    # Run health check
    log "Running health check..."
    sleep 10
    
    if curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
        log "✅ Deployment successful! Application is healthy."
        
        # Clean up old images
        docker image prune -f
        
        # Show running services
        docker-compose ps
        
    else
        log "❌ Deployment failed - health check failed"
        log "Rolling back..."
        rollback
        return 1
    fi
}

# Function to rollback deployment
rollback() {
    log "🔄 Rolling back deployment..."
    
    # Stop current services
    docker-compose down
    
    # Find latest backup
    local latest_backup=$(find backups -name "database.sql" | sort | tail -1)
    
    if [ -n "$latest_backup" ]; then
        # Start database
        docker-compose up -d db redis
        check_service_health db
        
        # Restore from backup
        restore_database "$latest_backup"
        
        # Start services
        docker-compose up -d
        
        log "✅ Rollback completed"
    else
        log "❌ No backup found for rollback"
    fi
}

# Function to show status
status() {
    log "📊 System Status:"
    echo
    docker-compose ps
    echo
    
    if curl -s http://localhost:8000/health/ | jq . 2>/dev/null; then
        echo "✅ Application is healthy"
    else
        echo "❌ Application health check failed"
    fi
}

# Function to show logs
logs() {
    local service=${1:-""}
    if [ -n "$service" ]; then
        docker-compose logs --tail=100 -f "$service"
    else
        docker-compose logs --tail=100 -f
    fi
}

# Function to update system
update() {
    log "📦 Updating system..."
    
    # Update code
    git fetch origin
    local current_commit=$(git rev-parse HEAD)
    local latest_commit=$(git rev-parse origin/main)
    
    if [ "$current_commit" != "$latest_commit" ]; then
        log "New changes detected, deploying..."
        deploy
    else
        log "No updates available"
    fi
}

# Main script
case "${1:-}" in
    "deploy")
        deploy
        ;;
    "rollback")
        rollback
        ;;
    "status")
        status
        ;;
    "logs")
        logs "${2:-}"
        ;;
    "update")
        update
        ;;
    "backup")
        backup_database
        ;;
    "restore")
        restore_database "${2}"
        ;;
    *)
        echo "Usage: $0 {deploy|rollback|status|logs [service]|update|backup|restore <backup_file>}"
        echo
        echo "Commands:"
        echo "  deploy   - Deploy the application"
        echo "  rollback - Rollback to previous version"
        echo "  status   - Show system status"
        echo "  logs     - Show logs (optionally for specific service)"
        echo "  update   - Check for updates and deploy if needed"
        echo "  backup   - Create database backup"
        echo "  restore  - Restore from backup file"
        echo
        echo "Examples:"
        echo "  $0 deploy"
        echo "  $0 logs web"
        echo "  $0 restore backups/2024-01-15_10-30-00/database.sql"
        exit 1
        ;;
esac
