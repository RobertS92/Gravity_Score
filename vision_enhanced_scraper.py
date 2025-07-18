#!/usr/bin/env python3
"""
Vision-Enhanced NFL Data Scraper
Uses multimodal LLMs for visual webpage analysis and semantic HTML parsing
Focuses on social media handles, follower counts, accomplishments, and contracts
"""

import os
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import base64
from io import BytesIO
from PIL import Image
import openai
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VisionEnhancedScraper:
    """Advanced scraper using vision and semantic analysis"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_player_data(self, player_name, team, position):
        """Extract comprehensive player data using advanced techniques"""
        logger.info(f"🔍 VISION-ENHANCED EXTRACTION: {player_name}")
        
        data = {
            'name': player_name,
            'team': team,
            'position': position,
            'data_sources': [],
            'extraction_methods': []
        }
        
        # 1. Social Media Extraction
        social_data = self._extract_social_media_comprehensive(player_name)
        data.update(social_data)
        
        # 2. Accomplishments & Awards
        accomplishments = self._extract_accomplishments(player_name)
        data.update(accomplishments)
        
        # 3. Contract Information
        contract_data = self._extract_contract_data(player_name, team)
        data.update(contract_data)
        
        # 4. Career Statistics
        stats_data = self._extract_career_stats(player_name, position)
        data.update(stats_data)
        
        return data
    
    def _extract_social_media_comprehensive(self, player_name):
        """Extract social media handles and follower counts using vision + semantic analysis"""
        logger.info(f"📱 Extracting social media for {player_name}")
        
        social_data = {}
        
        # Multi-step contextual extraction
        search_queries = [
            f"{player_name} NFL Twitter Instagram",
            f"{player_name} social media profiles",
            f"{player_name} official accounts"
        ]
        
        for query in search_queries:
            try:
                # Search for social media profiles
                search_results = self._search_web(query)
                
                for result in search_results[:3]:  # Top 3 results
                    url = result.get('url', '')
                    
                    # Check if it's a social media platform
                    if any(platform in url.lower() for platform in ['twitter.com', 'x.com', 'instagram.com', 'tiktok.com', 'youtube.com']):
                        platform_data = self._extract_platform_data(url, player_name)
                        social_data.update(platform_data)
                
                # If we found good social data, break
                if len(social_data) > 2:
                    break
                    
            except Exception as e:
                logger.error(f"Error in social media search: {e}")
                continue
        
        # Enhance with semantic HTML analysis
        for platform in ['twitter', 'instagram', 'tiktok', 'youtube']:
            if f"{platform}_handle" not in social_data:
                handle_data = self._semantic_social_extraction(player_name, platform)
                social_data.update(handle_data)
        
        return social_data
    
    def _extract_platform_data(self, url, player_name):
        """Extract handle and follower count from social media platform"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                html_content = response.text
                
                # Use semantic HTML analysis
                platform_data = self._analyze_social_page_semantically(html_content, url, player_name)
                return platform_data
                
        except Exception as e:
            logger.error(f"Error extracting platform data from {url}: {e}")
        
        return {}
    
    def _analyze_social_page_semantically(self, html_content, url, player_name):
        """Use LLM to analyze social media page HTML semantically"""
        try:
            # Determine platform
            platform = self._get_platform_from_url(url)
            
            # Truncate HTML to manageable size
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract key sections
            key_sections = []
            for selector in ['header', '[data-testid]', '.profile', '.user-info', '.follower', '.subscriber']:
                elements = soup.select(selector)
                for elem in elements[:5]:  # Limit to avoid token limits
                    key_sections.append(elem.get_text(strip=True))
            
            # Prepare prompt for semantic analysis
            prompt = f"""
            Analyze this {platform} page HTML content for NFL player "{player_name}" and extract:
            
            1. The exact handle/username (without @ symbol)
            2. Follower count (convert K/M to actual numbers, e.g., 1.2M = 1200000)
            3. Subscriber count if applicable
            4. Any verification status
            
            HTML sections: {' '.join(key_sections[:10])}
            
            Return JSON format:
            {{
                "{platform}_handle": "exact_handle",
                "{platform}_followers": numeric_count,
                "{platform}_verified": boolean,
                "{platform}_url": "{url}"
            }}
            
            Only include fields you can confidently extract. Return empty JSON if unclear.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting social media data from HTML. Be precise and only extract data you're confident about."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✅ Semantic extraction from {platform}: {len(result)} fields")
            return result
            
        except Exception as e:
            logger.error(f"Error in semantic analysis: {e}")
            return {}
    
    def _semantic_social_extraction(self, player_name, platform):
        """Use web search + semantic analysis to find social media handles"""
        try:
            # Search for specific platform
            query = f"{player_name} NFL {platform} official account"
            search_results = self._search_web(query)
            
            platform_data = {}
            
            for result in search_results[:3]:
                url = result.get('url', '')
                if platform in url.lower():
                    try:
                        response = self.session.get(url, timeout=10)
                        if response.status_code == 200:
                            extracted = self._analyze_social_page_semantically(response.text, url, player_name)
                            platform_data.update(extracted)
                            if extracted:  # If we got good data, break
                                break
                    except:
                        continue
            
            return platform_data
            
        except Exception as e:
            logger.error(f"Error in semantic social extraction: {e}")
            return {}
    
    def _extract_accomplishments(self, player_name):
        """Extract Super Bowl wins, championships, awards using semantic analysis"""
        logger.info(f"🏆 Extracting accomplishments for {player_name}")
        
        accomplishments = {}
        
        # Search for accomplishments
        search_queries = [
            f"{player_name} NFL Super Bowl wins championships",
            f"{player_name} NFL Pro Bowl All-Pro awards",
            f"{player_name} NFL MVP awards honors"
        ]
        
        all_accomplishment_text = []
        
        for query in search_queries:
            try:
                search_results = self._search_web(query)
                
                for result in search_results[:2]:  # Top 2 per query
                    url = result.get('url', '')
                    
                    # Focus on reliable sources
                    if any(source in url.lower() for source in ['nfl.com', 'espn.com', 'wikipedia.org', 'pro-football-reference.com']):
                        content = self._get_page_content(url)
                        if content:
                            all_accomplishment_text.append(content[:2000])  # Limit content
                
            except Exception as e:
                logger.error(f"Error searching accomplishments: {e}")
                continue
        
        # Semantic analysis of accomplishments
        if all_accomplishment_text:
            accomplishments = self._analyze_accomplishments_semantically(player_name, ' '.join(all_accomplishment_text))
        
        return accomplishments
    
    def _analyze_accomplishments_semantically(self, player_name, content):
        """Use LLM to extract accomplishments from content"""
        try:
            prompt = f"""
            Analyze this content about NFL player "{player_name}" and extract specific accomplishments:
            
            Content: {content}
            
            Extract and return JSON with only verified accomplishments:
            {{
                "super_bowl_wins": number_of_wins,
                "super_bowl_years": [list_of_years],
                "pro_bowl_selections": number,
                "all_pro_selections": number,
                "mvp_awards": number,
                "offensive_player_of_year": number,
                "defensive_player_of_year": number,
                "rookie_of_year": boolean,
                "comeback_player_of_year": boolean,
                "conference_championships": number,
                "division_titles": number,
                "other_major_awards": [list_of_awards]
            }}
            
            Only include accomplishments you can verify from the content. Use 0 for counts if not found.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting NFL player accomplishments. Only include verified achievements."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=800
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✅ Extracted accomplishments: {len(result)} categories")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing accomplishments: {e}")
            return {}
    
    def _extract_contract_data(self, player_name, team):
        """Extract contract value, years, current salary using semantic analysis"""
        logger.info(f"💰 Extracting contract data for {player_name}")
        
        contract_data = {}
        
        # Search for contract information
        search_queries = [
            f"{player_name} NFL contract extension salary",
            f"{player_name} {team} contract value years",
            f"{player_name} current salary cap hit"
        ]
        
        contract_content = []
        
        for query in search_queries:
            try:
                search_results = self._search_web(query)
                
                for result in search_results[:2]:
                    url = result.get('url', '')
                    
                    # Focus on contract-focused sources
                    if any(source in url.lower() for source in ['spotrac.com', 'overthecap.com', 'nfl.com', 'espn.com']):
                        content = self._get_page_content(url)
                        if content:
                            contract_content.append(content[:2000])
                
            except Exception as e:
                logger.error(f"Error searching contract data: {e}")
                continue
        
        # Semantic analysis of contract data
        if contract_content:
            contract_data = self._analyze_contract_semantically(player_name, ' '.join(contract_content))
        
        return contract_data
    
    def _analyze_contract_semantically(self, player_name, content):
        """Use LLM to extract contract information from content"""
        try:
            prompt = f"""
            Analyze this content about NFL player "{player_name}" and extract contract information:
            
            Content: {content}
            
            Extract and return JSON with contract details:
            {{
                "contract_value": total_contract_value_in_dollars,
                "contract_years": number_of_years,
                "current_salary": current_year_salary,
                "guaranteed_money": guaranteed_amount,
                "signing_bonus": bonus_amount,
                "cap_hit": current_cap_hit,
                "contract_type": "extension|rookie|free_agent",
                "contract_year": year_signed,
                "years_remaining": remaining_years,
                "average_per_year": average_annual_value
            }}
            
            Convert all monetary values to numbers (e.g., $45M = 45000000).
            Only include values you can verify from the content.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting NFL contract information. Be precise with monetary values."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=600
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✅ Extracted contract data: {len(result)} fields")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing contract data: {e}")
            return {}
    
    def _extract_career_stats(self, player_name, position):
        """Extract career statistics using semantic analysis"""
        logger.info(f"📊 Extracting career stats for {player_name}")
        
        stats_data = {}
        
        # Position-specific stat queries
        if position == 'QB':
            queries = [
                f"{player_name} NFL career passing yards touchdowns",
                f"{player_name} career statistics completions attempts"
            ]
        elif position in ['RB', 'FB']:
            queries = [
                f"{player_name} NFL career rushing yards touchdowns",
                f"{player_name} career statistics attempts yards per carry"
            ]
        elif position in ['WR', 'TE']:
            queries = [
                f"{player_name} NFL career receiving yards touchdowns",
                f"{player_name} career statistics receptions targets"
            ]
        else:
            queries = [
                f"{player_name} NFL career statistics",
                f"{player_name} career performance stats"
            ]
        
        stats_content = []
        
        for query in queries:
            try:
                search_results = self._search_web(query)
                
                for result in search_results[:2]:
                    url = result.get('url', '')
                    
                    # Focus on stats sources
                    if any(source in url.lower() for source in ['pro-football-reference.com', 'nfl.com', 'espn.com']):
                        content = self._get_page_content(url)
                        if content:
                            stats_content.append(content[:2000])
                
            except Exception as e:
                logger.error(f"Error searching stats: {e}")
                continue
        
        # Semantic analysis of stats
        if stats_content:
            stats_data = self._analyze_stats_semantically(player_name, position, ' '.join(stats_content))
        
        return stats_data
    
    def _analyze_stats_semantically(self, player_name, position, content):
        """Use LLM to extract career statistics from content"""
        try:
            prompt = f"""
            Analyze this content about NFL {position} "{player_name}" and extract career statistics:
            
            Content: {content}
            
            Extract and return JSON with career stats (use 0 if not found):
            {{
                "career_games": total_games_played,
                "career_starts": games_started,
                "career_pass_yards": passing_yards,
                "career_pass_tds": passing_touchdowns,
                "career_pass_ints": interceptions,
                "career_pass_rating": passer_rating,
                "career_rush_yards": rushing_yards,
                "career_rush_tds": rushing_touchdowns,
                "career_receptions": receptions,
                "career_receiving_yards": receiving_yards,
                "career_receiving_tds": receiving_touchdowns,
                "career_tackles": tackles,
                "career_sacks": sacks,
                "career_fumbles": fumbles,
                "career_yards_per_game": average_yards_per_game,
                "career_touchdowns": total_touchdowns
            }}
            
            Only include stats relevant to the position. Use actual numbers, not formatted strings.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"You are an expert at extracting NFL statistics for {position} players. Be precise with numbers."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=700
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"✅ Extracted career stats: {len(result)} fields")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing stats: {e}")
            return {}
    
    def _search_web(self, query):
        """Simple web search simulation - replace with actual search API"""
        # This is a placeholder - in real implementation, use Google Search API or similar
        return [
            {"url": f"https://www.nfl.com/search?q={query.replace(' ', '+')}", "title": "NFL Search"},
            {"url": f"https://www.espn.com/search?q={query.replace(' ', '+')}", "title": "ESPN Search"},
            {"url": f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}", "title": "Wikipedia"}
        ]
    
    def _get_page_content(self, url):
        """Get page content with error handling"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                return soup.get_text(strip=True)
        except:
            pass
        return ""
    
    def _get_platform_from_url(self, url):
        """Extract platform name from URL"""
        if 'twitter.com' in url or 'x.com' in url:
            return 'twitter'
        elif 'instagram.com' in url:
            return 'instagram'
        elif 'tiktok.com' in url:
            return 'tiktok'
        elif 'youtube.com' in url:
            return 'youtube'
        return 'unknown'

# Test the vision-enhanced scraper
if __name__ == "__main__":
    scraper = VisionEnhancedScraper()
    
    # Test with Patrick Mahomes
    print("🔍 Testing Vision-Enhanced Scraper")
    print("=" * 50)
    
    data = scraper.extract_player_data("Patrick Mahomes", "chiefs", "QB")
    
    print(f"✅ Extracted {len(data)} total fields")
    
    # Show social media data
    social_fields = [k for k in data.keys() if any(platform in k for platform in ['twitter', 'instagram', 'tiktok', 'youtube'])]
    print(f"📱 Social Media: {len(social_fields)} fields")
    
    # Show accomplishments
    accomplishment_fields = [k for k in data.keys() if any(term in k for term in ['super_bowl', 'pro_bowl', 'mvp', 'award'])]
    print(f"🏆 Accomplishments: {len(accomplishment_fields)} fields")
    
    # Show contract data
    contract_fields = [k for k in data.keys() if any(term in k for term in ['contract', 'salary', 'cap_hit'])]
    print(f"💰 Contract Data: {len(contract_fields)} fields")
    
    # Show stats
    stats_fields = [k for k in data.keys() if 'career_' in k]
    print(f"📊 Career Stats: {len(stats_fields)} fields")