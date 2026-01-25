"""
WNBA Player Data Scraper - Dedicated WNBA-only data collection
Includes both WNBA pro stats and Women's College Basketball stats
Supports: individual player, team, all players, test one player per team
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm

# Add parent directory to path
script_dir = Path(__file__).parent.absolute()
parent_dir = script_dir.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import shared components
import importlib.util

scrape_file_path = script_dir / "scrape"
if not scrape_file_path.exists():
    scrape_file_path = script_dir / "scrape.py"

if not scrape_file_path.exists():
    raise ImportError(f"Could not find scrape module at {scrape_file_path}")

# Load the scrape module
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
    scrape_module = type(sys.modules[__name__])('scrape')
    scrape_module.__file__ = str(scrape_file_path)
    scrape_module.__name__ = 'scrape'
    
    with open(scrape_file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    exec(compile(code, str(scrape_file_path), 'exec'), scrape_module.__dict__)
    
    sys.modules["scrape"] = scrape_module
    sys.modules["gravity.scrape"] = scrape_module

# Import shared components from scrape module
Config = scrape_module.Config
SocialMediaCollector = scrape_module.SocialMediaCollector
NewsAnalyzer = scrape_module.NewsAnalyzer
RiskAnalyzer = scrape_module.RiskAnalyzer
BusinessCollector = scrape_module.BusinessCollector
TrendsAnalyzer = scrape_module.TrendsAnalyzer
IdentityData = scrape_module.IdentityData
BrandData = scrape_module.BrandData
ProximityData = scrape_module.ProximityData
VelocityData = scrape_module.VelocityData
RiskData = scrape_module.RiskData
get_direct_api = scrape_module.get_direct_api

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import WNBA-specific components
try:
    from gravity.wnba_data_models import WNBAPlayerData, WNBAProofData, WNBAIdentityData
except ImportError:
    try:
        from wnba_data_models import WNBAPlayerData, WNBAProofData, WNBAIdentityData
    except ImportError as e:
        logger.error(f"WNBA data models not available: {e}")
        sys.exit(1)

# Import Free APIs collector (no Firecrawl costs for trends, wikipedia, social stats)
try:
    from gravity.free_apis import FreeDataCollector, get_free_data_collector
    FREE_APIS_AVAILABLE = True
except ImportError:
    try:
        from free_apis import FreeDataCollector, get_free_data_collector
        FREE_APIS_AVAILABLE = True
    except ImportError:
        FREE_APIS_AVAILABLE = False
        logger.info("Free APIs not available - trends/wikipedia/social stats will be limited")


# ============================================================================
# WNBA TEAMS AND HELPERS
# ============================================================================

def get_wnba_teams() -> Dict[str, str]:
    """Get WNBA team abbreviations and full names"""
    return {
        "ATL": "Atlanta Dream",
        "CHI": "Chicago Sky",
        "CONN": "Connecticut Sun",
        "DAL": "Dallas Wings",
        "IND": "Indiana Fever",
        "LVA": "Las Vegas Aces",
        "LA": "Los Angeles Sparks",
        "MIN": "Minnesota Lynx",
        "NY": "New York Liberty",
        "PHX": "Phoenix Mercury",
        "SEA": "Seattle Storm",
        "WSH": "Washington Mystics",
        # Alternative abbreviations
        "LV": "Las Vegas Aces",
        "LAX": "Los Angeles Sparks",
        "WAS": "Washington Mystics"
    }


# ============================================================================
# WNBA PLAYER COLLECTOR
# ============================================================================

class WNBAPlayerCollector:
    """Collects comprehensive WNBA player data using ESPN API + collectors"""
    
    def __init__(self):
        self.direct_api = get_direct_api()
        # Initialize Firecrawl scraper for social media only
        try:
            self.scraper = scrape_module.FirecrawlScraper()
        except:
            self.scraper = None
        
        # Initialize collectors (they may require scraper)
        self.social_collector = SocialMediaCollector(self.scraper) if self.scraper else None
        self.news_analyzer = NewsAnalyzer(self.scraper) if self.scraper else None
        self.risk_analyzer = RiskAnalyzer(self.scraper) if self.scraper else None
        self.business_collector = BusinessCollector(self.scraper) if self.scraper else None
        self.trends_analyzer = TrendsAnalyzer(self.scraper) if self.scraper else None
        self._espn_player_data = None  # Cache ESPN data during collection
        
        # Initialize FREE APIs collector (no Firecrawl costs!)
        # Uses: pytrends for Google Trends, Wikipedia API, direct social scraping
        if FREE_APIS_AVAILABLE:
            youtube_api_key = os.getenv("YOUTUBE_API_KEY")  # Optional
            self.free_collector = get_free_data_collector(youtube_api_key)
            logger.info("✅ Free APIs collector initialized (trends, wikipedia, social stats)")
        else:
            self.free_collector = None
    
    def collect_player_data(self, player_name: str, team: str = None, position: str = None) -> WNBAPlayerData:
        """
        Collect all available data for a single WNBA player.
        Returns complete player profile with WNBA and college stats.
        """
        logger.info(f"🏀 Starting WNBA data collection for {player_name}")
        start_time = time.time()
        errors = []
        
        # Initialize result
        player_data = WNBAPlayerData(
            player_name=player_name,
            team=team or "Unknown",
            position=position or "Unknown"
        )
        
        try:
            # Step 1: Get ESPN data (primary source - includes college stats)
            espn_data = self.direct_api.get_complete_wnba_player_data(player_name, team)
            self._espn_player_data = espn_data  # Cache for other collectors
            
            if espn_data:
                # Update team/position from ESPN if not provided
                if not team and espn_data.get("identity", {}).get("team"):
                    team = espn_data["identity"]["team"]
                    player_data.team = team
                
                if not position and espn_data.get("identity", {}).get("position"):
                    position = espn_data["identity"]["position"]
                    player_data.position = position
            
            # Step 2: Collect all data in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(self._collect_identity, player_name, team, position): "identity",
                    executor.submit(self._collect_proof, player_name, position): "proof",
                    executor.submit(self._collect_brand, player_name): "brand",
                    executor.submit(self._collect_proximity, player_name): "proximity",
                    executor.submit(self._collect_velocity, player_name, 
                                   espn_data.get("identity", {}).get("age", 25) if espn_data else 25,
                                   position): "velocity",
                    executor.submit(self._collect_risk, player_name, position,
                                   espn_data.get("identity", {}).get("age", 25) if espn_data else 25): "risk"
                }
                
                for future in as_completed(futures):
                    data_type = futures[future]
                    try:
                        result = future.result()
                        setattr(player_data, data_type, result)
                    except Exception as e:
                        logger.error(f"Failed to collect {data_type} for {player_name}: {e}")
                        errors.append(f"{data_type}: {str(e)}")
            
            player_data.collection_errors = errors
            
            elapsed = time.time() - start_time
            logger.info(f"✅ WNBA data collection complete for {player_name} in {elapsed:.1f}s")
            
        except Exception as e:
            logger.error(f"WNBA data collection failed for {player_name}: {e}")
            player_data.collection_errors.append(str(e))
        
        return player_data
    
    def _collect_identity(self, player_name: str, team: str, position: str) -> WNBAIdentityData:
        """Collect identity data primarily from ESPN API"""
        identity = WNBAIdentityData()
        
        try:
            # Use cached ESPN data
            if self._espn_player_data:
                espn_identity = self._espn_player_data.get("identity", {})
                
                identity.name = espn_identity.get("name", player_name)
                identity.position = espn_identity.get("position", position or "")
                identity.jersey_number = str(espn_identity.get("jersey", ""))
                identity.height = espn_identity.get("height", "")
                identity.weight = espn_identity.get("weight", "")
                identity.age = espn_identity.get("age", 0)
                identity.birth_date = espn_identity.get("birth_date", "")
                
                # Calculate age from birth_date if ESPN doesn't provide it
                if not identity.age and identity.birth_date:
                    try:
                        from datetime import datetime
                        birth_str = identity.birth_date.split('T')[0]
                        birth = datetime.strptime(birth_str, '%Y-%m-%d')
                        today = datetime.now()
                        identity.age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
                        logger.info(f"   ✓ Calculated age from birth_date: {identity.age}")
                    except Exception as e:
                        logger.debug(f"Age calculation failed: {e}")
                
                # Validate hometown to filter out garbage data
                raw_hometown = espn_identity.get("birth_place", "")
                identity.birth_place = self.direct_api._validate_hometown(raw_hometown) if raw_hometown else ""
                
                identity.team = espn_identity.get("team", team or "")
                identity.college = espn_identity.get("college", "")
                
                # Draft info - mark as "Undrafted" if missing
                identity.draft_year = espn_identity.get("draft_year")
                identity.draft_round = espn_identity.get("draft_round")
                identity.draft_pick = espn_identity.get("draft_pick")
                
                # If no draft data, mark as undrafted
                if not identity.draft_year and not identity.draft_round and not identity.draft_pick:
                    identity.draft_year = "Undrafted"
                    identity.draft_round = "Undrafted"
                    identity.draft_pick = "Undrafted"
                
                # Experience - multiple fallback strategies
                experience_years = espn_identity.get("experience", 0)
                
                # If ESPN says 0 or None but we have draft year, calculate it
                if not experience_years and identity.draft_year and isinstance(identity.draft_year, int):
                    experience_years = datetime.now().year - identity.draft_year
                
                # If still 0 and player has age, estimate (most enter WNBA at 21-22)
                if not experience_years and identity.age and identity.age > 21:
                    estimated_draft_age = 22
                    experience_years = identity.age - estimated_draft_age
                    if experience_years < 0:
                        experience_years = 0
                
                identity.experience_years = experience_years or 0
                identity.headshot_url = espn_identity.get("headshot_url", "")
                
                logger.info(f"📋 Identity: {identity.name}, {identity.team}, College: {identity.college}")
                
                # =====================================================================
                # RECRUITING DATA - Get college recruiting info (FREE APIs)
                # =====================================================================
                if identity.college and identity.draft_year and isinstance(identity.draft_year, int):
                    try:
                        from gravity.recruiting_collector import RecruitingCollector
                        recruiting_collector = RecruitingCollector()
                        
                        recruiting_data = recruiting_collector.collect_recruiting_data(
                            player_name=player_name,
                            college=identity.college,
                            draft_year=identity.draft_year,
                            sport='nba'  # WNBA players recruited through college basketball
                        )
                        
                        # Add recruiting data to identity
                        if recruiting_data:
                            identity.recruiting_stars = recruiting_data.get('recruiting_stars')
                            identity.recruiting_ranking = recruiting_data.get('recruiting_ranking')
                            identity.recruiting_state_ranking = recruiting_data.get('recruiting_state_ranking')
                            identity.recruiting_position_ranking = recruiting_data.get('recruiting_position_ranking')
                            identity.eligibility_year = recruiting_data.get('eligibility_year')
                            
                    except Exception as e:
                        logger.debug(f"Recruiting data collection failed: {e}")
                
                # =====================================================================
                # CONTRACT DATA - Get current contract details (FREE - Spotrac)
                # =====================================================================
                try:
                    from gravity.contract_collector import ContractCollector
                    contract_collector = ContractCollector()
                    
                    contract_data = contract_collector.collect_contract_data(
                        player_name=player_name,
                        team=identity.team or team,
                        sport='wnba'
                    )
                    
                    # Map contract data to identity
                    if contract_data:
                        identity.current_contract_length = contract_data.get('contract_years')
                        identity.contract_value = contract_data.get('contract_value')
                        
                        if identity.contract_value:
                            logger.info(f"   💰 Contract: {identity.current_contract_length} years, "
                                       f"${identity.contract_value:,}")
                        
                except Exception as e:
                    logger.debug(f"Contract data collection failed: {e}")
        
        except Exception as e:
            logger.error(f"Identity collection failed for {player_name}: {e}")
            identity.name = player_name
        
        return identity
    
    def _collect_proof(self, player_name: str, position: str) -> WNBAProofData:
        """Collect proof data from ESPN API (WNBA + College stats)"""
        proof = WNBAProofData()
        
        try:
            if self._espn_player_data:
                stats = self._espn_player_data.get("stats", {})
                awards_list = self._espn_player_data.get("awards", [])
                
                # WNBA Stats
                proof.current_season_stats = stats.get("current_season", {})
                proof.career_stats = stats.get("career", {})
                proof.career_stats_by_year = {int(k): v for k, v in stats.get("by_year", {}).items() if k.isdigit()}
                
                # College Stats (Women's College Basketball)
                college_stats = stats.get("college", {})
                proof.college_stats_by_year = {int(k): v for k, v in college_stats.get("by_year", {}).items() if k.isdigit()}
                proof.college_career_stats = college_stats.get("career", {})
                
                # Copy college career totals
                if proof.college_career_stats:
                    proof.college_career_games = proof.college_career_stats.get("career_games", 0)
                    proof.college_career_points = proof.college_career_stats.get("career_points", 0)
                    proof.college_career_rebounds = proof.college_career_stats.get("career_rebounds", 0)
                    proof.college_career_assists = proof.college_career_stats.get("career_assists", 0)
                    proof.college_career_ppg = proof.college_career_stats.get("career_ppg", 0)
                    proof.college_career_rpg = proof.college_career_stats.get("career_rpg", 0)
                    proof.college_career_apg = proof.college_career_stats.get("career_apg", 0)
                
                # Awards
                proof.awards = [a.get("name", "") for a in awards_list if a.get("name")]
                
                # Award counts from pre-calculated fields
                proof.all_star_selections = self._espn_player_data.get("all_star_selections", 0)
                proof.all_wnba_selections = self._espn_player_data.get("all_wnba_selections", 0)
                proof.all_wnba_first_team = self._espn_player_data.get("all_wnba_first_team", 0)
                proof.championships = self._espn_player_data.get("championships", 0)
                proof.mvp_awards = self._espn_player_data.get("mvp_awards", 0)
                proof.finals_mvp = self._espn_player_data.get("finals_mvp", 0)
                proof.dpoy_awards = self._espn_player_data.get("dpoy_awards", 0)
                proof.all_defensive = self._espn_player_data.get("all_defensive", 0)
                proof.rookie_of_year = self._espn_player_data.get("rookie_of_year", 0)
                
                # Career totals from career stats
                if proof.career_stats:
                    proof.career_games = proof.career_stats.get("career_games", 0)
                    proof.career_points = proof.career_stats.get("career_points", 0)
                    proof.career_rebounds = proof.career_stats.get("career_rebounds", 0)
                    proof.career_assists = proof.career_stats.get("career_assists", 0)
                    proof.career_steals = proof.career_stats.get("career_steals", 0)
                    proof.career_blocks = proof.career_stats.get("career_blocks", 0)
                    proof.career_points_per_game = proof.career_stats.get("career_ppg", 0)
                    proof.career_rebounds_per_game = proof.career_stats.get("career_rpg", 0)
                    proof.career_assists_per_game = proof.career_stats.get("career_apg", 0)
                
                # Log summary
                wnba_seasons = len(proof.career_stats_by_year)
                college_seasons = len(proof.college_stats_by_year)
                logger.info(f"📊 Proof: {wnba_seasons} WNBA seasons, {college_seasons} college seasons, {len(proof.awards)} awards")
        
        except Exception as e:
            logger.error(f"Proof collection failed for {player_name}: {e}")
        
        return proof
    
    def _collect_brand(self, player_name: str) -> BrandData:
        """
        Collect brand data.
        Uses Firecrawl for handles only, FREE APIs for follower counts.
        """
        brand = BrandData()
        social_handles = {}
        
        try:
            # Step 1: Get social media HANDLES
            # Try Firecrawl first, fallback to FREE DuckDuckGo
            firecrawl_available = self.social_collector and hasattr(self, 'scraper') and self.scraper and hasattr(self.scraper, 'api_key') and self.scraper.api_key and self.scraper.api_key != "fc-test"
            
            if firecrawl_available:
                logger.info(f"🔍 Finding social media handles for {player_name} (Firecrawl)...")
                for platform in ["twitter", "instagram", "tiktok"]:
                    try:
                        handle = self.social_collector.find_social_handle(player_name, platform)
                        if handle:
                            if platform == "twitter":
                                brand.twitter_handle = handle
                                social_handles["twitter"] = handle
                            elif platform == "instagram":
                                brand.instagram_handle = handle
                                social_handles["instagram"] = handle
                            elif platform == "tiktok":
                                brand.tiktok_handle = handle
                                social_handles["tiktok"] = handle
                    except Exception as e:
                        logger.debug(f"Social media {platform} failed: {e}")
            
            # Fallback to FREE DuckDuckGo search
            if not social_handles and self.free_collector and self.free_collector.ddg_finder:
                logger.info(f"🦆 Finding social media handles for {player_name} (DuckDuckGo - FREE)...")
                try:
                    ddg_handles = self.free_collector.ddg_finder.find_all_social_handles(player_name)
                    
                    if ddg_handles.get("instagram"):
                        brand.instagram_handle = ddg_handles["instagram"]
                        social_handles["instagram"] = ddg_handles["instagram"]
                    
                    if ddg_handles.get("twitter"):
                        brand.twitter_handle = ddg_handles["twitter"]
                        social_handles["twitter"] = ddg_handles["twitter"]
                    
                    if ddg_handles.get("tiktok"):
                        brand.tiktok_handle = ddg_handles["tiktok"]
                        social_handles["tiktok"] = ddg_handles["tiktok"]
                except Exception as e:
                    logger.debug(f"DuckDuckGo search failed: {e}")
            
            # Step 2: Get follower COUNTS using FREE APIs (no Firecrawl!)
            if self.free_collector and social_handles:
                logger.info(f"📊 Getting social stats for {player_name} (FREE APIs)...")
                
                # Get Instagram followers (free)
                if social_handles.get("instagram"):
                    ig_stats = self.free_collector.social.get_instagram_stats(social_handles["instagram"])
                    brand.instagram_followers = ig_stats.get("followers", 0)
                
                # Get Twitter followers (free)
                if social_handles.get("twitter"):
                    tw_stats = self.free_collector.social.get_twitter_stats(social_handles["twitter"])
                    brand.twitter_followers = tw_stats.get("followers", 0)
                
                # Get TikTok followers (free)
                if social_handles.get("tiktok"):
                    tt_stats = self.free_collector.social.get_tiktok_stats(social_handles["tiktok"])
                    brand.tiktok_followers = tt_stats.get("followers", 0)
                
                # Get YouTube stats (free)
                yt_stats = self.free_collector.youtube.get_player_youtube_stats(player_name, "WNBA")
                if yt_stats.get("subscribers"):
                    brand.youtube_subscribers = yt_stats.get("subscribers", 0)
                
                # Get Wikipedia page views (free)
                wiki_stats = self.free_collector.wikipedia.get_page_views(player_name)
                brand.wikipedia_page_views = wiki_stats.get("page_views_30d", 0)
                
                if brand.instagram_followers or brand.twitter_followers:
                    logger.info(f"📈 Social stats: IG={brand.instagram_followers:,}, TW={brand.twitter_followers:,}, Wiki={brand.wikipedia_page_views:,}")
            
            # Step 3: Get news via Google RSS (no Firecrawl)
            if self.news_analyzer:
                try:
                    news_data = self.news_analyzer.analyze_recent_news(player_name)
                    if news_data:
                        brand.recent_news_mentions = news_data.get("total_mentions", 0)
                        brand.recent_news_sentiment = news_data.get("sentiment", 0.0)
                        brand.news_topics = news_data.get("topics", [])
                except Exception as e:
                    logger.debug(f"News analysis failed: {e}")
            
            # Step 4: Get endorsement info via BusinessCollector
            if self.business_collector:
                try:
                    business_data = self.business_collector.collect_business_data(player_name)
                    if business_data:
                        brand.known_endorsements = business_data.get("endorsements", [])
                        brand.estimated_endorsement_value = business_data.get("estimated_value", 0)
                        brand.brand_partnerships = business_data.get("partnerships", [])
                except Exception as e:
                    logger.debug(f"Business data failed: {e}")
        
        except Exception as e:
            logger.error(f"Brand collection failed for {player_name}: {e}")
        
        return brand
    
    def _collect_proximity(self, player_name: str) -> ProximityData:
        """Collect proximity data - no Firecrawl, minimal data"""
        proximity = ProximityData()
        
        # Note: No Firecrawl scraping - return minimal data
        # This could be enhanced with social media connection analysis
        
        return proximity
    
    def _collect_velocity(self, player_name: str, age: int, position: str) -> VelocityData:
        """
        Collect velocity data - career trajectory analysis.
        Uses FREE pytrends for Google Trends (no Firecrawl!).
        """
        velocity = VelocityData()
        
        try:
            # Calculate career stage based on age (women's basketball specific)
            if age < 24:
                velocity.career_stage = "rising"
                velocity.career_stage_score = 0.85
            elif age < 28:
                velocity.career_stage = "prime"
                velocity.career_stage_score = 0.95
            elif age < 32:
                velocity.career_stage = "veteran"
                velocity.career_stage_score = 0.80
            else:
                velocity.career_stage = "late_career"
                velocity.career_stage_score = 0.65
            
            # Use FREE pytrends for Google Trends (no Firecrawl!)
            if self.free_collector:
                try:
                    trends_data = self.free_collector.trends.get_trends_score(player_name, "WNBA")
                    if trends_data.get("trends_score"):
                        velocity.trending_score = trends_data.get("trends_score", 0)
                        momentum = trends_data.get("trends_momentum", "stable")
                        velocity.trending_direction = momentum
                        logger.info(f"📈 Trends for {player_name}: Score={velocity.trending_score}, Direction={momentum}")
                except Exception as e:
                    logger.debug(f"Free trends failed: {e}")
            elif self.trends_analyzer:
                # Fallback to Firecrawl-based trends
                try:
                    trends_data = self.trends_analyzer.get_player_trends(player_name)
                    if trends_data:
                        velocity.trending_score = trends_data.get("interest_over_time", 0)
                        velocity.trending_direction = trends_data.get("direction", "stable")
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Velocity collection failed for {player_name}: {e}")
        
        return velocity
    
    def _collect_risk(self, player_name: str, position: str, age: int) -> RiskData:
        """Collect comprehensive risk data using FREE analyzers"""
        risk = RiskData()
        
        # =====================================================================
        # COMPREHENSIVE INJURY ANALYSIS (FREE - No Firecrawl)
        # =====================================================================
        try:
            from gravity.injury_risk_analyzer import InjuryRiskAnalyzer
            
            injury_analyzer = InjuryRiskAnalyzer()
            injury_data = injury_analyzer.analyze_injury_risk(
                player_name=player_name,
                position=position,
                age=age,
                sport='nba'  # WNBA uses basketball injury rates
            )
            
            # Map injury data
            risk.injury_history = injury_data.get('injury_history', [])
            risk.current_injury_status = injury_data.get('current_injury_status')
            risk.games_missed_career = injury_data.get('games_missed_career', 0)
            risk.games_missed_last_season = injury_data.get('games_missed_last_season', 0)
            risk.injury_risk_score = injury_data.get('injury_risk_score', 5.0)
            risk.position_injury_rate = injury_data.get('position_injury_rate', 50)
            
        except Exception as e:
            logger.debug(f"Injury analysis failed: {e}")
            # Fallback to ESPN data
            if self._espn_player_data:
                injuries = self._espn_player_data.get("injuries", [])
                if injuries:
                    risk.injury_history = injuries
                    risk.injury_risk_score = min(50.0, len(injuries) * 10)
        
        # =====================================================================
        # COMPREHENSIVE CONTROVERSY ANALYSIS (FREE - No Firecrawl)
        # =====================================================================
        try:
            from gravity.advanced_risk_analyzer import AdvancedRiskAnalyzer
            
            risk_analyzer = AdvancedRiskAnalyzer()
            controversy_data = risk_analyzer.analyze_risk(
                player_name=player_name,
                sport='nba'
            )
            
            # Map controversy data
            risk.controversies = controversy_data.get('controversies', [])
            risk.suspensions = [c for c in risk.controversies if 'suspend' in c.get('type', '').lower()]
            risk.arrests = [c for c in risk.controversies if 'arrest' in c.get('type', '').lower()]
            risk.fines = [c for c in risk.controversies if 'fine' in c.get('type', '').lower()]
            risk.controversy_risk_score = controversy_data.get('controversy_risk_score', 5)
            risk.reputation_score = controversy_data.get('reputation_score', 100.0)
            
        except Exception as e:
            logger.debug(f"Controversy analysis failed: {e}")
            risk.controversies = []
            risk.suspensions = []
            risk.arrests = []
            risk.fines = []
            risk.controversy_risk_score = 5
            risk.reputation_score = 100.0
        
        # Age risk calculation
        if age:
            if age > 33:
                risk.age_risk = 25
            elif age > 30:
                risk.age_risk = 12
            else:
                risk.age_risk = 0
        else:
            risk.age_risk = 0
        
        logger.info(f"📊 Risk: {len(risk.injury_history)} injuries, {len(risk.controversies)} controversies, "
                   f"Injury={risk.injury_risk_score:.1f}, Reputation={risk.reputation_score:.1f}")
        
        return risk


# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def save_wnba_results(players_data: List[WNBAPlayerData], output_dir: str = "scrapes/WNBA"):
    """Save WNBA scraping results to JSON and CSV"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output directory
    output_path = Path(output_dir) / timestamp
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Convert to dictionaries
    players_dicts = []
    for player in players_data:
        try:
            player_dict = asdict(player)
            players_dicts.append(player_dict)
        except Exception as e:
            logger.error(f"Failed to convert player data: {e}")
    
    # Save JSON
    json_file = output_path / f"wnba_players_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(players_dicts, f, indent=2, default=str)
    logger.info(f"💾 Saved JSON: {json_file}")
    
    # Save CSV (flattened)
    csv_file = output_path / f"wnba_players_{timestamp}.csv"
    try:
        import pandas as pd
        df = pd.json_normalize(players_dicts)
        df.to_csv(csv_file, index=False)
        logger.info(f"💾 Saved CSV: {csv_file}")
    except ImportError:
        logger.warning("pandas not available, skipping CSV output")
    
    return str(output_path)


# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="WNBA Player Data Scraper")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Player command
    player_parser = subparsers.add_parser("player", help="Scrape a single player")
    player_parser.add_argument("name", help="Player name")
    player_parser.add_argument("team", nargs="?", help="Team name (optional)")
    player_parser.add_argument("position", nargs="?", help="Position (optional)")
    
    # Team command
    team_parser = subparsers.add_parser("team", help="Scrape all players on a team")
    team_parser.add_argument("team", help="Team name or abbreviation")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test with one player per team")
    
    # All command
    all_parser = subparsers.add_parser("all", help="Scrape all WNBA players")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    collector = WNBAPlayerCollector()
    results = []
    
    if args.command == "player":
        # Single player
        player_data = collector.collect_player_data(args.name, args.team, args.position)
        results.append(player_data)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"WNBA Player: {player_data.player_name}")
        print(f"{'='*60}")
        
        if player_data.identity:
            print(f"Team: {player_data.identity.team}")
            print(f"Position: {player_data.identity.position}")
            print(f"College: {player_data.identity.college}")
            print(f"Draft: {player_data.identity.draft_year} Round {player_data.identity.draft_round}, Pick {player_data.identity.draft_pick}")
        
        if player_data.proof:
            print(f"\nWNBA Career:")
            print(f"  Seasons: {len(player_data.proof.career_stats_by_year)}")
            print(f"  Games: {player_data.proof.career_games}")
            print(f"  PPG: {player_data.proof.career_points_per_game}")
            print(f"  RPG: {player_data.proof.career_rebounds_per_game}")
            print(f"  APG: {player_data.proof.career_assists_per_game}")
            
            if player_data.proof.college_stats_by_year:
                print(f"\nCollege Career:")
                print(f"  Seasons: {len(player_data.proof.college_stats_by_year)}")
                print(f"  Games: {player_data.proof.college_career_games}")
                print(f"  PPG: {player_data.proof.college_career_ppg}")
                print(f"  RPG: {player_data.proof.college_career_rpg}")
                print(f"  APG: {player_data.proof.college_career_apg}")
            
            if player_data.proof.awards:
                print(f"\nAwards: {', '.join(player_data.proof.awards[:10])}")
        
        print(f"{'='*60}\n")
    
    elif args.command == "team":
        # Get team roster from ESPN API
        teams = get_wnba_teams()
        team_name = teams.get(args.team.upper(), args.team)
        
        logger.info(f"Fetching roster for {team_name}...")
        
        # Use ESPN API to get team roster
        api = get_direct_api()
        wnba_teams = api.get_wnba_teams()
        
        team_id = None
        for abbrev, team_info in wnba_teams.items():
            if team_name.lower() in team_info.get("name", "").lower() or abbrev.upper() == args.team.upper():
                team_id = team_info.get("id")
                team_name = team_info.get("name")
                break
        
        if team_id:
            roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team_id}/roster"
            import requests
            resp = requests.get(roster_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                players = []
                for athlete in data.get("athletes", []):
                    players.append({
                        "name": athlete.get("displayName"),
                        "position": athlete.get("position", {}).get("abbreviation", "")
                    })
                
                logger.info(f"Found {len(players)} players on {team_name}")
                
                for player_info in tqdm(players, desc=f"Scraping {team_name}"):
                    player_data = collector.collect_player_data(
                        player_info["name"],
                        team_name,
                        player_info["position"]
                    )
                    results.append(player_data)
                    time.sleep(1)  # Rate limiting
    
    elif args.command == "test":
        # Test with one player per team
        teams = get_wnba_teams()
        unique_teams = list(set(teams.values()))
        
        logger.info(f"Testing with one player from each of {len(unique_teams)} teams...")
        
        # Get one player from each team
        api = get_direct_api()
        wnba_teams = api.get_wnba_teams()
        
        for team_name in tqdm(unique_teams, desc="Teams"):
            try:
                # Find team ID
                team_id = None
                for abbrev, team_info in wnba_teams.items():
                    if team_name.lower() in team_info.get("name", "").lower():
                        team_id = team_info.get("id")
                        break
                
                if team_id:
                    roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team_id}/roster"
                    import requests
                    resp = requests.get(roster_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        athletes = data.get("athletes", [])
                        if athletes:
                            first_player = athletes[0]
                            player_data = collector.collect_player_data(
                                first_player.get("displayName"),
                                team_name,
                                first_player.get("position", {}).get("abbreviation", "")
                            )
                            results.append(player_data)
                            time.sleep(1)
            except Exception as e:
                logger.error(f"Failed to test {team_name}: {e}")
    
    elif args.command == "all":
        # Scrape all WNBA players
        teams = get_wnba_teams()
        unique_teams = list(set(teams.values()))
        
        api = get_direct_api()
        wnba_teams = api.get_wnba_teams()
        
        all_players = []
        for team_name in unique_teams:
            try:
                team_id = None
                for abbrev, team_info in wnba_teams.items():
                    if team_name.lower() in team_info.get("name", "").lower():
                        team_id = team_info.get("id")
                        break
                
                if team_id:
                    roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team_id}/roster"
                    import requests
                    resp = requests.get(roster_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        for athlete in data.get("athletes", []):
                            all_players.append({
                                "name": athlete.get("displayName"),
                                "team": team_name,
                                "position": athlete.get("position", {}).get("abbreviation", "")
                            })
            except Exception as e:
                logger.error(f"Failed to get roster for {team_name}: {e}")
        
        logger.info(f"Found {len(all_players)} total WNBA players")
        
        for player_info in tqdm(all_players, desc="Scraping all players"):
            try:
                player_data = collector.collect_player_data(
                    player_info["name"],
                    player_info["team"],
                    player_info["position"]
                )
                results.append(player_data)
                time.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to scrape {player_info['name']}: {e}")
    
    # Save results
    if results:
        output_dir = save_wnba_results(results)
        print(f"\n✅ Saved {len(results)} players to {output_dir}")
    else:
        print("No results to save")


if __name__ == "__main__":
    main()

