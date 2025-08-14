# GPW Daily Trading Advisor - Product Requirements Document

## Executive Summary

**Product Name:** GPW Daily Trading Advisor  
**Version:** 1.0 MVP  
**Date:** July 21, 2025  
**Document Owner:** Project Team  

### Product Vision
Create an automated trading advisory system for Polish stock exchange (GPW) that provides real-time BUY/SELL signals through advanced technical analysis, market sentiment monitoring, and instant Telegram notifications, enabling day traders to make profitable decisions with institutional-grade analysis tools.

### Success Metrics
- **Signal Accuracy:** >70% profitable recommendations
- **System Uptime:** >99% during trading hours (9:00-17:30)
- **Notification Speed:** <30 seconds from signal generation
- **User Retention:** >80% monthly subscription renewals
- **Concurrent Monitoring:** 12+ stocks simultaneously

## Product Overview

### Core Value Proposition
Transform complex market data into actionable trading signals by combining:
- Real-time price monitoring from stooq.pl
- ESPI/EBI corporate communications analysis
- Technical indicators (RSI, MACD, Bollinger Bands, SMA/EMA)
- Financial news sentiment analysis
- Instant mobile notifications via Telegram
- Performance tracking and risk management

### Target Users
- **Primary:** Active day traders on Polish stock exchange
- **Secondary:** Individual investors seeking data-driven insights
- **Tertiary:** Financial advisors needing market monitoring tools

## Functional Requirements

### FR-001: Real-time Data Collection
**Priority:** Critical  
**Epic:** Data Infrastructure

#### User Stories
- As a day trader, I want real-time stock prices updated every 1-5 minutes so I can respond quickly to market changes
- As a day trader, I want ESPI/EBI communications monitored so I understand corporate events affecting stock prices
- As a day trader, I want financial news integrated so I can gauge market sentiment

#### Acceptance Criteria
- [ ] System scrapes stooq.pl price data every 1-5 minutes (configurable)
- [ ] Selenium WebDriver handles JavaScript-heavy sites reliably
- [ ] Concurrent monitoring of 12+ stocks without performance degradation
- [ ] RSS scraper collects ESPI/EBI data hourly
- [ ] Financial news scraped from multiple sources
- [ ] Failed scraping attempts retry maximum 3 times with 30-second delays
- [ ] All data timestamped and stored in PostgreSQL with proper indexing

### FR-002: Technical Analysis Engine
**Priority:** Critical  
**Epic:** Signal Generation

#### User Stories
- As a day trader, I want automated technical analysis so I don't miss profitable opportunities
- As a day trader, I want multiple indicators combined so I get reliable signals
- As a day trader, I want configurable risk parameters so I can match my trading style

#### Acceptance Criteria
- [ ] RSI calculation with 14-period default (configurable)
- [ ] MACD calculation with 12/26/9 period defaults (configurable)
- [ ] Bollinger Bands with 20-period moving average and 2 standard deviations
- [ ] SMA/EMA calculations for multiple timeframes
- [ ] Signal generation requires minimum 3 indicators confirmation
- [ ] BUY signal: RSI < 30 AND volume > 20-day average * 1.5 (configurable thresholds)
- [ ] SELL signal: RSI > 70 AND MACD shows divergence (configurable thresholds)
- [ ] Confidence scoring from 0-100% based on indicator alignment
- [ ] Historical backtesting validates signal accuracy

### FR-003: User Management & Subscriptions
**Priority:** High  
**Epic:** User Platform

#### User Stories
- As a system administrator, I want to manage user accounts and subscriptions
- As a user, I want to configure my risk preferences and notification settings
- As a user, I want to track my subscription status and renewal dates

#### Acceptance Criteria
- [ ] User registration with unique username, email, Telegram chat ID
- [ ] Subscription periods: 7, 30, 90, 365 days
- [ ] User risk profiles: Conservative (>80% confidence), Moderate (>70%), Aggressive (>60%)
- [ ] Configurable profit targets: 1%, 3%, 5%, or custom values
- [ ] Configurable stop-loss: 0.5%, 1%, 2%, or custom values
- [ ] Subscription expiration notifications 3 days before expiry
- [ ] Automatic service suspension when subscription expires
- [ ] User preference changes applied within 5 minutes

### FR-004: Telegram Integration
**Priority:** Critical  
**Epic:** Notifications

#### User Stories
- As a day trader, I want instant notifications on my mobile device
- As a day trader, I want different types of alerts based on my preferences
- As a day trader, I want clear, actionable messages without technical jargon

#### Acceptance Criteria
- [ ] Telegram Bot API integration with secure token management
- [ ] Message delivery within 30 seconds of signal generation
- [ ] Message types: price_alerts, intraday_recommendations, scan_summary
- [ ] Rich message formatting with stock name, price, signal, indicators, confidence
- [ ] User-specific notification preferences (alert types, timing)
- [ ] Message delivery queue with retry mechanism for failed sends
- [ ] Daily summary reports with top opportunities
- [ ] Failed delivery alerts to system administrators

### FR-005: Performance Tracking
**Priority:** High  
**Epic:** Analytics

#### User Stories
- As a day trader, I want to track recommendation performance within the same trading day
- As a day trader, I want to see profit/loss calculations for each signal
- As a system administrator, I want to monitor overall system effectiveness

#### Acceptance Criteria
- [ ] Record signal generation: timestamp, entry price, signal type, indicators
- [ ] Calculate P&L at 1, 2, 3, 4, 5, 6, 7, 8 hours after signal
- [ ] End-of-day performance summary for all recommendations
- [ ] Success rate calculation: percentage of profitable signals
- [ ] Average return calculation per signal and per day
- [ ] Performance alerts when targets reached (suggest position closure)
- [ ] Historical performance data for system improvement
- [ ] User-specific performance tracking and reporting

### FR-006: System Reliability
**Priority:** Critical  
**Epic:** Infrastructure

#### User Stories
- As a day trader, I want the system to work reliably throughout trading hours
- As a system administrator, I want automatic error recovery and monitoring
- As a user, I want consistent service availability during market hours

#### Acceptance Criteria
- [ ] Multi-threaded processing (2-8 threads) for concurrent data collection
- [ ] Automatic task restart on failure with exponential backoff
- [ ] Comprehensive error logging with actionable alerts
- [ ] Trading hours automation: 9:00 start, 17:30 stop
- [ ] System restart recovery within 2 minutes
- [ ] Circuit breaker pattern for external service failures
- [ ] Health check endpoints for monitoring
- [ ] Database connection pooling for performance

## Non-Functional Requirements

### NFR-001: Performance
- **Response Time:** Signal generation < 30 seconds
- **Throughput:** Handle 12+ stocks simultaneously
- **Scalability:** Support 100+ concurrent users
- **Data Processing:** Process 1000+ price points per hour

### NFR-002: Reliability
- **Availability:** 99% uptime during trading hours
- **Error Rate:** <1% failed operations
- **Recovery Time:** <2 minutes from system restart
- **Data Accuracy:** 100% reliable data collection

### NFR-003: Security
- **Authentication:** Secure user login and session management
- **API Security:** Encrypted Telegram bot token storage
- **Data Privacy:** User data protection compliance
- **Input Validation:** Sanitize all user inputs and external data

### NFR-004: Usability
- **Learning Curve:** New users productive within 1 day
- **Message Clarity:** Non-technical language in notifications
- **Configuration:** Intuitive risk parameter settings
- **Support:** Clear error messages and help documentation

## Technical Architecture

### Technology Stack
- **Backend:** Django 5.0+ with Python 3.11+
- **Database:** PostgreSQL 15+ with time-series optimization
- **Task Queue:** Celery + Redis for background processing
- **Web Scraping:** Selenium WebDriver with Chrome/Firefox
- **Messaging:** python-telegram-bot library
- **Containerization:** Docker for development and deployment

### System Architecture
```
External APIs → Scrapers → Database → Analysis Engine → Signal Generator → Telegram Bot
     ↓              ↓           ↓            ↓              ↓              ↓
  stooq.pl      Selenium   PostgreSQL   Technical     Redis Queue    User Devices
  ESPI/EBI      RSS Feed   Time-series   Indicators    Background     Mobile App
  News Sites    Parsers    Indexing      Algorithms    Tasks          Notifications
```

## Task Status Section

### ✅ Done
- [x] Requirements analysis and documentation
- [x] Technical architecture design
- [x] Technology stack selection
- [x] Database schema design
- [x] System patterns definition

### 🚧 In Progress
- [ ] Django project initialization
- [ ] Development environment setup
- [ ] Core model implementation

### 📋 Blocked
- None currently

### 🎯 Next Sprint
- [ ] User management system
- [ ] Database model creation
- [ ] Basic Telegram bot setup
- [ ] Web scraping infrastructure
- [ ] Technical analysis algorithms

## Risk Assessment

### High Risk
- **External API Reliability:** Dependent on stooq.pl and other data sources
- **Real-time Performance:** Meeting <30 second notification requirement
- **Signal Accuracy:** Achieving >70% profitable recommendation rate

### Medium Risk
- **User Adoption:** Building trust in automated trading recommendations
- **Scalability:** Handling growing user base efficiently
- **Regulatory Compliance:** Potential financial service regulations

### Low Risk
- **Technology Stack:** Mature, well-documented technologies
- **Development Team:** Experienced with chosen technologies
- **Infrastructure:** Standard web application deployment patterns

## Success Criteria

### MVP Launch Criteria
- [ ] 12+ stocks monitored simultaneously
- [ ] 4+ technical indicators implemented
- [ ] Real-time Telegram notifications working
- [ ] User subscription system functional
- [ ] Basic performance tracking operational
- [ ] System uptime >95% during testing period

### 3-Month Success Criteria
- [ ] 50+ active subscribers
- [ ] >70% signal accuracy achieved
- [ ] 99% uptime during trading hours
- [ ] Positive user feedback and retention
- [ ] Revenue model validated

### 6-Month Success Criteria
- [ ] 200+ active subscribers
- [ ] Advanced features implemented
- [ ] Mobile app launched
- [ ] Partnership discussions initiated
- [ ] Sustainable business model established
