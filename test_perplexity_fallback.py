#!/usr/bin/env python3
"""
Unit Test for Perplexity AI Fallback
Tests API connection, field parsers, cost tracking, and "Undrafted" handling
"""
import sys
import os
from pathlib import Path

# Add paths
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(script_dir / 'gravity'))

# Set API key if available
if len(sys.argv) > 1:
    os.environ['PERPLEXITY_API_KEY'] = sys.argv[1]

from gravity.perplexity_fallback import PerplexityFallback

def test_initialization():
    """Test module initialization"""
    print("="*70)
    print("TEST 1: Initialization")
    print("="*70)
    
    fallback = PerplexityFallback()
    
    if fallback.enabled:
        print("✅ API key detected and initialized")
        print(f"   Enabled: {fallback.enabled}")
        print(f"   Cost per call: ${fallback.cost_per_call}")
    else:
        print("⚠️  No API key set - fallback disabled (this is OK for testing structure)")
    
    return fallback

def test_query_builder(fallback):
    """Test query building for different field types"""
    print("\n" + "="*70)
    print("TEST 2: Query Builder")
    print("="*70)
    
    test_cases = [
        ('draft_year', 'Patrick Mahomes', 'QB, Kansas City Chiefs'),
        ('hometown', 'Tom Brady', 'QB, Tampa Bay Buccaneers'),
        ('instagram_handle', 'Travis Kelce', 'TE, Kansas City Chiefs'),
        ('contract_value', 'Josh Allen', 'QB, Buffalo Bills'),
    ]
    
    for field_name, player_name, context in test_cases:
        query = fallback._build_query(player_name, field_name, 'NFL', context)
        print(f"\n{field_name}:")
        print(f"  Query: {query[:100]}...")
        print("  ✅ Query built successfully")

def test_response_parser(fallback):
    """Test response parsing for different field types"""
    print("\n" + "="*70)
    print("TEST 3: Response Parser")
    print("="*70)
    
    test_responses = [
        ('draft_year', {'choices': [{'message': {'content': 'Patrick Mahomes was drafted in 2017'}}]}, 2017),
        ('draft_year', {'choices': [{'message': {'content': 'He was undrafted'}}]}, 'Undrafted'),
        ('draft_round', {'choices': [{'message': {'content': 'Selected in the 1st round'}}]}, 1),
        ('draft_pick', {'choices': [{'message': {'content': 'He was the 10th overall pick'}}]}, 10),
        ('height', {'choices': [{'message': {'content': 'He is 6 feet 3 inches tall'}}]}, "6' 3\""),
        ('weight', {'choices': [{'message': {'content': 'He weighs 230 pounds'}}]}, 230),
        ('instagram_handle', {'choices': [{'message': {'content': 'His handle is @patrickmahomes'}}]}, 'patrickmahomes'),
    ]
    
    for field_name, response, expected in test_responses:
        result = fallback._parse_response(response, field_name)
        if result == expected:
            print(f"✅ {field_name}: {result}")
        else:
            print(f"❌ {field_name}: Expected {expected}, got {result}")

def test_cost_tracking(fallback):
    """Test cost tracking"""
    print("\n" + "="*70)
    print("TEST 4: Cost Tracking")
    print("="*70)
    
    initial_calls = fallback.calls_made
    
    # Simulate some calls
    fallback.calls_made += 5
    
    stats = fallback.get_stats()
    print(f"Calls made: {stats['calls_made']}")
    print(f"Estimated cost: ${stats['estimated_cost']:.3f}")
    print(f"Enabled: {stats['enabled']}")
    
    if stats['calls_made'] == initial_calls + 5:
        print("✅ Cost tracking working correctly")
    else:
        print("❌ Cost tracking error")
    
    # Reset for clean state
    fallback.calls_made = initial_calls

def test_live_api(fallback):
    """Test live API call (only if API key is set)"""
    print("\n" + "="*70)
    print("TEST 5: Live API Call")
    print("="*70)
    
    if not fallback.enabled:
        print("⚠️  Skipping live test - no API key set")
        print("   To test live API, run: python3 test_perplexity_fallback.py YOUR_API_KEY")
        return
    
    print("Testing live API call for Patrick Mahomes draft year...")
    
    try:
        context = {
            'position': 'QB',
            'team': 'Kansas City Chiefs',
            'college': 'Texas Tech'
        }
        
        result = fallback.search_missing_field(
            'Patrick Mahomes', 
            'draft_year', 
            'NFL', 
            context
        )
        
        if result:
            print(f"✅ API call successful!")
            print(f"   Result: {result}")
            print(f"   Cost: ${fallback.get_stats()['estimated_cost']:.3f}")
        else:
            print("⚠️  API returned no result")
            
    except Exception as e:
        print(f"❌ API call failed: {e}")

def test_endorsement_search(fallback):
    """Test endorsement search"""
    print("\n" + "="*70)
    print("TEST 6: Endorsement Search")
    print("="*70)
    
    if not fallback.enabled:
        print("⚠️  Skipping endorsement test - no API key set")
        return
    
    print("Testing endorsement search for Patrick Mahomes...")
    
    try:
        result = fallback.search_endorsements('Patrick Mahomes', 'NFL')
        
        print(f"Endorsements found: {len(result.get('endorsements', []))}")
        if result.get('endorsements'):
            print(f"   Brands: {', '.join(result['endorsements'][:5])}")
        if result.get('endorsement_value'):
            print(f"   Estimated value: ${result['endorsement_value']:,.0f}")
        
        print("✅ Endorsement search completed")
            
    except Exception as e:
        print(f"❌ Endorsement search failed: {e}")

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("PERPLEXITY AI FALLBACK - UNIT TESTS")
    print("="*70)
    
    # Initialize
    fallback = test_initialization()
    
    # Structure tests (work without API key)
    test_query_builder(fallback)
    test_response_parser(fallback)
    test_cost_tracking(fallback)
    
    # Live tests (require API key)
    test_live_api(fallback)
    test_endorsement_search(fallback)
    
    print("\n" + "="*70)
    print("TESTS COMPLETE")
    print("="*70)
    
    if fallback.enabled:
        stats = fallback.get_stats()
        print(f"\nTotal API calls made: {stats['calls_made']}")
        print(f"Total cost: ${stats['estimated_cost']:.3f}")
    else:
        print("\n⚠️  Live API tests skipped (no API key)")
        print("   Set PERPLEXITY_API_KEY environment variable to test live API")

if __name__ == "__main__":
    run_all_tests()

