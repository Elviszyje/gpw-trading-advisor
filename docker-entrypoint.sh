#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting GPW Trading Advisor${NC}"

# Wait for PostgreSQL
echo -e "${YELLOW}⏳ Waiting for PostgreSQL...${NC}"
until pg_isready -h ${DATABASE_HOST} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER}; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo -e "${GREEN}✅ PostgreSQL is ready!${NC}"

# Wait for Redis (using Python instead of redis-cli)
echo -e "${YELLOW}⏳ Waiting for Redis...${NC}"
until python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); r.ping()"; do
  echo "Redis is unavailable - sleeping"
  sleep 2
done
echo -e "${GREEN}✅ Redis is ready!${NC}"

# Run migrations
echo -e "${YELLOW}📦 Running database migrations...${NC}"
python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo -e "${YELLOW}👤 Creating superuser if needed...${NC}"
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123');
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
"

# Collect static files
echo -e "${YELLOW}📁 Collecting static files...${NC}"
python manage.py collectstatic --noinput

# Load initial data if needed
echo -e "${YELLOW}🔧 Setting up initial data...${NC}"
python manage.py shell -c "
from apps.core.models import StockSymbol
if not StockSymbol.objects.exists():
    # Add some default stocks
    stocks = [
        {'symbol': 'PKO', 'name': 'Bank PKO BP', 'sector': 'Banking'},
        {'symbol': 'ALE', 'name': 'Allegro', 'sector': 'Technology'},
        {'symbol': 'CDR', 'name': 'CD Projekt', 'sector': 'Technology'},
        {'symbol': '11B', 'name': '11 Bit Studio', 'sector': 'Technology'},
        {'symbol': 'JSW', 'name': 'Jastrzębska Spółka Węglowa', 'sector': 'Mining'},
    ]
    for stock_data in stocks:
        StockSymbol.objects.create(**stock_data, is_monitored=True)
    print('Initial stock data loaded')
else:
    print('Stock data already exists')
"

echo -e "${GREEN}✅ Setup complete! Starting application...${NC}"

# Execute the main command
exec "$@"
