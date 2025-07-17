#!/usr/bin/env python3
"""
Simple Firecrawl-based scraper for NFL data
Uses requests to interact with Firecrawl API directly
"""

import os
import json
import logging
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class SimpleFirecrawlScraper:
    """Simplified NFL scraper using Firecrawl API directly"""
    
    def __init__(self):
        self.api_key = os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable not set")
        
        self.base_url = "https://api.firecrawl.dev/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def scrape_url(self, url: str, formats: List[str] = None, json_options: Dict = None) -> Dict:
        """Scrape a URL using Firecrawl API"""
        if formats is None:
            formats = ["markdown"]
        
        payload = {
            "url": url,
            "formats": formats
        }
        
        if json_options:
            payload["jsonOptions"] = json_options
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {"success": False, "error": str(e)}
    
    def extract_structured_data(self, urls: List[str], prompt: str, schema: Dict = None) -> Dict:
        """Extract structured data using Firecrawl extract endpoint"""
        payload = {
            "urls": urls,
            "prompt": prompt
        }
        
        if schema:
            payload["schema"] = schema
        
        try:
            response = requests.post(
                f"{self.base_url}/extract",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            return {"success": False, "error": str(e)}
    
    def collect_player_data(self, player_name: str, team: str) -> Dict[str, Any]:
        """Collect comprehensive player data using Firecrawl"""
        logger.info(f"Collecting data for {player_name} ({team}) using Firecrawl")
        
        start_time = time.time()
        
        # Initialize player data
        player_data = {
            'name': player_name,
            'team': team,
            'position': None,
            'jersey_number': None,
            'height': None,
            'weight': None,
            'age': None,
            'college': None,
            'twitter_handle': None,
            'instagram_handle': None,
            'twitter_followers': None,
            'instagram_followers': None,
            'current_salary': None,
            'career_stats': None,
            'awards': None,
            'data_sources': [],
            'data_quality_score': 0,
            'collection_timestamp': datetime.now().isoformat(),
            'collection_duration': None
        }
        
        try:
            # 1. Extract biographical data from Wikipedia
            wikipedia_url = f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}"
            
            wiki_prompt = f"""Extract biographical information for NFL player {player_name}:
            - Age
            - Height and weight
            - College
            - Position
            - Jersey number
            - Birth date and place
            - Draft information
            Return as JSON with clear field names"""
            
            wiki_result = self.scrape_url(
                wikipedia_url, 
                formats=["json"],
                json_options={"prompt": wiki_prompt}
            )
            
            if wiki_result.get("success") and wiki_result.get("data", {}).get("json"):
                bio_data = wiki_result["data"]["json"]
                for field in ['age', 'height', 'weight', 'college', 'position', 'jersey_number']:
                    if field in bio_data:
                        player_data[field] = bio_data[field]
                player_data['data_sources'].append('Wikipedia')
            
            # 2. Extract social media data using web search
            social_prompt = f"""Find official social media accounts for NFL player {player_name}:
            - Twitter handle and follower count
            - Instagram handle and follower count
            - TikTok handle if available
            - YouTube channel if available
            Focus on verified accounts with high follower counts"""
            
            social_result = self.extract_structured_data(
                urls=[],
                prompt=social_prompt
            )
            
            if social_result.get("success") and social_result.get("data"):
                social_data = social_result["data"]
                if 'twitter_handle' in social_data:
                    player_data['twitter_handle'] = social_data['twitter_handle']
                if 'twitter_followers' in social_data:
                    player_data['twitter_followers'] = social_data['twitter_followers']
                if 'instagram_handle' in social_data:
                    player_data['instagram_handle'] = social_data['instagram_handle']
                if 'instagram_followers' in social_data:
                    player_data['instagram_followers'] = social_data['instagram_followers']
                player_data['data_sources'].append('Social Media Search')
            
            # 3. Extract contract data from Spotrac
            spotrac_url = f"https://www.spotrac.com/nfl/{player_name.lower().replace(' ', '-').replace(chr(39), '')}/"
            
            contract_prompt = f"""Extract contract information for NFL player {player_name}:
            - Current annual salary
            - Total contract value
            - Guaranteed money
            - Contract length
            - Career earnings
            Return as JSON with clear field names"""
            
            contract_result = self.scrape_url(
                spotrac_url,
                formats=["json"],
                json_options={"prompt": contract_prompt}
            )
            
            if contract_result.get("success") and contract_result.get("data", {}).get("json"):
                contract_data = contract_result["data"]["json"]
                if 'current_salary' in contract_data:
                    player_data['current_salary'] = contract_data['current_salary']
                player_data['data_sources'].append('Spotrac')
            
            # 4. Extract career stats from Pro Football Reference
            name_parts = player_name.lower().split()
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
                first_name = name_parts[0]
                pfr_id = f"{last_name[:4]}{first_name[:2]}00"
                pfr_url = f"https://www.pro-football-reference.com/players/{last_name[0].upper()}/{pfr_id}.htm"
                
                stats_prompt = f"""Extract career statistics for NFL player {player_name}:
                - Career games played
                - Career touchdowns
                - Career yards
                - Pro Bowl selections
                - All-Pro selections
                - Awards and achievements
                Return as JSON with clear field names"""
                
                stats_result = self.scrape_url(
                    pfr_url,
                    formats=["json"],
                    json_options={"prompt": stats_prompt}
                )
                
                if stats_result.get("success") and stats_result.get("data", {}).get("json"):
                    stats_data = stats_result["data"]["json"]
                    player_data['career_stats'] = json.dumps(stats_data)
                    if 'awards' in stats_data:
                        player_data['awards'] = stats_data['awards']
                    player_data['data_sources'].append('Pro Football Reference')
            
            # Calculate quality score
            filled_fields = sum(1 for v in player_data.values() if v is not None and v != '' and v != [])
            player_data['data_quality_score'] = round(min(filled_fields / 20 * 10, 10), 1)
            
            player_data['collection_duration'] = round(time.time() - start_time, 2)
            
            logger.info(f"Collected {filled_fields} fields for {player_name} from {len(player_data['data_sources'])} sources")
            
            return player_data
            
        except Exception as e:
            logger.error(f"Error collecting data for {player_name}: {e}")
            player_data['collection_duration'] = round(time.time() - start_time, 2)
            return player_data
    
    def collect_team_roster(self, team_name: str, players: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Collect comprehensive data for entire team roster"""
        logger.info(f"Collecting data for {len(players)} players from {team_name}")
        
        comprehensive_data = []
        
        for i, player in enumerate(players, 1):
            logger.info(f"Processing player {i}/{len(players)}: {player['name']}")
            
            try:
                player_data = self.collect_player_data(
                    player_name=player['name'],
                    team=team_name
                )
                comprehensive_data.append(player_data)
                
                # Respectful delay between requests
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to collect data for {player['name']}: {e}")
                # Add basic fallback data
                fallback_data = {
                    'name': player['name'],
                    'team': team_name,
                    'data_quality_score': 0.5,
                    'collection_timestamp': datetime.now().isoformat(),
                    'data_sources': []
                }
                comprehensive_data.append(fallback_data)
        
        logger.info(f"Completed roster collection for {team_name}: {len(comprehensive_data)} players")
        return comprehensive_data

# Test the scraper
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        scraper = SimpleFirecrawlScraper()
        
        # Test with a few players
        test_players = [
            {"name": "Brock Purdy", "team": "49ers"},
            {"name": "Christian McCaffrey", "team": "49ers"}
        ]
        
        results = []
        for player in test_players:
            result = scraper.collect_player_data(player['name'], player['team'])
            results.append(result)
            
            print(f"\n{'='*50}")
            print(f"Player: {result['name']}")
            print(f"Quality Score: {result['data_quality_score']}/10")
            print(f"Sources: {', '.join(result['data_sources'])}")
            print(f"Duration: {result['collection_duration']}s")
            
            # Show collected data
            for field in ['age', 'height', 'weight', 'college', 'position', 'twitter_handle', 'current_salary']:
                if result.get(field):
                    print(f"  {field}: {result[field]}")
        
        # Save results
        with open('simple_firecrawl_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to simple_firecrawl_results.json")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure FIRECRAWL_API_KEY is set in environment variables")