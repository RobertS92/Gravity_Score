"""
NFL Gravity Flask Application - Complete integration with Gravity Score System
Production-ready web interface for NFL player data with authentic gravity scoring
"""

import os
import json
import logging
import pandas as pd
import glob
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

# Import gravity score system  
from gravity_score_system import GravityScoreCalculator, calculate_gravity_scores_for_dataset

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize gravity calculator
gravity_calculator = GravityScoreCalculator()

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')

@app.route('/scraping')
def scraping():
    """Data collection/scraping configuration page."""
    return render_template('scraping.html')

@app.route('/data-collection')
def data_collection():
    """Data collection/scraping configuration page (alternative route)."""
    return render_template('scraping.html')

@app.route('/view-data')
def view_data():
    """Data viewing and filtering page."""
    return render_template('data_viewer.html')

@app.route('/data')
def data_viewer():
    """Data viewer page with Excel-like filtering."""
    return render_template('data_viewer.html')

@app.route('/players')
def all_players():
    """All NFL players page with gravity scores."""
    return render_template('players.html')

@app.route('/test-scraper')
def test_scraper():
    """Test scraper page for individual player testing."""
    return render_template('test_scraper.html')

@app.route('/gravity-scores')
def gravity_scores():
    """Gravity scores analysis page."""
    return render_template('gravity_scores.html')

@app.route('/player-search')
def player_search():
    """Player search and gravity score calculation page."""
    return render_template('player_search.html')

@app.route('/my-players')
def my_players():
    """My saved players page."""
    return render_template('my_players.html')

@app.route('/favorites')  
def favorites_page():
    """Favorite players page."""
    return render_template('favorites.html')

# ===== API ENDPOINTS =====

@app.route('/api/status')
def api_status():
    """API status endpoint."""
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "mode": "full_production"
    })

@app.route('/api/players/all')
def get_all_players():
    """Get all players with gravity scores calculated."""
    try:
        # Find latest data file with gravity scores or calculate them
        best_file = _find_best_data_file()
        
        if not best_file:
            return jsonify({
                "players": [],
                "count": 0,
                "status": "no_data",
                "message": "No authentic player data available. Please run data collection first."
            })

        # Load the data
        df = pd.read_csv(best_file)
        
        # Check if gravity scores already exist
        gravity_columns = ['brand_power', 'proof', 'proximity', 'velocity', 'risk', 'total_gravity']
        has_gravity_scores = all(col in df.columns for col in gravity_columns)
        
        if not has_gravity_scores:
            logger.info("Calculating gravity scores for players...")
            # Calculate gravity scores
            df = _calculate_gravity_scores_for_dataframe(df)
            
            # Save enhanced file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            enhanced_filename = f"data/players_with_gravity_{timestamp}.csv"
            df.to_csv(enhanced_filename, index=False)
            logger.info(f"Saved enhanced data with gravity scores to {enhanced_filename}")

        # Convert to dictionary and clean data
        players = _clean_players_data(df)

        return jsonify({
            "players": players,
            "count": len(players),
            "status": "success",
            "columns": list(df.columns),
            "source_file": best_file,
            "has_gravity_scores": True
        })

    except Exception as e:
        logger.error(f"Error getting all players: {e}")
        return jsonify({
            "players": [],
            "count": 0,
            "status": "error",
            "error": f"Failed to load player data: {str(e)}",
            "message": "Error loading authentic player data."
        })

@app.route('/api/data/latest')
def get_latest_data():
    """Get latest comprehensive data with gravity scores."""
    try:
        # Prioritize authentic gravity files first
        authentic_gravity_files = glob.glob('data/authentic_gravity_scores_*.csv')
        gravity_files = glob.glob('data/players_with_gravity_*.csv')
        comprehensive_files = glob.glob('data/comprehensive_players_*.csv')
        age_files = glob.glob('data/players_with_ages_*.csv')
        standard_files = glob.glob('data/players_*.csv')

        # Priority order: authentic gravity > other gravity > comprehensive > age > standard
        all_files = authentic_gravity_files + gravity_files + comprehensive_files + age_files + standard_files

        best_file = _find_largest_file_with_good_data(all_files)

        if not best_file:
            return jsonify({
                "players": [],
                "count": 0,
                "status": "no_data"
            })

        df = pd.read_csv(best_file)
        
        # Calculate gravity scores if not present
        gravity_columns = ['brand_power', 'proof', 'proximity', 'velocity', 'risk', 'total_gravity']
        if not all(col in df.columns for col in gravity_columns):
            logger.info("Adding gravity scores to comprehensive data...")
            df = _calculate_gravity_scores_for_dataframe(df)

        players = _clean_players_data(df)

        return jsonify({
            "players": players,
            "count": len(players),
            "status": "success",
            "columns": list(df.columns),
            "source_file": best_file
        })

    except Exception as e:
        logger.error(f"Error getting latest data: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/gravity/calculate', methods=['POST'])
def calculate_gravity_for_player():
    """Calculate gravity score for a specific player."""
    try:
        data = request.get_json()
        player_data = data.get('player_data', {})
        
        if not player_data:
            return jsonify({"error": "Player data is required"}), 400

        # Calculate gravity components
        gravity_components = gravity_calculator.calculate_total_gravity(player_data)
        
        return jsonify({
            "player_name": player_data.get('name', 'Unknown'),
            "gravity_scores": {
                "brand_power": gravity_components.brand_power,
                "proof": gravity_components.proof,
                "proximity": gravity_components.proximity,
                "velocity": gravity_components.velocity,
                "risk": gravity_components.risk,
                "total_gravity": gravity_components.total_gravity
            },
            "status": "success"
        })

    except Exception as e:
        logger.error(f"Error calculating gravity score: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/gravity/bulk-calculate', methods=['POST'])
def bulk_calculate_gravity():
    """Calculate gravity scores for all players in dataset."""
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path or not os.path.exists(file_path):
            # Find latest file
            file_path = _find_best_data_file()
            
        if not file_path:
            return jsonify({"error": "No data file found"}), 400

        logger.info(f"Calculating gravity scores for dataset: {file_path}")
        
        # Calculate gravity scores for entire dataset
        enhanced_df = calculate_gravity_scores_for_dataset(file_path)
        
        # Save enhanced dataset
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/players_with_gravity_{timestamp}.csv"
        enhanced_df.to_csv(output_file, index=False)
        
        # Get top players
        top_players_subset = enhanced_df.head(10)[['name', 'position', 'current_team', 'total_gravity']]
        top_players = top_players_subset.to_dict(orient='records')
        
        return jsonify({
            "status": "success",
            "total_players": len(enhanced_df),
            "output_file": output_file,
            "top_players": top_players,
            "avg_gravity_score": enhanced_df['total_gravity'].mean(),
            "message": f"Gravity scores calculated for {len(enhanced_df)} players"
        })

    except Exception as e:
        logger.error(f"Error in bulk gravity calculation: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape', methods=['POST'])
def scrape_unified():
    """Unified scraping endpoint - handles both standard and comprehensive modes."""
    try:
        data = request.get_json()
        mode = data.get('mode', 'standard')
        
        # Route to appropriate method based on mode
        if mode == 'comprehensive':
            return scrape_comprehensive()
        else:
            return scrape_standard()
            
    except Exception as e:
        logger.error(f"Error in unified scraping endpoint: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/standard', methods=['POST'])
def scrape_standard():
    """Standard NFL scraping endpoint - basic roster extraction."""
    try:
        data = request.get_json()
        teams = data.get('teams', ['49ers'])

        logger.info(f"Starting standard scraping for teams: {teams}")

        # Initialize progress tracking
        from progress_tracker import progress_tracker
        progress_tracker.start_scraping(teams, "standard")

        # Import the enhanced scraper
        from enhanced_nfl_scraper import EnhancedNFLScraper
        scraper = EnhancedNFLScraper()

        all_players = []
        results = {}

        for team_index, team in enumerate(teams):
            logger.info(f"Scraping {team}")
            progress_tracker.update_team_progress(team, 0, 92)

            try:
                players = scraper.extract_complete_team_roster(team)
                all_players.extend(players)

                results[team] = {
                    "players_count": len(players),
                    "status": "success"
                }

                progress_tracker.complete_team(team, len(players))
                logger.info(f"✅ {team}: {len(players)} players")

            except Exception as e:
                logger.error(f"Error scraping {team}: {e}")
                progress_tracker.add_error(team, str(e))
                results[team] = {
                    "players_count": 0,
                    "status": "error",
                    "error": str(e)
                }

        # Mark as completed
        progress_tracker.finish_scraping(success=True)

        # Save to CSV file with gravity scores
        if all_players:
            df = pd.DataFrame(all_players)
            
            # Calculate gravity scores
            df = _calculate_gravity_scores_for_dataframe(df)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"data/players_with_gravity_{timestamp}.csv"

            os.makedirs("data", exist_ok=True)
            df.to_csv(csv_filename, index=False)

            logger.info(f"Saved standard data with gravity scores to {csv_filename}")

        return jsonify({
            "status": "success",
            "total_players": len(all_players),
            "teams_processed": len(teams),
            "results": results,
            "message": f"Standard scraping completed for {len(all_players)} players with gravity scores"
        })

    except Exception as e:
        logger.error(f"Error in standard scraping: {e}")
        from progress_tracker import progress_tracker
        progress_tracker.finish_scraping(success=False)
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/comprehensive', methods=['POST'])
def scrape_comprehensive():
    """Comprehensive scraping with gravity score calculation and real-time progress tracking."""
    try:
        data = request.get_json()
        teams = data.get('teams', ['49ers'])

        logger.info(f"Starting comprehensive scraping with gravity scoring for teams: {teams}")

        # Initialize progress tracking
        from progress_tracker import progress_tracker
        progress_tracker.start_scraping(teams, "comprehensive")

        # Use enhanced scraping system for robust completion
        from enhanced_scraping_system import enhanced_scraping_system
        
        # Run comprehensive scraping with progress tracking
        scraping_results = enhanced_scraping_system.scrape_all_teams_comprehensive(teams)
        
        all_players = scraping_results["players_data"]
        results = scraping_results["results"]

        # Save comprehensive data with gravity scores
        if all_players:
            df = pd.DataFrame(all_players)
            
            # Calculate gravity scores for all players
            logger.info("Calculating gravity scores for all collected players...")
            df = _calculate_gravity_scores_for_dataframe(df)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"data/comprehensive_players_with_gravity_{timestamp}.csv"

            os.makedirs("data", exist_ok=True)
            df.to_csv(csv_filename, index=False)

            logger.info(f"Saved comprehensive data with gravity scores to {csv_filename}")

        return jsonify({
            "status": scraping_results["status"],
            "total_players": scraping_results["total_players"],
            "teams_processed": scraping_results["teams_processed"],
            "teams_successful": scraping_results["teams_successful"],
            "teams_failed": scraping_results["teams_failed"],
            "results": scraping_results["results"],
            "avg_quality_score": scraping_results["avg_quality_score"],
            "message": scraping_results["message"]
        })

    except Exception as e:
        logger.error(f"Error in comprehensive data scraping: {e}")
        from progress_tracker import progress_tracker
        progress_tracker.finish_scraping(success=False)
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/firecrawl', methods=['POST'])
def scrape_firecrawl():
    """Firecrawl scraping endpoint."""
    try:
        data = request.get_json()
        teams = data.get('teams', ['49ers'])

        logger.info(f"Starting firecrawl scraping for teams: {teams}")

        # Check if firecrawl comprehensive scraper exists
        try:
            from firecrawl_comprehensive_scraper import FirecrawlComprehensiveScraper
            scraper = FirecrawlComprehensiveScraper()
        except ImportError:
            # Fallback to comprehensive collector if firecrawl not available
            from real_data_collector import RealDataCollector
            collector = RealDataCollector()
            
            all_players = []
            results = {}

            for team in teams:
                try:
                    players = collector.collect_team_roster(team, limit_players=0)
                    all_players.extend(players)
                    results[team] = {"players_count": len(players), "status": "success"}
                except Exception as e:
                    logger.error(f"Error with {team}: {e}")
                    results[team] = {"players_count": 0, "status": "error", "error": str(e)}

            # Save results
            if all_players:
                df = pd.DataFrame(all_players)
                df = _calculate_gravity_scores_for_dataframe(df)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_filename = f"data/firecrawl_players_with_gravity_{timestamp}.csv"
                os.makedirs("data", exist_ok=True)
                df.to_csv(csv_filename, index=False)

            return jsonify({
                "status": "success",
                "total_players": len(all_players),
                "teams_processed": len(teams),
                "results": results,
                "message": f"Firecrawl scraping completed for {len(all_players)} players with gravity scores"
            })

        # If firecrawl scraper is available
        all_players = []
        results = {}

        for team in teams:
            logger.info(f"Firecrawl scraping {team}")

            try:
                players = scraper.scrape_team_comprehensive(team)
                all_players.extend(players)

                results[team] = {
                    "players_count": len(players),
                    "status": "success"
                }

                logger.info(f"✅ {team}: {len(players)} players via Firecrawl")

            except Exception as e:
                logger.error(f"Error scraping {team} with Firecrawl: {e}")
                results[team] = {
                    "players_count": 0,
                    "status": "error",
                    "error": str(e)
                }

        # Save to CSV file with gravity scores
        if all_players:
            df = pd.DataFrame(all_players)
            
            # Calculate gravity scores
            df = _calculate_gravity_scores_for_dataframe(df)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"data/firecrawl_players_with_gravity_{timestamp}.csv"

            os.makedirs("data", exist_ok=True)
            df.to_csv(csv_filename, index=False)

            logger.info(f"Saved Firecrawl data with gravity scores to {csv_filename}")

        return jsonify({
            "status": "success",
            "total_players": len(all_players),
            "teams_processed": len(teams),
            "results": results,
            "message": f"Firecrawl scraping completed for {len(all_players)} players with gravity scores"
        })

    except Exception as e:
        logger.error(f"Error in firecrawl scraping: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/teams')
def get_teams():
    """Get list of NFL teams."""
    teams = [
        "49ers", "bears", "bengals", "bills", "broncos", "browns", "buccaneers",
        "cardinals", "chargers", "chiefs", "colts", "commanders", "cowboys",
        "dolphins", "eagles", "falcons", "giants", "jaguars", "jets", "lions",
        "packers", "panthers", "patriots", "raiders", "rams", "ravens",
        "saints", "seahawks", "steelers", "texans", "titans", "vikings"
    ]
    return jsonify({"teams": teams})

@app.route('/api/scrape/progress')
def get_scrape_progress():
    """Get real-time scraping progress."""
    from progress_tracker import progress_tracker
    return jsonify(progress_tracker.get_progress())

@app.route('/api/players/search', methods=['GET'])
def search_players():
    """Search for players by name."""
    try:
        query = request.args.get('query', '').strip().lower()
        
        if not query:
            return jsonify({"players": [], "message": "No search query provided"})
        
        # Get all available player names from data files
        all_players = []
        data_files = glob.glob('data/players_*.csv') + glob.glob('data/comprehensive_*.csv')
        
        for file_path in data_files:
            try:
                df = pd.read_csv(file_path)
                if 'name' in df.columns:
                    players = df[['name', 'position', 'current_team']].fillna('').to_dict(orient='records')
                    all_players.extend(players)
            except:
                continue
        
        # Remove duplicates and filter by search query
        seen_names = set()
        unique_players = []
        
        for player in all_players:
            name = player.get('name', '').strip()
            if name and name.lower() not in seen_names:
                if query in name.lower():
                    unique_players.append(player)
                    seen_names.add(name.lower())
        
        # Sort by name and limit results
        unique_players.sort(key=lambda x: x.get('name', ''))
        limited_results = unique_players[:50]  # Limit to 50 results
        
        return jsonify({
            "players": limited_results,
            "total_found": len(unique_players),
            "showing": len(limited_results)
        })
    
    except Exception as e:
        logger.error(f"Error searching players: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/favorites/add', methods=['POST'])
def add_favorite_players():
    """Add players to favorites with comprehensive data collection."""
    try:
        data = request.get_json()
        player_names = data.get('players', [])
        
        if not player_names:
            return jsonify({"error": "No players specified"}), 400
        
        logger.info(f"Adding favorite players: {player_names}")
        
        from favorite_players_manager import favorite_players_manager
        result = favorite_players_manager.add_favorite_players(player_names)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error adding favorite players: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/favorites/list', methods=['GET'])
def get_favorite_players():
    """Get list of favorite players with comprehensive data."""
    try:
        from favorite_players_manager import favorite_players_manager
        result = favorite_players_manager.get_favorites_data()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting favorite players: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/players/process-selected', methods=['POST'])
def process_selected_players():
    """Process selected players - get their data and calculate gravity scores."""
    try:
        data = request.get_json()
        selected_names = data.get('players', [])
        
        if not selected_names:
            return jsonify({"error": "No players selected"}), 400
        
        logger.info(f"Processing {len(selected_names)} selected players")
        
        results = []
        for player_name in selected_names:
            try:
                # Check if player data already exists
                player_data = _find_existing_player_data(player_name)
                
                if player_data and _has_comprehensive_data(player_data):
                    # Calculate gravity score for existing data
                    gravity_components = gravity_calculator.calculate_total_gravity(player_data)
                    
                    player_result = {
                        "name": player_name,
                        "status": "existing_data",
                        "data": player_data,
                        "gravity_scores": {
                            "brand_power": gravity_components.brand_power,
                            "proof": gravity_components.proof,
                            "proximity": gravity_components.proximity,
                            "velocity": gravity_components.velocity,
                            "risk": gravity_components.risk,
                            "total_gravity": gravity_components.total_gravity
                        }
                    }
                else:
                    # Need to collect data for this player
                    logger.info(f"Collecting comprehensive data for {player_name}")
                    
                    # Use real data collector
                    from real_data_collector import RealDataCollector
                    collector = RealDataCollector()
                    
                    # Extract team and position if available
                    team = player_data.get('current_team', '49ers') if player_data else '49ers'
                    
                    # Collect comprehensive data
                    comprehensive_data = collector.collect_single_player_comprehensive(player_name, team)
                    
                    if comprehensive_data:
                        # Calculate gravity score
                        gravity_components = gravity_calculator.calculate_total_gravity(comprehensive_data)
                        
                        player_result = {
                            "name": player_name,
                            "status": "new_data_collected",
                            "data": comprehensive_data,
                            "gravity_scores": {
                                "brand_power": gravity_components.brand_power,
                                "proof": gravity_components.proof,
                                "proximity": gravity_components.proximity,
                                "velocity": gravity_components.velocity,
                                "risk": gravity_components.risk,
                                "total_gravity": gravity_components.total_gravity
                            }
                        }
                    else:
                        player_result = {
                            "name": player_name,
                            "status": "failed",
                            "error": "Could not collect data for this player"
                        }
                
                results.append(player_result)
                
            except Exception as e:
                logger.error(f"Error processing player {player_name}: {e}")
                results.append({
                    "name": player_name,
                    "status": "error",
                    "error": str(e)
                })
        
        # Save successful results to my_players file
        successful_players = [r for r in results if r["status"] in ["existing_data", "new_data_collected"]]
        
        if successful_players:
            _save_to_my_players(successful_players)
        
        return jsonify({
            "status": "success",
            "processed": len(results),
            "successful": len(successful_players),
            "results": results,
            "message": f"Processed {len(results)} players, {len(successful_players)} successful"
        })
        
    except Exception as e:
        logger.error(f"Error processing selected players: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/my-players', methods=['GET'])
def get_my_players():
    """Get saved players from my_players.csv."""
    try:
        my_players_file = "data/my_players.csv"
        
        if not os.path.exists(my_players_file):
            return jsonify({
                "players": [],
                "total": 0,
                "message": "No saved players found"
            })
        
        df = pd.read_csv(my_players_file)
        players = _clean_players_data(df)
        
        # Sort by total gravity score descending
        if 'total_gravity' in df.columns:
            players.sort(key=lambda x: x.get('total_gravity', 0), reverse=True)
        
        return jsonify({
            "players": players,
            "total": len(players),
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error getting my players: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/my-players', methods=['DELETE'])
def clear_my_players():
    """Clear all saved players."""
    try:
        my_players_file = "data/my_players.csv"
        
        if os.path.exists(my_players_file):
            os.remove(my_players_file)
        
        return jsonify({
            "status": "success",
            "message": "All saved players cleared"
        })
        
    except Exception as e:
        logger.error(f"Error clearing my players: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

# ===== HELPER FUNCTIONS =====

def _find_best_data_file():
    """Find the best available data file."""
    # Priority order: gravity files, comprehensive files, age files, standard files
    gravity_files = glob.glob('data/players_with_gravity_*.csv')
    comprehensive_files = glob.glob('data/comprehensive_players_*.csv')
    age_files = glob.glob('data/players_with_ages_*.csv') + glob.glob('data/priority_players_with_ages_*.csv')
    standard_files = glob.glob('data/players_*.csv')

    all_files = gravity_files + comprehensive_files + age_files + standard_files

    return _find_largest_file_with_good_data(all_files)

def _find_largest_file_with_good_data(file_list):
    """Find the largest file with realistic data."""
    if not file_list:
        return None

    best_file = None
    max_players_with_good_data = 0

    for file_path in file_list:
        try:
            df_temp = pd.read_csv(file_path)
            if len(df_temp) > 0:
                # Check data quality
                realistic_data_score = _assess_data_quality(df_temp)
                
                if realistic_data_score > 0 and len(df_temp) > max_players_with_good_data:
                    max_players_with_good_data = len(df_temp)
                    best_file = file_path
        except:
            continue

    return best_file

def _assess_data_quality(df):
    """Assess the quality of data in a DataFrame."""
    score = 0
    
    # Check for realistic heights
    if 'height' in df.columns:
        sample_heights = df['height'].dropna().head(5)
        realistic_heights = 0
        
        for height in sample_heights:
            if height and isinstance(height, str) and "'" in height:
                parts = height.replace('"', '').split("'")
                if len(parts) == 2 and parts[0].isdigit():
                    feet = int(parts[0])
                    if 5 <= feet <= 6:  # Realistic NFL height
                        realistic_heights += 1
        
        if realistic_heights >= 3:
            score += 1

    # Check for age data
    if 'age' in df.columns:
        ages = df['age'].dropna()
        if len(ages) > 0:
            realistic_ages = ages[(ages >= 20) & (ages <= 45)]
            if len(realistic_ages) > len(ages) * 0.8:  # 80% realistic ages
                score += 1

    # Check for comprehensive data
    comprehensive_columns = ['twitter_followers', 'instagram_followers', 'pro_bowls', 'contract_value']
    has_comprehensive = sum(1 for col in comprehensive_columns if col in df.columns)
    if has_comprehensive >= 2:
        score += 1

    return score

def _calculate_gravity_scores_for_dataframe(df):
    """Calculate gravity scores for all players in a DataFrame."""
    gravity_scores = []
    
    for index, row in df.iterrows():
        player_data = row.to_dict()
        
        try:
            components = gravity_calculator.calculate_total_gravity(player_data)
            gravity_scores.append({
                'brand_power': components.brand_power,
                'proof': components.proof,
                'proximity': components.proximity,
                'velocity': components.velocity,
                'risk': components.risk,
                'total_gravity': components.total_gravity
            })
        except Exception as e:
            logger.error(f"Error calculating gravity for {player_data.get('name', 'Unknown')}: {e}")
            # Add zero scores for failed calculations
            gravity_scores.append({
                'brand_power': 0.0,
                'proof': 0.0,
                'proximity': 0.0,
                'velocity': 0.0,
                'risk': 0.0,
                'total_gravity': 0.0
            })
    
    # Add gravity scores to dataframe
    gravity_df = pd.DataFrame(gravity_scores)
    enhanced_df = pd.concat([df, gravity_df], axis=1)
    
    # Sort by total gravity score (descending)
    enhanced_df = enhanced_df.sort_values('total_gravity', ascending=False)
    
    return enhanced_df

def _clean_players_data(df):
    """Clean and prepare players data for JSON response."""
    players_data = df.fillna('').to_dict('records')
    
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
    
    return players

def _find_existing_player_data(player_name):
    """Find existing data for a specific player."""
    data_files = glob.glob('data/players_*.csv') + glob.glob('data/comprehensive_*.csv') + glob.glob('data/my_players.csv')
    
    for file_path in data_files:
        try:
            df = pd.read_csv(file_path)
            if 'name' in df.columns:
                player_rows = df[df['name'].str.lower() == player_name.lower()]
                if not player_rows.empty:
                    return player_rows.iloc[0].to_dict()
        except:
            continue
    
    return None

def _has_comprehensive_data(player_data):
    """Check if player data has comprehensive information for gravity calculation."""
    if not player_data:
        return False
    
    # Check for key fields needed for gravity calculation
    key_fields = ['age', 'height', 'weight', 'position', 'current_team']
    social_fields = ['twitter_followers', 'instagram_followers']
    performance_fields = ['pro_bowls', 'all_pros', 'awards']
    financial_fields = ['contract_value', 'salary']
    
    has_basic = sum(1 for field in key_fields if player_data.get(field)) >= 4
    has_social = sum(1 for field in social_fields if player_data.get(field)) >= 1
    has_performance = sum(1 for field in performance_fields if player_data.get(field)) >= 1
    has_financial = sum(1 for field in financial_fields if player_data.get(field)) >= 1
    
    # Need at least basic info plus some comprehensive data
    return has_basic and (has_social or has_performance or has_financial)

def _save_to_my_players(player_results):
    """Save player results to my_players.csv file."""
    try:
        my_players_file = "data/my_players.csv"
        
        # Prepare data for saving
        players_to_save = []
        
        for result in player_results:
            if result.get("status") in ["existing_data", "new_data_collected"]:
                player_data = result.get("data", {}).copy()
                gravity_scores = result.get("gravity_scores", {})
                
                # Add gravity scores to player data
                player_data.update(gravity_scores)
                player_data['saved_at'] = datetime.now().isoformat()
                
                players_to_save.append(player_data)
        
        if not players_to_save:
            return
        
        new_df = pd.DataFrame(players_to_save)
        
        # If file exists, merge with existing data
        if os.path.exists(my_players_file):
            existing_df = pd.read_csv(my_players_file)
            
            # Remove duplicates by name and merge
            existing_df = existing_df[~existing_df['name'].isin(new_df['name'])]
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df
        
        # Save to file
        os.makedirs("data", exist_ok=True)
        combined_df.to_csv(my_players_file, index=False)
        
        logger.info(f"Saved {len(players_to_save)} players to my_players.csv")
        
    except Exception as e:
        logger.error(f"Error saving to my_players.csv: {e}")

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)