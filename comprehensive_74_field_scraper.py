"""
Comprehensive 74-Field NFL Player Data Scraper
Collects all required fields for complete player profiles
"""

import requests
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import logging
from urllib.parse import quote_plus
from social_media_agent import SocialMediaAgent
from web_search_social_scraper import WebSearchSocialScraper
from nfl_gravity.extractors.wikipedia import WikipediaExtractor
from nfl_gravity.core.config import Config
from enhanced_age_collector import EnhancedAgeCollector

logger = logging.getLogger(__name__)

class Comprehensive74FieldScraper:
    """Comprehensive scraper for all 74 NFL player data fields"""
    
    def __init__(self):
        self.config = Config()
        self.social_agent = SocialMediaAgent()
        self.web_scraper = WebSearchSocialScraper()
        self.wiki_extractor = WikipediaExtractor(self.config)
        self.age_collector = EnhancedAgeCollector()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def collect_all_fields(self, player_name: str, team: str, position: str = None) -> Dict:
        """Collect all 74 data fields for a player"""
        logger.info(f"Collecting ALL 74 fields for {player_name} ({team})")
        
        # Initialize all 74 fields
        data = {
            # Basic Player Information (8 fields)
            'name': player_name,
            'team': team,
            'position': position,
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
            'collection_timestamp': datetime.now().isoformat(),
            'collection_duration': None,
            'scraped_at': datetime.now().isoformat()
        }
        
        start_time = time.time()
        
        # Collect data from multiple sources
        try:
            # 1. Basic player info from NFL.com
            self._collect_nfl_basic_info(data)
            
            # 2. Social media profiles 
            self._collect_social_media_data(data)
            
            # 3. Wikipedia biographical data
            self._collect_wikipedia_data(data)
            
            # 4. Career statistics from Pro Football Reference
            self._collect_career_stats(data)
            
            # 5. Contract/financial data from Spotrac
            self._collect_contract_data(data)
            
            # 6. Awards and achievements
            self._collect_awards_data(data)
            
            # 7. Enhanced age collection
            self._collect_enhanced_age(data)
            
            # Calculate collection duration
            data['collection_duration'] = round(time.time() - start_time, 2)
            
            # Calculate data quality score
            data['data_quality_score'] = self._calculate_quality_score(data)
            
            logger.info(f"Collected {self._count_filled_fields(data)}/74 fields for {player_name}")
            
        except Exception as e:
            logger.error(f"Error collecting data for {player_name}: {e}")
            data['collection_duration'] = round(time.time() - start_time, 2)
            data['data_quality_score'] = 1.0
            
        return data
    
    def _collect_nfl_basic_info(self, data: Dict) -> None:
        """Collect basic player info from NFL.com"""
        try:
            # Search for player on NFL.com
            player_name = data['name']
            team = data['team']
            
            # Try NFL.com roster page
            nfl_url = f"https://www.nfl.com/teams/{team.lower()}/roster"
            response = self.session.get(nfl_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for player in roster
                player_divs = soup.find_all('div', class_='player-card')
                for div in player_divs:
                    name_elem = div.find('h3') or div.find('h4')
                    if name_elem and player_name.lower() in name_elem.get_text().lower():
                        # Extract basic info
                        stats_div = div.find('div', class_='player-stats')
                        if stats_div:
                            stats_text = stats_div.get_text()
                            
                            # Parse height, weight, age
                            height_match = re.search(r'(\d+)\'\s*(\d+)"', stats_text)
                            if height_match:
                                data['height'] = f"{height_match.group(1)}'{height_match.group(2)}\""
                            
                            weight_match = re.search(r'(\d+)\s*lbs', stats_text)
                            if weight_match:
                                data['weight'] = int(weight_match.group(1))
                            
                            # Jersey number
                            jersey_match = re.search(r'#(\d+)', stats_text)
                            if jersey_match:
                                data['jersey_number'] = int(jersey_match.group(1))
                
                data['data_sources'].append('NFL.com')
                
        except Exception as e:
            logger.warning(f"NFL.com scraping failed: {e}")
    
    def _collect_social_media_data(self, data: Dict) -> None:
        """Collect social media profiles and metrics"""
        try:
            player_name = data['name']
            
            # Use existing social media agent
            social_data = self.social_agent.search_social_profiles(player_name)
            
            if social_data:
                # Twitter data
                if 'twitter' in social_data:
                    twitter = social_data['twitter']
                    data['twitter_handle'] = twitter.get('handle')
                    data['twitter_followers'] = twitter.get('followers')
                    data['twitter_following'] = twitter.get('following')
                    data['twitter_verified'] = twitter.get('verified')
                    data['twitter_url'] = twitter.get('url')
                
                # Instagram data
                if 'instagram' in social_data:
                    instagram = social_data['instagram']
                    data['instagram_handle'] = instagram.get('handle')
                    data['instagram_followers'] = instagram.get('followers')
                    data['instagram_following'] = instagram.get('following')
                    data['instagram_verified'] = instagram.get('verified')
                    data['instagram_url'] = instagram.get('url')
                
                # TikTok data
                if 'tiktok' in social_data:
                    tiktok = social_data['tiktok']
                    data['tiktok_handle'] = tiktok.get('handle')
                    data['tiktok_followers'] = tiktok.get('followers')
                    data['tiktok_following'] = tiktok.get('following')
                    data['tiktok_url'] = tiktok.get('url')
                
                # YouTube data
                if 'youtube' in social_data:
                    youtube = social_data['youtube']
                    data['youtube_handle'] = youtube.get('handle')
                    data['youtube_subscribers'] = youtube.get('subscribers')
                    data['youtube_url'] = youtube.get('url')
                
                data['data_sources'].append('Social Media Agent')
                
        except Exception as e:
            logger.warning(f"Social media collection failed: {e}")
    
    def _collect_wikipedia_data(self, data: Dict) -> None:
        """Collect biographical data from Wikipedia"""
        try:
            player_name = data['name']
            
            # Use existing Wikipedia extractor
            wiki_data = self.wiki_extractor.extract_player_data(player_name)
            
            if wiki_data:
                data['birth_place'] = wiki_data.get('birthplace')
                data['college'] = wiki_data.get('college')
                data['draft_year'] = wiki_data.get('draft_year')
                data['draft_round'] = wiki_data.get('draft_round')
                data['draft_pick'] = wiki_data.get('draft_pick')
                data['draft_team'] = wiki_data.get('draft_team')
                data['hometown'] = wiki_data.get('hometown')
                data['high_school'] = wiki_data.get('high_school')
                data['wikipedia_url'] = wiki_data.get('wikipedia_url')
                data['wikipedia_summary'] = wiki_data.get('summary')
                data['personal_info'] = wiki_data.get('personal_info')
                data['career_highlights'] = wiki_data.get('career_highlights')
                data['awards'] = wiki_data.get('awards')
                
                data['data_sources'].append('Wikipedia')
                
        except Exception as e:
            logger.warning(f"Wikipedia collection failed: {e}")
    
    def _collect_career_stats(self, data: Dict) -> None:
        """Collect career statistics from Pro Football Reference"""
        try:
            player_name = data['name']
            
            # Generate Pro Football Reference URL
            name_parts = player_name.lower().split()
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
                first_name = name_parts[0]
                
                # PFR URL format: /players/L/LastnFirs00.htm
                pfr_id = f"{last_name[:4]}{first_name[:2]}00"
                pfr_url = f"https://www.pro-football-reference.com/players/{last_name[0].upper()}/{pfr_id}.htm"
                
                response = self.session.get(pfr_url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Extract career stats
                    stats_table = soup.find('table', {'id': 'stats'})
                    if stats_table:
                        career_row = stats_table.find('tfoot')
                        if career_row:
                            cells = career_row.find_all('td')
                            if len(cells) > 5:
                                data['career_games'] = self._extract_stat(cells, 'games')
                                data['career_starts'] = self._extract_stat(cells, 'starts')
                                data['career_yards'] = self._extract_stat(cells, 'yards')
                                data['career_touchdowns'] = self._extract_stat(cells, 'touchdowns')
                    
                    # Extract Pro Bowl and All-Pro info
                    honors_div = soup.find('div', {'id': 'honors'})
                    if honors_div:
                        honors_text = honors_div.get_text()
                        pro_bowl_matches = re.findall(r'Pro Bowl.*?(\d+)', honors_text)
                        if pro_bowl_matches:
                            data['pro_bowls'] = len(pro_bowl_matches)
                        
                        all_pro_matches = re.findall(r'All-Pro.*?(\d+)', honors_text)
                        if all_pro_matches:
                            data['all_pro'] = len(all_pro_matches)
                    
                    data['data_sources'].append('Pro Football Reference')
                
        except Exception as e:
            logger.warning(f"Career stats collection failed: {e}")
    
    def _collect_contract_data(self, data: Dict) -> None:
        """Collect contract and financial data from Spotrac"""
        try:
            player_name = data['name']
            
            # Generate Spotrac URL
            name_slug = player_name.lower().replace(' ', '-').replace("'", "")
            spotrac_url = f"https://www.spotrac.com/nfl/{name_slug}/"
            
            response = self.session.get(spotrac_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract contract info
                contract_div = soup.find('div', class_='contract-info')
                if contract_div:
                    contract_text = contract_div.get_text()
                    
                    # Parse contract value
                    value_match = re.search(r'\$([0-9,]+)', contract_text)
                    if value_match:
                        data['current_salary'] = value_match.group(1)
                    
                    # Parse contract years
                    years_match = re.search(r'(\d+)\s*year', contract_text)
                    if years_match:
                        data['contract_years'] = int(years_match.group(1))
                
                # Extract career earnings
                earnings_div = soup.find('div', class_='career-earnings')
                if earnings_div:
                    earnings_text = earnings_div.get_text()
                    earnings_match = re.search(r'Career Earnings.*?\$([0-9,]+)', earnings_text)
                    if earnings_match:
                        data['career_earnings'] = earnings_match.group(1)
                
                data['spotrac_url'] = spotrac_url
                data['data_sources'].append('Spotrac')
                
        except Exception as e:
            logger.warning(f"Contract data collection failed: {e}")
    
    def _collect_awards_data(self, data: Dict) -> None:
        """Collect awards and achievements"""
        try:
            player_name = data['name']
            
            # Search for awards information
            search_query = f'"{player_name}" NFL awards achievements honors'
            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                search_text = soup.get_text()
                
                # Look for common awards
                awards_found = []
                
                if 'super bowl' in search_text.lower():
                    awards_found.append('Super Bowl Champion')
                
                if 'pro bowl' in search_text.lower():
                    awards_found.append('Pro Bowl')
                
                if 'all-pro' in search_text.lower():
                    awards_found.append('All-Pro')
                
                if 'rookie of the year' in search_text.lower():
                    awards_found.append('Rookie of the Year')
                
                if 'mvp' in search_text.lower():
                    awards_found.append('MVP')
                
                if awards_found:
                    data['awards'] = ', '.join(awards_found)
                
                data['data_sources'].append('Google Search')
                
        except Exception as e:
            logger.warning(f"Awards collection failed: {e}")
    
    def _collect_enhanced_age(self, data: Dict) -> None:
        """Use enhanced age collector for accurate age data"""
        try:
            player_name = data['name']
            team = data['team']
            
            age_data = self.age_collector.collect_age_data(player_name, team)
            
            if age_data:
                data['age'] = age_data.get('age')
                data['birth_date'] = age_data.get('birth_date')
                
                # Add age collector source
                age_sources = age_data.get('sources_used', [])
                for source in age_sources:
                    if source not in data['data_sources']:
                        data['data_sources'].append(source)
                
        except Exception as e:
            logger.warning(f"Enhanced age collection failed: {e}")
    
    def _extract_stat(self, cells: List, stat_type: str) -> Optional[int]:
        """Extract specific stat from table cells"""
        try:
            # This is a simplified extraction - would need to be customized
            # based on actual table structure
            for cell in cells:
                if cell.get('data-stat') == stat_type:
                    value = cell.get_text().strip()
                    if value.isdigit():
                        return int(value)
            return None
        except:
            return None
    
    def _calculate_quality_score(self, data: Dict) -> float:
        """Calculate data quality score based on filled fields"""
        total_fields = 74
        filled_fields = self._count_filled_fields(data)
        
        # Base score from field completion
        completion_score = (filled_fields / total_fields) * 5
        
        # Bonus points for having multiple sources
        source_bonus = min(len(data['data_sources']) * 0.5, 2.5)
        
        # Bonus for having social media data
        social_bonus = 0.5 if any([
            data['twitter_handle'], data['instagram_handle'], 
            data['tiktok_handle'], data['youtube_handle']
        ]) else 0
        
        # Bonus for having contract data
        contract_bonus = 0.5 if any([
            data['current_salary'], data['contract_value'], 
            data['career_earnings']
        ]) else 0
        
        # Bonus for having career stats
        stats_bonus = 0.5 if any([
            data['career_games'], data['career_yards'], 
            data['career_touchdowns']
        ]) else 0
        
        total_score = completion_score + source_bonus + social_bonus + contract_bonus + stats_bonus
        
        return round(min(total_score, 10.0), 1)
    
    def _count_filled_fields(self, data: Dict) -> int:
        """Count how many fields have been filled with data"""
        filled_count = 0
        for key, value in data.items():
            if key in ['data_sources', 'collection_timestamp', 'scraped_at']:
                continue  # Skip metadata fields
            if value is not None and value != '' and value != []:
                filled_count += 1
        return filled_count

    def batch_collect_team_data(self, team_roster: List[Dict]) -> List[Dict]:
        """Collect comprehensive data for entire team roster"""
        logger.info(f"Collecting comprehensive data for {len(team_roster)} players")
        
        comprehensive_roster = []
        
        for player in team_roster:
            try:
                comprehensive_data = self.collect_all_fields(
                    player_name=player['name'],
                    team=player['team'],
                    position=player.get('position')
                )
                comprehensive_roster.append(comprehensive_data)
                
                # Add small delay to be respectful to servers
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to collect data for {player['name']}: {e}")
                # Add basic player data even if comprehensive collection fails
                comprehensive_roster.append({
                    'name': player['name'],
                    'team': player['team'],
                    'position': player.get('position'),
                    'data_quality_score': 1.0,
                    'collection_timestamp': datetime.now().isoformat(),
                    'scraped_at': datetime.now().isoformat()
                })
        
        return comprehensive_roster