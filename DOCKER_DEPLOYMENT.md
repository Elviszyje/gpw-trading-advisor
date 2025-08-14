# 🚀 GPW Trading Advisor - Docker Deployment Guide

Advanced stock trading platform with automated signal generation, real-time monitoring, and intelligent notifications.

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose V2
- At least 2GB RAM
- 5GB disk space

## ⚡ Quick Start

### Development Environment
```bash
# Clone and start development environment
git clone <repository>
cd GPW2
make quick-start
```

### Production Environment
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your production settings

# Start production services
make prod-build
make prod-up
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │◄──►│     Django      │◄──►│   PostgreSQL    │
│  (Reverse Proxy)│    │   (Web App)     │    │   (Database)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Celery Worker  │◄──►│      Redis      │◄──►│  Celery Beat    │
│   (Background)  │    │    (Cache)      │    │  (Scheduler)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Critical settings to change for production:
SECRET_KEY=your-very-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,localhost
DB_PASSWORD=secure-database-password
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
```

### Services
- **Web**: Django application (Port 8000)
- **Database**: PostgreSQL 15 (Port 5432)  
- **Cache**: Redis 7 (Port 6379)
- **Proxy**: Nginx (Ports 80/443)
- **Workers**: Celery for background tasks

## 🛠️ Management Commands

### Development
```bash
make build          # Build images
make up             # Start development
make logs           # View logs
make shell          # Django shell
make migrate        # Run migrations
make test           # Run tests
```

### Production
```bash
make prod-build     # Build production images
make prod-up        # Start production
make backup         # Database backup
make clean          # Cleanup resources
```

## 📊 Monitoring & Health Checks

### Health Endpoints
- `/health/` - Comprehensive health check
- `/health/live/` - Liveness probe
- `/health/ready/` - Readiness probe

### Monitoring Commands
```bash
make status         # Container status
make stats          # Resource usage
docker-compose logs -f web  # Application logs
```

## 🔄 Database Management

### Migrations
```bash
make makemigrations  # Create migrations
make migrate         # Apply migrations
```

### Backup & Restore
```bash
make backup                    # Create backup
make restore FILE=backup.sql   # Restore from backup
```

## 🔐 Security Considerations

### Production Security Checklist
- [ ] Change default SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configure proper ALLOWED_HOSTS
- [ ] Use strong database passwords
- [ ] Enable SSL certificates (uncomment HTTPS in nginx/default.conf)
- [ ] Configure firewall rules
- [ ] Regular security updates

### SSL Setup
1. Obtain SSL certificates (Let's Encrypt recommended)
2. Place certificates in `ssl/` directory
3. Uncomment HTTPS server block in `nginx/default.conf`
4. Update SECURE_SSL_REDIRECT=True in .env

## 🚨 Troubleshooting

### Common Issues

**Container won't start:**
```bash
make logs           # Check logs
make clean          # Clean resources
make build          # Rebuild
```

**Database connection failed:**
```bash
docker-compose exec db pg_isready -U gpw_user
make migrate        # Ensure migrations
```

**Static files not loading:**
```bash
make collectstatic  # Collect static files
docker-compose restart nginx
```

### Performance Tuning

**For High-Traffic Production:**
```yaml
# In docker-compose.yml, adjust:
web:
  deploy:
    replicas: 3       # Multiple web instances
    resources:
      limits:
        cpus: '2.0'
        memory: 2G

celery:
  command: celery -A gpw_advisor worker --concurrency=4
```

## 📈 Scaling

### Horizontal Scaling
- Use Docker Swarm or Kubernetes
- Add load balancer (HAProxy/AWS ALB)
- Database read replicas
- Redis cluster

### Monitoring Stack
```bash
# Add to docker-compose.yml:
# - Prometheus (metrics)
# - Grafana (dashboards) 
# - ELK Stack (logging)
```

## 🔄 CI/CD Integration

### GitHub Actions Example
```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to production
        run: |
          make prod-build
          make prod-up
```

## 📞 Support

### Logs Location
- Application: `logs/`
- Nginx: `/var/log/nginx/`
- PostgreSQL: Docker container logs

### Debug Mode
```bash
# Enable debug temporarily
docker-compose exec web python manage.py shell
# Check settings, run diagnostics
```

### Getting Help
1. Check logs: `make logs`
2. Verify health: `curl http://localhost:8000/health/`
3. Review configuration: `.env` and `docker-compose.yml`

---

## 🎯 Next Steps After Deployment

1. **Configure Telegram Bot** - Add bot token to receive notifications
2. **Set Trading Hours** - Configure market hours for your timezone
3. **Add Stocks** - Populate stock symbols for monitoring
4. **Schedule Tasks** - Set up periodic data collection
5. **Monitor Health** - Set up alerting for service health

For detailed configuration and usage, see the main project documentation.
