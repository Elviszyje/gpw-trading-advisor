"""
GPW Trading Advisor - Scrapers Module

Provides web scraping functionality for stock data collection.

Main classes:
- StooqCSVScraper: CSV-based scraper for reliable data extraction  
- SimpleStockDataCollector: High-level interface for stock data collection

Usage:
    from apps.scrapers.scraping import SimpleStockDataCollector
    
    collector = SimpleStockDataCollector()
    collector.collect_stock_data('PKN')
"""
