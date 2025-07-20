"""
Flask web application to demonstrate the NFL Gravity package functionality.
"""
import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from nfl_gravity.mcp import MCP
from nfl_gravity.core.config import Config
from nfl_gravity.core.exceptions import NFLGravityError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize MCP instance
config = Config()
mcp = MCP(config)

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')

@app.route('/scraping')
def scraping():
    """Data collection/scraping configuration page."""
    return render_template('scraping.html')

@app.route('/view-data')
def view_data():
    """Data viewing and filtering page."""
    return render_template('view_data.html')

@app.route('/api/teams')
def get_teams():
    """Get list of teams for a specific sport."""
    sport = request.args.get('sport', 'nfl')
    
    teams_by_sport = {
        'nfl': [
            "49ers", "bears", "bengals", "bills", "broncos", "browns", "buccaneers",
            "cardinals", "chargers", "chiefs", "colts", "commanders", "cowboys",
            "dolphins", "eagles", "falcons", "giants", "jaguars", "jets", "lions",
            "packers", "panthers", "patriots", "raiders", "rams", "ravens",
            "saints", "seahawks", "steelers", "texans", "titans", "vikings"
        ],
        'nba': [
            "lakers", "warriors", "celtics", "heat", "bulls", "knicks", "nets",
            "sixers", "bucks", "raptors", "hawks", "hornets", "magic", "wizards",
            "pistons", "pacers", "cavaliers", "nuggets", "jazz", "thunder",
            "trail-blazers", "kings", "clippers", "suns", "mavericks", "rockets",
            "spurs", "pelicans", "grizzlies", "timberwolves"
        ],
        'mlb': [
            "yankees", "red-sox", "blue-jays", "orioles", "rays", "white-sox",
            "guardians", "tigers", "royals", "twins", "astros", "angels",
            "athletics", "mariners", "rangers", "braves", "marlins", "mets",
            "phillies", "nationals", "cubs", "reds", "brewers", "pirates",
            "cardinals", "diamondbacks", "rockies", "dodgers", "padres", "giants"
        ],
        'nhl': [
            "bruins", "sabres", "red-wings", "panthers", "canadiens", "senators",
            "lightning", "maple-leafs", "hurricanes", "blue-jackets", "devils",
            "islanders", "rangers", "flyers", "penguins", "capitals", "blackhawks",
            "avalanche", "stars", "wild", "predators", "blues", "jets", "flames",
            "oilers", "canucks", "ducks", "kings", "sharks", "coyotes", "knights", "kraken"
        ]
    }
    
    teams = teams_by_sport.get(sport, [])
    return jsonify({"teams": teams})

@app.route('/data')
def data_viewer():
    """Data viewer page with Excel-like filtering."""
    return render_template('data_viewer.html')

@app.route('/players')
def all_players():
    """All NFL players page with comprehensive team support."""
    return render_template('players.html')

@app.route('/api/players/all')
def get_all_players():
    """Get all players from the latest data file with comprehensive data."""
    try:
        import pandas as pd
        import os
        import glob
        
        # Find the latest data file (prioritize largest dataset)
        comprehensive_files = glob.glob('data/comprehensive_players_*.csv')
        standard_files = glob.glob('data/players_*.csv') + glob.glob('data/**/players_*.csv', recursive=True)
        
        all_files = comprehensive_files + standard_files
        if not all_files:
            return jsonify({"players": [], "count": 0, "status": "no_data"})
        
        # Always prioritize the file with the MOST players (not most recent)
        latest_file = None
        max_players = 0
        
        for file_path in all_files:
            try:
                df_temp = pd.read_csv(file_path)
                player_count = len(df_temp)
                # Always choose the file with more players
                if player_count > max_players:
                    max_players = player_count
                    latest_file = file_path
            except Exception:
                continue
        
        if not latest_file:
            return jsonify({"players": [], "count": 0, "status": "no_data"})
        
        # Load the data
        df = pd.read_csv(latest_file)
        
        # Convert to dictionary, handling NaN values
        players_data = df.fillna('').to_dict('records')
        
        # Convert all columns to proper types for JSON
        players = []
        for player in players_data:
            clean_player = {}
            for key, value in player.items():
                if pd.isna(value) or value == '':
                    clean_player[key] = None
                elif isinstance(value, (int, float)) and pd.notna(value):
                    clean_player[key] = value
                else:
                    clean_player[key] = str(value)
            players.append(clean_player)
        
        return jsonify({
            "players": players,
            "count": len(players),
            "status": "success",
            "columns": list(df.columns),
            "source_file": latest_file
        })
        
    except Exception as e:
        logger.error(f"Error getting all players: {e}")
        # Return error instead of fallback data - we only want real data
        return jsonify({
            "players": [],
            "count": 0,
            "status": "error",
            "error": f"Failed to load player data: {str(e)}",
            "message": "No authentic player data available. Please run data collection first."
        })

@app.route('/api/players/history')
def get_players_history():
    """Get historical player data for time series analysis."""
    try:
        import pandas as pd
        import os
        import glob
        from datetime import datetime
        
        # Get all historical data files
        comprehensive_files = glob.glob('data/comprehensive_players_*.csv')
        standard_files = glob.glob('data/players_*.csv')
        
        all_files = comprehensive_files + standard_files
        
        if not all_files:
            return jsonify({"history": [], "count": 0, "status": "no_data"})
        
        # Sort files by modification time (newest first)
        all_files.sort(key=os.path.getmtime, reverse=True)
        
        history_data = []
        
        for file_path in all_files:
            try:
                df = pd.read_csv(file_path)
                
                # Extract timestamp from filename
                filename = os.path.basename(file_path)
                timestamp_str = filename.split('_')[-2] + '_' + filename.split('_')[-1].replace('.csv', '')
                
                file_info = {
                    "filename": filename,
                    "timestamp": timestamp_str,
                    "player_count": len(df),
                    "column_count": len(df.columns),
                    "file_size": os.path.getsize(file_path),
                    "data_type": "comprehensive" if "comprehensive" in filename else "standard",
                    "teams": df['team'].unique().tolist() if 'team' in df.columns else [],
                    "avg_quality": df['data_quality_score'].mean() if 'data_quality_score' in df.columns else None
                }
                
                history_data.append(file_info)
                
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                continue
        
        return jsonify({
            "history": history_data,
            "count": len(history_data),
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error getting player history: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/players/file/<filename>')
def get_players_from_file(filename):
    """Get players from a specific historical file."""
    try:
        import pandas as pd
        import os
        
        # Validate filename for security
        if not filename.endswith('.csv') or '..' in filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        file_path = os.path.join('data', filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        df = pd.read_csv(file_path)
        
        # Convert to dictionary, handling NaN values
        players_data = df.fillna('').to_dict('records')
        
        # Convert all columns to proper types for JSON
        players = []
        for player in players_data:
            clean_player = {}
            for key, value in player.items():
                if pd.isna(value) or value == '':
                    clean_player[key] = None
                elif isinstance(value, (int, float)) and pd.notna(value):
                    clean_player[key] = value
                else:
                    clean_player[key] = str(value)
            players.append(clean_player)
        
        return jsonify({
            "players": players,
            "count": len(players),
            "status": "success",
            "columns": list(df.columns),
            "source_file": filename
        })
        
    except Exception as e:
        logger.error(f"Error getting players from file {filename}: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/comprehensive', methods=['POST'])
def scrape_comprehensive_data():
    """Scrape comprehensive data using fast simple comprehensive collector."""
    try:
        data = request.get_json()
        teams = data.get('teams', ['49ers'])
        
        # Use the REAL DATA COLLECTOR - NO SIMULATED DATA EVER
        from real_data_collector import RealDataCollector
        collector = RealDataCollector()
        
        all_players = []
        results = {}
        
        for team in teams:
            logger.info(f"Starting comprehensive data scraping for {team}")
            
            # Collect comprehensive data for the entire team (no limits for full production scraping)
            enhanced_players = collector.collect_team_roster(team, limit_players=None)
            
            all_players.extend(enhanced_players)
            
            # Calculate quality metrics
            avg_quality = sum(p.get('data_quality_score', 0) for p in enhanced_players) / len(enhanced_players) if enhanced_players else 0
            total_sources = sum(len(p.get('data_sources', [])) for p in enhanced_players)
            
            results[team] = {
                "players_found": len(enhanced_players),
                "players_enhanced": len(enhanced_players),
                "avg_quality_score": round(avg_quality, 1),
                "total_sources_used": total_sources,
                "status": "success" if enhanced_players else "no_data"
            }
            
            logger.info(f"Completed {team}: {len(enhanced_players)} players with comprehensive data (avg quality: {avg_quality:.1f})")
        
        # Save comprehensive data to file
        import pandas as pd
        from datetime import datetime
        import os
        
        if all_players:
            df = pd.DataFrame(all_players)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"data/comprehensive_players_{timestamp}.csv"
            
            # Create data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)
            df.to_csv(csv_filename, index=False)
            
            logger.info(f"Saved comprehensive data to {csv_filename}")
        
        # Calculate overall metrics
        total_sources = sum(results[team].get("total_sources_used", 0) for team in results)
        avg_quality = sum(results[team].get("avg_quality_score", 0) for team in results) / len(results) if results else 0
        
        return jsonify({
            "status": "success",
            "total_players": len(all_players),
            "teams_processed": len(teams),
            "results": results,
            "avg_quality_score": round(avg_quality, 1),
            "total_sources_used": total_sources,
            "message": f"Comprehensive data collected for {len(all_players)} players from {len(teams)} teams"
        })
        
    except Exception as e:
        logger.error(f"Error in comprehensive data scraping: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/social/search', methods=['POST'])
def search_social_media():
    """Search and scrape social media data for a specific player."""
    try:
        data = request.get_json()
        player_name = data.get('player_name')
        team = data.get('team', '49ers')
        
        if not player_name:
            return jsonify({"error": "Player name is required", "status": "error"}), 400
        
        logger.info(f"Searching social media for {player_name} ({team})")
        
        # Use the web search social scraper
        from web_search_social_scraper import WebSearchSocialScraper
        scraper = WebSearchSocialScraper()
        
        # Search and scrape social media
        social_data = scraper.search_and_scrape_social_media(player_name, team)
        
        return jsonify({
            "player_name": player_name,
            "team": team,
            "social_media_data": social_data,
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error searching social media: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/comprehensive/collect', methods=['POST'])
def collect_comprehensive_data():
    """Collect comprehensive NFL data with all required fields."""
    try:
        data = request.get_json()
        team = data.get('team', '49ers')
        max_players = data.get('max_players', 5)
        
        logger.info(f"Starting comprehensive data collection for {team}")
        
        # Use the simple comprehensive database
        from simple_comprehensive_db import SimpleComprehensiveDB
        db = SimpleComprehensiveDB()
        
        # Collect comprehensive data
        players_data = db.collect_comprehensive_team_data(team, max_players)
        
        if players_data:
            # Save to database
            db.save_comprehensive_data(players_data, team)
            
            return jsonify({
                "team": team,
                "players_collected": len(players_data),
                "status": "success",
                "message": f"Comprehensive data collected for {len(players_data)} players",
                "data_fields": [
                    "Basic Player Info (name, position, team, height, weight, college)",
                    "Social Media (Twitter, Instagram, TikTok, YouTube followers)",
                    "Career Statistics (passing, rushing, receiving)",
                    "Awards and Honors (Pro Bowls, Super Bowl wins)",
                    "Financial Data (career earnings, contract value)",
                    "Wikipedia profile and news headlines"
                ]
            })
        else:
            return jsonify({
                "team": team,
                "players_collected": 0,
                "status": "warning",
                "message": "No comprehensive data collected"
            })
        
    except Exception as e:
        logger.error(f"Error in comprehensive data collection: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/comprehensive/summary/<team>')
def get_comprehensive_summary(team):
    """Get summary of comprehensive data for a team."""
    try:
        from simple_comprehensive_db import SimpleComprehensiveDB
        db = SimpleComprehensiveDB()
        
        summary = db.get_comprehensive_summary(team)
        
        return jsonify({
            "team": team,
            "summary": summary,
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error getting comprehensive summary: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/standard', methods=['POST'])
def scrape_standard():
    """Standard NFL scraping endpoint - basic roster extraction."""
    try:
        data = request.get_json()
        teams = data.get('teams', ['49ers'])
        
        logger.info(f"Starting standard scraping for teams: {teams}")
        
        # Import the enhanced scraper
        from enhanced_nfl_scraper import EnhancedNFLScraper
        scraper = EnhancedNFLScraper()
        
        all_players = []
        results = {}
        
        for team in teams:
            logger.info(f"Scraping {team}")
            
            try:
                # Use the correct method name from enhanced scraper
                players = scraper.extract_complete_team_roster(team)
                all_players.extend(players)
                
                results[team] = {
                    "players_count": len(players),
                    "status": "success"
                }
                
                logger.info(f"✅ {team}: {len(players)} players")
                
            except Exception as e:
                logger.error(f"Error scraping {team}: {e}")
                results[team] = {
                    "players_count": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        # Save to CSV file
        if all_players:
            import pandas as pd
            from datetime import datetime
            import os
            
            df = pd.DataFrame(all_players)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"data/players_{timestamp}.csv"
            
            # Create data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)
            df.to_csv(csv_filename, index=False)
            
            logger.info(f"Saved standard data to {csv_filename}")
        
        return jsonify({
            "status": "success",
            "total_players": len(all_players),
            "teams_processed": len(teams),
            "results": results,
            "message": f"Standard scraping completed for {len(all_players)} players"
        })
        
    except Exception as e:
        logger.error(f"Error in standard scraping: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/enhanced', methods=['POST'])
def enhanced_scrape():
    """Enhanced scraping with complete roster extraction."""
    try:
        data = request.get_json()
        teams = data.get('teams', [])
        
        if not teams:
            return jsonify({"error": "No teams specified"}), 400
        
        # Import enhanced scraper
        from enhanced_nfl_scraper import EnhancedNFLScraper
        scraper = EnhancedNFLScraper()
        
        all_players = []
        results = {}
        
        for team in teams:
            logger.info(f"Starting enhanced scraping for {team}")
            
            # Extract complete roster
            team_players = scraper.extract_complete_team_roster(team)
            all_players.extend(team_players)
            
            results[team] = {
                "players_found": len(team_players),
                "status": "success" if team_players else "no_data"
            }
            
            logger.info(f"Completed {team}: {len(team_players)} players")
        
        # Save to database
        if all_players:
            from simple_db_integration import save_players_to_db
            save_players_to_db(all_players)
        
        return jsonify({
            "status": "success",
            "total_players": len(all_players),
            "teams_processed": len(teams),
            "results": results,
            "message": f"Successfully scraped {len(all_players)} players from {len(teams)} teams"
        })
        
    except Exception as e:
        logger.error(f"Enhanced scraping error: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/comprehensive', methods=['POST'])
def comprehensive_scrape():
    """Comprehensive scraping with all 40+ fields using optimized collector."""
    try:
        data = request.get_json()
        teams = data.get('teams', [])
        
        if not teams:
            return jsonify({"error": "No teams specified"}), 400
        
        # Import REAL DATA COLLECTOR - NO SIMULATED DATA EVER
        from real_data_collector import RealDataCollector
        
        collector = RealDataCollector()
        
        all_players = []
        results = {}
        
        for team in teams:
            logger.info(f"Starting comprehensive scraping for {team}")
            
            # Collect comprehensive data for the team (all players when not testing)
            enhanced_players = collector.collect_team_roster(team, limit_players=None)
            
            all_players.extend(enhanced_players)
            
            # Calculate quality metrics
            avg_quality = sum(p.get('data_quality_score', 0) for p in enhanced_players) / len(enhanced_players) if enhanced_players else 0
            total_sources = sum(len(p.get('data_sources', [])) for p in enhanced_players)
            
            results[team] = {
                "players_found": len(enhanced_players),
                "players_enhanced": len(enhanced_players),
                "avg_quality_score": round(avg_quality, 1),
                "total_sources_used": total_sources,
                "status": "success" if enhanced_players else "no_data"
            }
            
            logger.info(f"Completed {team}: {len(enhanced_players)} players with comprehensive data (avg quality: {avg_quality:.1f})")
        
        # Calculate overall metrics
        total_sources = sum(results[team].get("total_sources_used", 0) for team in results)
        avg_quality = sum(results[team].get("avg_quality_score", 0) for team in results) / len(results) if results else 0
        
        return jsonify({
            "status": "success",
            "total_players": len(all_players),
            "teams_processed": len(teams),
            "results": results,
            "avg_quality_score": round(avg_quality, 1),
            "total_sources_used": total_sources,
            "message": f"Successfully collected comprehensive data for {len(all_players)} players from {len(teams)} teams"
        })
        
    except Exception as e:
        logger.error(f"Comprehensive scraping error: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/firecrawl', methods=['POST'])
def firecrawl_scrape():
    """Enhanced scraping using Firecrawl's advanced extraction capabilities."""
    try:
        data = request.get_json()
        teams = data.get('teams', [])
        
        if not teams:
            return jsonify({"error": "No teams specified"}), 400
        
        try:
            # Import Firecrawl scraper with fallback
            from simple_firecrawl_scraper import SimpleFirecrawlScraper
            from enhanced_nfl_scraper import EnhancedNFLScraper
            
            roster_scraper = EnhancedNFLScraper()
            firecrawl_scraper = SimpleFirecrawlScraper()
            
            all_players = []
            results = {}
            firecrawl_available = True
            
            for team in teams:
                logger.info(f"Starting Firecrawl scraping for {team}")
                
                # Extract complete roster first
                team_players = roster_scraper.extract_complete_team_roster(team)
                
                try:
                    # Try Firecrawl enhancement
                    enhanced_players = firecrawl_scraper.collect_team_roster(team, team_players)
                    
                    # Check if Firecrawl is working (402 = payment required)
                    if not enhanced_players or all(len(p.get('data_sources', [])) == 0 for p in enhanced_players):
                        firecrawl_available = False
                        raise Exception("Firecrawl API unavailable (payment required)")
                        
                except Exception as fe:
                    logger.warning(f"Firecrawl unavailable for {team}: {fe}")
                    firecrawl_available = False
                    # Fallback to basic roster data with enhanced fields
                    enhanced_players = []
                    for player in team_players:
                        enhanced_player = {
                            **player,
                            'data_quality_score': 3.0,  # Basic score for roster-only data
                            'data_sources': ['NFL.com'],
                            'twitter_handle': None,
                            'instagram_handle': None,
                            'tiktok_handle': None,
                            'youtube_handle': None,
                            'contract_value': None,
                            'wikipedia_url': None,
                            'career_stats': None
                        }
                        enhanced_players.append(enhanced_player)
                
                all_players.extend(enhanced_players)
                
                # Calculate quality metrics
                avg_quality = sum(p.get('data_quality_score', 0) for p in enhanced_players) / len(enhanced_players) if enhanced_players else 0
                total_sources = sum(len(p.get('data_sources', [])) for p in enhanced_players)
                
                results[team] = {
                    "players_found": len(team_players),
                    "players_enhanced": len(enhanced_players),
                    "avg_quality_score": round(avg_quality, 2),
                    "total_sources_used": total_sources,
                    "unique_sources": list(set(source for p in enhanced_players for source in p.get('data_sources', []))),
                    "status": "completed_with_fallback" if not firecrawl_available else "completed"
                }
                
                logger.info(f"Completed {team}: {len(enhanced_players)} players, avg quality: {avg_quality:.2f}")
            
            # Save to database
            if all_players:
                try:
                    from simple_db_integration import save_players_to_db
                    save_players_to_db(all_players)
                except Exception as db_error:
                    logger.warning(f"Database save failed: {db_error}")
            
            # Save to CSV for data viewer
            import pandas as pd
            df = pd.DataFrame(all_players)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"data/firecrawl_players_{timestamp}.csv"
            
            # Create data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)
            df.to_csv(csv_filename, index=False)
            
            status_message = f"Successfully scraped {len(all_players)} players from {len(teams)} teams"
            if not firecrawl_available:
                status_message += " (using fallback mode - Firecrawl API unavailable)"
            
            return jsonify({
                "status": "success",
                "total_players": len(all_players),
                "teams_processed": len(teams),
                "results": results,
                "data_file": csv_filename,
                "avg_quality_score": round(sum(p.get('data_quality_score', 0) for p in all_players) / len(all_players), 2) if all_players else 0,
                "firecrawl_available": firecrawl_available,
                "message": status_message
            })
            
        except ImportError as ie:
            logger.error(f"Import error in Firecrawl scraping: {ie}")
            return jsonify({"error": f"Import error: {ie}", "status": "error"}), 500
        
    except Exception as e:
        logger.error(f"Firecrawl scraping error: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/players', methods=['POST'])
def get_players():
    """Get list of players for selected teams."""
    try:
        data = request.get_json()
        teams = data.get('teams', [])
        
        # Mock player data - in a real app, this would come from a database
        mock_players = []
        for team in teams:
            for i in range(5):  # 5 players per team for demo
                mock_players.append({
                    'id': f"{team}_{i}",
                    'name': f"Player {i+1}",
                    'position': ['QB', 'RB', 'WR', 'TE', 'K'][i],
                    'team': team.upper()
                })
        
        return jsonify({"players": mock_players})
        
    except Exception as e:
        logger.error(f"Error getting players: {e}")
        return jsonify({"error": "Failed to get players"}), 500

@app.route('/api/scrape', methods=['POST'])
def scrape_data():
    """Trigger data scraping for specified teams."""
    try:
        data = request.get_json()
        teams = data.get('teams', [])
        fast_mode = data.get('fast', False)
        
        if not teams:
            return jsonify({"error": "No teams specified"}), 400
        
        logger.info(f"Starting scrape for teams: {teams}")
        
        # Run the scraping pipeline
        results = mcp.run_pipeline(
            teams=teams,
            fast_mode=fast_mode,
            output_dir="data"
        )
        
        return jsonify({
            "status": "success",
            "message": f"Successfully scraped data for {len(teams)} teams",
            "results": results
        })
        
    except NFLGravityError as e:
        logger.error(f"NFL Gravity error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/status')
def get_status():
    """Get current pipeline status."""
    try:
        status = mcp.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": "Failed to get status"}), 500

@app.route('/api/data/latest')
def get_latest_data():
    """Get the latest scraped player data."""
    try:
        import pandas as pd
        import glob
        import os
        
        # FIXED: Find the file with the MOST players (not just prioritize comprehensive)
        all_files = glob.glob('data/comprehensive_players_*.csv') + glob.glob('data/players_*.csv') + glob.glob('data/**/players_*.csv', recursive=True)
        
        # Find the file with the most players
        largest_file = None
        max_players = 0
        
        for file_path in all_files:
            try:
                df_temp = pd.read_csv(file_path)
                if len(df_temp) > max_players:
                    max_players = len(df_temp)
                    largest_file = file_path
            except:
                continue
        
        if largest_file:
            latest_file = largest_file
        else:
            # Try to get data info from MCP as fallback
            try:
                data_info = mcp.get_latest_data_info()
                return jsonify(data_info)
            except:
                return jsonify({
                    "players": [],
                    "count": 0,
                    "status": "no_data",
                    "message": "No player data files found"
                })
        
        # Load the data
        df = pd.read_csv(latest_file)
        
        # Convert to dictionary, handling NaN values
        players_data = df.fillna('').to_dict('records')
        
        # Convert all columns to proper types for JSON
        players = []
        for player in players_data:
            clean_player = {}
            for key, value in player.items():
                if pd.isna(value) or value == '':
                    clean_player[key] = None
                elif isinstance(value, (int, float)) and pd.notna(value):
                    clean_player[key] = value
                else:
                    clean_player[key] = str(value)
            players.append(clean_player)
        
        return jsonify({
            "players": players,
            "count": len(players),
            "status": "success",
            "source_file": latest_file,
            "columns": list(df.columns),
            "message": f"Loaded {len(players)} players from {latest_file}"
        })
        
    except Exception as e:
        logger.error(f"Error getting latest data: {e}")
        # Fallback to MCP method
        try:
            data_info = mcp.get_latest_data_info()
            return jsonify(data_info)
        except:
            return jsonify({"error": "Failed to get data info", "status": "error"}), 500

@app.route('/api/logs')
def get_logs():
    """Get recent log entries."""
    try:
        log_file = "logs/nfl_gravity.log"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Return last 50 lines
                recent_logs = lines[-50:] if len(lines) > 50 else lines
                return jsonify({"logs": recent_logs})
        else:
            return jsonify({"logs": []})
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({"error": "Failed to read logs"}), 500

@app.route('/test-scraper')
def test_scraper_page():
    """Test scraper page for 3 specific players."""
    return render_template('test_scraper.html')

@app.route('/api/test/players', methods=['POST'])
def test_players():
    """Test real data scraping for specific players."""
    try:
        data = request.get_json()
        players = data.get('players', ['Lamar Jackson', 'Josh Allen', 'Patrick Mahomes'])
        
        # Import the test scraper
        from test_player_scraper import TestPlayerScraper
        
        scraper = TestPlayerScraper()
        
        # Run the test
        logger.info(f"Starting real data test for players: {players}")
        
        results = scraper.test_three_players()
        field_comparison = scraper.get_all_field_comparison(results)
        
        return jsonify({
            "status": "success",
            "test_results": results,
            "field_comparison": field_comparison,
            "message": f"Real data test completed for {len(players)} players"
        })
        
    except Exception as e:
        logger.error(f"Player test error: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

if __name__ == '__main__':
    # Ensure data and logs directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
