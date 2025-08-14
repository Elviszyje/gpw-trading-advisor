# Contributing to GPW Trading Advisor

Dziękujemy za zainteresowanie współpracą z naszym projektem! 

## 🚀 Jak zacząć

1. **Fork repository**
2. **Clone swojego fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/gpw-trading-advisor.git
   cd gpw-trading-advisor
   ```
3. **Ustaw upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/gpw-trading-advisor.git
   ```

## 🔧 Development Setup

1. **Środowisko rozwojowe**:
   ```bash
   # Skopiuj przykładowy plik konfiguracyjny
   cp .env.example .env
   
   # Uruchom w trybie development
   make dev-start
   ```

2. **Pre-commit hooks** (opcjonalnie):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## 📝 Konwencje Kodowania

### Python
- **PEP 8** - standard kodowania Python
- **Type hints** - używaj tam gdzie to możliwe
- **Docstrings** - dokumentuj funkcje i klasy
- **Tests** - każda nowa funkcjonalność powinna mieć testy

Przykład:
```python
def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        prices: List of stock prices
        period: Period for RSI calculation (default: 14)
    
    Returns:
        RSI value as float
        
    Raises:
        ValueError: If prices list is empty or period is invalid
    """
    if not prices or period <= 0:
        raise ValueError("Invalid input parameters")
        
    # Implementation here...
    return rsi_value
```

### Django
- **Models**: Używaj verbose_name i help_text
- **Views**: Preferuj Class-Based Views
- **Templates**: Używaj template inheritance
- **URLs**: Używaj named URLs
- **Migrations**: Sprawdź migracje przed commitem

### Frontend
- **Bootstrap 5** - dla stylów
- **jQuery/Vanilla JS** - dla interaktywności
- **Chart.js** - dla wykresów
- **Responsive design** - mobile-first

## 🌟 Typy Contribucji

### 🐛 Bug Reports
Gdy zgłaszasz błąd, dołącz:
- **Kroki do reprodukcji**
- **Oczekiwane zachowanie**
- **Aktualne zachowanie**
- **Screenshoty** (jeśli dotyczy)
- **Informacje o środowisku** (OS, Python version, etc.)

### 💡 Feature Requests
Dla nowych funkcjonalności:
- **Opisz problem** który feature ma rozwiązać
- **Zaproponuj rozwiązanie**
- **Rozważ alternatywy**
- **Dodatkowy kontekst**

### 🔧 Code Contributions

#### Proces Pull Request
1. **Stwórz branch** z opisową nazwą:
   ```bash
   # Features
   git checkout -b feature/add-portfolio-analytics
   
   # Bug fixes  
   git checkout -b bugfix/fix-rsi-calculation
   
   # Hotfixes
   git checkout -b hotfix/security-vulnerability
   ```

2. **Commit messages** - używaj [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat: add portfolio performance analytics
   fix: correct RSI calculation for edge cases
   docs: update API documentation
   style: format code according to PEP 8
   refactor: extract common analysis functions
   test: add unit tests for portfolio module
   chore: update dependencies
   ```

3. **Testy**:
   ```bash
   # Uruchom wszystkie testy
   make test
   
   # Testy konkretnego modułu
   python manage.py test apps.analysis.tests
   
   # Coverage report
   make test-coverage
   ```

4. **Jakość kodu**:
   ```bash
   # Formatowanie
   make format
   
   # Linting
   make lint
   
   # Type checking
   make type-check
   ```

5. **Aktualizuj dokumentację** jeśli potrzeba

6. **Otwórz Pull Request** z:
   - **Opisowym tytułem**
   - **Szczegółowym opisem** zmian
   - **Lista zmian** (checklist)
   - **Screenshots** dla UI changes
   - **Breaking changes** jeśli występują

#### Pull Request Template
```markdown
## 🎯 Opis
<!-- Krótki opis tego co zmienia ten PR -->

## 🔧 Typ zmiany
- [ ] 🐛 Bug fix (non-breaking change)
- [ ] ✨ New feature (non-breaking change)  
- [ ] 💥 Breaking change (fix or feature causing existing functionality to not work)
- [ ] 📝 Documentation update
- [ ] 🔧 Refactoring
- [ ] ⚡ Performance improvement

## 🧪 Jak zostało przetestowane?
<!-- Opisz jak przetestowałeś swoje zmiany -->

## 📋 Checklist
- [ ] Kod jest zgodny z konwencjami projektu
- [ ] Przeprowadziłem samoocenę kodu
- [ ] Skomentowałem trudny do zrozumienia kod
- [ ] Zaktualizowałem dokumentację
- [ ] Moje zmiany nie generują nowych ostrzeżeń
- [ ] Dodałem testy pokrywające nowe funkcjonalności
- [ ] Wszystkie testy (nowe i istniejące) przechodzą
- [ ] Zmiany są backward compatible
```

## 🎨 Style Guidelines

### Database
- **Nazwy tabel**: snake_case, liczba pojedyncza
- **Nazwy kolumn**: snake_case, opisowe
- **Indeksy**: na często używanych kolumnach
- **Foreign keys**: `related_name` zawsze ustawiony

### API Design
- **REST principles**
- **Consistent naming** (snake_case dla JSON)
- **HTTP status codes** poprawnie używane
- **Error responses** w spójnym formacie
- **API versioning** przez URL (`/api/v1/`)

### Testing
- **Test coverage** > 80%
- **Unit tests** dla logiki biznesowej
- **Integration tests** dla API
- **Test names** opisowe (`test_should_return_error_when_invalid_symbol`)

## 🚀 Development Workflow

### 1. Lokalny development
```bash
# Pull latest changes
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes
# ... kod ...

# Test changes
make test
make lint

# Commit
git add .
git commit -m "feat: your feature description"

# Push to your fork  
git push origin feature/your-feature-name
```

### 2. Sync z upstream
```bash
# Fetch upstream changes
git fetch upstream

# Merge upstream changes
git checkout main
git merge upstream/main

# Rebase feature branch
git checkout feature/your-feature-name
git rebase main
```

## 🔍 Code Review Process

### Co sprawdzamy:
- **Funkcjonalność** - czy kod robi to co ma robić?
- **Wydajność** - czy nie ma wąskich gardeł?
- **Bezpieczeństwo** - czy nie ma luk bezpieczeństwa?
- **Testowalność** - czy kod jest łatwy do testowania?
- **Czytelność** - czy inni mogą łatwo zrozumieć kod?
- **Zgodność** - czy kod jest zgodny z konwencjami?

### Dla reviewerów:
- **Bądź konstruktywny** - sugeruj rozwiązania
- **Bądź konkretny** - podaj dokładne przykłady
- **Bądź uprzejmy** - pamiętaj że za kodem stoją ludzie
- **Sprawdź testy** - czy pokrywają edge cases?

## 🏷️ Labels i Assignments

### Priority Labels
- `priority/critical` - Błędy bezpieczeństwa, awarie produkcji
- `priority/high` - Istotne bugs, popularne features  
- `priority/medium` - Standardowe features, refactoring
- `priority/low` - Nice-to-have features, cleanup

### Type Labels
- `bug` - Coś nie działa
- `enhancement` - Nowa funkcjonalność
- `documentation` - Dokumentacja
- `good first issue` - Dobre dla początkujących
- `help wanted` - Szukamy pomocy

## 📞 Komunikacja

- **GitHub Issues** - główny kanał komunikacji
- **Pull Requests** - do dyskusji nad kodem
- **Wiki** - dla dokumentacji technicznej

## 🎉 Uznanie

Wszyscy kontrybutorzy będą:
- **Wymienieni** w README.md
- **Oznaczeni** w release notes
- **Zaproszeni** do team discussions

## ❓ Pytania?

Jeśli masz pytania, nie wahaj się:
- Otwórz **GitHub Issue** z pytaniem
- Sprawdź **existing discussions**
- Zobacz **project Wiki**

Dziękujemy za wkład w rozwój GPW Trading Advisor! 🚀
