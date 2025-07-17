"""
Comprehensive NFL Player Data Scraper using Firecrawl
Leverages Firecrawl's advanced extraction capabilities for all 74 fields
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field
from firecrawl import FirecrawlApp, JsonConfig
import pandas as pd

logger = logging.getLogger(__name__)

# Pydantic schemas for structured data extraction
class PlayerBioSchema(BaseModel):
    """Schema for biographical information"""
    name: str = Field(description="Full player name")
    age: Optional[int] = Field(description="Player age in years")
    birth_date: Optional[str] = Field(description="Date of birth (YYYY-MM-DD)")
    birth_place: Optional[str] = Field(description="Place of birth (city, state)")
    hometown: Optional[str] = Field(description="Hometown")
    high_school: Optional[str] = Field(description="High school attended")
    college: Optional[str] = Field(description="College attended")
    height: Optional[str] = Field(description="Height (e.g., 6'2\")")
    weight: Optional[int] = Field(description="Weight in pounds")
    position: Optional[str] = Field(description="Playing position")
    jersey_number: Optional[int] = Field(description="Jersey number")

class PlayerDraftSchema(BaseModel):
    """Schema for draft information"""
    draft_year: Optional[int] = Field(description="Year drafted")
    draft_round: Optional[int] = Field(description="Round drafted")
    draft_pick: Optional[int] = Field(description="Pick number in draft")
    draft_team: Optional[str] = Field(description="Team that drafted the player")
    years_pro: Optional[int] = Field(description="Years as professional")

class PlayerCareerStatsSchema(BaseModel):
    """Schema for career statistics"""
    career_games: Optional[int] = Field(description="Total career games played")
    career_starts: Optional[int] = Field(description="Total career games started")
    career_yards: Optional[int] = Field(description="Total career yards")
    career_touchdowns: Optional[int] = Field(description="Total career touchdowns")
    career_receptions: Optional[int] = Field(description="Total career receptions")
    career_interceptions: Optional[int] = Field(description="Total career interceptions")
    career_sacks: Optional[int] = Field(description="Total career sacks")
    career_tackles: Optional[int] = Field(description="Total career tackles")
    pro_bowls: Optional[int] = Field(description="Number of Pro Bowl selections")
    all_pro: Optional[int] = Field(description="Number of All-Pro selections")

class PlayerContractSchema(BaseModel):
    """Schema for contract information"""
    current_salary: Optional[str] = Field(description="Current annual salary")
    contract_value: Optional[str] = Field(description="Total contract value")
    contract_years: Optional[int] = Field(description="Contract length in years")
    guaranteed_money: Optional[str] = Field(description="Guaranteed money")
    signing_bonus: Optional[str] = Field(description="Signing bonus")
    career_earnings: Optional[str] = Field(description="Total career earnings")
    cap_hit: Optional[str] = Field(description="Current year cap hit")

class PlayerSocialMediaSchema(BaseModel):
    """Schema for social media information"""
    twitter_handle: Optional[str] = Field(description="Twitter username without @")
    instagram_handle: Optional[str] = Field(description="Instagram username without @")
    tiktok_handle: Optional[str] = Field(description="TikTok username without @")
    youtube_handle: Optional[str] = Field(description="YouTube channel name")
    twitter_followers: Optional[int] = Field(description="Number of Twitter followers")
    instagram_followers: Optional[int] = Field(description="Number of Instagram followers")
    tiktok_followers: Optional[int] = Field(description="Number of TikTok followers")
    youtube_subscribers: Optional[int] = Field(description="Number of YouTube subscribers")
    twitter_verified: Optional[bool] = Field(description="Is Twitter account verified")
    instagram_verified: Optional[bool] = Field(description="Is Instagram account verified")

class PlayerAwardsSchema(BaseModel):
    """Schema for awards and achievements"""
    awards: Optional[List[str]] = Field(description="List of awards received")
    honors: Optional[List[str]] = Field(description="List of honors received")
    records: Optional[List[str]] = Field(description="List of records held")
    career_highlights: Optional[List[str]] = Field(description="Career highlights")
    championships: Optional[List[str]] = Field(description="Championships won")
    hall_of_fame: Optional[bool] = Field(description="Hall of Fame status")

class FirecrawlComprehensiveScraper:
    """Advanced NFL player data scraper using Firecrawl"""
    
    def __init__(self):
        # Initialize Firecrawl with API key
        self.api_key = os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable not set")
        
        self.app = FirecrawlApp(api_key=self.api_key)
        
        # URL generators for different data sources
        self.url_generators = {
            'nfl_roster': self._generate_nfl_roster_url,
            'wikipedia': self._generate_wikipedia_url,
            'pro_football_reference': self._generate_pfr_url,
            'spotrac': self._generate_spotrac_url,
            'twitter': self._generate_twitter_search_url,
            'instagram': self._generate_instagram_search_url,
            'google_search': self._generate_google_search_url
        }
        
    def collect_comprehensive_player_data(self, player_name: str, team: str) -> Dict[str, Any]:
        """Collect comprehensive data for a single player using Firecrawl's advanced features"""
        logger.info(f"Collecting comprehensive data for {player_name} ({team}) using Firecrawl")
        
        start_time = time.time()
        
        # Initialize comprehensive data structure with all 74 fields
        player_data = self._initialize_player_data(player_name, team)
        
        try:
            # 1. Extract biographical data from Wikipedia
            self._extract_wikipedia_data(player_data)
            
            # 2. Extract career statistics from Pro Football Reference  
            self._extract_pfr_stats(player_data)
            
            # 3. Extract contract data from Spotrac
            self._extract_spotrac_contract(player_data)
            
            # 4. Extract social media profiles and metrics
            self._extract_social_media_data(player_data)
            
            # 5. Extract awards and achievements
            self._extract_awards_data(player_data)
            
            # 6. Extract current NFL roster data
            self._extract_nfl_roster_data(player_data)
            
            # Calculate data quality metrics
            player_data['collection_duration'] = round(time.time() - start_time, 2)
            player_data['data_quality_score'] = self._calculate_quality_score(player_data)
            player_data['collection_timestamp'] = datetime.now().isoformat()
            
            filled_fields = self._count_filled_fields(player_data)
            logger.info(f"Completed data collection for {player_name}: {filled_fields}/74 fields filled")
            
            return player_data
            
        except Exception as e:
            logger.error(f"Error collecting data for {player_name}: {e}")
            player_data['collection_duration'] = round(time.time() - start_time, 2)
            player_data['data_quality_score'] = 1.0
            return player_data
    
    def _initialize_player_data(self, player_name: str, team: str) -> Dict[str, Any]:
        """Initialize comprehensive player data structure with all 74 fields"""
        return {
            # Basic Player Information (8 fields)
            'name': player_name,
            'team': team,
            'position': None,
            'jersey_number': None,
            'height': None,
            'weight': None,
            'age': None,
            'birth_date': None,
            
            # Social Media Profiles (16 fields)
            'twitter_handle': None,
            'twitter_followers': None,
            'twitter_following': None,
            'twitter_verified': None,
            'twitter_url': None,
            'instagram_handle': None,
            'instagram_followers': None,
            'instagram_following': None,
            'instagram_verified': None,
            'instagram_url': None,
            'tiktok_handle': None,
            'tiktok_followers': None,
            'tiktok_following': None,
            'tiktok_url': None,
            'youtube_handle': None,
            'youtube_subscribers': None,
            
            # Biographical Information (12 fields)
            'birth_place': None,
            'college': None,
            'draft_year': None,
            'draft_round': None,
            'draft_pick': None,
            'draft_team': None,
            'hometown': None,
            'high_school': None,
            'wikipedia_url': None,
            'wikipedia_summary': None,
            'personal_info': None,
            'years_pro': None,
            
            # Career Statistics (15 fields)
            'career_stats': None,
            'current_season_stats': None,
            'career_games': None,
            'career_starts': None,
            'career_touchdowns': None,
            'career_yards': None,
            'career_receptions': None,
            'career_interceptions': None,
            'career_sacks': None,
            'career_tackles': None,
            'pro_bowls': None,
            'all_pro': None,
            'rookie_year': None,
            'position_rank': None,
            'fantasy_points': None,
            
            # Contract & Financial Data (10 fields)
            'current_salary': None,
            'contract_value': None,
            'contract_years': None,
            'guaranteed_money': None,
            'signing_bonus': None,
            'career_earnings': None,
            'cap_hit': None,
            'dead_money': None,
            'spotrac_url': None,
            'market_value': None,
            
            # Awards & Achievements (8 fields)
            'awards': None,
            'honors': None,
            'records': None,
            'career_highlights': None,
            'championships': None,
            'hall_of_fame': None,
            'rookie_awards': None,
            'team_records': None,
            
            # Data Quality & Metadata (5 fields)
            'data_sources': [],
            'data_quality_score': None,
            'collection_timestamp': None,
            'collection_duration': None,
            'scraped_at': datetime.now().isoformat()
        }
    
    def _extract_wikipedia_data(self, player_data: Dict[str, Any]) -> None:
        """Extract biographical data from Wikipedia using Firecrawl's structured extraction"""
        try:
            player_name = player_data['name']
            wikipedia_url = self._generate_wikipedia_url(player_name)
            
            # Use Firecrawl's extract endpoint with schema
            json_config = JsonConfig(schema=PlayerBioSchema)
            
            result = self.app.scrape_url(
                wikipedia_url,
                formats=['json'],
                json_options=json_config,
                timeout=30000
            )
            
            if result.success and result.data.get('json'):
                bio_data = result.data['json']
                
                # Update player data with Wikipedia information
                for field in ['age', 'birth_date', 'birth_place', 'hometown', 'high_school', 
                             'college', 'height', 'weight', 'position', 'jersey_number']:
                    if bio_data.get(field):
                        player_data[field] = bio_data[field]
                
                player_data['wikipedia_url'] = wikipedia_url
                player_data['wikipedia_summary'] = bio_data.get('name', '') + ' biographical information'
                player_data['data_sources'].append('Wikipedia')
                
        except Exception as e:
            logger.warning(f"Wikipedia extraction failed: {e}")
    
    def _extract_pfr_stats(self, player_data: Dict[str, Any]) -> None:
        """Extract career statistics from Pro Football Reference"""
        try:
            player_name = player_data['name']
            pfr_url = self._generate_pfr_url(player_name)
            
            # Use Firecrawl's extract with prompt for career stats
            result = self.app.scrape_url(
                pfr_url,
                formats=['json'],
                json_options={
                    'prompt': f"""Extract career statistics for {player_name}:
                    - Total career games played and started
                    - Career yards, touchdowns, receptions, interceptions, sacks, tackles
                    - Pro Bowl selections and All-Pro selections
                    - Return as structured JSON with clear field names"""
                },
                timeout=30000
            )
            
            if result.success and result.data.get('json'):
                stats_data = result.data['json']
                
                # Map extracted stats to player data
                stat_mappings = {
                    'career_games': ['games', 'games_played', 'total_games'],
                    'career_starts': ['starts', 'games_started', 'total_starts'],
                    'career_yards': ['yards', 'total_yards', 'career_yards'],
                    'career_touchdowns': ['touchdowns', 'tds', 'total_touchdowns'],
                    'career_receptions': ['receptions', 'rec', 'total_receptions'],
                    'career_interceptions': ['interceptions', 'int', 'total_interceptions'],
                    'career_sacks': ['sacks', 'total_sacks'],
                    'career_tackles': ['tackles', 'total_tackles'],
                    'pro_bowls': ['pro_bowls', 'pro_bowl_selections'],
                    'all_pro': ['all_pro', 'all_pro_selections']
                }
                
                for field, possible_keys in stat_mappings.items():
                    for key in possible_keys:
                        if key in stats_data:
                            player_data[field] = stats_data[key]
                            break
                
                player_data['career_stats'] = json.dumps(stats_data)
                player_data['data_sources'].append('Pro Football Reference')
                
        except Exception as e:
            logger.warning(f"PFR stats extraction failed: {e}")
    
    def _extract_spotrac_contract(self, player_data: Dict[str, Any]) -> None:
        """Extract contract data from Spotrac"""
        try:
            player_name = player_data['name']
            spotrac_url = self._generate_spotrac_url(player_name)
            
            # Use Firecrawl's extract with schema for contract data
            json_config = JsonConfig(schema=PlayerContractSchema)
            
            result = self.app.scrape_url(
                spotrac_url,
                formats=['json'],
                json_options=json_config,
                timeout=30000
            )
            
            if result.success and result.data.get('json'):
                contract_data = result.data['json']
                
                # Update player data with contract information
                contract_fields = ['current_salary', 'contract_value', 'contract_years',
                                 'guaranteed_money', 'signing_bonus', 'career_earnings', 'cap_hit']
                
                for field in contract_fields:
                    if contract_data.get(field):
                        player_data[field] = contract_data[field]
                
                player_data['spotrac_url'] = spotrac_url
                player_data['data_sources'].append('Spotrac')
                
        except Exception as e:
            logger.warning(f"Spotrac contract extraction failed: {e}")
    
    def _extract_social_media_data(self, player_data: Dict[str, Any]) -> None:
        """Extract social media profiles and metrics using Firecrawl's web search"""
        try:
            player_name = player_data['name']
            
            # Use Firecrawl's extract with web search enabled
            result = self.app.extract(
                urls=[],  # No specific URLs - let Firecrawl search
                prompt=f"""Find social media profiles for NFL player {player_name}:
                - Twitter handle, follower count, verification status
                - Instagram handle, follower count, verification status  
                - TikTok handle, follower count
                - YouTube channel name, subscriber count
                Include actual URLs to the profiles""",
                enable_web_search=True
            )
            
            if result.success and result.data:
                social_data = result.data
                
                # Extract social media information
                if 'twitter_handle' in social_data:
                    player_data['twitter_handle'] = social_data['twitter_handle']
                    player_data['twitter_followers'] = social_data.get('twitter_followers')
                    player_data['twitter_verified'] = social_data.get('twitter_verified')
                    player_data['twitter_url'] = social_data.get('twitter_url')
                
                if 'instagram_handle' in social_data:
                    player_data['instagram_handle'] = social_data['instagram_handle']
                    player_data['instagram_followers'] = social_data.get('instagram_followers')
                    player_data['instagram_verified'] = social_data.get('instagram_verified')
                    player_data['instagram_url'] = social_data.get('instagram_url')
                
                if 'tiktok_handle' in social_data:
                    player_data['tiktok_handle'] = social_data['tiktok_handle']
                    player_data['tiktok_followers'] = social_data.get('tiktok_followers')
                    player_data['tiktok_url'] = social_data.get('tiktok_url')
                
                if 'youtube_handle' in social_data:
                    player_data['youtube_handle'] = social_data['youtube_handle']
                    player_data['youtube_subscribers'] = social_data.get('youtube_subscribers')
                    player_data['youtube_url'] = social_data.get('youtube_url')
                
                player_data['data_sources'].append('Social Media Search')
                
        except Exception as e:
            logger.warning(f"Social media extraction failed: {e}")
    
    def _extract_awards_data(self, player_data: Dict[str, Any]) -> None:
        """Extract awards and achievements using Firecrawl's intelligent search"""
        try:
            player_name = player_data['name']
            
            # Use Firecrawl's extract with web search for awards
            result = self.app.extract(
                urls=[],
                prompt=f"""Find awards and achievements for NFL player {player_name}:
                - NFL awards (MVP, OPOY, DPOY, etc.)
                - Pro Bowl selections
                - All-Pro selections
                - Super Bowl championships
                - College awards
                - Rookie awards
                - Team records
                - Hall of Fame status""",
                enable_web_search=True
            )
            
            if result.success and result.data:
                awards_data = result.data
                
                # Extract awards information
                if 'awards' in awards_data:
                    player_data['awards'] = awards_data['awards']
                if 'honors' in awards_data:
                    player_data['honors'] = awards_data['honors']
                if 'records' in awards_data:
                    player_data['records'] = awards_data['records']
                if 'career_highlights' in awards_data:
                    player_data['career_highlights'] = awards_data['career_highlights']
                if 'championships' in awards_data:
                    player_data['championships'] = awards_data['championships']
                if 'hall_of_fame' in awards_data:
                    player_data['hall_of_fame'] = awards_data['hall_of_fame']
                
                player_data['data_sources'].append('Awards Search')
                
        except Exception as e:
            logger.warning(f"Awards extraction failed: {e}")
    
    def _extract_nfl_roster_data(self, player_data: Dict[str, Any]) -> None:
        """Extract current NFL roster data"""
        try:
            team = player_data['team']
            nfl_url = self._generate_nfl_roster_url(team)
            
            # Use Firecrawl to extract roster data
            result = self.app.scrape_url(
                nfl_url,
                formats=['json'],
                json_options={
                    'prompt': f"""Extract current roster information for {player_data['name']}:
                    - Current jersey number
                    - Position
                    - Height and weight
                    - Experience level
                    - Current season stats if available"""
                },
                timeout=30000
            )
            
            if result.success and result.data.get('json'):
                roster_data = result.data['json']
                
                # Update basic information
                if 'jersey_number' in roster_data:
                    player_data['jersey_number'] = roster_data['jersey_number']
                if 'position' in roster_data:
                    player_data['position'] = roster_data['position']
                if 'height' in roster_data:
                    player_data['height'] = roster_data['height']
                if 'weight' in roster_data:
                    player_data['weight'] = roster_data['weight']
                if 'experience' in roster_data:
                    player_data['years_pro'] = roster_data['experience']
                
                player_data['data_sources'].append('NFL.com')
                
        except Exception as e:
            logger.warning(f"NFL roster extraction failed: {e}")
    
    def _generate_wikipedia_url(self, player_name: str) -> str:
        """Generate Wikipedia URL for player"""
        formatted_name = player_name.replace(' ', '_')
        return f"https://en.wikipedia.org/wiki/{formatted_name}"
    
    def _generate_pfr_url(self, player_name: str) -> str:
        """Generate Pro Football Reference URL for player"""
        name_parts = player_name.lower().split()
        if len(name_parts) >= 2:
            last_name = name_parts[-1]
            first_name = name_parts[0]
            pfr_id = f"{last_name[:4]}{first_name[:2]}00"
            return f"https://www.pro-football-reference.com/players/{last_name[0].upper()}/{pfr_id}.htm"
        return "https://www.pro-football-reference.com"
    
    def _generate_spotrac_url(self, player_name: str) -> str:
        """Generate Spotrac URL for player"""
        name_slug = player_name.lower().replace(' ', '-').replace("'", "")
        return f"https://www.spotrac.com/nfl/{name_slug}/"
    
    def _generate_nfl_roster_url(self, team: str) -> str:
        """Generate NFL.com roster URL for team"""
        team_slug = team.lower().replace(' ', '-')
        return f"https://www.nfl.com/teams/{team_slug}/roster"
    
    def _generate_twitter_search_url(self, player_name: str) -> str:
        """Generate Twitter search URL for player"""
        return f"https://twitter.com/search?q={player_name.replace(' ', '%20')}%20NFL"
    
    def _generate_instagram_search_url(self, player_name: str) -> str:
        """Generate Instagram search URL for player"""
        return f"https://www.instagram.com/explore/tags/{player_name.replace(' ', '').lower()}/"
    
    def _generate_google_search_url(self, query: str) -> str:
        """Generate Google search URL for query"""
        return f"https://www.google.com/search?q={query.replace(' ', '+')}"
    
    def _calculate_quality_score(self, player_data: Dict[str, Any]) -> float:
        """Calculate data quality score based on filled fields and sources"""
        total_fields = 74
        filled_fields = self._count_filled_fields(player_data)
        
        # Base score from completion percentage
        completion_score = (filled_fields / total_fields) * 6
        
        # Bonus for multiple sources
        source_bonus = min(len(player_data['data_sources']) * 0.8, 3.0)
        
        # Bonus for key field completion
        key_fields = ['age', 'position', 'college', 'career_stats', 'twitter_handle', 'current_salary']
        key_bonus = sum(1 for field in key_fields if player_data.get(field)) * 0.2
        
        total_score = completion_score + source_bonus + key_bonus
        return round(min(total_score, 10.0), 1)
    
    def _count_filled_fields(self, player_data: Dict[str, Any]) -> int:
        """Count filled fields in player data"""
        filled_count = 0
        excluded_fields = ['data_sources', 'collection_timestamp', 'collection_duration', 
                          'scraped_at', 'data_quality_score']
        
        for key, value in player_data.items():
            if key not in excluded_fields and value is not None and value != '' and value != []:
                filled_count += 1
        
        return filled_count
    
    def batch_collect_team_data(self, team_roster: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Collect comprehensive data for entire team roster"""
        logger.info(f"Starting batch collection for {len(team_roster)} players")
        
        comprehensive_roster = []
        
        for i, player in enumerate(team_roster, 1):
            logger.info(f"Processing player {i}/{len(team_roster)}: {player['name']}")
            
            try:
                comprehensive_data = self.collect_comprehensive_player_data(
                    player_name=player['name'],
                    team=player['team']
                )
                comprehensive_roster.append(comprehensive_data)
                
                # Respectful delay between requests
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to collect data for {player['name']}: {e}")
                # Add basic fallback data
                fallback_data = self._initialize_player_data(player['name'], player['team'])
                fallback_data['data_quality_score'] = 0.5
                comprehensive_roster.append(fallback_data)
        
        logger.info(f"Batch collection completed for {len(comprehensive_roster)} players")
        return comprehensive_roster
    
    def save_comprehensive_data(self, comprehensive_data: List[Dict[str, Any]], 
                              filename: Optional[str] = None) -> str:
        """Save comprehensive data to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_nfl_data_{timestamp}.csv"
        
        # Convert to DataFrame and save
        df = pd.DataFrame(comprehensive_data)
        df.to_csv(filename, index=False)
        
        logger.info(f"Comprehensive data saved to {filename}")
        return filename