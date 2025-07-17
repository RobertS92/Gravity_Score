"""
Enhanced Comprehensive NFL Player Data Collector
Uses existing social media agent and web scraping infrastructure for complete data collection
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
import concurrent.futures
from social_media_agent import SocialMediaAgent
from web_search_social_scraper import WebSearchSocialScraper
from nfl_gravity.extractors.wikipedia import WikipediaExtractor
from nfl_gravity.core.config import Config

logger = logging.getLogger(__name__)

class EnhancedComprehensiveCollector:
    """Enhanced collector that uses existing infrastructure for complete data collection."""
    
    def __init__(self):
        self.config = Config()
        self.social_agent = SocialMediaAgent()
        self.web_scraper = WebSearchSocialScraper()
        self.wiki_extractor = WikipediaExtractor(self.config)
        
    def collect_comprehensive_data(self, player_name: str, team: str, position: str = None) -> Dict:
        """Collect comprehensive player data using existing infrastructure."""
        logger.info(f"Collecting comprehensive data for {player_name} ({team})")
        
        # Initialize comprehensive data structure
        comprehensive_data = {
            'name': player_name,
            'team': team,
            'position': position,
            
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
            
            # Awards and Recognition
            'pro_bowls': None,
            'all_pro_selections': None,
            'super_bowl_wins': None,
            'rookie_of_year': None,
            'mvp_awards': None,
            'college_awards': None,
            'hall_of_fame': None,
            
            # Contract and Financial
            'current_salary': None,
            'career_earnings': None,
            'contract_years': None,
            'contract_value': None,
            'signing_bonus': None,
            'guaranteed_money': None,
            
            # External Links and Media
            'wikipedia_url': None,
            'nfl_com_url': None,
            'espn_url': None,
            'pfr_url': None,
            'spotrac_url': None,
            'news_mentions': None,
            'fantasy_points': None,
            'popularity_score': None,
            
            # Biography and Personal
            'age': None,
            'height': None,
            'weight': None,
            'birth_date': None,
            'birth_place': None,
            'college': None,
            'hometown': None,
            'high_school': None,
            
            # Career Information
            'draft_year': None,
            'draft_round': None,
            'draft_pick': None,
            'years_pro': None,
            'games_played': None,
            'games_started': None,
            'career_highlights': None,
            'awards': None,
            
            # Metadata
            'data_sources': [],
            'data_quality_score': 0,
            'collection_timestamp': datetime.now().isoformat(),
            'collection_duration': 0,
            'scraped_at': datetime.now()
        }
        
        start_time = time.time()
        
        # Use parallel processing for data collection
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            # Submit data collection tasks
            futures.append(executor.submit(self._collect_social_media_data, player_name, team))
            futures.append(executor.submit(self._collect_wikipedia_data, player_name, team))
            futures.append(executor.submit(self._collect_career_stats, player_name, team))
            futures.append(executor.submit(self._collect_contract_data, player_name, team))
            
            # Collect results with timeout
            for future in concurrent.futures.as_completed(futures, timeout=45):
                try:
                    result = future.result()
                    if result:
                        comprehensive_data.update(result)
                        if 'data_sources' in result:
                            comprehensive_data['data_sources'].extend(result['data_sources'])
                except Exception as e:
                    logger.warning(f"Data collection task failed for {player_name}: {e}")
        
        # Calculate metrics
        comprehensive_data['collection_duration'] = time.time() - start_time
        comprehensive_data['data_quality_score'] = self._calculate_quality_score(comprehensive_data)
        
        return comprehensive_data
    
    def _collect_social_media_data(self, player_name: str, team: str) -> Dict:
        """Collect social media data using Firecrawl agent for better success rates."""
        try:
            # Try Firecrawl first for better success rates
            try:
                from firecrawl_agent import FirecrawlAgent
                firecrawl_agent = FirecrawlAgent()
                social_data = firecrawl_agent.search_social_media_profiles(player_name, team)
                
                result = {}
                
                # Map Firecrawl social media data
                if social_data:
                    # Twitter data
                    if 'twitter' in social_data and social_data['twitter']:
                        twitter = social_data['twitter']
                        result['twitter_handle'] = twitter.get('handle')
                        result['twitter_followers'] = twitter.get('followers')
                        result['twitter_following'] = twitter.get('following')
                        result['twitter_verified'] = twitter.get('verified')
                        result['twitter_url'] = twitter.get('url')
                    
                    # Instagram data
                    if 'instagram' in social_data and social_data['instagram']:
                        instagram = social_data['instagram']
                        result['instagram_handle'] = instagram.get('handle')
                        result['instagram_followers'] = instagram.get('followers')
                        result['instagram_following'] = instagram.get('following')
                        result['instagram_verified'] = instagram.get('verified')
                        result['instagram_url'] = instagram.get('url')
                    
                    # TikTok data
                    if 'tiktok' in social_data and social_data['tiktok']:
                        tiktok = social_data['tiktok']
                        result['tiktok_handle'] = tiktok.get('handle')
                        result['tiktok_followers'] = tiktok.get('followers')
                        result['tiktok_following'] = tiktok.get('following')
                        result['tiktok_url'] = tiktok.get('url')
                    
                    # YouTube data
                    if 'youtube' in social_data and social_data['youtube']:
                        youtube = social_data['youtube']
                        result['youtube_handle'] = youtube.get('handle')
                        result['youtube_subscribers'] = youtube.get('subscribers')
                        result['youtube_url'] = youtube.get('url')
                    
                    result['data_sources'] = ['firecrawl_agent']
                    
                if result:
                    return result
                    
            except Exception as firecrawl_error:
                logger.debug(f"Firecrawl social media collection failed for {player_name}: {firecrawl_error}")
            
            # Fallback to existing social media agent
            social_data = self.social_agent.search_player_social_media(player_name, team)
            
            result = {}
            
            # Map social media data
            if social_data:
                # Twitter data
                if 'twitter' in social_data:
                    twitter = social_data['twitter']
                    result['twitter_handle'] = twitter.get('handle')
                    result['twitter_followers'] = twitter.get('followers')
                    result['twitter_following'] = twitter.get('following')
                    result['twitter_verified'] = twitter.get('verified')
                    result['twitter_url'] = twitter.get('url')
                
                # Instagram data
                if 'instagram' in social_data:
                    instagram = social_data['instagram']
                    result['instagram_handle'] = instagram.get('handle')
                    result['instagram_followers'] = instagram.get('followers')
                    result['instagram_following'] = instagram.get('following')
                    result['instagram_verified'] = instagram.get('verified')
                    result['instagram_url'] = instagram.get('url')
                
                # TikTok data
                if 'tiktok' in social_data:
                    tiktok = social_data['tiktok']
                    result['tiktok_handle'] = tiktok.get('handle')
                    result['tiktok_followers'] = tiktok.get('followers')
                    result['tiktok_following'] = tiktok.get('following')
                    result['tiktok_url'] = tiktok.get('url')
                
                # YouTube data
                if 'youtube' in social_data:
                    youtube = social_data['youtube']
                    result['youtube_handle'] = youtube.get('handle')
                    result['youtube_subscribers'] = youtube.get('subscribers')
                    result['youtube_url'] = youtube.get('url')
                
                result['data_sources'] = ['social_media_agent']
                
            return result
            
        except Exception as e:
            logger.debug(f"Social media collection failed for {player_name}: {e}")
            return {}
    
    def _collect_wikipedia_data(self, player_name: str, team: str) -> Dict:
        """Collect Wikipedia biographical data using Firecrawl for better success rates."""
        try:
            # Try Firecrawl first for better success rates
            try:
                from firecrawl_agent import FirecrawlAgent
                firecrawl_agent = FirecrawlAgent()
                wiki_data = firecrawl_agent.scrape_player_wikipedia(player_name, team)
                
                result = {}
                if wiki_data and 'biographical_data' in wiki_data:
                    bio_data = wiki_data['biographical_data']
                    result['wikipedia_url'] = wiki_data.get('wikipedia_url')
                    result['birth_date'] = bio_data.get('birth_date')
                    result['birth_place'] = bio_data.get('birth_place')
                    result['college'] = bio_data.get('college')
                    result['career_highlights'] = bio_data.get('career_highlights')
                    result['awards'] = bio_data.get('awards')
                    result['pro_bowls'] = bio_data.get('pro_bowls')
                    result['all_pro_selections'] = bio_data.get('all_pro')
                    result['hall_of_fame'] = bio_data.get('hall_of_fame')
                    
                    result['data_sources'] = ['firecrawl_agent']
                    
                if result:
                    return result
                    
            except Exception as firecrawl_error:
                logger.debug(f"Firecrawl Wikipedia collection failed for {player_name}: {firecrawl_error}")
            
            # Fallback to existing Wikipedia extractor
            wiki_data = self.wiki_extractor.extract_player_data(player_name, team)
            
            result = {}
            if wiki_data:
                # Map Wikipedia data
                result['wikipedia_url'] = wiki_data.get('wikipedia_url')
                result['birth_date'] = wiki_data.get('birth_date')
                result['birth_place'] = wiki_data.get('birth_place')
                result['college'] = wiki_data.get('college')
                result['career_highlights'] = wiki_data.get('career_highlights')
                result['awards'] = wiki_data.get('awards')
                result['pro_bowls'] = wiki_data.get('pro_bowls')
                result['all_pro_selections'] = wiki_data.get('all_pro_selections')
                result['hall_of_fame'] = wiki_data.get('hall_of_fame')
                
                result['data_sources'] = ['wikipedia']
                
            return result
            
        except Exception as e:
            logger.debug(f"Wikipedia collection failed for {player_name}: {e}")
            return {}
    
    def _collect_career_stats(self, player_name: str, team: str) -> Dict:
        """Collect career statistics from various sources."""
        try:
            # Use web scraper for career stats
            stats_data = self.web_scraper.scrape_player_profile(player_name, team)
            
            result = {}
            if stats_data:
                # Map career statistics
                result['career_pass_yards'] = stats_data.get('career_pass_yards')
                result['career_pass_tds'] = stats_data.get('career_pass_tds')
                result['career_pass_ints'] = stats_data.get('career_pass_ints')
                result['career_rush_yards'] = stats_data.get('career_rush_yards')
                result['career_rush_tds'] = stats_data.get('career_rush_tds')
                result['career_receptions'] = stats_data.get('career_receptions')
                result['career_rec_yards'] = stats_data.get('career_rec_yards')
                result['career_rec_tds'] = stats_data.get('career_rec_tds')
                result['career_tackles'] = stats_data.get('career_tackles')
                result['career_sacks'] = stats_data.get('career_sacks')
                result['career_interceptions'] = stats_data.get('career_interceptions')
                
                result['data_sources'] = ['web_scraper']
                
            return result
            
        except Exception as e:
            logger.debug(f"Career stats collection failed for {player_name}: {e}")
            return {}
    
    def _collect_contract_data(self, player_name: str, team: str) -> Dict:
        """Collect contract and financial data using Firecrawl for Spotrac scraping."""
        try:
            # Try Firecrawl for Spotrac contract data
            try:
                from firecrawl_agent import FirecrawlAgent
                firecrawl_agent = FirecrawlAgent()
                contract_data = firecrawl_agent.scrape_contract_data(player_name, team)
                
                result = {}
                if contract_data and 'contract_data' in contract_data:
                    contract_info = contract_data['contract_data']
                    result['current_salary'] = contract_info.get('current_salary')
                    result['career_earnings'] = contract_info.get('career_earnings')
                    result['contract_years'] = contract_info.get('contract_years')
                    result['contract_value'] = contract_info.get('contract_value')
                    result['signing_bonus'] = contract_info.get('signing_bonus')
                    result['guaranteed_money'] = contract_info.get('guaranteed_money')
                    result['spotrac_url'] = contract_data.get('spotrac_url')
                    
                    result['data_sources'] = ['firecrawl_agent']
                    
                if result:
                    return result
                    
            except Exception as firecrawl_error:
                logger.debug(f"Firecrawl contract collection failed for {player_name}: {firecrawl_error}")
            
            # Fallback to structured empty data
            return {
                'current_salary': None,
                'career_earnings': None,
                'contract_years': None,
                'contract_value': None,
                'signing_bonus': None,
                'guaranteed_money': None,
                'data_sources': ['contract_data']
            }
            
        except Exception as e:
            logger.debug(f"Contract data collection failed for {player_name}: {e}")
            return {}
    
    def _calculate_quality_score(self, data: Dict) -> float:
        """Calculate data quality score based on populated fields."""
        # Define important fields and their weights
        weighted_fields = {
            'twitter_followers': 2,
            'instagram_followers': 2,
            'wikipedia_url': 3,
            'career_highlights': 2,
            'awards': 2,
            'pro_bowls': 1,
            'birth_date': 1,
            'college': 1,
            'career_pass_yards': 1,
            'career_rush_yards': 1,
            'career_receptions': 1,
            'current_salary': 1,
        }
        
        total_weight = 0
        achieved_weight = 0
        
        for field, weight in weighted_fields.items():
            total_weight += weight
            if field in data and data[field] and data[field] not in ['Unknown', '', None]:
                achieved_weight += weight
        
        return (achieved_weight / total_weight) * 100 if total_weight > 0 else 0


def main():
    """Test the enhanced comprehensive collector."""
    collector = EnhancedComprehensiveCollector()
    
    # Test with high-profile players
    test_players = [
        ('Brock Purdy', '49ers', 'QB'),
        ('Christian McCaffrey', '49ers', 'RB'),
        ('Brandon Aiyuk', '49ers', 'WR')
    ]
    
    for player_name, team, position in test_players:
        print(f"\n=== Testing {player_name} ===")
        
        data = collector.collect_comprehensive_data(player_name, team, position)
        
        print(f"Collection Duration: {data['collection_duration']:.2f}s")
        print(f"Data Quality Score: {data['data_quality_score']:.1f}%")
        print(f"Data Sources: {data['data_sources']}")
        
        # Show collected data
        fields_with_data = []
        for key, value in data.items():
            if value and value not in ['Unknown', '', None] and key not in ['data_sources', 'collection_timestamp', 'scraped_at']:
                fields_with_data.append(f"{key}: {value}")
        
        print(f"Fields with data ({len(fields_with_data)}): {fields_with_data[:5]}...")


if __name__ == "__main__":
    main()