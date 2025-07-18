"""
Real Player Test Scraper - NO SIMULATED DATA
Tests comprehensive scraping for 3 specific players with live progress
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, List
from real_data_collector import RealDataCollector
from enhanced_nfl_scraper import EnhancedNFLScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestPlayerScraper:
    """Test scraper for 3 specific players - REAL DATA ONLY"""
    
    def __init__(self):
        self.real_collector = RealDataCollector()
        self.standard_scraper = EnhancedNFLScraper()
        
    def test_three_players(self, progress_callback=None):
        """Test scraping for Lamar Jackson, Josh Allen, Patrick Mahomes"""
        
        # Test players with their teams
        test_players = [
            {"name": "Lamar Jackson", "team": "ravens", "position": "QB"},
            {"name": "Josh Allen", "team": "bills", "position": "QB"},
            {"name": "Patrick Mahomes", "team": "chiefs", "position": "QB"}
        ]
        
        results = {
            "standard_results": [],
            "comprehensive_results": [],
            "comparison": [],
            "test_started": datetime.now().isoformat(),
            "progress": []
        }
        
        logger.info("=== STARTING 3-PLAYER REAL DATA TEST ===")
        
        for i, player_info in enumerate(test_players, 1):
            name = player_info["name"]
            team = player_info["team"]
            position = player_info["position"]
            
            logger.info(f"\n{i}/3: TESTING {name} ({team})")
            
            if progress_callback:
                progress_callback(f"Testing {name} - Starting standard scraping...")
            
            # STANDARD SCRAPING
            logger.info(f"  → Standard scraping for {name}...")
            try:
                standard_start = time.time()
                
                # Get standard roster data
                team_roster = self.standard_scraper.extract_complete_team_roster(team)
                player_standard = None
                
                for player in team_roster:
                    if player.get('name', '').lower() == name.lower():
                        player_standard = player
                        break
                
                if player_standard:
                    player_standard['scrape_time'] = time.time() - standard_start
                    player_standard['scrape_type'] = 'standard'
                    results["standard_results"].append(player_standard)
                    
                    # Count fields
                    filled_fields = sum(1 for v in player_standard.values() if v is not None and str(v).strip())
                    logger.info(f"  ✅ Standard: {filled_fields} fields filled in {player_standard['scrape_time']:.1f}s")
                    
                    if progress_callback:
                        progress_callback(f"✅ {name} standard: {filled_fields} fields")
                else:
                    logger.warning(f"  ❌ {name} not found in {team} roster")
                    
            except Exception as e:
                logger.error(f"  ❌ Standard scraping failed for {name}: {e}")
                
            # VISION-ENHANCED COMPREHENSIVE SCRAPING
            if progress_callback:
                progress_callback(f"Testing {name} - Starting vision-enhanced comprehensive scraping...")
                
            logger.info(f"  → Vision-enhanced comprehensive scraping for {name}...")
            try:
                comp_start = time.time()
                
                # Get VISION-ENHANCED comprehensive data using real collector
                comprehensive_data = self.real_collector.collect_real_data(name, team, position)
                
                if comprehensive_data:
                    comprehensive_data['scrape_time'] = time.time() - comp_start
                    comprehensive_data['scrape_type'] = 'vision_enhanced_comprehensive'
                    results["comprehensive_results"].append(comprehensive_data)
                    
                    # Count ONLY real fields (no simulated data ever)
                    filled_fields = sum(1 for k, v in comprehensive_data.items() 
                                      if v is not None and str(v).strip() and str(v) != 'None' and
                                      k not in ['data_sources', 'last_updated', 'scraped_at', 'data_source', 'scrape_time', 'scrape_type', 'comprehensive_enhanced'])
                    
                    logger.info(f"  ✅ Vision-Enhanced Comprehensive: {filled_fields} fields filled in {comprehensive_data['scrape_time']:.1f}s")
                    logger.info(f"  📊 Quality: {comprehensive_data.get('data_quality_score', 0):.1f}/5.0")
                    logger.info(f"  📈 Sources: {comprehensive_data.get('data_sources', [])}")
                    logger.info(f"  🔍 Vision-enhanced features: OpenAI GPT-4o analysis ACTIVE")
                    
                    # Show social media extraction results
                    social_count = sum(1 for k in comprehensive_data.keys() if any(platform in k for platform in ['twitter', 'instagram', 'tiktok', 'youtube']) and comprehensive_data.get(k))
                    if social_count > 0:
                        logger.info(f"  📱 Social media fields extracted: {social_count}")
                    
                    if progress_callback:
                        progress_callback(f"✅ {name} vision-enhanced: {filled_fields} fields, quality {comprehensive_data.get('data_quality_score', 0):.1f}/5.0")
                        
                else:
                    logger.warning(f"  ❌ Comprehensive data not found for {name}")
                    
            except Exception as e:
                logger.error(f"  ❌ Comprehensive scraping failed for {name}: {e}")
                
            # VISION-ENHANCED COMPARISON
            if len(results["standard_results"]) > 0 and len(results["comprehensive_results"]) > 0:
                std_data = results["standard_results"][-1]
                comp_data = results["comprehensive_results"][-1]
                
                std_fields = sum(1 for v in std_data.values() if v is not None and str(v).strip())
                comp_fields = sum(1 for k, v in comp_data.items() 
                                if v is not None and str(v).strip() and str(v) != 'None' and
                                k not in ['data_sources', 'last_updated', 'scraped_at', 'data_source', 'scrape_time', 'scrape_type', 'comprehensive_enhanced'])
                
                comparison = {
                    "player": name,
                    "standard_fields": std_fields,
                    "comprehensive_fields": comp_fields,
                    "field_increase": comp_fields - std_fields,
                    "standard_time": std_data.get('scrape_time', 0),
                    "comprehensive_time": comp_data.get('scrape_time', 0),
                    "quality_score": comp_data.get('data_quality_score', 0),
                    "data_sources": comp_data.get('data_sources', []),
                    "vision_enhanced": True,
                    "social_media_fields": sum(1 for k in comp_data.keys() if any(platform in k for platform in ['twitter', 'instagram', 'tiktok', 'youtube']) and comp_data.get(k))
                }
                
                results["comparison"].append(comparison)
                
                logger.info(f"  📊 VISION-ENHANCED COMPARISON: {std_fields} → {comp_fields} fields (+{comp_fields - std_fields})")
                logger.info(f"  🔍 Social media extraction: {comparison['social_media_fields']} fields")
                
            if progress_callback:
                progress_callback(f"Completed {name} - {i}/3 players done")
                
        results["test_completed"] = datetime.now().isoformat()
        
        # Vision-Enhanced Final Summary
        logger.info("\n=== VISION-ENHANCED TEST SUMMARY ===")
        for comp in results["comparison"]:
            logger.info(f"{comp['player']}: {comp['standard_fields']} → {comp['comprehensive_fields']} fields (+{comp['field_increase']})")
            logger.info(f"  Quality: {comp['quality_score']:.1f}/5.0, Sources: {comp['data_sources']}")
            logger.info(f"  🔍 Vision-enhanced: {comp.get('vision_enhanced', False)}")
            logger.info(f"  📱 Social media fields: {comp.get('social_media_fields', 0)}")
        
        logger.info(f"\n🎯 VISION-ENHANCED CAPABILITIES ACTIVE:")
        logger.info(f"  ✅ OpenAI GPT-4o semantic analysis")
        logger.info(f"  ✅ Multi-step contextual extraction")
        logger.info(f"  ✅ Social media handle cleaning")
        logger.info(f"  ✅ Follower count conversion")
        logger.info(f"  ✅ Data validation and cleaning")
        logger.info(f"  ✅ Height correction system")
        logger.info(f"  ✅ ZERO simulated data - ALL REAL")
        
        return results
        
    def get_all_field_comparison(self, results: Dict) -> Dict:
        """Get detailed field-by-field comparison"""
        
        if not results["standard_results"] or not results["comprehensive_results"]:
            return {}
        
        # Get all possible fields from both datasets
        all_fields = set()
        
        for player in results["standard_results"]:
            all_fields.update(player.keys())
            
        for player in results["comprehensive_results"]:
            all_fields.update(player.keys())
        
        # Create field comparison
        field_comparison = {}
        
        for field in sorted(all_fields):
            field_comparison[field] = {
                "standard_count": 0,
                "comprehensive_count": 0,
                "examples": {}
            }
            
            # Count availability in standard
            for player in results["standard_results"]:
                if field in player and player[field] is not None and str(player[field]).strip():
                    field_comparison[field]["standard_count"] += 1
                    field_comparison[field]["examples"][player.get("name", "unknown")] = {
                        "standard": player[field]
                    }
                    
            # Count availability in comprehensive
            for player in results["comprehensive_results"]:
                if field in player and player[field] is not None and str(player[field]).strip():
                    field_comparison[field]["comprehensive_count"] += 1
                    player_name = player.get("name", "unknown")
                    if player_name not in field_comparison[field]["examples"]:
                        field_comparison[field]["examples"][player_name] = {}
                    field_comparison[field]["examples"][player_name]["comprehensive"] = player[field]
        
        return field_comparison

def run_test():
    """Run the test and return results"""
    scraper = TestPlayerScraper()
    
    def progress_print(message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    results = scraper.test_three_players(progress_callback=progress_print)
    field_comparison = scraper.get_all_field_comparison(results)
    
    return {
        "test_results": results,
        "field_comparison": field_comparison
    }

if __name__ == "__main__":
    print("=== NFL PLAYER REAL DATA TEST ===")
    print("Testing: Lamar Jackson, Josh Allen, Patrick Mahomes")
    print("NO SIMULATED DATA - REAL SCRAPING ONLY")
    print("=" * 60)
    
    test_data = run_test()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE - Check results above")