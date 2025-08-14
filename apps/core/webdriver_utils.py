"""
WebDriver configuration utilities for cross-platform compatibility
"""
import os
import platform
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


def get_chrome_driver():
    """
    Get Chrome WebDriver with cross-platform configuration
    """
    options = ChromeOptions()
    
    # Common options for all environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Environment-specific configuration
    if os.getenv('DOCKER_ENV'):
        # Docker environment settings
        options.add_argument('--headless=new')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')
        options.add_argument('--disable-javascript')
        
        # Try to detect architecture
        arch = platform.machine().lower()
        if 'arm' in arch or 'aarch64' in arch:
            # Use system chromium on ARM
            options.binary_location = '/usr/bin/chromium'
            service = ChromeService()
        else:
            # Use Chrome on x86_64
            options.binary_location = '/usr/bin/google-chrome'
            service = ChromeService()
            
    elif os.getenv('CI'):
        # CI environment (GitHub Actions)
        options.add_argument('--headless=new')
        options.add_argument('--disable-extensions')
        service = ChromeService(ChromeDriverManager().install())
        
    else:
        # Local development
        if os.getenv('HEADLESS', 'False').lower() == 'true':
            options.add_argument('--headless=new')
        
        # Use webdriver-manager for local development
        service = ChromeService(ChromeDriverManager().install())
    
    return webdriver.Chrome(service=service, options=options)


def get_chrome_options():
    """
    Get Chrome options configuration
    """
    options = ChromeOptions()
    
    # Common options for all environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    if os.getenv('DOCKER_ENV') or os.getenv('CI'):
        options.add_argument('--headless=new')
        options.add_argument('--disable-extensions')
        
    return options
