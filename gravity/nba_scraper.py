"""
NBA Player Data Scraper - Dedicated NBA-only data collection
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

# Import NBA and shared components
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
NFLPlayerCollector = scrape_module.NFLPlayerCollector  # For reusing collectors
PlayerData = scrape_module.PlayerData

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import NBA-specific components
try:
    from gravity.nba_stats_collector import NBAStatsCollector
    from gravity.nba_data_models import NBAPlayerData, NBAProofData
    NBA_AVAILABLE = True
except ImportError:
    try:
        from nba_stats_collector import NBAStatsCollector
        from nba_data_models import NBAPlayerData, NBAProofData
        NBA_AVAILABLE = True
    except ImportError as e:
        NBA_AVAILABLE = False
        logger.error("NBA stats collector not available. Please install required dependencies.")
        sys.exit(1)

# Import Free APIs collector (no Firecrawl needed for trends, YouTube, Wikipedia)
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
# NBA TEAMS AND HELPERS
# ============================================================================

def get_nba_teams() -> Dict[str, str]:
    """Get NBA team abbreviations and full names"""
    return {
        "ATL": "Atlanta Hawks",
        "BOS": "Boston Celtics",
        "BKN": "Brooklyn Nets",
        "CHA": "Charlotte Hornets",
        "CHI": "Chicago Bulls",
        "CLE": "Cleveland Cavaliers",
        "DAL": "Dallas Mavericks",
        "DEN": "Denver Nuggets",
        "DET": "Detroit Pistons",
        "GSW": "Golden State Warriors",
        "HOU": "Houston Rockets",
        "IND": "Indiana Pacers",
        "LAC": "LA Clippers",
        "LAL": "Los Angeles Lakers",
        "MEM": "Memphis Grizzlies",
        "MIA": "Miami Heat",
        "MIL": "Milwaukee Bucks",
        "MIN": "Minnesota Timberwolves",
        "NOP": "New Orleans Pelicans",
        "NYK": "New York Knicks",
        "OKC": "Oklahoma City Thunder",
        "ORL": "Orlando Magic",
        "PHI": "Philadelphia 76ers",
        "PHX": "Phoenix Suns",
        "POR": "Portland Trail Blazers",
        "SAC": "Sacramento Kings",
        "SAS": "San Antonio Spurs",
        "TOR": "Toronto Raptors",
        "UTA": "Utah Jazz",
        "WAS": "Washington Wizards"
    }


def get_nba_team_roster(collector, team_name: str) -> List[Dict]:
    """Get NBA team roster from NBA.com using Firecrawl"""
    logger.info(f"Fetching NBA roster for {team_name}...")
    
    players = []
    
    # Map team names to NBA.com slugs
    team_slug_map = {
        "Atlanta Hawks": "hawks",
        "Boston Celtics": "celtics",
        "Brooklyn Nets": "nets",
        "Charlotte Hornets": "hornets",
        "Chicago Bulls": "bulls",
        "Cleveland Cavaliers": "cavaliers",
        "Dallas Mavericks": "mavericks",
        "Denver Nuggets": "nuggets",
        "Detroit Pistons": "pistons",
        "Golden State Warriors": "warriors",
        "Houston Rockets": "rockets",
        "Indiana Pacers": "pacers",
        "LA Clippers": "clippers",
        "Los Angeles Clippers": "clippers",
        "Los Angeles Lakers": "lakers",
        "Memphis Grizzlies": "grizzlies",
        "Miami Heat": "heat",
        "Milwaukee Bucks": "bucks",
        "Minnesota Timberwolves": "timberwolves",
        "New Orleans Pelicans": "pelicans",
        "New York Knicks": "knicks",
        "Oklahoma City Thunder": "thunder",
        "Orlando Magic": "magic",
        "Philadelphia 76ers": "76ers",
        "Phoenix Suns": "suns",
        "Portland Trail Blazers": "blazers",
        "Sacramento Kings": "kings",
        "San Antonio Spurs": "spurs",
        "Toronto Raptors": "raptors",
        "Utah Jazz": "jazz",
        "Washington Wizards": "wizards"
    }
    
    # Get team slug
    team_slug = team_slug_map.get(team_name)
    if not team_slug:
        # Try to find by partial match
        team_name_lower = team_name.lower()
        for full_name, slug in team_slug_map.items():
            if team_name_lower in full_name.lower() or full_name.lower() in team_name_lower:
                team_slug = slug
                break
    
    if not team_slug:
        logger.error(f"Could not find team slug for {team_name}")
        return []
    
    # Try multiple NBA.com roster URL formats
    roster_urls = [
        f"https://www.nba.com/team/{team_slug}/roster",
        f"https://www.nba.com/teams/{team_slug}/roster",
        f"https://www.nba.com/{team_slug}/roster"
    ]
    
    for roster_url in roster_urls:
        try:
            logger.info(f"Trying NBA.com roster URL: {roster_url}")
            result = collector.scraper.scrape(roster_url)
            
            if result and 'markdown' in result:
                text = result['markdown']
                
                # Try LLM parsing if available
                if Config.USE_LLM_PARSING:
                    try:
                        extraction_schema = {
                            "type": "object",
                            "properties": {
                                "players": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "position": {"type": "string"},
                                            "jersey_number": {"type": "integer"}
                                        }
                                    }
                                }
                            }
                        }
                        
                        llm_data = collector.scraper.scrape_with_llm_parsing(
                            roster_url,
                            extraction_schema=extraction_schema
                        )
                        
                        if llm_data and 'players' in llm_data:
                            for player in llm_data['players']:
                                if player.get('name'):
                                    players.append({
                                        'name': player.get('name', '').strip(),
                                        'position': player.get('position', 'UNK').strip().upper(),
                                        'jersey_number': player.get('jersey_number'),
                                        'team': team_name
                                    })
                            
                            if players:
                                logger.info(f"✓ LLM extracted {len(players)} players from {roster_url}")
                                break
                    except Exception as e:
                        logger.debug(f"LLM parsing failed: {e}")
                
                # Fallback to regex extraction
                if not players:
                    import re
                    
                    # Pattern: Name, Position, Number
                    player_patterns = [
                        r'([A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?)[^\n]*?(PG|SG|SF|PF|C)[^\n]*?#?(\d+)',
                        r'#(\d+)[^\n]*?([A-Z][a-z]+ [A-Z][a-z]+)[^\n]*?(PG|SG|SF|PF|C)',
                        r'([A-Z][a-z]+ [A-Z][a-z]+)[^\n]{0,50}(PG|SG|SF|PF|C)'
                    ]
                    
                    for pattern in player_patterns:
                        matches = re.finditer(pattern, text, re.MULTILINE)
                        for match in matches:
                            if len(match.groups()) >= 2:
                                name = match.group(1) if match.lastindex >= 1 else None
                                position = match.group(2) if match.lastindex >= 2 else 'UNK'
                                number = match.group(3) if match.lastindex >= 3 else None
                                
                                if name and len(name.split()) >= 2:
                                    try:
                                        jersey = int(number) if number else None
                                    except:
                                        jersey = None
                                    
                                    if not any(p.get('name', '').lower() == name.lower() for p in players):
                                        players.append({
                                            'name': name.strip(),
                                            'position': position.strip().upper() if position else 'UNK',
                                            'jersey_number': jersey,
                                            'team': team_name
                                        })
                    
                    if players:
                        logger.info(f"✓ Regex extracted {len(players)} players from {roster_url}")
                        break
            
            time.sleep(Config.REQUEST_DELAY)
            
        except Exception as e:
            logger.debug(f"Failed to scrape {roster_url}: {e}")
            continue
    
    if not players:
        logger.warning(f"⚠️  Could not extract roster for {team_name}")
    
    return players


def get_nba_test_players(collector) -> List[Dict]:
    """Get one well-known player from each NBA team for testing"""
    test_players = {
        "Atlanta Hawks": {"name": "Trae Young", "position": "PG"},
        "Boston Celtics": {"name": "Jayson Tatum", "position": "SF"},
        "Brooklyn Nets": {"name": "Mikal Bridges", "position": "SF"},
        "Charlotte Hornets": {"name": "LaMelo Ball", "position": "PG"},
        "Chicago Bulls": {"name": "DeMar DeRozan", "position": "SG"},
        "Cleveland Cavaliers": {"name": "Donovan Mitchell", "position": "SG"},
        "Dallas Mavericks": {"name": "Luka Dončić", "position": "PG"},
        "Denver Nuggets": {"name": "Nikola Jokić", "position": "C"},
        "Detroit Pistons": {"name": "Cade Cunningham", "position": "PG"},
        "Golden State Warriors": {"name": "Stephen Curry", "position": "PG"},
        "Houston Rockets": {"name": "Alperen Şengün", "position": "C"},
        "Indiana Pacers": {"name": "Tyrese Haliburton", "position": "PG"},
        "LA Clippers": {"name": "Kawhi Leonard", "position": "SF"},
        "Los Angeles Lakers": {"name": "LeBron James", "position": "SF"},
        "Memphis Grizzlies": {"name": "Ja Morant", "position": "PG"},
        "Miami Heat": {"name": "Jimmy Butler", "position": "SF"},
        "Milwaukee Bucks": {"name": "Giannis Antetokounmpo", "position": "PF"},
        "Minnesota Timberwolves": {"name": "Anthony Edwards", "position": "SG"},
        "New Orleans Pelicans": {"name": "Zion Williamson", "position": "PF"},
        "New York Knicks": {"name": "Jalen Brunson", "position": "PG"},
        "Oklahoma City Thunder": {"name": "Shai Gilgeous-Alexander", "position": "PG"},
        "Orlando Magic": {"name": "Paolo Banchero", "position": "PF"},
        "Philadelphia 76ers": {"name": "Joel Embiid", "position": "C"},
        "Phoenix Suns": {"name": "Devin Booker", "position": "SG"},
        "Portland Trail Blazers": {"name": "Anfernee Simons", "position": "SG"},
        "Sacramento Kings": {"name": "De'Aaron Fox", "position": "PG"},
        "San Antonio Spurs": {"name": "Victor Wembanyama", "position": "C"},
        "Toronto Raptors": {"name": "Scottie Barnes", "position": "PF"},
        "Utah Jazz": {"name": "Lauri Markkanen", "position": "PF"},
        "Washington Wizards": {"name": "Kyle Kuzma", "position": "PF"}
    }
    
    players = []
    for team_name, player_info in test_players.items():
        players.append({
            "name": player_info["name"],
            "team": team_name,
            "position": player_info["position"]
        })
    
    return players


# ============================================================================
# NBA PLAYER COLLECTOR
# ============================================================================

class NBAPlayerCollector:
    """Main class to orchestrate NBA data collection"""
    
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
        
        # Initialize NBA stats collector
        if NBA_AVAILABLE:
            self.stats_collector = NBAStatsCollector(self.scraper)
        else:
            logger.error("NBA stats collector not available")
            sys.exit(1)
        
        # Reuse other collectors from NFL (social, news, etc. work the same)
        SocialMediaCollector = scrape_module.SocialMediaCollector
        NewsAnalyzer = scrape_module.NewsAnalyzer
        RiskAnalyzer = scrape_module.RiskAnalyzer
        BusinessCollector = scrape_module.BusinessCollector
        TrendsAnalyzer = scrape_module.TrendsAnalyzer
        self.social_collector = SocialMediaCollector(self.scraper)
        self.news_analyzer = NewsAnalyzer(self.scraper)
        self.risk_analyzer = RiskAnalyzer(self.scraper)
        self.business_collector = BusinessCollector(self.scraper)
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
        
        # Initialize Perplexity AI fallback (same as NFL scraper)
        try:
            from gravity.perplexity_fallback import PerplexityFallback
            self.perplexity = PerplexityFallback()
        except ImportError as e:
            logger.warning(f"Could not import PerplexityFallback: {e}")
            self.perplexity = None
    
    def collect_player_data(self, player_name: str, team: str, position: str):
        """Collect comprehensive NBA player data using NBA-specific data structures"""
        IdentityData = scrape_module.IdentityData
        BrandData = scrape_module.BrandData
        ProximityData = scrape_module.ProximityData
        VelocityData = scrape_module.VelocityData
        RiskData = scrape_module.RiskData
        
        # Reset ESPN data cache for each player
        self._espn_player_data = None
        self._accurate_team = None
        
        # Initialize player data with NBA-specific structure
        player_data = NBAPlayerData(
            player_name=player_name,
            team=team,
            position=position
        )
        
        try:
            # STEP 1: Collect Identity first (from ESPN)
            logger.info("📋 Collecting identity data from ESPN NBA API...")
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
                            results[category] = NBAProofData()
                        elif category == 'proximity':
                            results[category] = ProximityData()
                        elif category == 'velocity':
                            results[category] = VelocityData()
                        elif category == 'risk':
                            results[category] = RiskData()
                        player_data.collection_errors.append(f"{category}: {str(e)}")
            
            player_data.brand = results.get('brand', BrandData())
            player_data.proof = results.get('proof', NBAProofData())
            player_data.proximity = results.get('proximity', ProximityData())
            player_data.velocity = results.get('velocity', VelocityData())
            player_data.risk = results.get('risk', RiskData())
            
            player_data.data_quality_score = self._calculate_quality_score(player_data)
            
            # STEP 3: AI Fallback for missing fields (Perplexity)
            if self.perplexity and self.perplexity.enabled and Config.USE_AI_FALLBACK:
                logger.info(f"🤖 Running comprehensive AI fallback for {player_name}...")
                
                # Build context for better AI searches
                context = {
                    'position': position,
                    'team': player_data.team,
                    'college': player_data.identity.college if player_data.identity else None
                }
                
                fields_filled = self.perplexity.check_all_missing_fields(
                    player_data, 
                    player_name, 
                    sport='NBA',
                    max_cost=Config.AI_FALLBACK_MAX_COST_PER_PLAYER
                )
                
                if fields_filled > 0:
                    stats = self.perplexity.get_stats()
                    logger.info(f"💰 AI Fallback: Filled {fields_filled} fields, "
                               f"${stats['estimated_cost']:.3f} total cost, "
                               f"{stats['calls_made']} API calls")
                    
                    # Recalculate quality score after AI enrichment
                    player_data.data_quality_score = self._calculate_quality_score(player_data)
            
        except Exception as e:
            logger.error(f"Error collecting data: {str(e)}")
            player_data.collection_errors.append(str(e))
            if not player_data.identity:
                player_data.identity = IdentityData()
            if not player_data.brand:
                player_data.brand = BrandData()
            if not player_data.proof:
                player_data.proof = NBAProofData()
            if not player_data.proximity:
                player_data.proximity = ProximityData()
            if not player_data.velocity:
                player_data.velocity = VelocityData()
            if not player_data.risk:
                player_data.risk = RiskData()
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ Data collection complete for {player_name}")
        logger.info(f"Data quality score: {player_data.data_quality_score}%")
        logger.info(f"{'='*70}")
        
        return player_data
    
    def _collect_identity(self, player_name: str, team: str, position: str):
        """
        Collect identity data from ESPN NBA API (Core + Overview APIs).
        Gets draft info, hometown, awards, stats from ESPN.
        """
        IdentityData = scrape_module.IdentityData
        identity = IdentityData()
        
        # Use ESPN NBA API directly
        if self.direct_api:
            logger.info(f"🏀 ESPN NBA API: Fetching {player_name}...")
            espn_data = self.direct_api.get_complete_nba_player_data(player_name, team)
            
            if espn_data and espn_data.get("identity"):
                # Store for reuse in _collect_proof
                self._espn_player_data = espn_data
                
                player_info = espn_data["identity"]
                
                # Map ESPN data to IdentityData
                identity.age = player_info.get("age")
                identity.birth_date = player_info.get("birth_date")
                
                # Calculate age from birth_date if ESPN doesn't provide it
                if not identity.age and identity.birth_date:
                    try:
                        from datetime import datetime
                        # Parse birth date (various formats)
                        birth_str = identity.birth_date.split('T')[0]  # Remove time if present
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
                
                identity.college = player_info.get("college") or ""
                
                # Draft info - mark as "Undrafted" if missing
                identity.draft_year = player_info.get("draft_year")
                identity.draft_round = player_info.get("draft_round")
                identity.draft_pick = player_info.get("draft_pick")
                
                # If no draft data, mark as undrafted
                if not identity.draft_year and not identity.draft_round and not identity.draft_pick:
                    identity.draft_year = "Undrafted"
                    identity.draft_round = "Undrafted"
                    identity.draft_pick = "Undrafted"
                
                identity.height = player_info.get("height")
                identity.weight = player_info.get("weight")
                
                # Experience - multiple fallback strategies
                experience_years = player_info.get("experience_years", 0)
                
                # If ESPN says 0 or None but we have draft year, calculate it
                if not experience_years and identity.draft_year and isinstance(identity.draft_year, int):
                    experience_years = datetime.now().year - identity.draft_year
                
                # If still 0 and player has age, estimate (most enter NBA at 19-20)
                if not experience_years and identity.age and identity.age > 19:
                    estimated_draft_age = 20
                    experience_years = identity.age - estimated_draft_age
                    if experience_years < 0:
                        experience_years = 0
                
                identity.years_in_league = experience_years or 0
                identity.jersey_number = player_info.get("jersey_number")
                
                # Update team if ESPN has correct info
                if player_info.get("team"):
                    self._accurate_team = player_info.get("team")
                
                # Log detailed info
                draft_info = f"Draft: {identity.draft_year} R{identity.draft_round} P{identity.draft_pick}" if identity.draft_year else "Undrafted"
                logger.info(f"✅ ESPN NBA API: {player_name} - {player_info.get('team', '?')}, {player_info.get('position', '?')}")
                logger.info(f"   Hometown: {identity.hometown}, {draft_info}")
                logger.info(f"   Experience: {identity.years_in_league} years, College: {identity.college or 'N/A'}")
                
                # Log awards summary
                all_star = espn_data.get("all_star_selections", 0)
                all_nba = espn_data.get("all_nba_selections", 0)
                mvp = espn_data.get("mvp_awards", 0)
                champs = espn_data.get("championships", 0)
                if all_star or all_nba or mvp or champs:
                    logger.info(f"   🏆 Awards: All-Star={all_star}, All-NBA={all_nba}, MVP={mvp}, Championships={champs}")
                
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
                            sport='nba'
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
                    
                    # Get accurate team name
                    team_name = self._accurate_team or team
                    
                    contract_data = contract_collector.collect_contract_data(
                        player_name=player_name,
                        team=team_name,
                        sport='nba'
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
                
                return identity
        
        # Fallback to NFL method if ESPN fails
        logger.warning(f"ESPN NBA API failed, using fallback for {player_name}")
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        return nfl_collector._collect_identity(player_name, team, position)
    
    def _collect_brand(self, player_name: str):
        """
        Collect brand/social media data.
        Uses Firecrawl ONLY for finding social media handles.
        Uses FREE APIs for follower counts, Wikipedia views, etc.
        News uses Google RSS (no Firecrawl).
        """
        BrandData = scrape_module.BrandData
        brand = BrandData()
        
        # Step 1: Get social media HANDLES
        # Try Firecrawl first, fallback to FREE DuckDuckGo search
        social_handles = {}
        firecrawl_available = self.social_collector and hasattr(self.scraper, 'api_key') and self.scraper.api_key and self.scraper.api_key != "fc-test"
        
        if firecrawl_available:
            # Use Firecrawl (paid)
            try:
                logger.info(f"🔍 Finding social media handles for {player_name} (Firecrawl)...")
                
                ig_handle = self.social_collector.find_social_handle(player_name, 'instagram')
                brand.instagram_handle = ig_handle
                if ig_handle:
                    social_handles["instagram"] = ig_handle
                
                tw_handle = self.social_collector.find_social_handle(player_name, 'twitter')
                brand.twitter_handle = tw_handle
                if tw_handle:
                    social_handles["twitter"] = tw_handle
                
                tt_handle = self.social_collector.find_social_handle(player_name, 'tiktok')
                brand.tiktok_handle = tt_handle
                if tt_handle:
                    social_handles["tiktok"] = tt_handle
                
                yt_channel = self.social_collector.find_social_handle(player_name, 'youtube')
                brand.youtube_channel = yt_channel
                
            except Exception as e:
                logger.debug(f"Firecrawl search failed for {player_name}: {e}")
        
        # Fallback to FREE DuckDuckGo search if Firecrawl not available or failed
        if not social_handles and self.free_collector and self.free_collector.ddg_finder:
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
                
                if ddg_handles.get("youtube"):
                    brand.youtube_channel = ddg_handles["youtube"]
                
            except Exception as e:
                logger.debug(f"DuckDuckGo search failed for {player_name}: {e}")
        
        # Step 2: Get follower COUNTS using FREE APIs (no Firecrawl!)
        if self.free_collector and social_handles:
            try:
                logger.info(f"📊 Getting social stats for {player_name} (FREE APIs)...")
                
                # Get Instagram followers (free)
                if social_handles.get("instagram"):
                    ig_stats = self.free_collector.social.get_instagram_stats(social_handles["instagram"])
                    brand.instagram_followers = ig_stats.get("followers", 0)
                    brand.instagram_verified = ig_stats.get("verified", False)
                
                # Get Twitter followers (free)
                if social_handles.get("twitter"):
                    tw_stats = self.free_collector.social.get_twitter_stats(social_handles["twitter"])
                    brand.twitter_followers = tw_stats.get("followers", 0)
                    brand.twitter_verified = tw_stats.get("verified", False)
                
                # Get TikTok followers (free)
                if social_handles.get("tiktok"):
                    tt_stats = self.free_collector.social.get_tiktok_stats(social_handles["tiktok"])
                    brand.tiktok_followers = tt_stats.get("followers", 0)
                    brand.tiktok_likes = tt_stats.get("likes", 0)
                
                # Get YouTube stats (free)
                yt_stats = self.free_collector.youtube.get_player_youtube_stats(player_name, "NBA")
                if yt_stats.get("subscribers"):
                    brand.youtube_subscribers = yt_stats.get("subscribers", 0)
                    brand.youtube_views = yt_stats.get("total_views", 0)
                    brand.youtube_videos_count = yt_stats.get("video_count", 0)
                
                # Get Wikipedia page views (free)
                wiki_stats = self.free_collector.wikipedia.get_page_views(player_name)
                brand.wikipedia_page_views = wiki_stats.get("page_views_30d", 0)
                
                logger.info(f"📈 Social stats: IG={brand.instagram_followers:,}, TW={brand.twitter_followers:,}, Wiki={brand.wikipedia_page_views:,}")
                
            except Exception as e:
                logger.debug(f"Free API stats collection failed for {player_name}: {e}")
        
        # Step 3: News - Use Google News RSS (NO Firecrawl)
        try:
            get_direct_api = scrape_module.get_direct_api
            api = get_direct_api()
            
            news_data = api.get_google_news_rss(f"{player_name} NBA basketball")
            if news_data:
                brand.news_headline_count_30d = len(news_data)
                brand.news_headline_count_7d = len([n for n in news_data if n.get('recent', False)])
                brand.mention_velocity = len(news_data) / 30.0  # Per day
                
                # Simple sentiment (no LLM)
                brand.brand_sentiment = 0.0  # Neutral default
                
                logger.info(f"📰 News for {player_name}: {brand.news_headline_count_30d} articles (Google RSS)")
        except Exception as e:
            logger.debug(f"News collection failed for {player_name}: {e}")
            brand.news_headline_count_30d = 0
            brand.news_headline_count_7d = 0
        
        return brand
    
    def _collect_proof(self, player_name: str, position: str):
        """
        Collect NBA stats and proof data.
        Uses cached ESPN data with comprehensive awards from Overview API.
        """
        proof = NBAProofData()
        
        # First, try to use cached ESPN data from _collect_identity
        if self._espn_player_data and self._espn_player_data.get("stats"):
            logger.info(f"📊 Using cached ESPN NBA stats for {player_name}...")
            espn_stats = self._espn_player_data["stats"]
            espn_awards = self._espn_player_data.get("awards", [])
            
            # Map ESPN stats to proof structure
            if espn_stats.get("current_season"):
                proof.current_season_stats = espn_stats["current_season"]
            
            if espn_stats.get("career"):
                proof.career_stats = espn_stats["career"]
            
            if espn_stats.get("by_year"):
                proof.career_stats_by_year = espn_stats["by_year"]
            
            # Extract game-by-game stats (gamelog)
            if self._espn_player_data.get("current_season_gamelog"):
                proof.current_season_gamelog = self._espn_player_data["current_season_gamelog"]
                proof.games_played_current_season = len(proof.current_season_gamelog)
                proof.recent_games = self._espn_player_data.get("recent_games", [])
                logger.info(f"   📊 Gamelog: {proof.games_played_current_season} games this season")
            
            if self._espn_player_data.get("gamelog_by_year"):
                proof.gamelog_by_year = self._espn_player_data["gamelog_by_year"]
                total_historical_games = sum(len(games) for games in proof.gamelog_by_year.values())
                logger.info(f"   📊 Historical: {total_historical_games} games across {len(proof.gamelog_by_year)} seasons")
            
            # NBA-specific awards from ESPN Overview API
            proof.all_star_selections = self._espn_player_data.get("all_star_selections", 0)
            proof.all_star_mvp = self._espn_player_data.get("all_star_mvp", 0)
            proof.all_nba_selections = self._espn_player_data.get("all_nba_selections", 0)
            proof.all_nba_first_team = self._espn_player_data.get("all_nba_first_team", 0)
            proof.championships = self._espn_player_data.get("championships", 0)
            proof.mvp_awards = self._espn_player_data.get("mvp_awards", 0)
            proof.finals_mvp = self._espn_player_data.get("finals_mvp", 0)
            proof.dpoy_awards = self._espn_player_data.get("dpoy_awards", 0)
            proof.all_defensive = self._espn_player_data.get("all_defensive", 0)
            proof.all_defensive_first = self._espn_player_data.get("all_defensive_first", 0)
            proof.scoring_titles = self._espn_player_data.get("scoring_titles", 0)
            proof.rookie_of_year = self._espn_player_data.get("rookie_of_year", 0)
            proof.nba_cup_mvp = self._espn_player_data.get("nba_cup_mvp", 0)
            proof.awards = espn_awards
            
            # College stats
            college_data = espn_stats.get("college", {})
            if college_data:
                proof.college_stats_by_year = college_data.get("by_year", {})
                proof.college_career_stats = college_data.get("career", {})
                
                # Extract college career totals
                if proof.college_career_stats:
                    proof.college_career_games = proof.college_career_stats.get("career_games", 0)
                    proof.college_career_points = proof.college_career_stats.get("career_points", 0)
                    proof.college_career_rebounds = proof.college_career_stats.get("career_rebounds", 0)
                    proof.college_career_assists = proof.college_career_stats.get("career_assists", 0)
                    proof.college_career_ppg = proof.college_career_stats.get("career_ppg", 0)
                    proof.college_career_rpg = proof.college_career_stats.get("career_rpg", 0)
                    proof.college_career_apg = proof.college_career_stats.get("career_apg", 0)
            
            # Log stats summary
            career = proof.career_stats
            ppg = career.get('PPG', career.get('career_ppg', career.get('avgPoints', 'N/A')))
            rpg = career.get('RPG', career.get('career_rpg', career.get('avgRebounds', 'N/A')))
            apg = career.get('APG', career.get('career_apg', career.get('avgAssists', 'N/A')))
            
            logger.info(f"✅ ESPN NBA Stats: PPG={ppg}, RPG={rpg}, APG={apg}")
            logger.info(f"   🏆 Awards: All-Star={proof.all_star_selections}, All-NBA={proof.all_nba_selections}, MVP={proof.mvp_awards}, Champs={proof.championships}")
            
            if proof.dpoy_awards or proof.finals_mvp or proof.all_defensive:
                logger.info(f"   🛡️ Defense: DPOY={proof.dpoy_awards}, All-Def={proof.all_defensive}, Finals MVP={proof.finals_mvp}")
            
            if proof.college_stats_by_year:
                logger.info(f"   🎓 College: {len(proof.college_stats_by_year)} seasons, {proof.college_career_ppg} PPG")
            
            return proof
        
        # Fallback to NBAStatsCollector if no cached ESPN data
        if self.stats_collector:
            logger.info(f"📊 Collecting NBA stats via NBAStatsCollector for {player_name}...")
            proof_stats = self.stats_collector.collect_stats(player_name, position)
            
            # Map stats to proof data structure
            career_stats = proof_stats.get('career_stats', {}) or {}
            current_season_stats = proof_stats.get('current_season_stats', {}) or {}
            last_season_stats = proof_stats.get('last_season_stats', {}) or {}
            
            proof.career_stats = career_stats
            proof.current_season_stats = current_season_stats
            proof.last_season_stats = last_season_stats
            proof.career_stats_by_year = proof_stats.get('career_stats_by_year', {}) or {}
            
            # NBA-specific awards
            proof.all_star_selections = proof_stats.get('all_star_selections', 0)
            proof.all_nba_selections = proof_stats.get('all_nba_selections', 0)
            proof.championships = proof_stats.get('championships', 0)
            proof.mvp_awards = proof_stats.get('mvp_awards', 0)
            proof.awards = proof_stats.get('awards', []) or []
            
            logger.info(f"✅ Collected NBA stats via NBAStatsCollector")
        
        return proof
    
    def _collect_proximity(self, player_name: str):
        """
        Collect market position data including endorsements.
        Uses ProximityCollector (same as NFL) for comprehensive data.
        """
        ProximityData = scrape_module.ProximityData
        proximity = ProximityData()
        
        # Try ProximityCollector with timeout protection (same as NFL)
        prox_success = False
        try:
            from gravity.proximity_collector import ProximityCollector
            prox_collector = ProximityCollector()
            
            # Collect with timeout
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(prox_collector.collect_all_proximity_data, player_name, 'nba')
                try:
                    prox_data = future.result(timeout=20)  # 20 second timeout
                    
                    # Map collected data
                    proximity.endorsements = prox_data.get('endorsements', [])
                    proximity.endorsement_value = prox_data.get('endorsement_value')
                    proximity.brand_partnerships = prox_data.get('brand_partnerships', [])
                    proximity.upcoming_media = prox_data.get('upcoming_media', [])
                    proximity.recent_interviews = prox_data.get('recent_interviews', [])
                    proximity.podcast_appearances = prox_data.get('podcast_appearances', [])
                    proximity.business_ventures = prox_data.get('business_ventures', [])
                    proximity.investments = prox_data.get('investments', [])
                    
                    prox_success = True
                    
                    if proximity.endorsement_value:
                        logger.info(f"   💰 Endorsements: ${proximity.endorsement_value:,.0f} ({len(proximity.endorsements)} brands)")
                    elif proximity.endorsements:
                        logger.info(f"   💰 Endorsements: {len(proximity.endorsements)} brands")
                        
                except concurrent.futures.TimeoutError:
                    logger.warning(f"⏱️  ProximityCollector timed out for {player_name} (>20s)")
                    
        except Exception as e:
            logger.warning(f"ProximityCollector failed: {e}")
        
        # Fallback to BusinessCollector if ProximityCollector failed
        if not prox_success and hasattr(self, 'business_collector'):
            try:
                business_data = self.business_collector.collect_business_data(player_name)
                
                # Filter to verified brands only
                verified_brands = [
                    'Nike', 'Adidas', 'Under Armour', 'Puma', 'New Balance', 'Jordan Brand',
                    'Gatorade', 'Pepsi', 'Coca-Cola', 'State Farm', 'GEICO',
                    'Apple', 'Samsung', 'Beats', 'Bose', 'EA Sports', '2K Sports'
                ]
                
                raw_endorsements = business_data.get('endorsements', [])
                filtered_endorsements = []
                
                for e in raw_endorsements:
                    brand = e['brand'] if isinstance(e, dict) else e
                    if brand and isinstance(brand, str):
                        for verified in verified_brands:
                            if verified.lower() in brand.lower():
                                filtered_endorsements.append(verified)
                                break
                
                proximity.endorsements = list(set(filtered_endorsements))
                proximity.business_ventures = business_data.get('ventures', [])
                proximity.investments = business_data.get('investments', [])
                
            except Exception as e2:
                logger.warning(f"BusinessCollector also failed: {e2}")
        
        return proximity
    
    def _collect_velocity(self, player_name: str, age: int, position: str):
        """
        Collect momentum data.
        Uses FREE pytrends for Google Trends (no Firecrawl costs!).
        """
        VelocityData = scrape_module.VelocityData
        velocity = VelocityData()
        
        # Set default values
        velocity.google_trends_momentum = 0.0
        velocity.career_trajectory = 'stable'
        velocity.performance_trend = 'stable'
        velocity.engagement_trend = 'stable'
        velocity.follower_growth_rate_30d = 0.0
        velocity.follower_growth_rate_7d = 0.0
        
        # Get Google Trends data using FREE pytrends (no Firecrawl!)
        if self.free_collector:
            try:
                trends_data = self.free_collector.trends.get_trends_score(player_name, "NBA")
                
                if trends_data.get("trends_score"):
                    velocity.google_trends_momentum = float(trends_data["trends_score"])
                    
                    # Map momentum to engagement trend
                    momentum = trends_data.get("trends_momentum", "stable")
                    if momentum == "rising":
                        velocity.engagement_trend = "rising"
                    elif momentum == "falling":
                        velocity.engagement_trend = "declining"
                    else:
                        velocity.engagement_trend = "stable"
                    
                    logger.info(f"📈 Trends for {player_name}: Score={velocity.google_trends_momentum}, Momentum={momentum}")
            except Exception as e:
                logger.debug(f"Trends collection failed for {player_name}: {e}")
        
        # Calculate age curve position if age available
        if age:
            # NBA players typically peak around 27-28
            if age < 24:
                velocity.age_curve_position = 0.6  # Rising
                velocity.career_trajectory = 'ascending'
            elif age < 28:
                velocity.age_curve_position = 1.0  # Peak
                velocity.career_trajectory = 'peak'
            elif age < 32:
                velocity.age_curve_position = 0.8  # Plateau
                velocity.career_trajectory = 'plateau'
            else:
                velocity.age_curve_position = 0.5  # Declining
                velocity.career_trajectory = 'descending'
        
        logger.info(f"📊 Velocity data for {player_name}: Trajectory={velocity.career_trajectory}")
        return velocity
    
    def _collect_risk(self, player_name: str, position: str, age: int):
        """
        Collect comprehensive risk data using FREE analyzers
        """
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
                sport='nba'
            )
            
            # Map injury data to RiskData
            risk.injury_history = injury_data.get('injury_history', [])
            risk.current_injury_status = injury_data.get('current_injury_status')
            risk.games_missed_career = injury_data.get('games_missed_career', 0)
            risk.games_missed_last_season = injury_data.get('games_missed_last_season', 0)
            risk.injury_risk_score = injury_data.get('injury_risk_score', 5.0)
            risk.position_injury_rate = injury_data.get('position_injury_rate', 50)
            
        except Exception as e:
            logger.debug(f"Injury risk analysis failed: {e}")
            # Fallback to ESPN injury data if comprehensive analysis fails
            if self._espn_player_data and self._espn_player_data.get("injuries"):
                injuries = self._espn_player_data["injuries"]
                risk.injury_history = injuries
                risk.injury_risk_score = 5.0 if not injuries else min(50.0, len(injuries) * 10)
        
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
            
            # Map controversy data to RiskData
            risk.controversies = controversy_data.get('controversies', [])
            risk.suspensions = [c for c in risk.controversies if 'suspend' in c.get('type', '').lower()]
            risk.arrests = [c for c in risk.controversies if 'arrest' in c.get('type', '').lower()]
            risk.fines = [c for c in risk.controversies if 'fine' in c.get('type', '').lower()]
            risk.controversy_risk_score = controversy_data.get('controversy_risk_score', 5)
            risk.reputation_score = controversy_data.get('reputation_score', 100.0)
            
        except Exception as e:
            logger.debug(f"Controversy risk analysis failed: {e}")
            # Set safe defaults
            risk.controversies = []
            risk.suspensions = []
            risk.fines = []
            risk.arrests = []
            risk.controversy_risk_score = 5
            risk.reputation_score = 100.0
        
        # Age risk calculation
        if age:
            if age >= 35:
                risk.age_risk = 30
            elif age >= 32:
                risk.age_risk = 15
            elif age >= 30:
                risk.age_risk = 5
            else:
                risk.age_risk = 0
        else:
            risk.age_risk = 0
        
        logger.info(f"📊 Risk: {len(risk.injury_history)} injuries, {len(risk.controversies)} controversies, "
                   f"Injury risk={risk.injury_risk_score:.1f}, Reputation={risk.reputation_score:.1f}")
        
        return risk
    
    def _calculate_quality_score(self, player_data: PlayerData) -> float:
        """Calculate data quality score - reuse NFL method"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        return nfl_collector._calculate_quality_score(player_data)
    
    def export_both(self, player_data: PlayerData):
        """Export player data to both JSON and CSV"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        if hasattr(self, 'output_folder') and self.output_folder:
            nfl_collector.output_folder = self.output_folder
        return nfl_collector.export_both(player_data)
    
    def export_multiple_to_csv(self, player_data_list: List[PlayerData], filename: str = None) -> str:
        """Export multiple players to a single CSV file"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        if hasattr(self, 'output_folder') and self.output_folder:
            nfl_collector.output_folder = self.output_folder
        return nfl_collector.export_multiple_to_csv(player_data_list, filename)


# ============================================================================
# PLAYER COLLECTION
# ============================================================================

def collect_players_by_selection(collector, selection: str = None) -> List[Dict]:
    """
    Collect NBA players based on selection mode
    """
    players = []
    
    if not selection:
        if len(sys.argv) > 1:
            selection = sys.argv[1]
        else:
            selection = os.getenv("SCRAPE_MODE", "interactive")
    
    if selection == "interactive" or selection is None:
        print("\n" + "="*70)
        print("NBA Player Data Collector")
        print("="*70)
        print("\nSelect collection mode:")
        print("1. Single player")
        print("2. Team roster")
        print("3. All teams")
        print("4. Test mode (one well-known player per team)")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            player_name = input("Enter player name: ").strip()
            team = input("Enter team name: ").strip()
            position = input("Enter position (PG, SG, SF, PF, C): ").strip().upper()
            players = [{"name": player_name, "team": team, "position": position}]
        
        elif choice == "2":
            teams = get_nba_teams()
            print("\nAvailable NBA teams:")
            for abbrev, full_name in sorted(teams.items(), key=lambda x: x[1]):
                print(f"  {abbrev}: {full_name}")
            team_input = input("\nEnter team abbreviation or full name: ").strip()
            
            team_name = None
            if team_input.upper() in teams:
                team_name = teams[team_input.upper()]
            else:
                for abbrev, full_name in teams.items():
                    if team_input.lower() in full_name.lower():
                        team_name = full_name
                        break
            
            if team_name:
                roster = get_nba_team_roster(collector, team_name)
                players = roster
            else:
                logger.error(f"Team not found: {team_input}")
                return []
        
        elif choice == "3":
            teams = get_nba_teams()
            print(f"\nCollecting rosters for all {len(teams)} NBA teams...")
            for abbrev, team_name in teams.items():
                roster = get_nba_team_roster(collector, team_name)
                players.extend(roster)
                time.sleep(Config.REQUEST_DELAY)
        
        elif choice == "4":
            print(f"\n🧪 Test Mode: Collecting one well-known player from each NBA team...")
            players = get_nba_test_players(collector)
            if players:
                print(f"✓ Selected {len(players)} test players (one per team)")
    
    elif selection == "player":
        player_name = os.getenv("PLAYER_NAME")
        team = os.getenv("PLAYER_TEAM")
        position = os.getenv("PLAYER_POSITION")
        
        if not all([player_name, team, position]):
            if not player_name:
                player_name = sys.argv[2] if len(sys.argv) > 2 else None
            if not team:
                team = sys.argv[3] if len(sys.argv) > 3 else None
            if not position:
                position = sys.argv[4] if len(sys.argv) > 4 else None
        
        if not all([player_name, team, position]):
            logger.error("Player mode requires: player_name, team, position")
            return []
        
        players = [{"name": player_name, "team": team, "position": position}]
    
    elif selection == "team":
        team_input = os.getenv("TEAM_NAME")
        if not team_input:
            team_input = sys.argv[2] if len(sys.argv) > 2 else None
        
        if not team_input:
            logger.error("Team mode requires: team_name")
            logger.error("Usage: python nba_scraper.py team \"LAL\"")
            return []
        
        teams = get_nba_teams()
        team_name = None
        if team_input.upper() in teams:
            team_name = teams[team_input.upper()]
        else:
            for abbrev, full_name in teams.items():
                if team_input.lower() in full_name.lower():
                    team_name = full_name
                    break
        
        if team_name:
            roster = get_nba_team_roster(collector, team_name)
            players = roster
        else:
            logger.error(f"Team not found: {team_input}")
            return []
    
    elif selection == "test":
        print(f"\n🧪 Test Mode: Collecting one well-known player from each NBA team...")
        players = get_nba_test_players(collector)
        if players:
            print(f"✓ Selected {len(players)} test players (one per team)")
    
    elif selection == "all":
        # All teams mode with parallel processing
        teams = get_nba_teams()
        logger.info(f"🚀 Collecting rosters for all {len(teams)} NBA teams in parallel...")
        
        def collect_team_roster(team_info):
            abbrev, team_name = team_info
            try:
                roster = get_nba_team_roster(collector, team_name)
                return (team_name, roster)
            except Exception as e:
                logger.error(f"❌ Failed to get roster for {team_name}: {e}")
                return (team_name, [])
        
        max_concurrent_teams = min(5, len(teams))
        with ThreadPoolExecutor(max_workers=max_concurrent_teams) as executor:
            # Submit all tasks
            futures = {executor.submit(collect_team_roster, team_info): team_info for team_info in teams.items()}
            
            # Use tqdm to track progress
            with tqdm(total=len(teams), desc="🏀 Collecting NBA team rosters", unit="team", 
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                for future in as_completed(futures):
                    try:
                        team_name, roster = future.result()
                        players.extend(roster)
                        pbar.set_postfix_str(f"✅ {team_name}: {len(roster)} players")
                        pbar.update(1)
                    except Exception as e:
                        team_info = futures[future]
                        pbar.set_postfix_str(f"❌ Failed")
                        pbar.update(1)
        
        logger.info(f"✅ Collected {len(players)} total players from all {len(teams)} teams")
    
    else:
        logger.error(f"Unknown selection mode: {selection}")
        return []
    
    return players


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for NBA player data collection"""
    # Parse command line arguments
    args_to_remove = []
    for i, arg in enumerate(sys.argv):
        if arg == "--help" or arg == "-h":
            print_usage()
            return
        elif arg == "--openai-key" and i + 1 < len(sys.argv):
            Config.OPENAI_API_KEY = sys.argv[i + 1]
            logger.info("OpenAI API key set from command line")
            args_to_remove.extend([i, i + 1])
            break
        elif arg.startswith("--openai-key="):
            Config.OPENAI_API_KEY = arg.split("=", 1)[1]
            logger.info("OpenAI API key set from command line")
            args_to_remove.append(i)
            break
    
    # Remove processed arguments
    for i in sorted(args_to_remove, reverse=True):
        sys.argv.pop(i)
    
    # Set Firecrawl API key (optional - will use free APIs if not set)
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-NONE")
    
    # Check for OpenAI API key
    if not Config.OPENAI_API_KEY:
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            Config.OPENAI_API_KEY = openai_key
            logger.info("OpenAI API key configured from environment variable")
    
    # Firecrawl is optional - warn but continue with free APIs
    if not api_key or "YOUR_API_KEY" in api_key or api_key == "fc-NONE":
        logger.warning("⚠️  Firecrawl API key not set - using FREE APIs only")
        logger.warning("   Data sources: ESPN, Wikipedia, DuckDuckGo")
        logger.warning("   Some features may be limited (endorsements, detailed contracts)")
        logger.warning("   To enable Firecrawl: export FIRECRAWL_API_KEY='fc-your-key'")
        print()
        # Continue with free APIs
    
    # Initialize NBA collector
    collector = NBAPlayerCollector(api_key)
    
    # Create output folder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_folder = f"scrapes/NBA/{timestamp}"
    os.makedirs(output_folder, exist_ok=True)
    logger.info(f"📁 Output folder: {output_folder}")
    collector.output_folder = output_folder
    
    # Get selection mode
    selection_mode = None
    if len(sys.argv) > 1:
        selection_mode = sys.argv[1]
    
    if not selection_mode:
        selection_mode = os.getenv("SCRAPE_MODE", "interactive")
    
    # Collect players
    players = collect_players_by_selection(collector, selection_mode)
    
    if not players:
        logger.error("❌ No players selected for collection")
        return
    
    # Print summary
    print("\n" + "="*70)
    print("NBA COLLECTION SUMMARY")
    print("="*70)
    print(f"Total players to collect: {len(players)}")
    print(f"Parallel workers: {Config.MAX_CONCURRENT_PLAYERS}")
    print("="*70 + "\n")
    
    logger.info(f"✓ Found {len(players)} player(s) to collect data for...")
    logger.info(f"Starting data collection for {len(players)} player(s)...")
    
    # Collect data for each player
    all_player_data = []
    successful_collections = 0
    failed_collections = 0
    player_times = []  # Track individual player times for accurate ETA
    
    start_time = time.time()
    
    def process_single_player(player_info: Dict, player_idx: int):
        """Process a single player with timing"""
        nonlocal successful_collections, failed_collections
        
        player_start = time.time()
        player_name = player_info.get('name', '')
        team = player_info.get('team', '')
        position = player_info.get('position', 'UNK')
        
        logger.info(f"\n[{player_idx}/{len(players)}] Collecting data for {player_name}...")
        logger.info(f"Team: {team}, Position: {position}")
        
        try:
            player_data = collector.collect_player_data(player_name, team, position)
            json_file, csv_file = collector.export_both(player_data)
            successful_collections += 1
            player_time = time.time() - player_start
            logger.info(f"✓ Collected data for {player_name} in {player_time:.1f}s")
            return player_data, player_time
        except Exception as e:
            failed_collections += 1
            player_time = time.time() - player_start
            logger.error(f"Failed to collect data for {player_name}: {e}")
            return None, player_time
    
    # Process players
    if len(players) == 1:
        player_data, _ = process_single_player(players[0], 1)
        if player_data:
            all_player_data.append(player_data)
    else:
        # Multiple players - use parallel processing with enhanced progress bar
        print(f"\n🚀 Starting collection with {Config.MAX_CONCURRENT_PLAYERS} parallel workers...")
        
        with ThreadPoolExecutor(max_workers=Config.MAX_CONCURRENT_PLAYERS) as executor:
            future_to_player = {
                executor.submit(process_single_player, player_info, idx + 1): player_info
                for idx, player_info in enumerate(players)
            }
            
            # Enhanced progress bar with accurate ETA
            with tqdm(total=len(players), desc="🏀 NBA Players", unit="player",
                     ncols=120, colour='blue',
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
                
                for future in as_completed(future_to_player):
                    player_info = future_to_player[future]
                    try:
                        player_data, player_time = future.result()
                        
                        if player_data:
                            all_player_data.append(player_data)
                            player_times.append(player_time)
                        
                        # Calculate accurate ETA based on recent player times
                        if len(player_times) >= 3:
                            # Use last 20 player times for rolling average (more accurate)
                            recent_times = player_times[-20:]
                            avg_time = sum(recent_times) / len(recent_times)
                            remaining = len(players) - pbar.n
                            # Account for parallel processing
                            eta_seconds = (avg_time * remaining) / Config.MAX_CONCURRENT_PLAYERS
                            
                            hours = int(eta_seconds // 3600)
                            minutes = int((eta_seconds % 3600) // 60)
                            seconds = int(eta_seconds % 60)
                            
                            if hours > 0:
                                eta_str = f"{hours}h {minutes}m"
                            elif minutes > 0:
                                eta_str = f"{minutes}m {seconds}s"
                            else:
                                eta_str = f"{seconds}s"
                            
                            pbar.set_postfix({
                                'Success': successful_collections,
                                'Failed': failed_collections,
                                'ETA': eta_str,
                                'Avg': f"{avg_time:.1f}s"
                            })
                        
                        pbar.update(1)
                    except Exception as e:
                        logger.error(f"Unexpected error processing {player_info.get('name', 'Unknown')}: {e}")
                        pbar.update(1)
    
    # Final summary
    total_time = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"NBA COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"Total players processed: {len(players)}")
    print(f"Successful collections: {successful_collections}")
    print(f"Failed collections: {failed_collections}")
    print(f"Total time: {int(total_time // 60)}m {int(total_time % 60)}s")
    print(f"{'='*70}")
    
    # Export combined data if multiple players
    if len(all_player_data) > 1:
        try:
            output_folder = getattr(collector, 'output_folder', '')
            if output_folder:
                combined_json = os.path.join(output_folder, f"nba_players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                combined_csv = os.path.join(output_folder, f"nba_players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                
                # Export combined JSON
                with open(combined_json, 'w') as f:
                    json.dump([asdict(p) for p in all_player_data], f, indent=2, default=str)
                
                # Export combined CSV
                combined_csv = collector.export_multiple_to_csv(all_player_data, combined_csv)
                
                print(f"\n✅ Combined data exported to: {output_folder}")
                print(f"   Combined JSON: {combined_json}")
                print(f"   Combined CSV: {combined_csv}")
                print(f"   Total players: {len(all_player_data)}")
        except Exception as e:
            logger.error(f"Failed to export combined data: {e}")


def print_usage():
    """Print usage information"""
    print("""
NBA Player Data Collector - Usage

Environment Variables:
  FIRECRAWL_API_KEY    - Required: Your Firecrawl API key
  OPENAI_API_KEY       - Optional: Your OpenAI API key for enhanced parsing
  SCRAPE_MODE          - Optional: Selection mode (player, team, all, test, interactive)
  PLAYER_NAME          - Optional: Player name (if SCRAPE_MODE=player)
  PLAYER_TEAM          - Optional: Team name (if SCRAPE_MODE=player)
  PLAYER_POSITION      - Optional: Position (if SCRAPE_MODE=player)
  TEAM_NAME            - Optional: Team name/abbreviation (if SCRAPE_MODE=team)

Command Line Usage:
  python gravity/nba_scraper.py [mode] [args...]
  
  Examples:
    # Interactive mode
    python gravity/nba_scraper.py
    
    # Single player
    python gravity/nba_scraper.py player "LeBron James" "Los Angeles Lakers" "SF"
    
    # Team roster
    python gravity/nba_scraper.py team "LAL"
    
    # All NBA teams (recommended - creates ONE combined CSV)
    python gravity/nba_scraper.py all
    
    # Test mode (one player per team)
    python gravity/nba_scraper.py test
""")


if __name__ == "__main__":
    main()

