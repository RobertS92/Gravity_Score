"""
NFL Player Data Scraper - Dedicated NFL-only data collection
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

# Import NFL components
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

# Import from the loaded module
Config = scrape_module.Config
FirecrawlScraper = scrape_module.FirecrawlScraper
NFLPlayerCollector = scrape_module.NFLPlayerCollector
collect_nfl_players = scrape_module.collect_players_by_selection
get_nfl_team_roster = scrape_module.get_team_roster
get_nfl_teams = scrape_module.get_nfl_teams
PlayerData = scrape_module.PlayerData

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Conference/division mappings for filtering
NFL_CONFERENCES = {
    "AFC": {
        "AFC East": ["Bills", "Dolphins", "Patriots", "Jets"],
        "AFC North": ["Ravens", "Bengals", "Browns", "Steelers"],
        "AFC South": ["Texans", "Colts", "Jaguars", "Titans"],
        "AFC West": ["Broncos", "Chiefs", "Raiders", "Chargers"],
    },
    "NFC": {
        "NFC East": ["Cowboys", "Giants", "Eagles", "Commanders"],
        "NFC North": ["Bears", "Lions", "Packers", "Vikings"],
        "NFC South": ["Falcons", "Panthers", "Saints", "Buccaneers"],
        "NFC West": ["Cardinals", "49ers", "Rams", "Seahawks"],
    },
}


# ============================================================================
# NFL PLAYER COLLECTION
# ============================================================================

def collect_players_by_selection(collector, selection: str = None) -> List[Dict]:
    """
    Collect NFL players based on selection mode
    
    Args:
        collector: NFLPlayerCollector instance
        selection: Selection mode - 'player', 'team', 'all', 'test', or None for interactive
    
    Returns:
        List of player dictionaries with name, team, position
    """
    players = []
    
    # If no selection provided, check command line args or env
    if not selection:
        if len(sys.argv) > 1:
            selection = sys.argv[1]
        else:
            selection = os.getenv("SCRAPE_MODE", "interactive")
    
    if selection == "interactive" or selection is None:
        # Interactive mode
        print("\n" + "="*70)
        print("NFL Player Data Collector")
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
            position = input("Enter position (QB, RB, WR, etc.): ").strip().upper()
            players = [{"name": player_name, "team": team, "position": position}]
        
        elif choice == "2":
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
        
        elif choice == "3":
            teams = get_nfl_teams()
            print(f"\nCollecting rosters for all {len(teams)} NFL teams...")
            for abbrev, team_name in teams.items():
                roster = get_nfl_team_roster(collector, team_name)
                players.extend(roster)
                time.sleep(Config.REQUEST_DELAY)
        
        elif choice == "4":
            print(f"\n🧪 Test Mode: Collecting one well-known player from each NFL team...")
            get_test_players = scrape_module.get_test_players_from_all_teams
            players = get_test_players(collector)
            if players:
                print(f"✓ Selected {len(players)} test players (one per team)")
    
    elif selection == "player":
        # Single player mode from args/env
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
        # Team mode from args/env
        team_input = os.getenv("TEAM_NAME")
        if not team_input:
            team_input = sys.argv[2] if len(sys.argv) > 2 else None
        
        if not team_input:
            logger.error("Team mode requires: team_name")
            logger.error("Usage: python nfl_scraper.py team \"Team Name\"")
            return []
        
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

    elif selection == "conference":
        # Conference or division selection
        conference = sys.argv[2] if len(sys.argv) > 2 else os.getenv("NFL_CONFERENCE")
        if not conference:
            logger.error("Conference mode requires: conference name (AFC, NFC, AFC East, etc.)")
            return []
        conference_norm = conference.strip()
        teams = []
        if conference_norm.upper() in NFL_CONFERENCES:
            # Whole conference
            for division_teams in NFL_CONFERENCES[conference_norm.upper()].values():
                teams.extend(division_teams)
        else:
            # Try division match
            found = False
            for conf_dict in NFL_CONFERENCES.values():
                for div_name, division_teams in conf_dict.items():
                    if conference_norm.lower() == div_name.lower():
                        teams.extend(division_teams)
                        found = True
                        break
                if found:
                    break
        if not teams:
            logger.error(f"Conference/Division not found: {conference}")
            return []
        logger.info(f"Collecting rosters for {conference} ({len(teams)} teams)...")
        for t in teams:
            roster = get_nfl_team_roster(collector, t)
            players.extend(roster)
            time.sleep(Config.REQUEST_DELAY)

    elif selection == "dict":
        # Dictionary-based selection: JSON file path or stdin JSON
        dict_file = sys.argv[2] if len(sys.argv) > 2 else None
        try:
            import json
            if dict_file:
                with open(dict_file, "r") as f:
                    team_dict = json.load(f)
            else:
                team_dict = json.loads(sys.stdin.read())
            logger.info(f"Collecting teams from dict keys: {list(team_dict.keys())}")
            for key, team_list in team_dict.items():
                logger.info(f"{key}: {team_list}")
                for t in team_list:
                    roster = get_nfl_team_roster(collector, t)
                    players.extend(roster)
                    time.sleep(Config.REQUEST_DELAY)
        except Exception as e:
            logger.error(f"Failed to load dict selection: {e}")
            return []
    
    elif selection == "test":
        # Test mode: one well-known player from each team
        print(f"\n🧪 Test Mode: Collecting one well-known player from each NFL team...")
        get_test_players = scrape_module.get_test_players_from_all_teams
        players = get_test_players(collector)
        if players:
            print(f"✓ Selected {len(players)} test players (one per team)")
    
    elif selection == "all":
        # All teams mode with parallel processing
        teams = get_nfl_teams()
        logger.info(f"🚀 Collecting rosters for all {len(teams)} NFL teams in parallel...")
        
        def collect_team_roster(team_info):
            abbrev, team_name = team_info
            try:
                roster = get_nfl_team_roster(collector, team_name)
                return (team_name, roster)
            except Exception as e:
                logger.error(f"❌ Failed to get roster for {team_name}: {e}")
                return (team_name, [])
        
        max_concurrent_teams = min(5, len(teams))
        with ThreadPoolExecutor(max_workers=max_concurrent_teams) as executor:
            # Submit all tasks
            futures = {executor.submit(collect_team_roster, team_info): team_info for team_info in teams.items()}
            
            # Use tqdm to track progress
            with tqdm(total=len(teams), desc="🏈 Collecting NFL team rosters", unit="team", 
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
    """Main function for NFL player data collection"""
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
    
    # Initialize NFL collector
    collector = NFLPlayerCollector(api_key)
    
    # Create output folder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_folder = f"scrapes/NFL/{timestamp}"
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
    print("NFL COLLECTION SUMMARY")
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
    
    # Process players (parallel for multiple, sequential for single)
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
            with tqdm(total=len(players), desc="🏈 NFL Players", unit="player",
                     ncols=120, colour='green',
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
    print(f"NFL COLLECTION COMPLETE")
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
                combined_json = os.path.join(output_folder, f"nfl_players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                combined_csv = os.path.join(output_folder, f"nfl_players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                
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
NFL Player Data Collector - Usage

Environment Variables:
  FIRECRAWL_API_KEY    - Required: Your Firecrawl API key
  OPENAI_API_KEY       - Optional: Your OpenAI API key for enhanced parsing
  SCRAPE_MODE          - Optional: Selection mode (player, team, all, test, interactive)
  PLAYER_NAME          - Optional: Player name (if SCRAPE_MODE=player)
  PLAYER_TEAM          - Optional: Team name (if SCRAPE_MODE=player)
  PLAYER_POSITION      - Optional: Position (if SCRAPE_MODE=player)
  TEAM_NAME            - Optional: Team name/abbreviation (if SCRAPE_MODE=team)

Command Line Usage:
  python gravity/nfl_scraper.py [mode] [args...]
  
  Examples:
    # Interactive mode
    python gravity/nfl_scraper.py
    
    # Single player
    python gravity/nfl_scraper.py player "Patrick Mahomes" "Kansas City Chiefs" "QB"
    
    # Team roster
    python gravity/nfl_scraper.py team "KC"
    
    # All NFL teams (recommended - creates ONE combined CSV)
    python gravity/nfl_scraper.py all
    
    # Test mode (one player per team)
    python gravity/nfl_scraper.py test
""")


if __name__ == "__main__":
    main()

