"""
Performance and Integration Tests for Async Scraper Enhancements
Tests async functionality, speed improvements, and AI extraction
"""

import asyncio
import time
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gravity.nil.connector_orchestrator import ConnectorOrchestrator
from gravity.nil.connectors import On3Connector
from gravity.ai.extractor import AIExtractor


class AsyncPerformanceTester:
    """Test async performance improvements"""
    
    def __init__(self):
        self.orchestrator = ConnectorOrchestrator()
        self.test_athletes = [
            {'name': 'Shedeur Sanders', 'school': 'Colorado', 'sport': 'football'},
            {'name': 'Arch Manning', 'school': 'Texas', 'sport': 'football'},
            {'name': 'Travis Hunter', 'school': 'Colorado', 'sport': 'football'}
        ]
    
    async def test_async_vs_sync_speed(self):
        """Compare async vs sync collection speed"""
        print("\n" + "="*70)
        print("TEST 1: Async vs Sync Performance Comparison")
        print("="*70)
        
        athlete = self.test_athletes[0]
        
        # Test sync (original ThreadPoolExecutor approach)
        print(f"\n⏱️  Testing SYNC collection for {athlete['name']}...")
        start_sync = time.time()
        
        # Create new orchestrator to avoid async client caching
        sync_orchestrator = ConnectorOrchestrator()
        sync_results = sync_orchestrator.collect_all(
            athlete['name'],
            athlete['school'],
            athlete['sport'],
            save_raw=False
        )
        
        sync_duration = time.time() - start_sync
        sync_sources = len(sync_results['sources'])
        
        print(f"✅ SYNC completed in {sync_duration:.2f}s")
        print(f"   Sources successful: {sync_sources}/6")
        
        # Small delay between tests
        await asyncio.sleep(2)
        
        # Test async (new asyncio.gather approach)
        print(f"\n⚡ Testing ASYNC collection for {athlete['name']}...")
        start_async = time.time()
        
        async_results = await self.orchestrator.collect_all_async(
            athlete['name'],
            athlete['school'],
            athlete['sport'],
            save_raw=False
        )
        
        async_duration = time.time() - start_async
        async_sources = len(async_results['sources'])
        
        print(f"✅ ASYNC completed in {async_duration:.2f}s")
        print(f"   Sources successful: {async_sources}/6")
        
        # Calculate improvement
        speedup = ((sync_duration - async_duration) / sync_duration) * 100
        
        print(f"\n📊 RESULTS:")
        print(f"   Sync time:  {sync_duration:.2f}s")
        print(f"   Async time: {async_duration:.2f}s")
        print(f"   Speedup:    {speedup:.1f}% faster")
        print(f"   Target:     <10s per athlete")
        
        if async_duration < 10:
            print(f"   ✅ PASSED: Under 10 second target!")
        else:
            print(f"   ⚠️  WARNING: Slower than 10 second target")
        
        return {
            'sync_duration': sync_duration,
            'async_duration': async_duration,
            'speedup_percent': speedup,
            'passed': async_duration < 10
        }
    
    async def test_parallel_execution(self):
        """Test true parallel execution with multiple athletes"""
        print("\n" + "="*70)
        print("TEST 2: Parallel Multi-Athlete Collection")
        print("="*70)
        
        print(f"\n🚀 Collecting data for {len(self.test_athletes)} athletes in parallel...")
        start = time.time()
        
        # Create tasks for all athletes
        tasks = [
            self.orchestrator.collect_all_async(
                athlete['name'],
                athlete['school'],
                athlete['sport'],
                save_raw=False
            )
            for athlete in self.test_athletes
        ]
        
        # Run all in parallel
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start
        
        # Count successes
        successful = sum(1 for r in all_results if not isinstance(r, Exception) and r.get('sources'))
        
        print(f"✅ Collected data for {successful}/{len(self.test_athletes)} athletes")
        print(f"⏱️  Total time: {duration:.2f}s")
        print(f"📊 Average per athlete: {duration/len(self.test_athletes):.2f}s")
        
        if duration < 15:  # Should be faster than sequential
            print(f"✅ PASSED: Parallel execution is efficient")
        else:
            print(f"⚠️  WARNING: Parallel execution slower than expected")
        
        return {
            'total_duration': duration,
            'avg_per_athlete': duration / len(self.test_athletes),
            'successful': successful,
            'passed': duration < 15
        }
    
    async def test_ai_extraction(self):
        """Test AI extraction fallback"""
        print("\n" + "="*70)
        print("TEST 3: AI Extraction Fallback")
        print("="*70)
        
        # Check if OpenAI key is available
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            print("⚠️  SKIPPED: OPENAI_API_KEY not set")
            return {'skipped': True}
        
        print("\n🤖 Testing AI extraction with sample text...")
        
        sample_text = """
        Shedeur Sanders has signed major NIL deals with Nike, Gatorade, and Beats by Dre.
        His partnership with Nike is estimated at $500K annually. He also has a local 
        deal with a Colorado car dealership worth approximately $50,000.
        """
        
        extractor = AIExtractor()
        
        try:
            start = time.time()
            deals = extractor.extract(
                text=sample_text,
                extraction_type='nil_deals',
                context={'athlete_name': 'Shedeur Sanders'}
            )
            duration = time.time() - start
            
            print(f"✅ AI extraction completed in {duration:.2f}s")
            
            if deals:
                print(f"📋 Extracted {len(deals)} deals:")
                for deal in deals:
                    brand = deal.get('brand', 'Unknown')
                    deal_type = deal.get('type', 'Unknown')
                    value = deal.get('value', 'Not specified')
                    print(f"   - {brand} ({deal_type}): {value}")
                
                print(f"✅ PASSED: AI extraction working")
                return {'passed': True, 'deals_found': len(deals)}
            else:
                print(f"⚠️  WARNING: No deals extracted")
                return {'passed': False, 'deals_found': 0}
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return {'passed': False, 'error': str(e)}
    
    async def test_connector_async_methods(self):
        """Test individual connector async methods"""
        print("\n" + "="*70)
        print("TEST 4: Individual Connector Async Methods")
        print("="*70)
        
        connector = On3Connector()
        athlete = self.test_athletes[0]
        
        print(f"\n🔍 Testing On3Connector.fetch_raw_async()...")
        
        try:
            start = time.time()
            raw_data = await connector.fetch_raw_async(
                athlete['name'],
                athlete['school'],
                athlete['sport']
            )
            duration = time.time() - start
            
            if raw_data:
                print(f"✅ Async fetch completed in {duration:.2f}s")
                print(f"   Data keys: {list(raw_data.keys())}")
                print(f"✅ PASSED: Connector async method working")
                return {'passed': True, 'duration': duration}
            else:
                print(f"⚠️  No data returned (may be normal for test)")
                return {'passed': True, 'duration': duration, 'no_data': True}
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return {'passed': False, 'error': str(e)}
    
    async def test_rate_limiting(self):
        """Test optimized rate limiting"""
        print("\n" + "="*70)
        print("TEST 5: Rate Limiting Optimization")
        print("="*70)
        
        on3 = On3Connector()
        
        print(f"\n⚙️  On3Connector rate limit: {on3.rate_limit_delay}s")
        
        if on3.rate_limit_delay == 0.5:
            print(f"✅ PASSED: On3 rate limit optimized to 0.5s")
            passed = True
        else:
            print(f"❌ FAILED: Expected 0.5s, got {on3.rate_limit_delay}s")
            passed = False
        
        return {'passed': passed, 'rate_limit': on3.rate_limit_delay}
    
    async def run_all_tests(self):
        """Run all performance tests"""
        print("\n" + "="*70)
        print("🧪 ASYNC PERFORMANCE & INTEGRATION TEST SUITE")
        print("="*70)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        results = {}
        
        # Run tests
        results['async_vs_sync'] = await self.test_async_vs_sync_speed()
        results['parallel'] = await self.test_parallel_execution()
        results['ai_extraction'] = await self.test_ai_extraction()
        results['connector_async'] = await self.test_connector_async_methods()
        results['rate_limiting'] = await self.test_rate_limiting()
        
        # Summary
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for r in results.values() 
                    if not r.get('skipped') and r.get('passed', False))
        total = sum(1 for r in results.values() if not r.get('skipped'))
        
        print(f"\n✅ Passed: {passed}/{total} tests")
        
        if results['async_vs_sync'].get('passed'):
            speedup = results['async_vs_sync']['speedup_percent']
            print(f"⚡ Speed improvement: {speedup:.1f}% faster")
        
        print("\n" + "="*70)
        
        return results


async def main():
    """Main test runner"""
    tester = AsyncPerformanceTester()
    results = await tester.run_all_tests()
    
    # Return exit code based on results
    all_passed = all(
        r.get('passed', False) or r.get('skipped', False)
        for r in results.values()
    )
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
