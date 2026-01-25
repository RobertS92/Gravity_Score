"""
College Football (CFB) Player Data Scraper - Dedicated CFB data collection
Supports: individual player, team, conference, ranked teams, all FBS
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
FirecrawlScraper = scrape_module.FirecrawlScraper
PlayerData = scrape_module.PlayerData

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import CFB-specific components
try:
    from gravity.cfb_data_models import CFBPlayerData, CFBProofData, CFBIdentityData
    CFB_AVAILABLE = True
except ImportError:
    try:
        from cfb_data_models import CFBPlayerData, CFBProofData, CFBIdentityData
        CFB_AVAILABLE = True
    except ImportError as e:
        CFB_AVAILABLE = False
        logger.error(f"CFB data models not available: {e}")
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
# CFB TEAMS AND CONFERENCES
# ============================================================================

def get_power_five_teams() -> Dict[str, str]:
    """Get Power Five conference teams (SEC, Big Ten, Big 12, ACC, Pac-12 remnants)"""
    return {
        # SEC
        "ALA": "Alabama Crimson Tide",
        "ARK": "Arkansas Razorbacks", 
        "AUB": "Auburn Tigers",
        "FLA": "Florida Gators",
        "UGA": "Georgia Bulldogs",
        "UK": "Kentucky Wildcats",
        "LSU": "LSU Tigers",
        "MISS": "Ole Miss Rebels",
        "MSST": "Mississippi State Bulldogs",
        "MIZZ": "Missouri Tigers",
        "OKLA": "Oklahoma Sooners",
        "SCAR": "South Carolina Gamecocks",
        "TENN": "Tennessee Volunteers",
        "TEX": "Texas Longhorns",
        "TAMU": "Texas A&M Aggies",
        "VAN": "Vanderbilt Commodores",
        # Big Ten
        "ILL": "Illinois Fighting Illini",
        "IU": "Indiana Hoosiers",
        "IOWA": "Iowa Hawkeyes",
        "MD": "Maryland Terrapins",
        "MICH": "Michigan Wolverines",
        "MSU": "Michigan State Spartans",
        "MINN": "Minnesota Golden Gophers",
        "NEB": "Nebraska Cornhuskers",
        "NW": "Northwestern Wildcats",
        "OSU": "Ohio State Buckeyes",
        "ORE": "Oregon Ducks",
        "PSU": "Penn State Nittany Lions",
        "PUR": "Purdue Boilermakers",
        "RUTG": "Rutgers Scarlet Knights",
        "USC": "USC Trojans",
        "UCLA": "UCLA Bruins",
        "WASH": "Washington Huskies",
        "WIS": "Wisconsin Badgers",
        # Big 12
        "AFA": "Air Force Falcons",
        "ARIZ": "Arizona Wildcats",
        "ASU": "Arizona State Sun Devils",
        "BAY": "Baylor Bears",
        "BYU": "BYU Cougars",
        "CIN": "Cincinnati Bearcats",
        "COLO": "Colorado Buffaloes",
        "HOU": "Houston Cougars",
        "ISU": "Iowa State Cyclones",
        "KU": "Kansas Jayhawks",
        "KSU": "Kansas State Wildcats",
        "OKST": "Oklahoma State Cowboys",
        "TCU": "TCU Horned Frogs",
        "TTU": "Texas Tech Red Raiders",
        "UCF": "UCF Knights",
        "WVU": "West Virginia Mountaineers",
        # ACC
        "BC": "Boston College Eagles",
        "CAL": "California Golden Bears",
        "CLEM": "Clemson Tigers",
        "DUKE": "Duke Blue Devils",
        "FSU": "Florida State Seminoles",
        "GT": "Georgia Tech Yellow Jackets",
        "LOU": "Louisville Cardinals",
        "MIA": "Miami Hurricanes",
        "NC": "North Carolina Tar Heels",
        "NCST": "NC State Wolfpack",
        "ND": "Notre Dame Fighting Irish",
        "PITT": "Pittsburgh Panthers",
        "SMU": "SMU Mustangs",
        "STAN": "Stanford Cardinal",
        "SYR": "Syracuse Orange",
        "UVA": "Virginia Cavaliers",
        "VT": "Virginia Tech Hokies",
        "WAKE": "Wake Forest Demon Deacons",
    }


def get_cfb_conferences() -> Dict[str, List[str]]:
    """Get conference to team mapping"""
    return {
        "SEC": ["ALA", "ARK", "AUB", "FLA", "UGA", "UK", "LSU", "MISS", "MSST", 
                "MIZZ", "OKLA", "SCAR", "TENN", "TEX", "TAMU", "VAN"],
        "Big Ten": ["ILL", "IU", "IOWA", "MD", "MICH", "MSU", "MINN", "NEB", "NW",
                    "OSU", "ORE", "PSU", "PUR", "RUTG", "USC", "UCLA", "WASH", "WIS"],
        "Big 12": ["ARIZ", "ASU", "BAY", "BYU", "CIN", "COLO", "HOU", "ISU", "KU",
                   "KSU", "OKST", "TCU", "TTU", "UCF", "WVU"],
        "ACC": ["BC", "CAL", "CLEM", "DUKE", "FSU", "GT", "LOU", "MIA", "NC", 
                "NCST", "ND", "PITT", "SMU", "STAN", "SYR", "UVA", "VT", "WAKE"],
    }


# ============================================================================
# CFB PLAYER COLLECTOR
# ============================================================================

class CFBPlayerCollector:
    """Main class to orchestrate College Football data collection"""
    
    def __init__(self, firecrawl_api_key: str):
        self.scraper = FirecrawlScraper(firecrawl_api_key)
        self.scrapes_base_dir = os.getenv("SCRAPES_DIR", "scrapes")
        
        # Get DirectSportsAPI for ESPN data
        try:
            get_direct_api = scrape_module.get_direct_api
            self.direct_api = get_direct_api()
        except (AttributeError, Exception) as e:
            logger.warning(f"DirectSportsAPI not available: {e}")
            self.direct_api = None
        
        # Store ESPN player data for reuse across collectors
        self._espn_player_data = None
        self._accurate_team = None
        
        # Reuse collectors from NFL (social, news, etc. work the same)
        SocialMediaCollector = scrape_module.SocialMediaCollector
        NewsAnalyzer = scrape_module.NewsAnalyzer
        TrendsAnalyzer = scrape_module.TrendsAnalyzer
        self.social_collector = SocialMediaCollector(self.scraper)
        self.news_analyzer = NewsAnalyzer(self.scraper)
        self.trends_analyzer = TrendsAnalyzer(self.scraper)
        self.trends_analyzer.set_news_analyzer(self.news_analyzer)
        
        # Initialize FREE APIs collector (no Firecrawl costs!)
        # Uses: pytrends for Google Trends, Wikipedia API, direct social scraping
        if FREE_APIS_AVAILABLE:
            youtube_api_key = os.getenv("YOUTUBE_API_KEY")  # Optional
            self.free_collector = get_free_data_collector(youtube_api_key)
            logger.info("✅ Free APIs collector initialized (trends, wikipedia, social stats)")
        else:
            self.free_collector = None
    
    def collect_player_data(self, player_name: str, team: str, position: str):
        """Collect comprehensive CFB player data"""
        BrandData = scrape_module.BrandData
        ProximityData = scrape_module.ProximityData
        VelocityData = scrape_module.VelocityData
        RiskData = scrape_module.RiskData
        
        # Reset ESPN data cache for each player
        self._espn_player_data = None
        self._accurate_team = None
        
        # Get conference from team
        conference = self._get_conference_for_team(team)
        
        # Initialize player data with CFB-specific structure
        player_data = CFBPlayerData(
            player_name=player_name,
            team=team,
            position=position,
            conference=conference
        )
        
        try:
            # STEP 1: Collect Identity first (from ESPN)
            logger.info("📋 Collecting identity data from ESPN CFB API...")
            identity_data = self._collect_identity(player_name, team, position)
            player_data.identity = identity_data
            age = identity_data.age if identity_data else None
            
            # Update team with accurate ESPN data if available
            if self._accurate_team:
                player_data.team = self._accurate_team
            
            # STEP 2: Collect all other data categories in parallel
            logger.info("🚀 Starting parallel data collection...")
            
            max_workers = Config.MAX_CONCURRENT_DATA_COLLECTORS
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_brand = executor.submit(self._collect_brand, player_name)
                future_proof = executor.submit(self._collect_proof, player_name, position)
                future_proximity = executor.submit(self._collect_proximity, player_name)
                future_velocity = executor.submit(self._collect_velocity, player_name, age, position)
                future_risk = executor.submit(self._collect_risk, player_name, position, age)
                
                results = {}
                futures_map = {
                    'brand': future_brand,
                    'proof': future_proof,
                    'proximity': future_proximity,
                    'velocity': future_velocity,
                    'risk': future_risk
                }
                
                for category, future in futures_map.items():
                    try:
                        logger.info(f"⏳ Waiting for {category} data...")
                        result = future.result(timeout=300)
                        results[category] = result
                        logger.info(f"✅ {category.capitalize()} data collected")
                    except Exception as e:
                        logger.error(f"❌ Error collecting {category} data: {e}")
                        if category == 'brand':
                            results[category] = BrandData()
                        elif category == 'proof':
                            results[category] = CFBProofData()
                        elif category == 'proximity':
                            results[category] = ProximityData()
                        elif category == 'velocity':
                            results[category] = VelocityData()
                        elif category == 'risk':
                            results[category] = RiskData()
                        player_data.collection_errors.append(f"{category}: {str(e)}")
            
            player_data.brand = results.get('brand', BrandData())
            player_data.proof = results.get('proof', CFBProofData())
            player_data.proximity = results.get('proximity', ProximityData())
            player_data.velocity = results.get('velocity', VelocityData())
            player_data.risk = results.get('risk', RiskData())
            
            player_data.data_quality_score = self._calculate_quality_score(player_data)
            
        except Exception as e:
            logger.error(f"Error collecting data: {str(e)}")
            player_data.collection_errors.append(str(e))
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ Data collection complete for {player_name}")
        logger.info(f"Data quality score: {player_data.data_quality_score}%")
        logger.info(f"{'='*70}")
        
        return player_data
    
    def _get_conference_for_team(self, team: str) -> str:
        """Get conference for a team abbreviation"""
        conferences = get_cfb_conferences()
        for conf, teams in conferences.items():
            if team.upper() in teams:
                return conf
        return ""
    
    def _collect_identity(self, player_name: str, team: str, position: str):
        """Collect identity data from ESPN CFB API."""
        identity = CFBIdentityData()
        
        # Use ESPN CFB API directly
        if self.direct_api:
            logger.info(f"🏈 ESPN CFB API: Fetching {player_name}...")
            espn_data = self.direct_api.get_complete_cfb_player_data(player_name, team)
            
            if espn_data and espn_data.get("identity"):
                # Store for reuse in _collect_proof
                self._espn_player_data = espn_data
                
                player_info = espn_data["identity"]
                
                # Map ESPN data to CFBIdentityData
                identity.age = player_info.get("age")
                identity.birth_date = player_info.get("birth_date")
                
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
                
                identity.nationality = player_info.get("birth_country", "USA")
                
                # Validate hometown to filter out garbage data
                raw_hometown = player_info.get("hometown") or player_info.get("birth_place")
                identity.hometown = self.direct_api._validate_hometown(raw_hometown) if raw_hometown else ""
                
                identity.college = player_info.get("college") or player_info.get("team")
                identity.conference = player_info.get("conference")
                identity.class_year = player_info.get("class_year")
                identity.height = player_info.get("height")
                identity.weight = player_info.get("weight")
                identity.jersey_number = player_info.get("jersey_number")
                
                # Update team if ESPN has correct info
                if player_info.get("team"):
                    self._accurate_team = player_info.get("team")
                
                # Log detailed info
                logger.info(f"✅ ESPN CFB API: {player_name} - {player_info.get('team', '?')}, {player_info.get('position', '?')}")
                logger.info(f"   Hometown: {identity.hometown}, Class: {identity.class_year}")
                
                # Log awards summary
                all_american = espn_data.get("all_american", 0)
                heisman = espn_data.get("heisman_finalist", False)
                if all_american or heisman:
                    logger.info(f"   🏆 Awards: All-American={all_american}, Heisman={'Yes' if heisman else 'No'}")
                
                # =====================================================================
                # RECRUITING DATA - For current college players
                # Calculate recruiting year from class year
                # =====================================================================
                if identity.college and identity.class_year:
                    try:
                        from gravity.recruiting_collector import RecruitingCollector
                        from datetime import datetime
                        
                        recruiting_collector = RecruitingCollector()
                        
                        # Calculate recruiting year from class year
                        # Freshman (2024) → recruited in 2024
                        # Sophomore (2024) → recruited in 2023
                        # Junior (2024) → recruited in 2022
                        # Senior (2024) → recruited in 2021
                        current_year = datetime.now().year
                        class_to_years_offset = {
                            'freshman': 0,
                            'fr': 0,
                            'sophomore': 1,
                            'so': 1,
                            'junior': 2,
                            'jr': 2,
                            'senior': 3,
                            'sr': 3,
                            'redshirt freshman': 1,
                            'redshirt sophomore': 2,
                            'redshirt junior': 3,
                            'redshirt senior': 4,
                            '5th year': 4
                        }
                        
                        years_offset = class_to_years_offset.get(identity.class_year.lower(), 0)
                        recruiting_year = current_year - years_offset
                        
                        recruiting_data = recruiting_collector.collect_recruiting_data(
                            player_name=player_name,
                            college=identity.college,
                            draft_year=recruiting_year + 4,  # Estimate draft year (4 years after recruiting)
                            sport='nfl'  # CFB players will go to NFL
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
                
                return identity
        
        logger.warning(f"ESPN CFB API failed for {player_name}")
        return identity
    
    def _collect_brand(self, player_name: str):
        """
        Collect brand/social media data.
        Uses Firecrawl for handles, FREE APIs for follower counts.
        News uses Google RSS (no Firecrawl).
        """
        BrandData = scrape_module.BrandData
        brand = BrandData()
        social_handles = {}
        
        # Step 1: Get social media HANDLES
        # Try Firecrawl first, fallback to FREE DuckDuckGo
        firecrawl_available = self.social_collector and hasattr(self, 'scraper') and self.scraper.api_key and self.scraper.api_key != "fc-test"
        
        if firecrawl_available:
            try:
                logger.info(f"🔍 Finding social media handles for {player_name} (Firecrawl)...")
                
                ig_handle = self.social_collector.find_social_handle(player_name, 'instagram')
                if ig_handle:
                    brand.instagram_handle = ig_handle
                    social_handles["instagram"] = ig_handle
                
                tw_handle = self.social_collector.find_social_handle(player_name, 'twitter')
                if tw_handle:
                    brand.twitter_handle = tw_handle
                    social_handles["twitter"] = tw_handle
                
                tt_handle = self.social_collector.find_social_handle(player_name, 'tiktok')
                if tt_handle:
                    brand.tiktok_handle = tt_handle
                    social_handles["tiktok"] = tt_handle
                
            except Exception as e:
                logger.debug(f"Firecrawl search failed for {player_name}: {e}")
        
        # Fallback to FREE DuckDuckGo search
        if not social_handles and hasattr(self, 'free_collector') and self.free_collector and self.free_collector.ddg_finder:
            try:
                logger.info(f"🦆 Finding social media handles for {player_name} (DuckDuckGo - FREE)...")
                
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
        if hasattr(self, 'free_collector') and self.free_collector and social_handles:
            try:
                logger.info(f"📊 Getting social stats for {player_name} (FREE APIs)...")
                
                if social_handles.get("instagram"):
                    ig_stats = self.free_collector.social.get_instagram_stats(social_handles["instagram"])
                    brand.instagram_followers = ig_stats.get("followers", 0)
                
                if social_handles.get("twitter"):
                    tw_stats = self.free_collector.social.get_twitter_stats(social_handles["twitter"])
                    brand.twitter_followers = tw_stats.get("followers", 0)
                
                if social_handles.get("tiktok"):
                    tt_stats = self.free_collector.social.get_tiktok_stats(social_handles["tiktok"])
                    brand.tiktok_followers = tt_stats.get("followers", 0)
                
                # Get Wikipedia page views (free)
                wiki_stats = self.free_collector.wikipedia.get_page_views(player_name)
                brand.wikipedia_page_views = wiki_stats.get("page_views_30d", 0)
                
                if brand.instagram_followers or brand.twitter_followers:
                    logger.info(f"📈 Social stats: IG={brand.instagram_followers:,}, TW={brand.twitter_followers:,}, Wiki={brand.wikipedia_page_views:,}")
                
            except Exception as e:
                logger.debug(f"Free API stats collection failed: {e}")
        
        # Step 3: News - Use Google News RSS (NO Firecrawl)
        try:
            get_direct_api = scrape_module.get_direct_api
            api = get_direct_api()
            
            news_data = api.get_google_news_rss(f"{player_name} college football")
            if news_data:
                brand.news_headline_count_30d = len(news_data)
                brand.news_headline_count_7d = len([n for n in news_data if n.get('recent', False)])
                brand.mention_velocity = len(news_data) / 30.0
                brand.brand_sentiment = 0.0
                
                logger.info(f"📰 News for {player_name}: {brand.news_headline_count_30d} articles (Google RSS)")
        except Exception as e:
            logger.debug(f"News collection failed for {player_name}: {e}")
            brand.news_headline_count_30d = 0
            brand.news_headline_count_7d = 0
        
        # Step 4: Google Trends (FREE pytrends)
        if hasattr(self, 'free_collector') and self.free_collector:
            try:
                trends_data = self.free_collector.trends.get_trends_score(player_name, "college football")
                brand.google_trends_score = trends_data.get('trends_score', 0)
            except Exception as e:
                logger.debug(f"Free trends failed: {e}")
        
        return brand
    
    def _collect_proof(self, player_name: str, position: str):
        """Collect CFB stats and proof data from cached ESPN data."""
        proof = CFBProofData()
        
        # Use cached ESPN data from _collect_identity
        if self._espn_player_data and self._espn_player_data.get("stats"):
            logger.info(f"📊 Using cached ESPN CFB stats for {player_name}...")
            espn_stats = self._espn_player_data["stats"]
            espn_awards = self._espn_player_data.get("awards", [])
            
            # Map ESPN stats to proof structure
            if espn_stats.get("current_season"):
                proof.current_season_stats = espn_stats["current_season"]
            
            if espn_stats.get("career"):
                proof.career_stats = espn_stats["career"]
            
            if espn_stats.get("by_year"):
                proof.career_stats_by_year = espn_stats["by_year"]
            
            # CFB-specific awards
            proof.all_american = self._espn_player_data.get("all_american", 0)
            proof.all_american_first_team = self._espn_player_data.get("all_american_first_team", 0)
            proof.heisman_winner = self._espn_player_data.get("heisman_winner", False)
            proof.heisman_votes = 1 if self._espn_player_data.get("heisman_finalist", False) else 0
            proof.conference_honors = self._espn_player_data.get("conference_honors", 0)
            proof.awards = espn_awards
            
            # Log stats summary
            career = proof.career_stats
            logger.info(f"✅ ESPN CFB Stats: Games={career.get('total_games', 'N/A')}")
            logger.info(f"   🏆 Awards: All-American={proof.all_american}, Heisman={'Yes' if proof.heisman_winner else 'No'}")
        
        # =====================================================================
        # NIL DATA - Collect NIL deals and valuation (FREE)
        # =====================================================================
        try:
            from gravity.nil_collector import NILDealCollector
            
            # Get college from cached identity data
            college = None
            if self._espn_player_data and self._espn_player_data.get("identity"):
                college = self._espn_player_data["identity"].get("college") or self._espn_player_data["identity"].get("team")
            
            if college:
                nil_collector = NILDealCollector()
                nil_data = nil_collector.collect_nil_data(
                    player_name=player_name,
                    college=college,
                    sport='football'
                )
                
                # Add NIL data to proof
                if nil_data:
                    proof.nil_valuation = nil_data.get('nil_valuation')
                    proof.nil_ranking = nil_data.get('nil_ranking')
                    proof.nil_deals = nil_data.get('nil_deals', [])
                    
                    # Log NIL summary
                    if proof.nil_valuation or proof.nil_deals:
                        val_str = f"${proof.nil_valuation:,}" if proof.nil_valuation else "N/A"
                        logger.info(f"   💰 NIL: {val_str} valuation, {len(proof.nil_deals)} deals")
        
        except Exception as e:
            logger.debug(f"NIL data collection failed: {e}")
        
        return proof
        
        logger.warning(f"No ESPN stats available for {player_name}")
        return proof
    
    def _collect_proximity(self, player_name: str):
        """Collect market position data. NO FIRECRAWL."""
        ProximityData = scrape_module.ProximityData
        proximity = ProximityData()
        
        # Skip Firecrawl-heavy operations
        proximity.endorsements = []
        proximity.brand_partnerships = []
        proximity.upcoming_media = []
        
        logger.info(f"📊 Proximity data for {player_name}: No Firecrawl scraping (disabled)")
        return proximity
    
    def _collect_velocity(self, player_name: str, age: int, position: str):
        """Collect momentum data. NO FIRECRAWL."""
        VelocityData = scrape_module.VelocityData
        velocity = VelocityData()
        
        # Set default values
        velocity.google_trends_momentum = 0.0
        velocity.career_trajectory = 'ascending'  # College players are rising
        velocity.performance_trend = 'stable'
        velocity.engagement_trend = 'stable'
        velocity.follower_growth_rate_30d = 0.0
        velocity.follower_growth_rate_7d = 0.0
        
        # College players are typically on the rise
        velocity.age_curve_position = 1.0  # Rising
        
        logger.info(f"📊 Velocity data for {player_name}: Trajectory={velocity.career_trajectory}")
        return velocity
    
    def _collect_risk(self, player_name: str, position: str, age: int):
        """Collect comprehensive risk data using FREE analyzers"""
        RiskData = scrape_module.RiskData
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
                sport='nfl'  # CFB players will go to NFL
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
            if self._espn_player_data and self._espn_player_data.get("injuries"):
                risk.injury_history = self._espn_player_data["injuries"]
                risk.injury_risk_score = min(50.0, len(risk.injury_history) * 10)
        
        # =====================================================================
        # COMPREHENSIVE CONTROVERSY ANALYSIS (FREE - No Firecrawl)
        # =====================================================================
        try:
            from gravity.advanced_risk_analyzer import AdvancedRiskAnalyzer
            
            risk_analyzer = AdvancedRiskAnalyzer()
            controversy_data = risk_analyzer.analyze_risk(
                player_name=player_name,
                sport='nfl'
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
        
        # Age risk (college players are young)
        risk.age_risk = 0
        
        logger.info(f"📊 Risk: {len(risk.injury_history)} injuries, {len(risk.controversies)} controversies, "
                   f"Injury={risk.injury_risk_score:.1f}, Reputation={risk.reputation_score:.1f}")
        
        return risk
    
    def _calculate_quality_score(self, player_data) -> float:
        """Calculate data quality score"""
        score = 0
        max_score = 100
        
        # Identity data (30 points)
        if player_data.identity:
            if player_data.identity.hometown:
                score += 5
            if player_data.identity.college:
                score += 5
            if player_data.identity.class_year:
                score += 5
            if player_data.identity.height:
                score += 5
            if player_data.identity.jersey_number:
                score += 5
            if player_data.identity.conference:
                score += 5
        
        # Stats data (30 points)
        if player_data.proof:
            if player_data.proof.current_season_stats:
                score += 15
            if player_data.proof.career_stats:
                score += 15
        
        # Brand data (20 points)
        if player_data.brand:
            if player_data.brand.instagram_handle or player_data.brand.twitter_handle:
                score += 10
            if player_data.brand.news_headline_count_30d:
                score += 10
        
        # Other (20 points)
        if player_data.proof and player_data.proof.awards:
            score += 10
        if player_data.team:
            score += 10
        
        return round((score / max_score) * 100, 1)
    
    def _export_combined_files(self, all_players: List, mode: str = "all"):
        """Export all players to combined JSON and CSV files"""
        if not hasattr(self, 'output_folder'):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_folder = os.path.join(self.scrapes_base_dir, "CFB", timestamp)
        
        os.makedirs(self.output_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export combined JSON
        json_filename = f"cfb_{mode}_players_{timestamp}.json"
        json_filepath = os.path.join(self.output_folder, json_filename)
        
        all_data = [asdict(p) for p in all_players]
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, default=str)
        
        logger.info(f"📄 Combined JSON exported to {json_filepath}")
        
        # Export combined CSV
        csv_filename = f"cfb_{mode}_players_{timestamp}.csv"
        csv_filepath = os.path.join(self.output_folder, csv_filename)
        
        if all_data:
            # Flatten data for CSV
            import csv
            flattened = []
            for player in all_data:
                flat = {"player_name": player.get("player_name", "")}
                flat["team"] = player.get("team", "")
                flat["position"] = player.get("position", "")
                flat["conference"] = player.get("conference", "")
                
                # Flatten identity
                identity = player.get("identity", {})
                for k, v in identity.items():
                    flat[f"identity_{k}"] = v
                
                # Flatten proof
                proof = player.get("proof", {})
                for k, v in proof.items():
                    if not isinstance(v, (dict, list)):
                        flat[f"proof_{k}"] = v
                
                # Flatten brand
                brand = player.get("brand", {})
                for k, v in brand.items():
                    if not isinstance(v, (dict, list)):
                        flat[f"brand_{k}"] = v
                
                flattened.append(flat)
            
            if flattened:
                keys = flattened[0].keys()
                with open(csv_filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(flattened)
                
                logger.info(f"📊 Combined CSV exported to {csv_filepath}")
        
        return json_filepath
    
    def export_to_json(self, player_data, filename: str = None) -> str:
        """Export player data to JSON file"""
        if not hasattr(self, 'output_folder'):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_folder = os.path.join(self.scrapes_base_dir, "CFB", timestamp)
        
        os.makedirs(self.output_folder, exist_ok=True)
        
        if filename is None:
            safe_name = player_data.player_name.replace(" ", "_").replace(".", "")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.json"
        
        filepath = os.path.join(self.output_folder, filename)
        
        # Convert to dict
        data_dict = asdict(player_data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, indent=2, default=str)
        
        logger.info(f"Data exported to {filepath}")
        return filepath


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def print_usage():
    """Print usage instructions"""
    print("""
College Football Player Data Collector - Usage

Environment Variables:
  FIRECRAWL_API_KEY    - Required: Your Firecrawl API key
  YOUTUBE_API_KEY      - Optional: For YouTube stats (free)
  SCRAPE_MODE          - Optional: Selection mode

Command Line Usage:
  python gravity/cfb_scraper.py [mode] [args...]
  
  Examples:
    # Single player
    python gravity/cfb_scraper.py player "Travis Hunter" "Colorado" "WR"
    
    # Team roster
    python gravity/cfb_scraper.py team "UGA"
    
    # Conference
    python gravity/cfb_scraper.py conference "SEC"
    
    # Power 5 teams only (SEC, Big Ten, Big 12, ACC) - RECOMMENDED
    python gravity/cfb_scraper.py power5
    
    # Test mode (one player per Power 5 team)
    python gravity/cfb_scraper.py test
    
    # All teams (Power 5 + Group of 5 - takes longer)
    python gravity/cfb_scraper.py all
""")


def main():
    """Main entry point"""
    # Get API key
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print_usage()
        logger.error("Please set your Firecrawl API key!")
        logger.error("Set FIRECRAWL_API_KEY environment variable")
        sys.exit(1)
    
    # Parse arguments
    args = sys.argv[1:]
    
    if not args:
        print_usage()
        sys.exit(0)
    
    mode = args[0].lower()
    collector = CFBPlayerCollector(api_key)
    
    # Create output folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collector.output_folder = os.path.join(collector.scrapes_base_dir, "CFB", timestamp)
    os.makedirs(collector.output_folder, exist_ok=True)
    logger.info(f"📁 Output folder: {collector.output_folder}")
    
    if mode == "player":
        # Single player mode
        if len(args) < 4:
            logger.error("Usage: cfb_scraper.py player <name> <team> <position>")
            sys.exit(1)
        
        player_name = args[1]
        team = args[2]
        position = args[3]
        
        logger.info(f"Collecting data for {player_name} ({team}, {position})...")
        player_data = collector.collect_player_data(player_name, team, position)
        collector.export_to_json(player_data)
        logger.info(f"✅ Done!")
    
    elif mode == "team":
        # Team roster mode
        if len(args) < 2:
            logger.error("Usage: cfb_scraper.py team <team_abbrev>")
            sys.exit(1)
        
        team_abbrev = args[1].upper()
        teams = get_power_five_teams()
        
        if team_abbrev not in teams:
            logger.error(f"Team {team_abbrev} not found. Available: {list(teams.keys())[:20]}...")
            sys.exit(1)
        
        team_name = teams[team_abbrev]
        logger.info(f"Getting roster for {team_name}...")
        
        # Get roster from ESPN
        if collector.direct_api:
            cfb_teams = collector.direct_api.get_cfb_teams()
            team_info = cfb_teams.get(team_abbrev, {})
            team_id = team_info.get("id")
            
            if team_id:
                roster = collector.direct_api.get_cfb_team_roster(team_id)
                logger.info(f"Found {len(roster)} players on {team_name} roster")
                
                for player in tqdm(roster[:10], desc=f"Collecting {team_name}"):  # Limit for testing
                    try:
                        player_data = collector.collect_player_data(
                            player["name"],
                            team_name,
                            player.get("position", "")
                        )
                        collector.export_to_json(player_data)
                    except Exception as e:
                        logger.error(f"Error collecting {player['name']}: {e}")
    
    elif mode == "conference":
        # Conference mode
        if len(args) < 2:
            logger.error("Usage: cfb_scraper.py conference <conference_name>")
            sys.exit(1)
        
        conf_name = args[1].upper()
        conferences = get_cfb_conferences()
        
        if conf_name not in conferences:
            logger.error(f"Conference {conf_name} not found. Available: {list(conferences.keys())}")
            sys.exit(1)
        
        team_abbrevs = conferences[conf_name]
        teams = get_power_five_teams()
        
        logger.info(f"Collecting data for {conf_name} ({len(team_abbrevs)} teams)...")
        
        for abbrev in tqdm(team_abbrevs, desc=f"Collecting {conf_name}"):
            team_name = teams.get(abbrev, abbrev)
            # Would collect full rosters here - limited for example
            logger.info(f"Would collect roster for {team_name}")
    
    elif mode == "power5":
        # Power 5 teams only (SEC, Big Ten, Big 12, ACC)
        teams = get_power_five_teams()
        logger.info(f"🏈 Collecting data for all {len(teams)} Power 5 teams...")
        
        all_players = []
        
        for team_abbrev, team_name in tqdm(teams.items(), desc="Power 5 Teams"):
            try:
                if collector.direct_api:
                    # Get team roster from ESPN
                    cfb_teams = collector.direct_api.get_cfb_teams()
                    team_info = cfb_teams.get(team_abbrev, {})
                    team_id = team_info.get("id")
                    
                    if team_id:
                        roster = collector.direct_api.get_cfb_team_roster(team_id)
                        logger.info(f"📋 {team_name}: {len(roster)} players")
                        
                        for player in roster:
                            try:
                                player_data = collector.collect_player_data(
                                    player["name"],
                                    team_name,
                                    player.get("position", "")
                                )
                                all_players.append(player_data)
                            except Exception as e:
                                logger.error(f"Error collecting {player['name']}: {e}")
            except Exception as e:
                logger.error(f"Error with team {team_name}: {e}")
        
        # Export all players to combined files
        if all_players:
            collector._export_combined_files(all_players, "power5")
            logger.info(f"✅ Collected data for {len(all_players)} Power 5 players")
    
    elif mode == "test":
        # Test mode - one player per Power 5 team
        teams = get_power_five_teams()
        logger.info(f"🧪 Test mode: Collecting ONE player per Power 5 team ({len(teams)} teams)...")
        
        all_players = []
        
        for team_abbrev, team_name in tqdm(list(teams.items())[:10], desc="Test Teams"):  # First 10 teams
            try:
                if collector.direct_api:
                    cfb_teams = collector.direct_api.get_cfb_teams()
                    team_info = cfb_teams.get(team_abbrev, {})
                    team_id = team_info.get("id")
                    
                    if team_id:
                        roster = collector.direct_api.get_cfb_team_roster(team_id)
                        if roster:
                            player = roster[0]  # First player only
                            logger.info(f"📋 {team_name}: Testing {player['name']}")
                            
                            try:
                                player_data = collector.collect_player_data(
                                    player["name"],
                                    team_name,
                                    player.get("position", "")
                                )
                                all_players.append(player_data)
                            except Exception as e:
                                logger.error(f"Error collecting {player['name']}: {e}")
            except Exception as e:
                logger.error(f"Error with team {team_name}: {e}")
        
        if all_players:
            collector._export_combined_files(all_players, "test")
            logger.info(f"✅ Test complete: Collected data for {len(all_players)} players")
    
    elif mode == "all":
        # All FBS teams (Power 5 + Group of 5)
        teams = get_power_five_teams()  # Start with Power 5
        logger.info(f"🏈 Collecting data for all {len(teams)} teams (Power 5)...")
        logger.info("💡 Tip: Use 'power5' mode for faster results with major programs only")
        
        all_players = []
        
        for team_abbrev, team_name in tqdm(teams.items(), desc="All Teams"):
            try:
                if collector.direct_api:
                    cfb_teams = collector.direct_api.get_cfb_teams()
                    team_info = cfb_teams.get(team_abbrev, {})
                    team_id = team_info.get("id")
                    
                    if team_id:
                        roster = collector.direct_api.get_cfb_team_roster(team_id)
                        logger.info(f"📋 {team_name}: {len(roster)} players")
                        
                        for player in roster:
                            try:
                                player_data = collector.collect_player_data(
                                    player["name"],
                                    team_name,
                                    player.get("position", "")
                                )
                                all_players.append(player_data)
                            except Exception as e:
                                logger.error(f"Error collecting {player['name']}: {e}")
            except Exception as e:
                logger.error(f"Error with team {team_name}: {e}")
        
        if all_players:
            collector._export_combined_files(all_players, "all")
            logger.info(f"✅ Collected data for {len(all_players)} players")
    
    else:
        print_usage()
        logger.error(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()

