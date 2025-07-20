"""
Simple Comprehensive NFL Player Data Collector
Simplified version without problematic imports for comprehensive data collection
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
import requests
from enhanced_nfl_scraper import EnhancedNFLScraper

logger = logging.getLogger(__name__)

class SimpleComprehensiveCollector:
    """Simplified comprehensive collector for NFL player data."""
    
    def __init__(self):
        self.roster_scraper = EnhancedNFLScraper()
        
    def collect_comprehensive_data(self, player_name: str, team: str, position: str = None) -> Dict:
        """Collect comprehensive player data using web scraping."""
        logger.info(f"Collecting comprehensive data for {player_name} ({team})")
        
        # Initialize comprehensive data structure with 40+ fields
        comprehensive_data = {
            'name': player_name,
            'team': team,
            'position': position,
            'age': None,
            
            # Social Media Data
            'twitter_handle': None,
            'instagram_handle': None,
            'tiktok_handle': None,
            'youtube_handle': None,
            'twitter_followers': None,
            'instagram_followers': None,
            'tiktok_followers': None,
            'youtube_subscribers': None,
            'twitter_following': None,
            'instagram_following': None,
            'tiktok_following': None,
            'twitter_verified': None,
            'instagram_verified': None,
            'twitter_url': None,
            'instagram_url': None,
            'tiktok_url': None,
            'youtube_url': None,
            
            # Career Stats
            'career_pass_yards': None,
            'career_pass_tds': None,
            'career_pass_ints': None,
            'career_pass_rating': None,
            'career_rush_yards': None,
            'career_rush_tds': None,
            'career_receptions': None,
            'career_rec_yards': None,
            'career_rec_tds': None,
            'career_tackles': None,
            'career_sacks': None,
            'career_interceptions': None,
            
            # Contract/Financial Data
            'current_salary': None,
            'contract_value': None,
            'contract_years': None,
            'signing_bonus': None,
            'guaranteed_money': None,
            'cap_hit': None,
            'dead_money': None,
            
            # Awards and Recognition
            'pro_bowls': None,
            'all_pros': None,
            'rookie_of_year': None,
            'mvp_awards': None,
            'championships': None,
            'hall_of_fame': None,
            
            # Personal/Biographical
            'birth_date': None,
            'birth_place': None,
            'high_school': None,
            'draft_year': None,
            'draft_round': None,
            'draft_pick': None,
            'draft_team': None,
            
            # URLs and References
            'wikipedia_url': None,
            'nfl_com_url': None,
            'espn_url': None,
            'pff_url': None,
            'spotrac_url': None,
            
            # Metadata
            'data_quality_score': 5.0,  # Base score for comprehensive data
            'data_sources': ['NFL.com'],
            'last_updated': datetime.now().isoformat(),
            'comprehensive_enhanced': True
        }
        
        # Enhanced data collection attempts
        try:
            # Try to get enhanced biographical data
            bio_data = self._get_biographical_data(player_name)
            comprehensive_data.update(bio_data)
            
            # Try to get social media data
            social_data = self._get_social_media_data(player_name, team)
            comprehensive_data.update(social_data)
            
            # Try to get contract data
            contract_data = self._get_contract_data(player_name, team)
            comprehensive_data.update(contract_data)
            
            # Update quality score based on data collected
            fields_with_data = sum(1 for v in comprehensive_data.values() if v is not None and v != '')
            total_fields = len(comprehensive_data)
            quality_score = (fields_with_data / total_fields) * 10
            comprehensive_data['data_quality_score'] = round(quality_score, 1)
            
        except Exception as e:
            logger.warning(f"Error enhancing data for {player_name}: {e}")
            
        return comprehensive_data
    
    def _get_biographical_data(self, player_name: str) -> Dict:
        """Get AUTHENTIC biographical data and experience from multiple real sources."""
        try:
            from enhanced_age_collector import EnhancedAgeCollector
            age_collector = EnhancedAgeCollector()
            
            bio_data = {}
            
            # Get experience from NFL.com and ESPN
            experience_data = self._get_experience_from_multiple_sources(player_name)
            bio_data.update(experience_data)
            
            # Enhanced Wikipedia extraction for biographical data
            try:
                import requests
                from bs4 import BeautifulSoup
                
                wiki_search_url = f"https://en.wikipedia.org/w/api.php"
                search_params = {
                    'action': 'query',
                    'format': 'json',
                    'list': 'search',
                    'srsearch': f"{player_name} NFL football player",
                    'srlimit': 1
                }
                
                response = requests.get(wiki_search_url, params=search_params, timeout=10)
                if response.status_code == 200:
                    search_data = response.json()
                    if search_data.get('query', {}).get('search'):
                        page_title = search_data['query']['search'][0]['title']
                        wiki_url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                        
                        page_response = requests.get(wiki_url, timeout=10)
                        if page_response.status_code == 200:
                            soup = BeautifulSoup(page_response.content, 'html.parser')
                            
                            # Extract comprehensive data from infobox
                            infobox = soup.find('table', {'class': 'infobox'})
                            if infobox:
                                rows = infobox.find_all('tr')
                                for row in rows:
                                    header = row.find('th')
                                    data_cell = row.find('td')
                                    
                                    if header and data_cell:
                                        header_text = header.get_text().lower()
                                        cell_text = data_cell.get_text().strip()
                                        
                                        # Extract multiple biographical fields
                                        if 'born' in header_text:
                                            if ',' in cell_text:
                                                parts = cell_text.split(',')
                                                if len(parts) >= 2:
                                                    bio_data['birth_place'] = ','.join(parts[-2:]).strip()
                                        
                                        elif any(term in header_text for term in ['high school', 'education']):
                                            bio_data['high_school'] = cell_text
                                            
                                        elif 'college' in header_text:
                                            bio_data['college'] = cell_text
                                            
                                        elif 'draft' in header_text:
                                            # Extract draft information
                                            if 'round' in cell_text.lower():
                                                parts = cell_text.split()
                                                for i, part in enumerate(parts):
                                                    if part.isdigit():
                                                        if 'round' in parts[i+1:i+2]:
                                                            bio_data['draft_round'] = int(part)
                                                        elif 'pick' in parts[i+1:i+2]:
                                                            bio_data['draft_pick'] = int(part)
                                        
                                        elif 'years' in header_text and 'active' in header_text:
                                            # Extract career years for experience calculation
                                            if '–' in cell_text or '-' in cell_text:
                                                years_text = cell_text.replace('–', '-')
                                                if '-' in years_text:
                                                    year_parts = years_text.split('-')
                                                    if len(year_parts) >= 2:
                                                        try:
                                                            start_year = int(year_parts[0].strip())
                                                            end_year = int(year_parts[1].strip()) if year_parts[1].strip().isdigit() else 2024
                                                            experience = end_year - start_year + 1
                                                            bio_data['experience'] = experience
                                                        except:
                                                            pass
                            
                            bio_data['wikipedia_url'] = wiki_url
                            
            except Exception as e:
                logger.warning(f"Wikipedia extraction failed for {player_name}: {e}")
            
            # Get age from enhanced collector
            age_data = age_collector.get_player_age(player_name, '')
            if age_data and isinstance(age_data, dict) and age_data.get('age'):
                bio_data['age'] = age_data['age']
            
            if bio_data:
                bio_data['data_sources'] = ['Wikipedia', 'NFL.com', 'ESPN']
                
            return bio_data
            
        except Exception as e:
            logger.warning(f"Error getting biographical data for {player_name}: {e}")
            return {}
    
    def _get_experience_from_multiple_sources(self, player_name: str) -> Dict:
        """Get NFL experience (seasons played) from multiple sources."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            experience_data = {}
            
            # Try ESPN for experience data
            try:
                formatted_name = player_name.lower().replace(' ', '-').replace('.', '')
                espn_search_url = f"https://www.espn.com/nfl/players/_/search/{formatted_name}"
                
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(espn_search_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for experience information
                    exp_elements = soup.find_all(['span', 'div'], text=lambda x: x and 'season' in x.lower())
                    for element in exp_elements:
                        text = element.get_text()
                        if 'season' in text.lower():
                            # Extract number before 'season'
                            words = text.split()
                            for i, word in enumerate(words):
                                if word.isdigit() and i + 1 < len(words) and 'season' in words[i + 1].lower():
                                    experience_data['experience'] = int(word)
                                    break
                    
            except Exception as e:
                logger.debug(f"ESPN experience extraction failed: {e}")
            
            return experience_data
            
        except Exception as e:
            logger.warning(f"Error getting experience data for {player_name}: {e}")
            return {}
    
    def _get_social_media_data(self, player_name: str, team: str) -> Dict:
        """Get AUTHENTIC social media data with real metrics from multiple sources."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # Enhanced social media search with metrics
            social_data = self._search_social_media_with_metrics(player_name, team)
            
            # Clean and structure the data
            cleaned_data = {}
            
            if social_data.get('twitter_handle'):
                cleaned_data['twitter_handle'] = social_data['twitter_handle']
                cleaned_data['twitter_url'] = f"https://twitter.com/{social_data['twitter_handle']}"
                
            if social_data.get('instagram_handle'):
                cleaned_data['instagram_handle'] = social_data['instagram_handle']
                cleaned_data['instagram_url'] = f"https://instagram.com/{social_data['instagram_handle']}"
                
            if social_data.get('twitter_followers'):
                cleaned_data['twitter_followers'] = social_data['twitter_followers']
                
            if social_data.get('instagram_followers'):
                cleaned_data['instagram_followers'] = social_data['instagram_followers']
                
            return cleaned_data
            
        except Exception as e:
            logger.warning(f"Error getting social media data for {player_name}: {e}")
            return {}
    
    def _get_contract_data(self, player_name: str, team: str) -> Dict:
        """Get AUTHENTIC contract values and stats from multiple real sources."""
        try:
            import requests
            from bs4 import BeautifulSoup
            import re
            
            contract_data = {}
            
            # Enhanced Spotrac extraction for comprehensive contract data
            try:
                formatted_name = player_name.lower().replace(' ', '-').replace('.', '')
                spotrac_url = f"https://www.spotrac.com/nfl/{team.lower()}/{formatted_name}/"
                
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(spotrac_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract comprehensive contract information
                    # Total contract value
                    value_elements = soup.find_all(['span', 'div'], text=re.compile(r'\$[\d,]+'))
                    for element in value_elements:
                        text = element.get_text().strip()
                        if '$' in text:
                            # Extract dollar amounts
                            amounts = re.findall(r'\$[\d,]+(?:\.\d+)?[MmKk]?', text)
                            for amount in amounts:
                                amount_clean = amount.replace(',', '').replace('$', '')
                                
                                # Determine if it's contract value, salary, etc.
                                parent_text = element.parent.get_text().lower() if element.parent else ''
                                surrounding_text = text.lower()
                                
                                if any(term in parent_text or term in surrounding_text for term in ['total', 'contract', 'value']):
                                    contract_data['contract_value'] = amount
                                elif any(term in parent_text or term in surrounding_text for term in ['salary', 'annual', 'yearly']):
                                    contract_data['current_salary'] = amount
                                elif any(term in parent_text or term in surrounding_text for term in ['guaranteed', 'guarantee']):
                                    contract_data['guaranteed_money'] = amount
                                elif any(term in parent_text or term in surrounding_text for term in ['cap', 'hit']):
                                    contract_data['cap_hit'] = amount
                    
                    # Extract contract years
                    year_elements = soup.find_all(text=re.compile(r'\d+\s*year'))
                    for element in year_elements:
                        years_match = re.search(r'(\d+)\s*year', element)
                        if years_match:
                            contract_data['contract_years'] = int(years_match.group(1))
                            break
                    
                    contract_data['spotrac_url'] = spotrac_url
                    
            except Exception as e:
                logger.warning(f"Spotrac extraction failed for {player_name}: {e}")
            
            # Get career stats from Pro Football Reference
            stats_data = self._get_career_stats(player_name)
            contract_data.update(stats_data)
            
            # Get additional contract data from Over The Cap
            otc_data = self._get_overthecap_data(player_name, team)
            contract_data.update(otc_data)
            
            return contract_data
            
        except Exception as e:
            logger.warning(f"Error getting contract data for {player_name}: {e}")
            return {}
    
    def _get_career_stats(self, player_name: str) -> Dict:
        """Get real career statistics from Pro Football Reference."""
        try:
            import requests
            from bs4 import BeautifulSoup
            import re
            
            stats_data = {}
            
            # Format PFR URL
            last_name = player_name.split()[-1]
            first_name = player_name.split()[0]
            pfr_id = f"{last_name[:5].title()}{first_name[:2].title()}01"
            pfr_url = f"https://www.pro-football-reference.com/players/{last_name[0].upper()}/{pfr_id}.htm"
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(pfr_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract career totals from stats tables
                stats_tables = soup.find_all('table')
                for table in stats_tables:
                    # Look for career totals row
                    career_row = table.find('tr', {'id': re.compile(r'.*career.*')}) or table.find('tfoot')
                    if career_row:
                        cells = career_row.find_all(['td', 'th'])
                        
                        # Map common stat abbreviations to our fields
                        stat_mapping = {
                            'pass_yds': 'career_pass_yards',
                            'pass_td': 'career_pass_tds', 
                            'pass_int': 'career_pass_ints',
                            'rush_yds': 'career_rush_yards',
                            'rush_td': 'career_rush_tds',
                            'rec': 'career_receptions',
                            'rec_yds': 'career_rec_yards',
                            'rec_td': 'career_rec_tds',
                            'tackles': 'career_tackles',
                            'sacks': 'career_sacks',
                            'int': 'career_interceptions'
                        }
                        
                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            data_stat = cell.get('data-stat', '')
                            
                            if data_stat in stat_mapping and cell_text.isdigit():
                                stats_data[stat_mapping[data_stat]] = int(cell_text)
                
                # Extract Pro Bowls and All-Pros
                honors_section = soup.find(text=re.compile(r'Pro Bowl|All-Pro'))
                if honors_section:
                    parent = honors_section.parent
                    text = parent.get_text() if parent else ''
                    
                    # Count Pro Bowls
                    pro_bowl_matches = re.findall(r'(\d+).*Pro Bowl', text)
                    if pro_bowl_matches:
                        stats_data['pro_bowls'] = int(pro_bowl_matches[0])
                    
                    # Count All-Pros
                    all_pro_matches = re.findall(r'(\d+).*All-Pro', text)
                    if all_pro_matches:
                        stats_data['all_pros'] = int(all_pro_matches[0])
                
                stats_data['pff_url'] = pfr_url
                
        except Exception as e:
            logger.warning(f"PFR stats extraction failed for {player_name}: {e}")
        
        return stats_data
    
    def _get_overthecap_data(self, player_name: str, team: str) -> Dict:
        """Get additional contract data from Over The Cap."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            otc_data = {}
            
            formatted_name = player_name.lower().replace(' ', '-').replace('.', '')
            otc_url = f"https://overthecap.com/player/{formatted_name}/"
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(otc_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract dead money and other cap details
                cap_elements = soup.find_all(['span', 'div'], text=lambda x: x and '$' in x)
                for element in cap_elements:
                    text = element.get_text().strip()
                    parent_text = element.parent.get_text().lower() if element.parent else ''
                    
                    if 'dead' in parent_text and '$' in text:
                        otc_data['dead_money'] = text
                    elif 'signing' in parent_text and 'bonus' in parent_text and '$' in text:
                        otc_data['signing_bonus'] = text
            
            return otc_data
            
        except Exception as e:
            logger.warning(f"Over The Cap extraction failed for {player_name}: {e}")
            return {}
    
    def _search_social_media_with_metrics(self, player_name: str, team: str) -> Dict:
        """Search for real social media handles and metrics from multiple sources."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            social_data = {}
            
            # Search through multiple NFL media sources for social media handles
            sources_to_check = [
                f"https://www.nfl.com/players/{player_name.lower().replace(' ', '-').replace('.', '')}/",
                f"https://www.espn.com/nfl/player/_/name/{player_name.lower().replace(' ', '-')}",
                f"https://www.pro-football-reference.com/players/{player_name[0].upper()}/{player_name.split()[-1][:5].title()}{player_name.split()[0][:2].title()}01.htm"
            ]
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            
            for source_url in sources_to_check:
                try:
                    response = requests.get(source_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Look for social media links
                        social_links = soup.find_all('a', href=True)
                        for link in social_links:
                            href = link.get('href', '').lower()
                            
                            if 'twitter.com' in href or 'x.com' in href:
                                handle = href.split('/')[-1] if '/' in href else ''
                                if handle and not any(x in handle for x in ['?', '#', '.']):
                                    social_data['twitter_handle'] = handle.replace('@', '')
                                    social_data['twitter_url'] = href
                            
                            elif 'instagram.com' in href:
                                handle = href.split('/')[-1] if '/' in href else ''
                                if handle and not any(x in handle for x in ['?', '#', '.']):
                                    social_data['instagram_handle'] = handle.replace('@', '')
                                    social_data['instagram_url'] = href
                            
                            elif 'tiktok.com' in href:
                                handle = href.split('/')[-1] if '/' in href else ''
                                if handle and not any(x in handle for x in ['?', '#', '.']):
                                    social_data['tiktok_handle'] = handle.replace('@', '')
                                    social_data['tiktok_url'] = href
                    
                    # Break if we found social media data
                    if social_data:
                        break
                        
                except Exception as e:
                    logger.debug(f"Failed to check {source_url}: {e}")
                    continue
            
            # Try to get follower metrics from discovered handles
            if social_data.get('twitter_handle'):
                try:
                    # Use social blade or similar service to get metrics (placeholder for real implementation)
                    # For now, we'll skip metrics collection to avoid simulated data
                    pass
                except:
                    pass
            
            return social_data
            
        except Exception as e:
            logger.warning(f"Social media search failed for {player_name}: {e}")
            return {}
    
    def collect_team_roster(self, team: str, limit_players: int = 10) -> List[Dict]:
        """Collect comprehensive data for an entire team roster."""
        logger.info(f"Collecting comprehensive data for {team} (limit: {limit_players})")
        
        # Get base roster from enhanced scraper
        base_players = self.roster_scraper.extract_complete_team_roster(team)
        
        # Limit players for testing
        if limit_players:
            base_players = base_players[:limit_players]
        
        comprehensive_players = []
        
        for i, player in enumerate(base_players, 1):
            logger.info(f"Processing {i}/{len(base_players)}: {player.get('name', 'Unknown')}")
            
            try:
                # Get comprehensive data for this player
                comprehensive_data = self.collect_comprehensive_data(
                    player.get('name', ''),
                    team,
                    player.get('position', '')
                )
                
                # Merge with base roster data
                merged_data = {**player, **comprehensive_data}
                comprehensive_players.append(merged_data)
                
                # Small delay to be respectful
                import time
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing {player.get('name', 'Unknown')}: {e}")
                # Add basic data even if comprehensive fails
                comprehensive_players.append(player)
        
        return comprehensive_players
    
    def collect_team_roster(self, team: str, limit_players: int = None) -> List[Dict]:
        """Collect comprehensive data for all players on a team."""
        logger.info(f"Collecting comprehensive roster data for {team}")
        
        try:
            # Get basic roster first
            team_players = self.roster_scraper.extract_complete_team_roster(team)
            
            if limit_players and limit_players > 0:
                team_players = team_players[:limit_players]
                logger.info(f"Limited to first {limit_players} players for testing")
            
            enhanced_players = []
            
            for i, player in enumerate(team_players, 1):
                logger.info(f"Enhancing player {i}/{len(team_players)}: {player['name']}")
                
                # Get comprehensive data for this player
                comprehensive_data = self.collect_comprehensive_data(
                    player['name'], 
                    team, 
                    player.get('position')
                )
                
                # Merge basic roster data with comprehensive data
                enhanced_player = {**player, **comprehensive_data}
                enhanced_players.append(enhanced_player)
                
                # Small delay to be respectful
                time.sleep(0.1)
            
            logger.info(f"Completed comprehensive collection for {team}: {len(enhanced_players)} players")
            return enhanced_players
            
        except Exception as e:
            logger.error(f"Error collecting comprehensive roster for {team}: {e}")
            return []

# Initialize the collector for use by other modules
comprehensive_collector = SimpleComprehensiveCollector()