"""
AI Response parsing utilities with error handling and retry logic
"""

import json
import re
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class AIResponseParser:
    """Enhanced AI response parser with error handling and JSON repair"""
    
    def __init__(self):
        self.fallback_values = {
            'overall_sentiment': 'neutral',
            'overall_sentiment_score': 0.5,
            'confidence_score': 0.3,
            'market_impact': 'low',
            'mentioned_companies': [],
            'mentioned_people': [],
            'mentioned_locations': [],
            'mentioned_stocks': [],
            'industry_categories': [],
            'general_summary': 'Unable to analyze article content'
        }
    
    def clean_json_content(self, content: str) -> str:
        """Clean and extract JSON content from AI response"""
        if not content:
            return ""
        
        # Remove markdown formatting
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        
        # Remove leading/trailing whitespace
        content = content.strip()
        
        # Remove common AI text prefixes
        prefixes_to_remove = [
            "Here's the analysis:",
            "Analysis:",
            "Result:",
            "JSON:",
            "Response:"
        ]
        
        for prefix in prefixes_to_remove:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()
        
        return content
    
    def repair_incomplete_json(self, content: str) -> str:
        """Attempt to repair incomplete JSON"""
        content = content.strip()
        
        # If JSON doesn't end with }, try to complete it
        if content and not content.endswith('}'):
            # Count open braces vs closed braces
            open_braces = content.count('{')
            close_braces = content.count('}')
            
            if open_braces > close_braces:
                # Add missing closing braces
                missing_braces = open_braces - close_braces
                content += '}' * missing_braces
        
        # Fix common JSON issues
        content = re.sub(r',(\s*[}\]])', r'\1', content)  # Remove trailing commas
        content = re.sub(r'(\w+):', r'"\1":', content)     # Add quotes to keys without quotes
        
        return content
    
    def extract_partial_data(self, content: str) -> Dict[str, Any]:
        """Extract whatever data we can from partial/broken JSON"""
        extracted = {}
        
        # Try to extract sentiment
        sentiment_match = re.search(r'"overall_sentiment":\s*"([^"]+)"', content)
        if sentiment_match:
            extracted['overall_sentiment'] = sentiment_match.group(1)
        
        # Try to extract sentiment score
        score_match = re.search(r'"overall_sentiment_score":\s*([0-9.]+)', content)
        if score_match:
            try:
                extracted['overall_sentiment_score'] = float(score_match.group(1))
            except ValueError:
                pass
        
        # Try to extract confidence score
        conf_match = re.search(r'"confidence_score":\s*([0-9.]+)', content)
        if conf_match:
            try:
                extracted['confidence_score'] = float(conf_match.group(1))
            except ValueError:
                pass
        
        # Try to extract market impact
        impact_match = re.search(r'"market_impact":\s*"([^"]+)"', content)
        if impact_match:
            extracted['market_impact'] = impact_match.group(1)
        
        # Try to extract summary
        summary_match = re.search(r'"general_summary":\s*"([^"]+)"', content)
        if summary_match:
            extracted['general_summary'] = summary_match.group(1)
        
        return extracted
    
    def parse_ai_response(self, content: str, attempt: int = 1) -> Optional[Dict[str, Any]]:
        """
        Parse AI response with multiple strategies
        
        Args:
            content: Raw AI response content
            attempt: Current parsing attempt (for logging)
            
        Returns:
            Parsed data dictionary or None if parsing fails completely
        """
        if not content:
            logger.warning("Empty AI response content")
            return None
        
        # Step 1: Clean the content
        cleaned_content = self.clean_json_content(content)
        
        if not cleaned_content:
            logger.warning("No JSON content found after cleaning")
            return None
        
        # Step 2: Try direct JSON parsing
        try:
            data = json.loads(cleaned_content)
            logger.debug(f"Successfully parsed JSON on attempt {attempt}")
            return self.validate_and_complete_data(data)
        except json.JSONDecodeError as e:
            logger.debug(f"Direct JSON parsing failed: {e}")
        
        # Step 3: Try to repair and parse JSON
        try:
            repaired_content = self.repair_incomplete_json(cleaned_content)
            data = json.loads(repaired_content)
            logger.info(f"Successfully parsed repaired JSON on attempt {attempt}")
            return self.validate_and_complete_data(data)
        except json.JSONDecodeError as e:
            logger.debug(f"Repaired JSON parsing failed: {e}")
        
        # Step 4: Extract partial data
        try:
            partial_data = self.extract_partial_data(cleaned_content)
            if partial_data:
                logger.warning(f"Using partial data extraction on attempt {attempt}")
                return self.validate_and_complete_data(partial_data)
        except Exception as e:
            logger.error(f"Partial data extraction failed: {e}")
        
        # Step 5: Use fallback values with error logging
        logger.error(f"All parsing strategies failed for content: {cleaned_content[:200]}...")
        return None
    
    def validate_and_complete_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and complete parsed data with fallback values"""
        completed_data = self.fallback_values.copy()
        
        # Update with parsed data
        for key, value in data.items():
            if key in completed_data:
                # Validate specific fields
                if key == 'overall_sentiment' and value in ['positive', 'negative', 'neutral', 'very_positive', 'very_negative']:
                    completed_data[key] = value
                elif key in ['overall_sentiment_score', 'confidence_score'] and isinstance(value, (int, float)):
                    # Clamp to valid range
                    completed_data[key] = max(0.0, min(1.0, float(value)))
                elif key == 'market_impact' and value in ['low', 'medium', 'high']:
                    completed_data[key] = value
                elif key in ['mentioned_companies', 'mentioned_people', 'mentioned_locations', 'mentioned_stocks', 'industry_categories']:
                    if isinstance(value, list):
                        completed_data[key] = value
                elif key == 'general_summary' and isinstance(value, str):
                    completed_data[key] = value[:1000]  # Limit summary length
                else:
                    completed_data[key] = value
        
        return completed_data


# Global parser instance
ai_response_parser = AIResponseParser()
