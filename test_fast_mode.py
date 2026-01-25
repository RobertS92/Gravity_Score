#!/usr/bin/env python3
"""
Quick test to verify FAST_MODE optimizations work correctly
Tests parallel social media collection on 1 player
"""
import os
import sys
import time
from pathlib import Path

# Set FAST_MODE
os.environ['FAST_MODE'] = 'true'
os.environ['MAX_CONCURRENT_PLAYERS'] = '100'
os.environ['MAX_CONCURRENT_DATA_COLLECTORS'] = '30'

# Add paths
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(script_dir / 'gravity'))

# Import NFL collector
import importlib.util
scrape_file_path = script_dir / 'gravity' / 'scrape'
if not scrape_file_path.exists():
    scrape_file_path = script_dir / 'gravity' / 'scrape.py'

if not scrape_file_path.exists():
    raise ImportError(f"Could not find scrape module at {scrape_file_path}")

# Load the scrape module (handles files without .py extension)
try:
    spec = importlib.util.spec_from_file_location("scrape", scrape_file_path)
    if spec is not None and spec.loader is not None:
        scrape_module = importlib.util.module_from_spec(spec)
        sys.modules["scrape"] = scrape_module
        sys.modules["gravity.scrape"] = scrape_module
        spec.loader.exec_module(scrape_module)
    else:
        raise ValueError("spec_from_file_location returned None")
except (ValueError, AttributeError):
    # Fallback: load directly using exec
    scrape_module = type(sys.modules[__name__])('scrape')
    scrape_module.__file__ = str(scrape_file_path)
    scrape_module.__name__ = 'scrape'
    
    with open(scrape_file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    exec(compile(code, str(scrape_file_path), 'exec'), scrape_module.__dict__)
    
    sys.modules["scrape"] = scrape_module
    sys.modules["gravity.scrape"] = scrape_module

NFLPlayerCollector = scrape_module.NFLPlayerCollector
Config = scrape_module.Config

print("🚀 Testing FAST_MODE Optimizations")
print("="*70)
print(f"Configuration:")
print(f"  FAST_MODE: {Config.FAST_MODE}")
print(f"  MAX_CONCURRENT_PLAYERS: {Config.MAX_CONCURRENT_PLAYERS}")
print(f"  MAX_CONCURRENT_DATA_COLLECTORS: {Config.MAX_CONCURRENT_DATA_COLLECTORS}")
print(f"  PLAYER_TIMEOUT: {Config.PLAYER_TIMEOUT}s")
print(f"  REQUEST_DELAY: {Config.REQUEST_DELAY}s")
print(f"  MAX_NEWS_ARTICLES: {Config.MAX_NEWS_ARTICLES}")
print("="*70)
print()

# Test with Patrick Mahomes
print("Testing with Patrick Mahomes...")
start_time = time.time()

collector = NFLPlayerCollector(Config.FIRECRAWL_API_KEY)
player_data = collector.collect_player_data("Patrick Mahomes", "Kansas City Chiefs", "QB")

elapsed_time = time.time() - start_time

print()
print("="*70)
print("✅ TEST COMPLETE")
print("="*70)
print(f"Time: {elapsed_time:.1f} seconds")
print()
print("Data collected:")
print(f"  Instagram: {player_data.brand.instagram_handle} ({player_data.brand.instagram_followers:,} followers)")
print(f"  Twitter: {player_data.brand.twitter_handle} ({player_data.brand.twitter_followers:,} followers)")
print(f"  TikTok: {player_data.brand.tiktok_handle} ({player_data.brand.tiktok_followers:,} followers)")
print(f"  Contract: ${player_data.identity.contract_value:,.0f}" if player_data.identity.contract_value else "  Contract: Unknown")
print(f"  News Headlines: {player_data.brand.news_headline_count_30d}")
print()

if elapsed_time < 60:
    print(f"⚡ FAST! Completed in {elapsed_time:.1f}s")
    print(f"   Projected full scrape: ~{(2500 / Config.MAX_CONCURRENT_PLAYERS) * elapsed_time / 3600:.1f} hours")
else:
    print(f"⚠️  Slower than expected ({elapsed_time:.1f}s)")
    print(f"   Check network connection and API availability")

print("="*70)
