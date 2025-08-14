"""
Enhanced stock symbol detection with fuzzy matching and context awareness
"""

import re
from typing import List, Dict, Set, Tuple
from difflib import SequenceMatcher
from apps.core.models import StockSymbol
import logging

logger = logging.getLogger(__name__)


class StockSymbolDetector:
    """Enhanced stock symbol detection with multiple strategies"""
    
    def __init__(self):
        self.symbols_cache = None
        self.company_names_cache = None
        self.refresh_cache()
    
    def refresh_cache(self):
        """Refresh cached stock symbols and company names"""
        symbols_data = StockSymbol.objects.values('symbol', 'name')
        
        self.symbols_cache = {}
        self.company_names_cache = {}
        
        for stock in symbols_data:
            symbol = stock['symbol'].upper()
            name = stock['name'] or ''
            
            # Cache symbols
            self.symbols_cache[symbol] = {
                'symbol': symbol,
                'name': name
            }
            
            # Cache company names for reverse lookup
            if name:
                self.company_names_cache[name.lower()] = symbol
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for better matching"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep Polish characters
        text = re.sub(r'[^\w\sąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', ' ', text)
        
        return text.strip()
    
    def extract_symbols_by_code(self, text: str) -> Set[str]:
        """Extract stock symbols by exact symbol code matching"""
        found_symbols = set()
        
        if not text or not self.symbols_cache:
            return found_symbols
        
        text_upper = text.upper()
        
        for symbol in self.symbols_cache:
            # Exact word boundary matching
            pattern = r'\b' + re.escape(symbol) + r'\b'
            if re.search(pattern, text_upper):
                found_symbols.add(symbol)
        
        return found_symbols
    
    def extract_symbols_by_company_name(self, text: str, similarity_threshold: float = 0.8) -> Set[str]:
        """Extract stock symbols by company name matching"""
        found_symbols = set()
        
        if not text or not self.company_names_cache:
            return found_symbols
        
        text_lower = self.normalize_text(text.lower())
        
        # Exact matches first
        for company_name, symbol in self.company_names_cache.items():
            if company_name in text_lower:
                found_symbols.add(symbol)
        
        # Fuzzy matching for partial names
        words = text_lower.split()
        for company_name, symbol in self.company_names_cache.items():
            company_words = company_name.split()
            
            # Check if significant portion of company name appears in text
            if len(company_words) >= 2:
                matches = 0
                for company_word in company_words:
                    if len(company_word) > 3:  # Skip short words
                        for text_word in words:
                            similarity = SequenceMatcher(None, company_word, text_word).ratio()
                            if similarity >= similarity_threshold:
                                matches += 1
                                break
                
                # If most words match, consider it a match
                if matches >= len(company_words) * 0.6:
                    found_symbols.add(symbol)
        
        return found_symbols
    
    def extract_symbols_by_context(self, text: str) -> Set[str]:
        """Extract symbols using financial context patterns"""
        found_symbols = set()
        
        if not text:
            return found_symbols
        
        # Financial context patterns
        financial_patterns = [
            r'akcje\s+(\w+)',
            r'spółka\s+(\w+)',
            r'(\w+)\s+(?:na|z)\s+gpw',
            r'notowania\s+(\w+)',
            r'(\w+)\s+zyskuje',
            r'(\w+)\s+traci',
            r'kurs\s+(\w+)',
            r'(\w+)\s+wzrost',
            r'(\w+)\s+spadek'
        ]
        
        text_lower = text.lower()
        
        for pattern in financial_patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                potential_symbol = match.group(1).upper()
                if self.symbols_cache and potential_symbol in self.symbols_cache:
                    found_symbols.add(potential_symbol)
        
        return found_symbols
    
    def filter_false_positives(self, symbols: Set[str], text: str) -> Set[str]:
        """Filter out common false positives"""
        if not symbols:
            return symbols
        
        # Common Polish words that might match symbols
        false_positive_words = {
            'CO', 'TO', 'NA', 'W', 'Z', 'I', 'A', 'O', 'U', 'E',
            'DO', 'PO', 'OD', 'ZA', 'BY', 'SE', 'SI', 'JE', 'GO',
            'MY', 'WY', 'ONI', 'ONE', 'TAK', 'NIE', 'ALE', 'ORAZ'
        }
        
        filtered_symbols = set()
        text_lower = text.lower()
        
        for symbol in symbols:
            # Skip if it's a common word and appears in non-financial context
            if symbol in false_positive_words:
                # Check if it appears in financial context
                financial_context_patterns = [
                    f'akcje {symbol.lower()}',
                    f'spółka {symbol.lower()}',
                    f'{symbol.lower()} na gpw',
                    f'notowania {symbol.lower()}'
                ]
                
                has_financial_context = any(
                    pattern in text_lower for pattern in financial_context_patterns
                )
                
                if has_financial_context:
                    filtered_symbols.add(symbol)
            else:
                filtered_symbols.add(symbol)
        
        return filtered_symbols
    
    def extract_stock_symbols(self, text: str, confidence_threshold: float = 0.7) -> Dict[str, float]:
        """
        Extract stock symbols with confidence scores
        
        Args:
            text: Text to analyze
            confidence_threshold: Minimum confidence score to include symbol
            
        Returns:
            Dictionary of {symbol: confidence_score}
        """
        if not text:
            return {}
        
        # Refresh cache if empty
        if not self.symbols_cache:
            self.refresh_cache()
        
        all_found_symbols = set()
        symbol_confidence = {}
        
        # Method 1: Direct symbol code matching (highest confidence)
        code_symbols = self.extract_symbols_by_code(text)
        for symbol in code_symbols:
            all_found_symbols.add(symbol)
            symbol_confidence[symbol] = max(symbol_confidence.get(symbol, 0), 0.9)
        
        # Method 2: Company name matching (medium confidence)
        name_symbols = self.extract_symbols_by_company_name(text)
        for symbol in name_symbols:
            all_found_symbols.add(symbol)
            symbol_confidence[symbol] = max(symbol_confidence.get(symbol, 0), 0.8)
        
        # Method 3: Context-based matching (lower confidence)
        context_symbols = self.extract_symbols_by_context(text)
        for symbol in context_symbols:
            all_found_symbols.add(symbol)
            symbol_confidence[symbol] = max(symbol_confidence.get(symbol, 0), 0.6)
        
        # Filter false positives
        filtered_symbols = self.filter_false_positives(all_found_symbols, text)
        
        # Return only symbols above confidence threshold
        result = {
            symbol: confidence 
            for symbol, confidence in symbol_confidence.items() 
            if symbol in filtered_symbols and confidence >= confidence_threshold
        }
        
        if result:
            logger.debug(f"Extracted {len(result)} stock symbols: {list(result.keys())}")
        
        return result
    
    def get_simple_symbol_list(self, text: str) -> List[str]:
        """Get simple list of symbols (for backward compatibility)"""
        symbol_dict = self.extract_stock_symbols(text)
        return list(symbol_dict.keys())


# Global detector instance
stock_symbol_detector = StockSymbolDetector()
