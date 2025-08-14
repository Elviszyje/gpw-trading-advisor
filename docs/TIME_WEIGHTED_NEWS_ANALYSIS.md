# Time-Weighted News Analysis System for Intraday Trading

## 🎯 Overview

This system adds sophisticated time-weighted news analysis to the GPW Trading Advisor, where recent news gets higher impact scores for intraday trading decisions. The system addresses the critical need for **real-time sentiment analysis** where news from different time periods has dramatically different impact on intraday trading decisions.

## 🔧 Key Features

### ⏰ Time-Weighted Impact Calculation
- **Exponential Decay**: News impact decays exponentially with configurable half-life (default: 120 minutes)
- **Time Period Weights**: Different weights for various time periods:
  - Last 15 minutes: **40%** weight (most critical for intraday)
  - Last 1 hour: **30%** weight
  - Last 4 hours: **20%** weight  
  - Earlier today: **10%** weight

### 🔥 Market Timing Multipliers
- **Market Hours (9:00-17:30)**: 1.5x multiplier
- **Pre-market (7:00-9:00)**: 1.2x multiplier
- **Breaking News**: 2.0x multiplier for high-impact news
- **After Hours**: 1.0x multiplier

### 📊 Multiple Trading Configurations
- **Intraday Aggressive**: 90-minute half-life, 50% weight for last 15min, 2.5x breaking news multiplier
- **Intraday Default**: 120-minute half-life, balanced weights, 2.0x breaking news multiplier
- **Intraday Conservative**: 180-minute half-life, more distributed weights, 1.5x breaking news multiplier
- **Swing Trading**: 720-minute half-life, longer-term focus

## 🏛️ Architecture

### Database Models

#### `TimeWeightConfiguration`
```python
- name: str (unique configuration name)
- trading_style: str (intraday/swing/position)
- half_life_minutes: int (exponential decay parameter)
- last_15min_weight: float (0.0-1.0)
- last_1hour_weight: float (0.0-1.0) 
- last_4hour_weight: float (0.0-1.0)
- today_weight: float (0.0-1.0)
- breaking_news_multiplier: float
- market_hours_multiplier: float
- pre_market_multiplier: float
- min_impact_threshold: float
```

### Core Components

#### `NewsTimeWeightAnalyzer`
Main analysis engine that:
- Calculates exponential time decay weights
- Applies market timing multipliers
- Computes weighted sentiment scores
- Generates trading signals based on news sentiment

#### `EnhancedDailyTradingSignalGenerator` 
Extends the base trading signal generator to integrate news analysis:
- Combines technical analysis with news sentiment
- Modifies signal confidence based on news impact
- Handles signal conflicts (positive news vs sell signals)
- Provides comprehensive reasoning for signal changes

## 📈 Signal Enhancement Logic

### Signal Modification Rules

1. **Positive News + Sell Signal**:
   - Strong positive news (>0.3): Convert SELL → HOLD, reduce confidence 30%
   - Moderate positive news: Reduce sell confidence proportionally

2. **Negative News + Buy Signal**:
   - Strong negative news (<-0.3): Convert BUY → HOLD, reduce confidence 30% 
   - Moderate negative news: Reduce buy confidence proportionally

3. **Strong News + Hold Signal**:
   - Positive news >0.3 + confidence >0.6: HOLD → BUY
   - Negative news <-0.3 + confidence >0.6: HOLD → SELL

4. **Reinforcement**:
   - Positive news + buy signal: Boost confidence up to 20%
   - Negative news + sell signal: Boost confidence up to 20%

### Momentum Analysis
- Compares recent news (last 2 hours) vs older news (2+ hours ago)
- Positive momentum: Recent sentiment > Older sentiment  
- Applied as additional confidence modifier

## 🚀 Usage Examples

### Setup Default Configurations
```bash
python manage.py setup_time_weights
```

### Analyze Current News Sentiment
```bash
python manage.py analyze_news_sentiment --stock-only --limit 50
```

### Test Time-Weighted Analysis
```bash
python manage.py test_time_weighted_news --stocks GPW CCC PKN JSW --show-details
```

### Demonstrate with Simulated Recent News
```bash
python manage.py demo_time_weighted_news --stock CCC
```

## 📊 Real-World Example

**CCC Stock Analysis Results**:
- **News Count**: 4 articles in last 4 hours
- **Weighted Sentiment**: +0.279 (positive)
- **Confidence**: 0.410 (moderate confidence)
- **Recent News Impact**: 4 articles boost recent activity
- **Sentiment Momentum**: +0.122 (improving sentiment)
- **Final Signal**: **BUY** with strength 0.139

**Time Weighting Breakdown**:
- Article 10min ago: Weight 0.378 × Sentiment +0.300 = High impact
- Article 30min ago: Weight 0.252 × Sentiment +0.300 = Medium impact  
- Article 90min ago: Weight 0.119 × Sentiment +0.300 = Lower impact
- Article 3h ago: Weight 0.071 × Sentiment +0.057 = Minimal impact

## 🔍 Technical Implementation

### Time Weight Calculation
```python
def calculate_time_weight(self, news_time, current_time):
    time_diff_minutes = (current_time - news_time).total_seconds() / 60
    decay_constant = ln(2) / half_life_minutes
    base_weight = exp(-decay_constant * time_diff_minutes)
    
    # Apply period-specific weights
    if time_diff <= 15: period_weight = 0.4
    elif time_diff <= 60: period_weight = 0.3  
    elif time_diff <= 240: period_weight = 0.2
    else: period_weight = 0.1
    
    return base_weight * period_weight
```

### Weighted Sentiment Score
```python
weighted_sentiment = sum(sentiment * weight for sentiment, weight in articles) / total_weights
```

## 🎯 Benefits for Intraday Trading

1. **Rapid Response**: News from last 15 minutes gets 40% of total weight
2. **Decay Function**: Old news automatically loses relevance  
3. **Market Context**: News during trading hours gets higher multipliers
4. **Breaking News Detection**: High-impact news gets 2x multiplier
5. **Momentum Tracking**: Sentiment direction changes are detected
6. **Signal Integration**: Seamlessly enhances existing technical analysis
7. **Configurable**: Different settings for aggressive/conservative/swing trading

## 📈 Performance Improvements Expected

- **Faster Signal Updates**: Responds to breaking news within minutes
- **Better Risk Management**: Conflicts between technical and news signals are resolved
- **Higher Accuracy**: News sentiment provides additional confirmation layer
- **Reduced False Signals**: Sentiment momentum helps filter noise
- **Market Timing**: Trading hour awareness improves signal quality

## 🔧 Configuration Management

The system provides flexible configuration through the admin interface:
- **Django Admin**: `/admin/analysis/timeweightconfiguration/`
- **Hot Reloading**: Configuration changes take effect immediately
- **A/B Testing**: Multiple configurations can be tested simultaneously
- **Validation**: Ensures time weights sum to 1.0 ± 5% tolerance

## 🚀 Future Enhancements

1. **Social Media Integration**: Extend to Twitter, Reddit sentiment
2. **Multi-language Support**: Polish news sentiment analysis
3. **Sector Analysis**: Industry-wide sentiment impact
4. **Real-time WebSocket**: Live sentiment updates
5. **ML Enhancement**: Learn optimal weights from historical performance
6. **Forum Integration**: WallStreetBets, investment forums sentiment

---

## 🎉 System Status: Production Ready

✅ **Time-weighted analysis implemented**  
✅ **Multiple trading style configurations**  
✅ **Enhanced signal generation**  
✅ **Comprehensive testing suite**  
✅ **Admin interface integration**  
✅ **Performance tracking ready**

The system successfully addresses the **critical gap** where intraday trading requires **immediate response to breaking news** while properly **weighing historical sentiment**. Recent news gets dramatically higher impact, ensuring the trading system can **react within minutes** to market-moving events.
