# System Automatyzacji Scraperów GPW2

## 🎯 Przegląd
Zaawansowany system harmonogramowania scraperów z konfigurowalnymi okresami czasowymi, wykrywaniem świąt i automatyczną analizą AI.

## 📋 Konfiguracja

### 1. Harmonogramy Domyślne

System zawiera 6 prekonfigurowanych harmonogramów:

#### News RSS
- **Market Hours**: Co 30min podczas godzin giełdowych (7:00-18:00, pon-pią)
- **Off Hours**: Co 2h poza godzinami giełdowymi (18:01-6:59, codziennie)

#### Stock Prices
- **Live Trading**: Co 5min podczas sesji (9:00-17:30, pon-pią)
- **EOD Update**: Codziennie po zamknięciu (18:00-19:00, pon-pią)

#### Calendar Events
- **Daily**: Codziennie rano (7:00-8:00, pon-pią)

#### ESPI Reports
- **Business Hours**: Co 2h w godzinach biznesowych (8:00-18:00, pon-pią)

### 2. Inteligentne Funkcje

✅ **Session-aware timing** - automatyczne dostosowanie do godzin giełdowych
✅ **Holiday detection** - pomijanie polskich świąt państwowych
✅ **Weekend handling** - konfigurowalne działanie w weekendy
✅ **Auto AI analysis** - automatyczna analiza nowych artykułów
✅ **Execution tracking** - pełne logowanie wykonań z metrykami
✅ **Error handling** - obsługa błędów bez przerywania innych harmonogramów

## 🚀 Uruchomienie

### Setup (jednorazowy)
```bash
# Utworzenie domyślnych harmonogramów
python manage.py setup_scraping_schedules

# Lub reset istniejących
python manage.py setup_scraping_schedules --reset
```

### Uruchamianie
```bash
# Sprawdzenie statusu
python manage.py run_scheduled_scrapers --status

# Uruchomienie wszystkich należnych zadań
python manage.py run_scheduled_scrapers

# Uruchomienie konkretnego typu
python manage.py run_scheduled_scrapers --type news_rss
python manage.py run_scheduled_scrapers --type stock_prices
python manage.py run_scheduled_scrapers --type calendar_events

# Uruchomienie konkretnego harmonogramu
python manage.py run_scheduled_scrapers --id 1
```

## � Przepływ Danych

### News Articles Processing Pipeline

```
1. 📰 SCRAPING PHASE (Batch)
   ├── RSS feeds fetched
   ├── Articles parsed & saved to database
   └── All articles stored with source references

2. 🤖 AI ANALYSIS PHASE (Incremental Batch)
   ├── Query: ai_classification__isnull=True
   ├── Process max 5 articles per session
   ├── Generate sentiment & industry analysis
   ├── Save analysis results to database
   └── Mark articles as analyzed

3. 🔁 CONTINUOUS PROCESSING
   ├── Next scraper run: new articles → database
   ├── Next AI session: analyze remaining 5 articles
   └── Repeat until all articles analyzed
```

**Kluczowe zalety:**
- ✅ **Oddzielone fazy** - scraping nie czeka na AI
- ✅ **Incremental** - każda sesja analizuje kolejną część
- ✅ **Fault tolerant** - błąd jednego artykułu nie blokuje innych
- ✅ **Performance aware** - limit 5 artykułów chroni przed timeout

### Crontab (zalecane)
```bash
# Dodaj do crontaba (crontab -e):
# Uruchamianie co 5 minut
*/5 * * * * cd /path/to/GPW2 && python manage.py run_scheduled_scrapers >> /var/log/scraping.log 2>&1

# Sprawdzanie statusu raz dziennie o 6:00
0 6 * * * cd /path/to/GPW2 && python manage.py run_scheduled_scrapers --status >> /var/log/scraping-status.log 2>&1
```

### Systemd Service
```ini
[Unit]
Description=GPW2 Scraping Scheduler
After=network.target

[Service]
Type=simple
User=gpw2
WorkingDirectory=/path/to/GPW2
ExecStart=/path/to/GPW2/venv/bin/python manage.py run_scheduled_scrapers --daemon
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
```

## 📊 Monitoring

### Status Check
```bash
python manage.py run_scheduled_scrapers --status
```

Pokazuje:
- Liczbę aktywnych harmonogramów
- Liczbę należnych zadań
- Ostatnie wykonania
- Następne zaplanowane uruchomienia

### Logi Wykonań
```python
# Django shell
from apps.core.models import ScrapingExecution
recent = ScrapingExecution.objects.all()[:10]
for exec in recent:
    print(f"{exec} - Duration: {exec.duration}s")
```

## ⚙️ Konfiguracja Harmonogramów

### Model: ScrapingSchedule

Każdy harmonogram ma:
- **Częstotliwość**: minuty, godziny, dni
- **Godziny aktywności**: start/stop (np. 9:00-17:30)
- **Dni tygodnia**: pon-nie (osobno konfigurowalne)
- **Wykrywanie świąt**: automatyczne pomijanie polskich świąt
- **Konfiguracja scrapera**: JSON z parametrami

### Przykład Tworzenia Custom Schedule

```python
from apps.core.models import ScrapingSchedule
from datetime import time

schedule = ScrapingSchedule.objects.create(
    name="Custom News - Frequent",
    scraper_type='news_rss',
    frequency_value=15,
    frequency_unit='minutes',
    active_hours_start=time(8, 0),
    active_hours_end=time(20, 0),
    monday=True,
    tuesday=True,
    wednesday=True,
    thursday=True,
    friday=True,
    saturday=False,
    sunday=False,
    scraper_config={
        'auto_analyze': True,
        'max_articles_per_run': 50
    }
)
schedule.calculate_next_run()
```

## 🎛️ Panel Administracyjny

Harmonogramy są dostępne w Django Admin pod `/admin/core/scrapingschedule/`:

- **Podgląd**: Status, następne uruchomienie, statystyki
- **Edycja**: Zmiana częstotliwości, godzin, dni
- **Aktywacja/Deaktywacja**: Łatwe włączanie/wyłączanie
- **Historia**: Logi wszystkich wykonań

## 🚨 Rozwiązywanie Problemów

### Schedule nie uruchamia się
```bash
# Sprawdź czy jest aktywny
python manage.py shell -c "
from apps.core.models import ScrapingSchedule
schedule = ScrapingSchedule.objects.get(name='Nazwa Schedule')
print(f'Active: {schedule.is_active}')
print(f'Next run: {schedule.next_run}')
print(f'Should run now: {schedule.should_run_now()}')
"
```

### Błędy wykonania
```bash
# Sprawdź ostatnie błędy
python manage.py shell -c "
from apps.core.models import ScrapingExecution
failed = ScrapingExecution.objects.filter(success=False)[:5]
for exec in failed:
    print(f'{exec.schedule.name}: {exec.error_message}')
"
```

### Reset harmonogramów
```bash
# Usuń wszystkie i utwórz ponownie
python manage.py setup_scraping_schedules --reset
```

## 📈 Metryki

System automatycznie zbiera:
- **Czas wykonania** (duration)
- **Przetworzone elementy** (items_processed)
- **Utworzone elementy** (items_created)
- **Zaktualizowane elementy** (items_updated)
- **Komunikaty błędów** (error_message)
- **Szczegóły wykonania** (execution_details)

## 🔮 Funkcje Zaawansowane

### Automatyczna Analiza AI
- **Inteligentny przepływ**: Najpierw batch scrapingu artykułów, potem batch analizy AI
- **Incremental processing**: Analizuje tylko nieanalyzowane artykuły (`ai_classification__isnull=True`)
- **Performance limit**: Maksymalnie 5 artykułów na sesję analizy
- **Continuous processing**: Każde uruchomienie analizuje kolejną część nieanalyzowanych
- **Graceful errors**: Błędy analizy nie przerywają procesu dla innych artykułów
- **Market hours awareness**: Auto-analiza tylko podczas godzin giełdowych (config: `auto_analyze: true`)
- **Off-hours mode**: Poza godzinami giełdowymi scraping bez auto-analizy (config: `auto_analyze: false`)

### Wykrywanie Świąt
- Automatycznie pomija polskie święta państwowe
- Konfigurowalne przez `respect_holidays=True/False`
- Można dodać custom dni wolne w metodzie `is_polish_holiday()`

### Session-aware Scheduling
- Automatycznie dostosowuje się do godzin giełdowych
- Różne częstotliwości dla różnych pór dnia
- Inteligentne calculation next_run uwzględniając weekendy

---

## ✅ Podsumowanie Implementacji

System automatyzacji scraperów jest w pełni gotowy do produkcji z:

1. ✅ **6 prekonfigurowanych harmonogramów** z inteligentnymi interwałami
2. ✅ **Pełna automatyzacja** z session-aware timing i holiday detection
3. ✅ **Management commands** do kontroli i monitoringu
4. ✅ **Execution tracking** z metrykami i logowaniem błędów
5. ✅ **Automatyczna analiza AI** nowych artykułów
6. ✅ **Gotowe do produkcji** z instrukcjami crontab i systemd

Konfiguracja: **5min** | Uruchomienie: **1 command** | Monitoring: **Built-in**
