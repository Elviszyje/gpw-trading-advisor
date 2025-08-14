#!/usr/bin/env python
"""
Test script for LLM service setup
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from apps.core.models import LLMProvider
from apps.core.llm_service import LLMService

def main():
    print("=== LLM Service Setup Test ===\n")
    
    # Update OLLAMA provider with available model
    try:
        ollama_provider = LLMProvider.objects.get(provider_type='ollama')
        ollama_provider.model_name = 'llama3.1:latest'
        ollama_provider.save()
        print(f"✅ OLLAMA provider updated: {ollama_provider.name}")
        print(f"   Model: {ollama_provider.model_name}")
    except Exception as e:
        print(f"❌ Error updating OLLAMA: {e}")
    
    print("\n=== Testing LLM Providers ===")
    
    # Test LLM service availability
    try:
        service = LLMService()
        
        for provider in LLMProvider.objects.filter(is_active=True):
            print(f"\nTesting {provider.name} ({provider.provider_type})...")
            try:
                is_available = service.check_provider_availability(provider)
                status = "✅ Available" if is_available else "❌ Not Available"
                print(f"   {status}")
                
                if provider.provider_type == 'openai' and is_available:
                    print(f"   API Key: {provider.api_key[:20]}...")
                elif provider.provider_type == 'ollama' and is_available:
                    print(f"   Model: {provider.model_name}")
                    print(f"   URL: {provider.api_url}")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                
    except Exception as e:
        print(f"❌ Error creating LLM service: {e}")
        
    print("\n=== Current Provider Status ===")
    for provider in LLMProvider.objects.all():
        print(f"{provider.name}: Active={provider.is_active}, Available={provider.is_available}")
        
if __name__ == "__main__":
    main()
