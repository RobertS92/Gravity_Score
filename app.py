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

# ===== API ENDPOINTS =====

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
        top_players = enhanced_df.head(10)[['name', 'position', 'current_team', 'total_gravity']].to_dict('records')
        
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
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/comprehensive', methods=['POST'])
def scrape_comprehensive():
    """Comprehensive scraping with gravity score calculation."""
    try:
        data = request.get_json()
        teams = data.get('teams', ['49ers'])

        logger.info(f"Starting comprehensive scraping with gravity scoring for teams: {teams}")

        # Use REAL DATA COLLECTOR - NO SIMULATED DATA
        from real_data_collector import RealDataCollector
        collector = RealDataCollector()

        all_players = []
        results = {}

        for team in teams:
            logger.info(f"Starting comprehensive data collection for {team}")

            # Collect comprehensive data for the entire team
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
            "message": f"Comprehensive data with gravity scores collected for {len(all_players)} players from {len(teams)} teams"
        })

    except Exception as e:
        logger.error(f"Error in comprehensive data scraping: {e}")
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
    return jsonify({
        "status": "idle",
        "overall_progress": 0,
        "current_team": None,
        "current_player": None,
        "teams_completed": 0,
        "total_teams": 0,
        "players_processed": 0,
        "current_team_progress": 0,
        "current_team_total": 0,
        "eta_seconds": 0,
        "avg_quality": 0.0,
        "scraping_mode": None,
        "start_time": None
    })

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

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)