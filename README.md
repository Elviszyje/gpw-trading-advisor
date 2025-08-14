# GPW Trading Advisor 📈

[![CI/CD Pipeline](https://github.com/YOUR_USERNAME/gpw-trading-advisor/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/YOUR_USERNAME/gpw-trading-advisor/actions/workflows/ci-cd.yml)
[![Security Scan](https://github.com/YOUR_USERNAME/gpw-trading-advisor/actions/workflows/dependencies.yml/badge.svg)](https://github.com/YOUR_USERNAME/gpw-trading-advisor/actions/workflows/dependencies.yml)
[![Docker](https://img.shields.io/docker/automated/your-dockerhub/gpw-advisor)](https://hub.docker.com/r/your-dockerhub/gpw-advisor)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Django](https://img.shields.io/badge/django-4.2-green.svg)](https://www.djangoproject.com/)

Inteligentny system doradztwa inwestycyjnego dla Giełdy Papierów Wartościowych w Warszawie (GPW).

## 🚀 Funkcjonalności

- **Analiza techniczna** - Wskaźniki techniczne (RSI, MACD, Bollinger Bands, SMA/EMA)
- **Analiza fundamentalna** - Ocena kondycji finansowej spółek
- **Rekomendacje inwestycyjne** - AI-powered doradztwo
- **Monitoring portfela** - Śledzenie inwestycji w czasie rzeczywistym
- **Powiadomienia Telegram** - Alerty o ważnych zdarzeniach rynkowych
- **Dashboard analityczny** - Wizualizacje i wykresy
- **API RESTful** - Integracja z zewnętrznymi systemami

## 🛠 Technologie

- **Backend**: Django 4.2, Django REST Framework
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Task Queue**: Celery + Redis
- **Frontend**: Bootstrap 5, Chart.js
- **Containerization**: Docker + Docker Compose
- **Web Scraping**: Selenium, BeautifulSoup4
- **Data Analysis**: pandas, numpy, yfinance
- **Monitoring**: Health checks, logging

## 📦 Szybki Start

### Wymagania
- Docker i Docker Compose
- Python 3.11+ (dla development bez Docker)
- Git

### 1. Klonowanie repository
```bash
git clone https://github.com/YOUR_USERNAME/gpw-trading-advisor.git
cd gpw-trading-advisor
```

### 2. Konfiguracja środowiska
```bash
# Skopiuj i dostosuj plik konfiguracyjny
cp .env.example .env

# Edytuj .env i ustaw swoje wartości:
# - SECRET_KEY
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID
# - API keys dla zewnętrznych serwisów
```

### 3. Uruchomienie z Docker (Zalecane)

#### Development
```bash
# Zbuduj i uruchom wszystkie serwisy
make dev-start

# Lub bezpośrednio:
docker-compose -f docker-compose.dev.yml up --build
```

#### Production
```bash
# Zbuduj i uruchom w trybie produkcyjnym
make prod-start

# Lub bezpośrednio:
docker-compose up --build -d
```

### 4. Inicjalizacja danych
```bash
# Aplikuj migracje i załaduj dane początkowe
make init-data

# Utwórz superuser'a
make create-superuser
```

### 5. Dostęp do aplikacji
- **Web Interface**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/api/docs/
- **Health Check**: http://localhost:8000/health/

## 🔧 Development

### Struktura projektu
```
gpw-trading-advisor/
├── apps/                    # Aplikacje Django
│   ├── core/               # Główna logika
│   ├── stocks/             # Zarządzanie akcjami
│   ├── analysis/           # Analiza techniczna/fundamentalna
│   ├── portfolio/          # Zarządzanie portfelem
│   └── notifications/      # System powiadomień
├── docker/                 # Konfiguracje Docker
├── scripts/               # Skrypty pomocnicze
├── static/                # Pliki statyczne
├── templates/             # Szablony HTML
├── .github/workflows/     # CI/CD GitHub Actions
└── requirements/          # Zależności Python
```

### Przydatne komendy
```bash
# Zobacz wszystkie dostępne komendy
make help

# Uruchom testy
make test

# Sprawdź jakość kodu
make lint

# Zbierz logi
make logs

# Backup bazy danych
make db-backup

# Restart serwisów
make restart
```

### API Endpoints
- `GET /api/stocks/` - Lista wszystkich akcji
- `GET /api/stocks/{symbol}/analysis/` - Analiza konkretnej akcji
- `GET /api/portfolio/` - Portfel użytkownika
- `POST /api/recommendations/` - Generuj rekomendacje
- `GET /api/health/` - Status systemu

## 🚢 Deployment

### Production Deployment
1. **Przygotowanie serwera**:
   ```bash
   # Zainstaluj Docker i Docker Compose
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Sklonuj repo
   git clone https://github.com/YOUR_USERNAME/gpw-trading-advisor.git
   cd gpw-trading-advisor
   ```

2. **Konfiguracja production**:
   ```bash
   # Skopiuj i dostosuj zmienne środowiskowe
   cp .env.example .env
   
   # Ustaw production values:
   # DEBUG=False
   # ALLOWED_HOSTS=your-domain.com
   # SECURE_SSL_REDIRECT=True
   # DATABASE_URL=postgresql://...
   ```

3. **Deploy**:
   ```bash
   # Uruchom w trybie produkcyjnym
   make prod-deploy
   
   # Lub:
   docker-compose up -d --build
   make init-prod-data
   ```

### CI/CD Pipeline
GitHub Actions automatycznie:
- Uruchamia testy przy każdym push/PR
- Skanuje pod kątem bezpieczeństwa
- Buduje obrazy Docker
- Deploy na production branch (main)

## 📊 Monitoring

### Health Checks
System posiada wbudowane health checks:
- Database connectivity
- Redis connectivity  
- External API availability
- Celery workers status

```bash
# Sprawdź status wszystkich serwisów
curl http://localhost:8000/health/

# Detailed health info
curl http://localhost:8000/health/detailed/
```

### Logs
```bash
# Zobacz logi aplikacji
make logs

# Logi konkretnego serwisu
docker-compose logs web
docker-compose logs celery
```

## 🔒 Bezpieczeństwo

- **HTTPS tylko** w produkcji
- **Rate limiting** na API endpoints
- **Input validation** i sanitization
- **SQL Injection protection** via Django ORM
- **XSS protection** via Django templates
- **CSRF protection** włączona
- **Security headers** via nginx
- **Secrets** w zmiennych środowiskowych

## 🤝 Współpraca

1. Fork repository
2. Stwórz feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push do branch (`git push origin feature/amazing-feature`)
5. Otwórz Pull Request

### Konwencje kodowania
- Python: PEP 8, isort, black
- Commit messages: Conventional Commits
- Branch naming: `feature/`, `bugfix/`, `hotfix/`

## 📝 Licencja

Ten projekt jest licencjonowany na podstawie MIT License - zobacz plik [LICENSE](LICENSE) dla szczegółów.

## 🆘 Wsparcie

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/gpw-trading-advisor/issues)
- **Wiki**: [Project Wiki](https://github.com/YOUR_USERNAME/gpw-trading-advisor/wiki)
- **Email**: your-email@example.com

## 📈 Roadmap

- [ ] **v1.1**: Machine Learning predictions
- [ ] **v1.2**: Mobile app (React Native)
- [ ] **v1.3**: Multi-market support (NASDAQ, DAX)
- [ ] **v1.4**: Social trading features
- [ ] **v2.0**: Advanced AI trading algorithms

---

**⚠️ Disclaimer**: Ten system jest narzędziem edukacyjnym i informacyjnym. Nie stanowi porady finansowej. Zawsze skonsultuj się z doradcą finansowym przed podejmowaniem decyzji inwestycyjnych.
