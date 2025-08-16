# Plan Implementacji Funkcji Długoterminowych Inwestycji

## Cele Projektu

1. **Zachowanie istniejącej funkcjonalności**: Wszystkie obecne funkcje tradingu krótkookresowego muszą pozostać niezmienione
2. **Dodanie analizy długoterminowej**: Nowy moduł dla inwestycji długoterminowych (tygodnie/miesiące/lata)
3. **Dualna architektura**: Użytkownik może wybrać między tradingiem dziennym a inwestycjami długoterminowymi
4. **Różne strategie analizy**: Inne wskaźniki i podejścia dla długoterminowych inwestycji

## Analiza Obecnej Architektury

### Modele Kluczowe
- `TradingSignal` - sygnały handlowe (buy/sell/hold/watch)
- `UserTradingPreferences` - preferencje handlowe użytkownika
- `TimeWeightConfiguration` - konfiguracja stylów handlowych
- `MarketAnalysis` - analiza rynku dla sesji handlowych
- `PredictionResult` - predykcje ML dla krótkiego okresu

### Obecne Style Handlowe
- `intraday` - handel wewnątrzdniowy
- `swing` - swing trading (dni/tygodnie)
- `position` - pozycje pozycyjne

### Ograniczenia Obecnego Systemu
1. Focus na handel dzienny/tygodniowy
2. Brak analizy fundamentalnej dla długoterminowych inwestycji
3. Brak osobnych preferencji dla inwestycji długoterminowych
4. Brak modeli dla rekomendacji portfelowych

## Plan Implementacji

### Faza 1: Rozszerzenie Modeli Użytkownika

#### 1.1 Dodanie Investment Preferences
```python
class UserInvestmentPreferences(SoftDeleteModel):
    user = models.OneToOneField(User, related_name='investment_preferences')
    
    # Investment Horizon
    investment_horizon_months = models.IntegerField(default=12)  # 1-5 lat
    
    # Risk Profile
    risk_tolerance = models.CharField(choices=[
        ('conservative', 'Conservative'),
        ('moderate', 'Moderate'), 
        ('aggressive', 'Aggressive')
    ])
    
    # Financial Goals
    target_annual_return_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_drawdown_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Asset Allocation Preferences
    max_single_stock_percentage = models.DecimalField(default=10.0)
    preferred_sectors = models.JSONField(default=list)
    diversification_preference = models.CharField(...)
    
    # ESG Preferences
    esg_focus = models.BooleanField(default=False)
    exclude_tobacco = models.BooleanField(default=False)
    exclude_gambling = models.BooleanField(default=False)
```

#### 1.2 User Profile Extension
```python
# Rozszerzenie User model
investment_mode_enabled = models.BooleanField(default=False)
primary_mode = models.CharField(choices=[
    ('trading', 'Daily Trading'),
    ('investing', 'Long-term Investing'),
    ('hybrid', 'Both')
], default='trading')
```

### Faza 2: Nowe Modele Analityczne

#### 2.1 Investment Recommendation
```python
class InvestmentRecommendation(SoftDeleteModel):
    RECOMMENDATION_TYPES = [
        ('buy', 'Buy'),
        ('hold', 'Hold'), 
        ('sell', 'Sell'),
        ('avoid', 'Avoid')
    ]
    
    user = models.ForeignKey(User, related_name='investment_recommendations')
    stock = models.ForeignKey(StockSymbol)
    recommendation_type = models.CharField(choices=RECOMMENDATION_TYPES)
    
    # Long-term Analysis
    target_price_12m = models.DecimalField(...)
    target_price_24m = models.DecimalField(...)
    confidence_score = models.FloatField()
    
    # Fundamental Analysis
    pe_analysis = models.JSONField()
    revenue_growth_analysis = models.JSONField()
    debt_analysis = models.JSONField()
    dividend_analysis = models.JSONField()
    
    # Technical Long-term
    trend_analysis = models.JSONField()
    support_resistance_levels = models.JSONField()
    
    # Risk Assessment
    volatility_score = models.FloatField()
    beta_coefficient = models.FloatField()
    sector_risk_score = models.FloatField()
```

#### 2.2 Portfolio Analysis
```python
class PortfolioAnalysis(SoftDeleteModel):
    user = models.ForeignKey(User, related_name='portfolio_analyses')
    analysis_date = models.DateField()
    
    # Current Portfolio State
    total_value = models.DecimalField()
    cash_percentage = models.DecimalField()
    stock_allocations = models.JSONField()  # {symbol: percentage}
    sector_allocations = models.JSONField()
    
    # Performance Metrics
    ytd_return = models.DecimalField()
    annual_volatility = models.DecimalField()
    sharpe_ratio = models.DecimalField()
    max_drawdown = models.DecimalField()
    
    # Risk Metrics
    portfolio_beta = models.DecimalField()
    diversification_score = models.FloatField()
    concentration_risk = models.FloatField()
    
    # Recommendations
    rebalancing_suggestions = models.JSONField()
    new_positions_suggested = models.JSONField()
    positions_to_reduce = models.JSONField()
```

### Faza 3: Logika Biznesowa

#### 3.1 Investment Analysis Engine
```python
class InvestmentAnalysisEngine:
    def analyze_for_long_term(self, stock: StockSymbol, user_preferences: UserInvestmentPreferences):
        # Fundamental Analysis
        # Technical Analysis (long-term)
        # Valuation Models
        # Risk Assessment
        # Generate Investment Recommendation
        
    def portfolio_optimization(self, user: User):
        # Modern Portfolio Theory
        # Asset Allocation
        # Diversification Analysis
        # Rebalancing Recommendations
```

#### 3.2 Dual Mode Management
```python
class TradingModeManager:
    def get_user_active_mode(self, user: User) -> str:
        # Return 'trading', 'investing', or 'hybrid'
        
    def get_relevant_signals(self, user: User):
        mode = self.get_user_active_mode(user)
        if mode == 'trading':
            return TradingSignal.objects.filter(user=user)
        elif mode == 'investing': 
            return InvestmentRecommendation.objects.filter(user=user)
        else:  # hybrid
            return both
```

### Faza 4: Interface Użytkownika

#### 4.1 Mode Selector
- Dashboard toggle: Trading vs Investment mode
- Hybrid view showing both
- Separate navigation sections

#### 4.2 Investment Dashboard
- Portfolio overview
- Long-term recommendations
- Performance tracking
- Rebalancing alerts

#### 4.3 Investment Preferences
- Risk tolerance questionnaire
- Investment goals setup
- Asset allocation preferences
- ESG preferences

### Faza 5: Integracja z Istniejącym Systemem

#### 5.1 Notification System
- Extend dla investment recommendations
- Different frequencies (monthly/quarterly)
- Portfolio rebalancing alerts

#### 5.2 Data Pipeline
- Long-term data collection
- Fundamental data integration
- Economic indicators

## Harmonogram Implementacji

### Week 1-2: Core Models
- [ ] UserInvestmentPreferences model
- [ ] InvestmentRecommendation model
- [ ] PortfolioAnalysis model
- [ ] Database migrations

### Week 3-4: Analysis Engine
- [ ] Investment analysis algorithms
- [ ] Portfolio optimization logic
- [ ] Fundamental analysis integration
- [ ] Long-term technical analysis

### Week 5-6: User Interface
- [ ] Mode selector
- [ ] Investment dashboard
- [ ] Investment preferences forms
- [ ] Portfolio analysis views

### Week 7-8: Integration & Testing
- [ ] Notification system integration
- [ ] Data pipeline setup
- [ ] Testing both modes
- [ ] Performance optimization

## Todo List

- [x] Analyze existing UserTradingPreferences model structure
- [x] Design UserInvestmentPreferences model
- [x] Create InvestmentRecommendation model
- [x] Create PortfolioAnalysis model
- [x] Implement dual mode system in User model
- [x] Create database migrations for new models
- [x] Create InvestmentPreferencesForm
- [x] Create ModeSelectionForm
- [x] Create investment preference views
- [x] Create mode selection view
- [x] Create investment summary view
- [x] Create investment wizard view
- [x] Create URL routing for new views
- [x] Create templates for new views
- [x] Add navigation links in base.html
- [ ] Create investment analysis engine
- [ ] Design investment dashboard UI
- [ ] Integrate with notification system
- [ ] Add investment-specific data collection
- [ ] Test entire system end-to-end
- [ ] Document new features

## Risk Mitigation

1. **Backward Compatibility**: All changes must be additive, no breaking changes
2. **Feature Flags**: Use feature flags to gradually roll out investment features
3. **Data Migration**: Careful migration of existing user preferences
4. **Testing**: Comprehensive testing of both trading and investment modes
5. **Performance**: Monitor performance impact of dual system
