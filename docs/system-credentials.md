# System Access Credentials & Configuration

## Database Access
**PostgreSQL Database:**
- **Host:** localhost
- **Port:** 5432
- **Database Name:** gpw_advisor
- **Username:** postgres
- **Password:** 123postgreS
- **Database Version:** PostgreSQL 17

## Django Admin Access
**Superuser Account:**
- **Username:** admin
- **Email:** admin@gpw.com
- **Password:** 123 (simplified password with validation bypass)
- **Admin URL:** http://localhost:8000/admin/

## Environment Configuration
**Development Server:**
- **Host:** localhost
- **Port:** 8000 (default Django)
- **Debug Mode:** Enabled
- **Environment File:** `.env` in project root

## Application Structure
**Django Project:** gpw_advisor
**Active Apps:**
- core (StockSymbol, TradingSession models)
- users (User, Subscription, NotificationPreferences models)
- scrapers (ScrapingSource, ScrapingJob, StockData models)
- analysis (TechnicalIndicator, TradingSignal models)
- notifications (NotificationChannel, UserNotification models)
- tracking (Portfolio, PerformanceMetric models)
- dashboard (DashboardWidget, UserDashboard models)

## Security Notes
- All passwords are development-only credentials
- SECRET_KEY is development key (change for production)
- DEBUG=True (disable for production)
- Default admin password bypasses Django validation (acceptable for development)

## Database Status
- ✅ Database created successfully
- ✅ All migrations applied
- ✅ Admin interface configured
- ✅ All 22 models implemented across 7 apps

## Next Steps Required
1. Start development server (`python manage.py runserver`)
2. Configure Telegram Bot token when ready
3. Set up Redis for Celery tasks
4. Implement web scraping functionality
5. Create initial stock symbols and trading sessions

## Important File Locations
- **Project Root:** `/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2/`
- **Settings:** `gpw_advisor/settings.py`
- **Environment:** `.env`
- **Requirements:** `requirements.txt`
- **Memory Bank:** `memory-bank/` directory

---
*Last Updated: July 21, 2025*
*Created during initial system setup phase*
