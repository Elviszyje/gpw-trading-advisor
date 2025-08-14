"""
Test debugowania scrapera Bankier.pl
Analizuje HTML i strukture strony
"""

import requests
from bs4 import BeautifulSoup
import re

def debug_bankier_page():
    """Debuguje strukturę strony Bankier.pl"""
    
    url = "https://www.bankier.pl/gielda/kalendarium"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"Pobieranie: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print(f"Status: {response.status_code}")
        print(f"Długość contentu: {len(response.content)}")
        
        # Wyszukaj wszystkie elementy z tekstem zawierającym symbole spółek
        print("\n=== WYSZUKIWANIE LINKÓW DO SPÓŁEK ===")
        company_links = soup.find_all('a', href=re.compile(r'symbol='))
        print(f"Znaleziono {len(company_links)} linków do spółek")
        
        for i, link in enumerate(company_links[:10]):  # Pierwsze 10
            try:
                href = link.get('href')
                text = link.get_text().strip()
                print(f"{i+1}. {text} -> {href}")
            except:
                pass
        
        # Wyszukaj elementy z datami
        print("\n=== WYSZUKIWANIE DAT ===")
        date_elements = soup.find_all(text=re.compile(r'\d{1,2}\s+\w+'))
        print(f"Znaleziono {len(date_elements)} elementów z datami")
        
        for i, date_text in enumerate(date_elements[:10]):
            try:
                date_clean = date_text.strip()
                if len(date_clean) > 0:
                    print(f"{i+1}. '{date_clean}'")
            except:
                pass
        
        # Wyszukaj elementy zawierające nazwy kategorii
        print("\n=== WYSZUKIWANIE KATEGORII WYDARZEŃ ===")
        categories = ['Dywidendy', 'WZA', 'Wyniki', 'dywidend', 'wza', 'wyniki']
        for category in categories:
            elements = soup.find_all(text=re.compile(category, re.IGNORECASE))
            print(f"'{category}': {len(elements)} wystąpień")
        
        # Sprawdź strukturę tygodniową
        print("\n=== STRUKTURA TYGODNIOWA ===")
        weekly_structure = soup.find_all(['h2', 'h3', 'h4'], text=re.compile(r'(poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela)', re.IGNORECASE))
        print(f"Znaleziono {len(weekly_structure)} nagłówków dni tygodnia")
        
        for day in weekly_structure:
            print(f"Dzień: '{day.get_text().strip()}'")
            
        # Zapisz fragment HTML do analizy
        print("\n=== ZAPISYWANIE FRAGMENTU HTML ===")
        with open('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2/debug_bankier.html', 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        print("Zapisano debug_bankier.html")
        
        # Wyszukaj strukturę główną kalendarza
        print("\n=== STRUKTURA GŁÓWNA ===")
        main_content = soup.find('div', class_=re.compile(r'calendar|kalendarium', re.IGNORECASE))
        if main_content:
            print("Znaleziono główny kontener kalendarza")
        else:
            print("Nie znaleziono głównego kontenera kalendarza")
            
        # Sprawdź czy strona wymaga JavaScript
        scripts = soup.find_all('script')
        print(f"Znaleziono {len(scripts)} skryptów JavaScript")
        
        return True
        
    except Exception as e:
        print(f"Błąd: {e}")
        return False

if __name__ == "__main__":
    debug_bankier_page()
