# Project Brief: GPW Daily Trading Advisor

## Core Project Identity

**Name:** GPW Daily Trading Advisor  
**Type:** Advanced Financial Analysis and Trading Recommendation System  
**Primary Goal:** Automated daily trading recommendations for Polish stock exchange (GPW) with real-time market sentiment analysis

## Project Scope

### What We're Building
A comprehensive trading advisory system that combines:
- Real-time stock price monitoring from stooq.pl
- ESPI/EBI corporate communications analysis
- Financial news sentiment analysis
- Technical analysis with multiple indicators (RSI, MACD, Bollinger Bands, SMA/EMA)
- Instant Telegram notifications for trading signals
- Multi-user subscription management system
- Performance tracking and historical analysis

### Core Value Proposition
Enables day traders to make informed decisions by providing:
- BUY/SELL signals based on technical analysis
- Real-time market sentiment context
- Risk-adjusted recommendations
- Performance tracking within trading hours
- Instant mobile notifications

## Technical Foundation

### Technology Stack
- **Backend:** Django (Python web framework)
- **Database:** PostgreSQL
- **Web Scraping:** Selenium for stooq.pl data extraction
- **Messaging:** Telegram Bot API
- **Scheduling:** Celery with Redis/RabbitMQ
- **Monitoring:** Custom Django management commands

### Architecture Approach
- Feature-sliced architecture
- Microservice-style Django apps for each major function
- Concurrent processing with threading/async support
- Robust error handling and retry mechanisms
- Scalable user management with subscription tiers

## Key Business Requirements

### Primary Features (MVP)
1. **Real-time Data Collection:** Stock prices every 1-5 minutes
2. **Technical Analysis Engine:** Multi-indicator signal generation
3. **Telegram Integration:** Instant notifications to users
4. **User Management:** Subscription-based access control
5. **Performance Tracking:** Intraday recommendation effectiveness

### Success Metrics
- Signal accuracy > 70% for profitable trades
- System uptime during trading hours > 99%
- Notification delivery < 30 seconds
- Support for 12+ stocks simultaneously
- User retention through subscription renewals

## Project Constraints

### Time Constraints
- Trading hours: 9:00-17:30 (Polish time)
- Real-time requirements for notifications
- Daily performance reporting deadlines

### Technical Constraints
- Rate limiting for web scraping
- Telegram API limitations
- Database performance with high-frequency data
- Concurrent user notification processing

### Business Constraints
- Compliance with financial data usage terms
- User privacy and data protection
- Subscription model viability
- Scalability for growing user base

## Project Vision
Create a reliable, automated trading advisor that democratizes access to sophisticated market analysis, enabling individual traders to compete with institutional algorithms through data-driven insights and timely execution signals.
