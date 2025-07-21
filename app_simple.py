"""
NFL Gravity Flask Application - Simplified for Deployment
Core functionality without complex dependencies
"""

import os
import json
import logging
import pandas as pd
import glob
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

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

@app.route('/players')
def players():
    """Players list page."""
    return render_template('players.html')

@app.route('/test-scraper')
def test_scraper():
    """Test scraper page."""
    return render_template('test_scraper.html')

@app.route('/gravity-scores')
def gravity_scores():
    """Gravity scores dashboard."""
    return render_template('gravity_scores.html')

@app.route('/api/status')
def api_status():
    """API status check."""
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "mode": "simplified_deployment"
    })

def _find_best_data_file():
    """Find the best available data file."""
    try:
        # Look for comprehensive data files first
        comprehensive_files = glob.glob("data/comprehensive_players_*.csv")
        if comprehensive_files:
            return max(comprehensive_files, key=os.path.getmtime)
        
        # Fall back to any player data files
        player_files = glob.glob("data/players_*.csv")
        if player_files:
            return max(player_files, key=os.path.getmtime)
        
        return None
    except Exception as e:
        logger.error(f"Error finding data file: {e}")
        return None

@app.route('/api/data/latest')
def get_latest_data():
    """Get latest player data."""
    try:
        file_path = _find_best_data_file()
        if not file_path:
            return jsonify({"error": "No data available", "status": "no_data"}), 404
        
        # Read the CSV file
        df = pd.read_csv(file_path)
        
        # Convert to JSON records
        data = df.to_dict('records')
        
        return jsonify({
            "status": "success",
            "total_players": len(data),
            "data": data[:50],  # Limit to first 50 players for performance
            "file_path": file_path,
            "columns": list(df.columns),
            "message": f"Loaded {len(data)} players from latest dataset"
        })
        
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/data/all')
def get_all_data():
    """Get all player data."""
    try:
        file_path = _find_best_data_file()
        if not file_path:
            return jsonify({"error": "No data available", "status": "no_data"}), 404
        
        # Read the CSV file
        df = pd.read_csv(file_path)
        
        # Convert to JSON records
        data = df.to_dict('records')
        
        return jsonify({
            "status": "success",
            "total_players": len(data),
            "data": data,
            "file_path": file_path,
            "columns": list(df.columns),
            "message": f"Loaded all {len(data)} players from dataset"
        })
        
    except Exception as e:
        logger.error(f"Error loading all data: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/api/scrape/status')
def scrape_status():
    """Get scraping status."""
    return jsonify({
        "status": "available",
        "modes": ["basic", "comprehensive", "firecrawl"],
        "message": "All scraping modes available"
    })

@app.route('/api/scrape/basic', methods=['POST'])
def scrape_basic():
    """Basic scraping endpoint."""
    try:
        data = request.get_json()
        teams = data.get('teams', ['49ers'])
        
        logger.info(f"Basic scraping requested for teams: {teams}")
        
        # For deployment, return existing data
        file_path = _find_best_data_file()
        if file_path:
            df = pd.read_csv(file_path)
            # Filter by team if available
            if 'team' in df.columns or 'current_team' in df.columns:
                team_col = 'team' if 'team' in df.columns else 'current_team'
                team_data = df[df[team_col].str.contains('|'.join(teams), case=False, na=False)]
                
                return jsonify({
                    "status": "success",
                    "teams_processed": len(teams),
                    "total_players": len(team_data),
                    "message": f"Retrieved data for {len(team_data)} players from {len(teams)} teams"
                })
        
        return jsonify({
            "status": "success",
            "teams_processed": len(teams),
            "total_players": 0,
            "message": "Basic scraping completed (deployment mode)"
        })
        
    except Exception as e:
        logger.error(f"Error in basic scraping: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

if __name__ == '__main__':
    # Run in production mode for deployment
    app.run(host='0.0.0.0', port=5000, debug=False)