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
    """Get information about the latest scraped data."""
    try:
        data_info = mcp.get_latest_data_info()
        return jsonify(data_info)
    except Exception as e:
        logger.error(f"Error getting latest data: {e}")
        return jsonify({"error": "Failed to get data info"}), 500

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

if __name__ == '__main__':
    # Ensure data and logs directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
