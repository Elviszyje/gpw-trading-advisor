# GPW Advisor - Quick Reference Guide

## 🚀 Co Mamy Obecnie

### ✅ **Działające Systemy**
1. **RSS News Scraping** - 6 źródeł, 18 artykułów
2. **Dual LLM Analysis** - OpenAI + OLLAMA 
3. **Granular Sentiment** - per branża/spółka
4. **Polish Market Data** - 3 rynki, 13 branż, 35+ spółek

### 🎯 **Kluczowe Commands**
```bash
# Pobierz nowe newsy
python manage.py scrape_news_rss

# Analizuj z OpenAI (szybko)
python manage.py analyze_news_ai --provider openai --limit 5

# Analizuj z OLLAMA (lokalnie) 
python manage.py analyze_news_ai --provider ollama --limit 2

# Sprawdź status LLM
python test_llm_setup.py

# Zobacz szczegóły analizy
python check_detailed_sentiments.py
```

### 📊 **Database Overview**
- **18 newsów** gotowych do analizy
- **3 przeanalizowane** z granularnym sentymentem
- **35+ spółek GPW** w bazie
- **13 branż** z keywords
- **2 LLM providery** skonfigurowane

## 🎯 **Następne Opcje**

### A. **Dashboard & Batch Analysis**
- Przeanalizuj wszystkie 18 artykułów
- Stwórz web interface
- Dodaj filtering po branżach/spółkach

### B. **Automation & Monitoring**  
- Automated scraping co 2-4h
- Email alerts przy high-impact news
- Health monitoring RSS feeds

### C. **More Data Sources**
- Puls Biznesu, Parkiet RSS
- ESPI reports integration
- Expand stock database

### D. **Price Correlation**
- Stock price tracking API
- Sentiment vs price analysis
- Performance metrics

**System jest production-ready i gotowy na każdy kierunek rozwoju!** 🚀

## 📁 **Lokalizacja Plików**
```
/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2/
├── apps/core/llm_service.py          # LLM analysis logic
├── apps/core/management/commands/    # Management commands
├── apps/news/models.py               # News article models
├── apps/scrapers/management/         # RSS scraping
└── docs/                            # Documentation
```
