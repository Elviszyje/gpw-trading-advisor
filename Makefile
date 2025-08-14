# GPW Trading Advisor - Docker Management
.PHONY: help build up down logs restart clean test backup restore

# Default target
help: ## Show this help message
	@echo "GPW Trading Advisor - Docker Commands"
	@echo "===================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development commands
build: ## Build Docker images
	docker-compose build

up: ## Start development environment
	docker-compose -f docker-compose.dev.yml up -d

down: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

restart: ## Restart all services
	docker-compose restart

# Production commands
prod-build: ## Build production images
	docker-compose build --no-cache

prod-up: ## Start production environment
	docker-compose up -d

prod-logs: ## Show production logs
	docker-compose logs -f

# Database commands
migrate: ## Run Django migrations
	docker-compose exec web python manage.py migrate

makemigrations: ## Create Django migrations
	docker-compose exec web python manage.py makemigrations

shell: ## Open Django shell
	docker-compose exec web python manage.py shell

superuser: ## Create Django superuser
	docker-compose exec web python manage.py createsuperuser

# Maintenance commands
clean: ## Clean up Docker resources
	docker-compose down -v --remove-orphans
	docker system prune -f
	docker volume prune -f

clean-all: ## Clean up all Docker resources (DANGER: removes all containers/images)
	docker-compose down -v --remove-orphans
	docker system prune -af
	docker volume prune -f

# Database backup and restore
backup: ## Backup PostgreSQL database
	docker-compose exec db pg_dump -U gpw_user gpw_advisor_db > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore: ## Restore PostgreSQL database (specify file with FILE=backup.sql)
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=backup.sql"; exit 1; fi
	docker-compose exec -T db psql -U gpw_user gpw_advisor_db < $(FILE)

# Testing
test: ## Run tests
	docker-compose exec web python manage.py test

test-coverage: ## Run tests with coverage
	docker-compose exec web coverage run --source='.' manage.py test
	docker-compose exec web coverage report

# Static files
collectstatic: ## Collect static files
	docker-compose exec web python manage.py collectstatic --noinput

# Monitoring
status: ## Show container status
	docker-compose ps

stats: ## Show container resource usage
	docker stats

# Development helpers
dev-install: ## Install development dependencies
	docker-compose exec web pip install -r requirements.txt

dev-reset: ## Reset development environment
	make down
	make clean
	make build
	make up
	sleep 10
	make migrate
	make superuser

# Quick start
quick-start: ## Quick start for development
	@echo "🚀 Starting GPW Trading Advisor..."
	make build
	make up
	@echo "⏳ Waiting for services to start..."
	sleep 15
	make migrate
	@echo "✅ Application is ready at http://localhost:8000"
	@echo "📊 Admin panel: http://localhost:8000/admin"
	@echo "🔍 Use 'make logs' to see application logs"
