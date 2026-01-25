"""
Unified Scraper CLI for NFL and NBA
Supports: individual player, team, all players, test one player per team
"""

import os
import sys
import time
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add parent directory to path so we can import gravity modules
# This allows the script to be run from anywhere
script_dir = Path(__file__).parent.absolute()
parent_dir = script_dir.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
# Also add the gravity directory itself
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import NFL components - the file is named 'scrape' (no .py extension)
# We need to use importlib to load it
import importlib.util

scrape_file_path = script_dir / "scrape"
if not scrape_file_path.exists():
    scrape_file_path = script_dir / "scrape.py"

if not scrape_file_path.exists():
    raise ImportError(f"Could not find scrape module at {scrape_file_path} or {script_dir / 'scrape.py'}")

# Try to load the file - handle both .py and non-.py extensions
try:
    # First try with importlib (works for .py files)
    spec = importlib.util.spec_from_file_location("scrape", scrape_file_path)
    if spec is not None and spec.loader is not None:
        scrape_module = importlib.util.module_from_spec(spec)
        sys.modules["scrape"] = scrape_module
        sys.modules["gravity.scrape"] = scrape_module
        spec.loader.exec_module(scrape_module)
    else:
        # Fallback: load file directly and execute it
        raise ValueError("spec_from_file_location returned None")
except (ValueError, AttributeError):
    # Fallback: load and execute the file directly
    scrape_module = type(sys.modules[__name__])('scrape')
    scrape_module.__file__ = str(scrape_file_path)
    scrape_module.__name__ = 'scrape'
    
    # Read and execute the file
    with open(scrape_file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Execute in the module's namespace
    exec(compile(code, str(scrape_file_path), 'exec'), scrape_module.__dict__)
    
    # Register in sys.modules
    sys.modules["scrape"] = scrape_module
    sys.modules["gravity.scrape"] = scrape_module

# Now import from the loaded module
Config = scrape_module.Config
FirecrawlScraper = scrape_module.FirecrawlScraper
NFLPlayerCollector = scrape_module.NFLPlayerCollector
collect_nfl_players = scrape_module.collect_players_by_selection
get_nfl_team_roster = scrape_module.get_team_roster
get_nfl_teams = scrape_module.get_nfl_teams
PlayerData = scrape_module.PlayerData

# Configure logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import NBA components - try multiple import paths
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
        # Don't log warning here - logger not initialized yet
        pass


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
                    # Look for player patterns in markdown
                    # NBA.com typically lists players with name, position, number
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
                                
                                if name and len(name.split()) >= 2:  # Must have first and last name
                                    try:
                                        jersey = int(number) if number else None
                                    except:
                                        jersey = None
                                    
                                    # Avoid duplicates
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
        logger.warning(f"⚠️  Could not extract roster for {team_name}. You may need to manually enter players.")
        logger.info(f"Try using individual player mode or check NBA.com for the roster URL")
    
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
# UNIFIED PLAYER COLLECTION
# ============================================================================

def collect_players_by_selection_unified(collector, sport: str, selection: str = None) -> List[Dict]:
    """
    Collect players based on selection mode for either NFL or NBA
    
    Args:
        collector: PlayerCollector instance (NFL or NBA)
        sport: 'nfl' or 'nba'
        selection: Selection mode - 'player', 'team', 'all', 'test', or None for interactive
    
    Returns:
        List of player dictionaries with name, team, position
    """
    players = []
    
    # If no selection provided, use command line args or environment variables
    if not selection:
        if len(sys.argv) > 1:
            selection = sys.argv[1]
        else:
            selection = os.getenv("SCRAPE_MODE", "interactive")
    
    if selection == "interactive" or selection is None:
        # Interactive mode
        print("\n" + "="*70)
        print(f"{sport.upper()} Player Data Collector")
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
            if sport == "nfl":
                position = input("Enter position (QB, RB, WR, etc.): ").strip().upper()
            else:
                position = input("Enter position (PG, SG, SF, PF, C): ").strip().upper()
            players = [{"name": player_name, "team": team, "position": position}]
        
        elif choice == "2":
            if sport == "nfl":
                teams = get_nfl_teams()
                print("\nAvailable NFL teams:")
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
                    roster = get_nfl_team_roster(collector, team_name)
                    players = roster
                else:
                    logger.error(f"Team not found: {team_input}")
                    return []
            else:  # NBA
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
            if sport == "nfl":
                teams = get_nfl_teams()
                print(f"\nCollecting rosters for all {len(teams)} NFL teams...")
                for abbrev, team_name in teams.items():
                    roster = get_nfl_team_roster(collector, team_name)
                    players.extend(roster)
                    time.sleep(Config.REQUEST_DELAY)
            else:  # NBA
                teams = get_nba_teams()
                print(f"\nCollecting rosters for all {len(teams)} NBA teams...")
                for abbrev, team_name in teams.items():
                    roster = get_nba_team_roster(collector, team_name)
                    players.extend(roster)
                    time.sleep(Config.REQUEST_DELAY)
        
        elif choice == "4":
            # Test mode: one well-known player from each team
            print(f"\n🧪 Test Mode: Collecting one well-known player from each {sport.upper()} team...")
            if sport == "nfl":
                get_test_players_from_all_teams = scrape_module.get_test_players_from_all_teams
                players = get_test_players_from_all_teams(collector)
            else:  # NBA
                players = get_nba_test_players(collector)
            if players:
                print(f"✓ Selected {len(players)} test players (one per team)")
    
    elif selection == "player":
        # Single player mode from args/env
        player_name = os.getenv("PLAYER_NAME")
        team = os.getenv("PLAYER_TEAM")
        position = os.getenv("PLAYER_POSITION")
        
        if not all([player_name, team, position]):
            # Check if sport was first arg (nfl/nba)
            if len(sys.argv) > 1 and sys.argv[1] in ['nfl', 'nba']:
                # Format: python script.py nba player "Name" "Team" "Position"
                # sys.argv[1] = sport, sys.argv[2] = "player", sys.argv[3] = name, sys.argv[4] = team, sys.argv[5] = position
                if not player_name:
                    player_name = sys.argv[3] if len(sys.argv) > 3 else None
                if not team:
                    team = sys.argv[4] if len(sys.argv) > 4 else None
                if not position:
                    position = sys.argv[5] if len(sys.argv) > 5 else None
            else:
                # Format: python script.py player "Name" "Team" "Position"
                # sys.argv[1] = "player", sys.argv[2] = name, sys.argv[3] = team, sys.argv[4] = position
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
        # Team mode from args/env
        # Need to get team name - it's after the mode in sys.argv
        # If sport was first arg, team is at index 3, otherwise at index 2
        team_input = os.getenv("TEAM_NAME")
        if not team_input:
            # Check if sport was first arg (nfl/nba)
            if len(sys.argv) > 1 and sys.argv[1] in ['nfl', 'nba']:
                # Format: python script.py nba team "LAL"
                # sys.argv[1] = sport, sys.argv[2] = "team", sys.argv[3] = team_name
                team_input = sys.argv[3] if len(sys.argv) > 3 else None
            else:
                # Format: python script.py team "LAL"
                # sys.argv[1] = "team", sys.argv[2] = team_name
                team_input = sys.argv[2] if len(sys.argv) > 2 else None
        
        if not team_input:
            logger.error("Team mode requires: team_name")
            logger.error("Usage: python unified_scraper.py [sport] team \"Team Name\"")
            return []
        
        if sport == "nfl":
            teams = get_nfl_teams()
            team_name = None
            if team_input.upper() in teams:
                team_name = teams[team_input.upper()]
            else:
                for abbrev, full_name in teams.items():
                    if team_input.lower() in full_name.lower():
                        team_name = full_name
                        break
            
            if team_name:
                roster = get_nfl_team_roster(collector, team_name)
                players = roster
            else:
                logger.error(f"Team not found: {team_input}")
                return []
        else:  # NBA
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
        # Test mode: one well-known player from each team
        print(f"\n🧪 Test Mode: Collecting one well-known player from each {sport.upper()} team...")
        if sport == "nfl":
            get_test_players_from_all_teams = scrape_module.get_test_players_from_all_teams
            players = get_test_players_from_all_teams(collector)
        else:  # NBA
            players = get_nba_test_players(collector)
        if players:
            print(f"✓ Selected {len(players)} test players (one per team)")
    
    elif selection == "all":
        # All teams mode
        if sport == "nfl":
            teams = get_nfl_teams()
            logger.info(f"🚀 Collecting rosters for all {len(teams)} NFL teams in parallel...")
            
            def collect_team_roster(team_info):
                abbrev, team_name = team_info
                try:
                    logger.info(f"📋 Fetching roster for {team_name}...")
                    roster = get_nfl_team_roster(collector, team_name)
                    logger.info(f"✅ {team_name}: Found {len(roster)} players")
                    return roster
                except Exception as e:
                    logger.error(f"❌ Failed to get roster for {team_name}: {e}")
                    return []
            
            max_concurrent_teams = min(5, len(teams))
            with ThreadPoolExecutor(max_workers=max_concurrent_teams) as executor:
                team_rosters = list(executor.map(collect_team_roster, teams.items()))
            
            for roster in team_rosters:
                players.extend(roster)
            
            logger.info(f"✅ Collected {len(players)} total players from all {len(teams)} teams")
        else:  # NBA
            teams = get_nba_teams()
            logger.info(f"🚀 Collecting rosters for all {len(teams)} NBA teams...")
            # TODO: Implement parallel NBA roster collection
            for abbrev, team_name in teams.items():
                roster = get_nba_team_roster(collector, team_name)
                players.extend(roster)
                time.sleep(Config.REQUEST_DELAY)
    
    else:
        logger.error(f"Unknown selection mode: {selection}")
        return []
    
    return players


# ============================================================================
# NBA PLAYER COLLECTOR (Similar structure to NFL)
# ============================================================================

class NBAPlayerCollector:
    """Main class to orchestrate NBA data collection"""
    
    def __init__(self, firecrawl_api_key: str):
        self.scraper = FirecrawlScraper(firecrawl_api_key)
        self.scrapes_base_dir = os.getenv("SCRAPES_DIR", "scrapes")
        
        # Initialize NBA stats collector
        if NBA_AVAILABLE:
            self.stats_collector = NBAStatsCollector(self.scraper)
        else:
            logger.warning("NBA stats collector not available")
            self.stats_collector = None
        
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
    
    def collect_player_data(self, player_name: str, team: str, position: str):
        """Collect comprehensive NBA player data using NBA-specific data structures"""
        IdentityData = scrape_module.IdentityData
        BrandData = scrape_module.BrandData
        ProximityData = scrape_module.ProximityData
        VelocityData = scrape_module.VelocityData
        RiskData = scrape_module.RiskData
        
        # Import NBA-specific data models
        from gravity.nba_data_models import NBAProofData, NBAPlayerData
        
        # Initialize player data with NBA-specific structure
        player_data = NBAPlayerData(
            player_name=player_name,
            team=team,
            position=position
        )
        
        try:
            # STEP 1: Collect Identity first (needed for age in Velocity and Risk)
            logger.info("📋 Collecting identity data...")
            identity_data = self._collect_identity(player_name, team, position)
            player_data.identity = identity_data
            age = identity_data.age if identity_data else None
            
            # STEP 2: Collect all other data categories in parallel
            logger.info("🚀 Starting parallel data collection...")
            
            max_workers = Config.MAX_CONCURRENT_DATA_COLLECTORS
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all independent tasks
                future_brand = executor.submit(self._collect_brand, player_name)
                future_proof = executor.submit(self._collect_proof, player_name, position)
                future_proximity = executor.submit(self._collect_proximity, player_name)
                future_velocity = executor.submit(self._collect_velocity, player_name, age, position)
                future_risk = executor.submit(self.risk_analyzer.analyze_risk, player_name, position, age)
                
                # Collect results as they complete
                results = {}
                futures_map = {
                    'brand': future_brand,
                    'proof': future_proof,
                    'proximity': future_proximity,
                    'velocity': future_velocity,
                    'risk': future_risk
                }
                
                # Wait for all to complete and collect results
                for category, future in futures_map.items():
                    try:
                        logger.info(f"⏳ Waiting for {category} data...")
                        result = future.result(timeout=300)  # 5 minute timeout per category
                        results[category] = result
                        logger.info(f"✅ {category.capitalize()} data collected")
                    except Exception as e:
                        logger.error(f"❌ Error collecting {category} data: {e}")
                        # Still create empty data structure - never skip
                        if category == 'brand':
                            results[category] = BrandData()
                        elif category == 'proof':
                            from gravity.nba_data_models import NBAProofData
                            results[category] = NBAProofData()
                        elif category == 'proximity':
                            results[category] = ProximityData()
                        elif category == 'velocity':
                            results[category] = VelocityData()
                        elif category == 'risk':
                            results[category] = RiskData()
                        player_data.collection_errors.append(f"{category}: {str(e)}")
            
            # Assign results to player_data
            player_data.brand = results.get('brand', BrandData())
            from gravity.nba_data_models import NBAProofData
            player_data.proof = results.get('proof', NBAProofData())
            player_data.proximity = results.get('proximity', ProximityData())
            player_data.velocity = results.get('velocity', VelocityData())
            player_data.risk = results.get('risk', RiskData())
            
            # Calculate data quality score
            player_data.data_quality_score = self._calculate_quality_score(player_data)
            
        except Exception as e:
            logger.error(f"Error collecting data: {str(e)}")
            player_data.collection_errors.append(str(e))
            # Ensure all data structures exist even on error
            if not player_data.identity:
                player_data.identity = IdentityData()
            if not player_data.brand:
                player_data.brand = BrandData()
            if not player_data.proof:
                from gravity.nba_data_models import NBAProofData
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
        """Collect identity data - reuse NFL method"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        return nfl_collector._collect_identity(player_name, team, position)
    
    def _collect_brand(self, player_name: str):
        """Collect brand/social media data - reuse NFL method"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        return nfl_collector._collect_brand(player_name)
    
    def _collect_proof(self, player_name: str, position: str):
        """Collect NBA stats and proof data using NBA-specific data structure"""
        from gravity.nba_data_models import NBAProofData
        proof = NBAProofData()
        
        # Collect NBA stats using NBAStatsCollector
        if self.stats_collector:
            logger.info(f"📊 Collecting NBA stats for {player_name}...")
            proof_stats = self.stats_collector.collect_stats(player_name, position)
            
            logger.info(f"📊 NBA stats collected: {len(proof_stats)} categories")
            logger.info(f"   Career stats keys: {list(proof_stats.get('career_stats', {}).keys())}")
            logger.info(f"   Current season keys: {list(proof_stats.get('current_season_stats', {}).keys())}")
            logger.info(f"   Career stats by year: {len(proof_stats.get('career_stats_by_year', {}))} years")
            logger.info(f"   Historical seasons: {len(proof_stats.get('historical_seasons', []))} seasons")
            
            # Map NBA stats to proof data structure - PRESERVE ALL DATA (same approach as NFL)
            # Start with organized stats
            career_stats = proof_stats.get('career_stats', {}) or {}
            current_season_stats = proof_stats.get('current_season_stats', {}) or {}
            last_season_stats = proof_stats.get('last_season_stats', {}) or {}
            
            # Process ALL keys with prefixes (same as NFL method) to catch any stats that weren't organized
            for key, value in proof_stats.items():
                if value is None or value == {} or value == []:
                    continue
                    
                if key.startswith('career_') and value is not None:
                    stat_name = key.replace('career_', '')
                    if stat_name not in career_stats or career_stats[stat_name] is None:
                        career_stats[stat_name] = value
                elif key.startswith('current_season_') and value is not None:
                    stat_name = key.replace('current_season_', '')
                    # Remove year prefix if present
                    current_year = datetime.now().year
                    if stat_name.startswith(f'{current_year}_'):
                        stat_name = stat_name.replace(f'{current_year}_', '')
                    if stat_name not in current_season_stats or current_season_stats[stat_name] is None:
                        current_season_stats[stat_name] = value
                elif key.startswith('last_season_') and value is not None:
                    stat_name = key.replace('last_season_', '')
                    # Remove year prefix if present
                    previous_year = datetime.now().year - 1
                    if stat_name.startswith(f'{previous_year}_'):
                        stat_name = stat_name.replace(f'{previous_year}_', '')
                    if stat_name not in last_season_stats or last_season_stats[stat_name] is None:
                        last_season_stats[stat_name] = value
            
            # Handle nested stats (in case stats are nested under 'stats' key)
            if isinstance(career_stats, dict) and 'stats' in career_stats and isinstance(career_stats['stats'], dict):
                nested_stats = career_stats.pop('stats', {})
                career_stats.update(nested_stats)
            if isinstance(current_season_stats, dict) and 'stats' in current_season_stats:
                nested = current_season_stats.pop('stats', {})
                current_season_stats.update(nested)
            if isinstance(last_season_stats, dict) and 'stats' in last_season_stats:
                nested = last_season_stats.pop('stats', {})
                last_season_stats.update(nested)
            
            proof.career_stats = career_stats if career_stats else {}
            proof.current_season_stats = current_season_stats if current_season_stats else {}
            proof.last_season_stats = last_season_stats if last_season_stats else {}
            
            # Year-by-year breakdowns - CRITICAL: preserve all historical data
            historical_seasons = proof_stats.get('historical_seasons', []) or []
            career_stats_by_year = proof_stats.get('career_stats_by_year', {}) or {}
            
            # Convert historical_seasons to career_stats_by_year (same as NFL)
            if historical_seasons:
                logger.info(f"   Processing {len(historical_seasons)} historical seasons for career_stats_by_year")
                for season_data in historical_seasons:
                    if isinstance(season_data, dict) and 'year' in season_data:
                        year = season_data['year']
                        # Create stats dict without 'year' key
                        year_stats = {k: v for k, v in season_data.items() if k != 'year'}
                        if year_stats:  # Only add if there are actual stats
                            career_stats_by_year[year] = year_stats
            
            proof.career_stats_by_year = career_stats_by_year
            
            logger.info(f"✅ Final stats: {len(proof.career_stats)} career, {len(proof.current_season_stats)} current season, {len(proof.career_stats_by_year)} years")
            
            # Map NBA-specific awards to NBA data structure (NOT NFL fields)
            # All-Star selections (NBA-specific)
            all_star_selections = proof_stats.get('all_star_selections', 0)
            all_star_by_year = proof_stats.get('all_star_selections_by_year', {}) or {}
            # Recalculate count from year-by-year data to ensure accuracy
            if all_star_by_year:
                all_star_selections = sum(1 for v in all_star_by_year.values() if v)
            proof.all_star_selections = all_star_selections
            proof.all_star_selections_by_year = all_star_by_year
            
            # All-NBA selections (NBA-specific)
            all_nba_selections = proof_stats.get('all_nba_selections', 0)
            all_nba_by_year = proof_stats.get('all_nba_selections_by_year', {}) or {}
            # Recalculate count from year-by-year data
            if all_nba_by_year:
                all_nba_selections = sum(1 for v in all_nba_by_year.values() if v)
            proof.all_nba_selections = all_nba_selections
            proof.all_nba_selections_by_year = all_nba_by_year
            
            # Championships (NBA-specific)
            championships = proof_stats.get('championships', 0)
            championships_by_year = proof_stats.get('championships_by_year', {}) or {}
            # Recalculate count from year-by-year data
            if championships_by_year:
                championships = sum(1 for v in championships_by_year.values() if v)
            proof.championships = championships
            proof.championships_by_year = championships_by_year
            
            # Awards - deduplicate and organize
            mvp_awards = proof_stats.get('mvp_awards', 0)
            all_awards = proof_stats.get('awards', []) or []
            
            # Extract unique MVP years from awards list
            mvp_years = set()
            other_awards_list = []
            
            for award in all_awards:
                if 'MVP' in award.upper() and 'NBA MVP' in award:
                    # Extract year from award string like "2012 NBA MVP"
                    year_match = re.search(r'(\d{4})', award)
                    if year_match:
                        mvp_years.add(int(year_match.group(1)))
                else:
                    # Keep non-MVP awards
                    other_awards_list.append(award)
            
            # Update MVP count to actual unique count
            if mvp_years:
                mvp_awards = len(mvp_years)
                proof.mvp_awards = mvp_awards
            
            # Build clean awards list - deduplicate
            proof.awards = []
            
            # Add MVP awards (only if we have accurate count)
            if mvp_awards > 0 and mvp_awards <= 10:  # Sanity check (no player has more than 10 MVPs)
                # Add individual MVP years (sorted, most recent first)
                for year in sorted(mvp_years, reverse=True):
                    proof.awards.append(f"{year} NBA MVP")
            
            # Add all other awards, deduplicating
            seen_awards = set()
            for award in other_awards_list:
                # Deduplicate
                award_lower = award.lower().strip()
                if award_lower and award_lower not in seen_awards:
                    seen_awards.add(award_lower)
                    proof.awards.append(award)
            
            # Map career totals (NBA-specific)
            career_stats = proof_stats.get('career_stats', {})
            proof.career_points = career_stats.get('career_points') or career_stats.get('points')
            proof.career_rebounds = career_stats.get('career_rebounds') or career_stats.get('rebounds')
            proof.career_assists = career_stats.get('career_assists') or career_stats.get('assists')
            
            # Store NBA-specific stats in career_stats for easy access
            # These will be in the career_stats dict already from NBAStatsCollector
            
            logger.info(f"✅ Collected NBA stats: {len(career_stats_by_year)} seasons, {all_star_selections} All-Stars, {championships} Championships")
        else:
            logger.warning("NBA stats collector not available")
        
        return proof
    
    def _collect_proximity(self, player_name: str):
        """Collect market position data - reuse NFL method"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        return nfl_collector._collect_proximity(player_name)
    
    def _collect_velocity(self, player_name: str, age: int, position: str):
        """Collect momentum data - reuse NFL method"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        return nfl_collector._collect_velocity(player_name, age, position)
    
    def _calculate_quality_score(self, player_data: PlayerData) -> float:
        """Calculate data quality score - reuse NFL method"""
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        return nfl_collector._calculate_quality_score(player_data)
    
    def export_both(self, player_data: PlayerData):
        """Export player data to both JSON and CSV"""
        # Use same export logic as NFL
        nfl_collector = NFLPlayerCollector(self.scraper.api_key)
        # Pass output folder if set
        if hasattr(self, 'output_folder') and self.output_folder:
            nfl_collector.output_folder = self.output_folder
        return nfl_collector.export_both(player_data)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function with sport and player/team selection"""
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
    
    # Set Firecrawl API key
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-YOUR_API_KEY_HERE")
    
    # Check for OpenAI API key
    if not Config.OPENAI_API_KEY:
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            Config.OPENAI_API_KEY = openai_key
            logger.info("OpenAI API key configured from environment variable")
    
    if "YOUR_API_KEY" in api_key:
        logger.error("Please set your Firecrawl API key!")
        logger.error("Set FIRECRAWL_API_KEY environment variable")
        print_usage()
        return
    
    # Select sport
    sport = os.getenv("SPORT") or (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ['nfl', 'nba'] else None)
    
    if not sport:
        print("\n" + "="*70)
        print("Unified Player Data Collector")
        print("="*70)
        print("\nSelect sport:")
        print("1. NFL")
        print("2. NBA")
        sport_choice = input("\nEnter choice (1 or 2): ").strip()
        sport = "nfl" if sport_choice == "1" else "nba"
    
    if sport not in ['nfl', 'nba']:
        logger.error(f"Invalid sport: {sport}. Must be 'nfl' or 'nba'")
        return
    
    if sport == "nba" and not NBA_AVAILABLE:
        logger.error("NBA support not available. Please install required dependencies.")
        return
    
    # Initialize collector
    if sport == "nfl":
        collector = NFLPlayerCollector(api_key)
    else:
        collector = NBAPlayerCollector(api_key)
    
    # Create output folder - organized by sport
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_folder = f"scrapes/{sport.upper()}/{timestamp}"
    os.makedirs(output_folder, exist_ok=True)
    logger.info(f"📁 Output folder: {output_folder}")
    logger.info(f"📂 Sport-specific folder: scrapes/{sport.upper()}/")
    collector.output_folder = output_folder
    
    # Get selection mode (skip sport if it was first arg)
    selection_mode = None
    if len(sys.argv) > 1:
        if sys.argv[1] in ['nfl', 'nba']:
            selection_mode = sys.argv[2] if len(sys.argv) > 2 else None
        else:
            selection_mode = sys.argv[1]
    
    if not selection_mode:
        selection_mode = os.getenv("SCRAPE_MODE", "interactive")
    
    # Collect players
    players = collect_players_by_selection_unified(collector, sport, selection_mode)
    
    if not players:
        logger.error("❌ No players selected for collection")
        return
    
    # Print summary
    print("\n" + "="*70)
    print("COLLECTION SUMMARY")
    print("="*70)
    print(f"Sport: {sport.upper()}")
    print(f"Total players to collect: {len(players)}")
    print(f"Parallel workers: {Config.MAX_CONCURRENT_PLAYERS}")
    print("="*70 + "\n")
    
    logger.info(f"✓ Found {len(players)} player(s) to collect data for...")
    logger.info(f"Starting data collection for {len(players)} player(s)...")
    
    # Collect data for each player
    all_player_data = []
    successful_collections = 0
    failed_collections = 0
    
    start_time = time.time()
    
    def process_single_player(player_info: Dict, player_idx: int):
        """Process a single player"""
        nonlocal successful_collections, failed_collections
        
        player_name = player_info.get('name', '')
        team = player_info.get('team', '')
        position = player_info.get('position', 'UNK')
        
        logger.info(f"\n[{player_idx}/{len(players)}] Collecting data for {player_name}...")
        logger.info(f"Team: {team}, Position: {position}")
        
        try:
            player_data = collector.collect_player_data(player_name, team, position)
            json_file, csv_file = collector.export_both(player_data)
            successful_collections += 1
            logger.info(f"✓ Collected data for {player_name}")
            return player_data
        except Exception as e:
            failed_collections += 1
            logger.error(f"Failed to collect data for {player_name}: {e}")
            return None
    
    # Process players (parallel for multiple, sequential for single)
    if len(players) == 1:
        player_data = process_single_player(players[0], 1)
        if player_data:
            all_player_data.append(player_data)
    else:
        # Multiple players - use parallel processing
        with ThreadPoolExecutor(max_workers=Config.MAX_CONCURRENT_PLAYERS) as executor:
            future_to_player = {
                executor.submit(process_single_player, player_info, idx + 1): player_info
                for idx, player_info in enumerate(players)
            }
            
            for future in as_completed(future_to_player):
                try:
                    player_data = future.result()
                    if player_data:
                        all_player_data.append(player_data)
                except Exception as e:
                    player_info = future_to_player[future]
                    logger.error(f"Unexpected error processing {player_info.get('name', 'Unknown')}: {e}")
    
    # Final summary
    total_time = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"Sport: {sport.upper()}")
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
                # Sport-specific combined file naming
                combined_json = os.path.join(output_folder, f"{sport.lower()}_players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                combined_csv = os.path.join(output_folder, f"{sport.lower()}_players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                
                # Export combined JSON
                with open(combined_json, 'w') as f:
                    json.dump([asdict(p) for p in all_player_data], f, indent=2, default=str)
                
                # Export combined CSV using the collector's method
                if hasattr(collector, 'export_multiple_to_csv'):
                    combined_csv = collector.export_multiple_to_csv(all_player_data, combined_csv)
                else:
                    # Fallback: use NFL collector's method
                    nfl_collector = NFLPlayerCollector(collector.scraper.api_key)
                    nfl_collector.output_folder = output_folder
                    # export_multiple_to_csv accepts filename as second parameter
                    combined_csv = nfl_collector.export_multiple_to_csv(all_player_data, combined_csv)
                
                print(f"\n✅ Combined data exported to: {output_folder}")
                print(f"   Combined JSON: {combined_json}")
                print(f"   Combined CSV: {combined_csv}")
                print(f"   Total players: {len(all_player_data)}")
        except Exception as e:
            logger.error(f"Failed to export combined data: {e}")


def print_usage():
    """Print usage information"""
    print("""
Unified Player Data Collector - Usage

Environment Variables:
  FIRECRAWL_API_KEY    - Required: Your Firecrawl API key
  OPENAI_API_KEY       - Optional: Your OpenAI API key
  SPORT                - Optional: 'nfl' or 'nba'
  SCRAPE_MODE          - Optional: Selection mode (player, team, all, test, interactive)
  PLAYER_NAME          - Optional: Player name (if SCRAPE_MODE=player)
  PLAYER_TEAM          - Optional: Team name (if SCRAPE_MODE=player)
  PLAYER_POSITION      - Optional: Position (if SCRAPE_MODE=player)
  TEAM_NAME            - Optional: Team name/abbreviation (if SCRAPE_MODE=team)

Command Line Usage:
  python gravity/unified_scraper.py [sport] [mode] [args...]
  
  Examples:
    # Interactive mode (selects sport and mode)
    python gravity/unified_scraper.py
    
    # NFL single player
    python gravity/unified_scraper.py nfl player "Patrick Mahomes" "Kansas City Chiefs" "QB"
    
    # NBA single player
    python gravity/unified_scraper.py nba player "LeBron James" "Los Angeles Lakers" "SF"
    
    # NFL team roster
    python gravity/unified_scraper.py nfl team "KC"
    
    # NBA team roster
    python gravity/unified_scraper.py nba team "LAL"
    
    # All NFL teams
    python gravity/unified_scraper.py nfl all
    
    # All NBA teams
    python gravity/unified_scraper.py nba all
    
    # Test mode (one player per team)
    python gravity/unified_scraper.py nfl test
    python gravity/unified_scraper.py nba test
""")


if __name__ == "__main__":
    main()

