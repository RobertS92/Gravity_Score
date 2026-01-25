#!/usr/bin/env python3
"""
Quick Perplexity API Key Test
==============================
Tests if your Perplexity API key is valid and working
"""
import os
import sys
import requests

def test_api_key(api_key=None):
    """Test if Perplexity API key works"""
    
    print("="*70)
    print("PERPLEXITY API KEY TEST")
    print("="*70)
    print()
    
    # Get API key
    if api_key is None:
        api_key = os.getenv('PERPLEXITY_API_KEY')
    
    if not api_key:
        print("❌ No API key provided!")
        print()
        print("Usage:")
        print("  1. Set environment variable: export PERPLEXITY_API_KEY='your-key'")
        print("  2. Or pass as argument: python3 test_perplexity_api.py 'your-key'")
        print()
        return False
    
    # Check format
    print(f"📋 API Key Info:")
    print(f"   Length: {len(api_key)} characters")
    print(f"   Starts with: '{api_key[:10]}...'")
    print(f"   Ends with: '...{api_key[-4:]}'")
    print()
    
    if not api_key.startswith('pplx-'):
        print("⚠️  WARNING: Key doesn't start with 'pplx-'")
        print("   This may not be a valid Perplexity API key.")
        print()
    
    if len(api_key) < 20:
        print("⚠️  WARNING: Key seems too short (expected 40+ characters)")
        print()
    
    # Test API call
    print("🔍 Testing API with simple query...")
    print()
    
    try:
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": "What is 2+2? Answer with just the number."
                }
            ],
            "temperature": 0.1,
            "max_tokens": 10
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"📡 API Response:")
        print(f"   Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            print("✅ API KEY WORKS!")
            print(f"   Test query response: {answer.strip()}")
            print()
            print("🎉 Your Perplexity API is configured correctly!")
            print("   You can now run the scraper with AI fallback enabled.")
            print()
            return True
        else:
            print(f"❌ API REQUEST FAILED!")
            print()
            print(f"Status Code: {response.status_code}")
            print()
            
            # Try to parse error details
            try:
                error_data = response.json()
                print("Error Details:")
                for key, value in error_data.items():
                    print(f"   {key}: {value}")
            except:
                print("Raw Response:")
                print(f"   {response.text[:500]}")
            
            print()
            print("Common issues:")
            print("  1. Invalid API key - check if it's correct")
            print("  2. API key not activated - verify in Perplexity dashboard")
            print("  3. Model not available on your plan - try a different model")
            print("  4. Rate limit exceeded - wait a moment and try again")
            print()
            return False
            
    except requests.exceptions.Timeout:
        print("❌ REQUEST TIMEOUT")
        print("   The API took too long to respond. Try again.")
        print()
        return False
        
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR")
        print("   Could not connect to Perplexity API. Check your internet.")
        print()
        return False
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print("="*70)


if __name__ == '__main__':
    # Get API key from argument or environment
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    success = test_api_key(api_key)
    sys.exit(0 if success else 1)

