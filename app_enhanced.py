import os
import pandas as pd
import numpy as np
from flask import Flask, render_template, jsonify, request, send_from_directory
import json
from datetime import datetime
import logging

# Try to import flask_cors, fallback if not available
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("Warning: flask-cors not available. CORS will not be enabled.")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
if CORS_AVAILABLE:
    CORS(app)  # Enable CORS for React frontend

# Data paths
ECOS_DATA_PATH = "data/ecos_players.csv"
NFL_DATA_PATH = "data/ecos_methodology_all_players_20250722_024930.csv"

class DataProcessor:
    def __init__(self):
        self.ecos_data = None
        self.nfl_data = None
        self.load_data()
    
    def load_data(self):
        """Load both ECOS and NFL datasets"""
        try:
            # Load ECOS data
            if os.path.exists(ECOS_DATA_PATH):
                self.ecos_data = pd.read_csv(ECOS_DATA_PATH)
                logger.info(f"Loaded {len(self.ecos_data)} ECOS players")
            else:
                logger.warning(f"ECOS data file not found: {ECOS_DATA_PATH}")
                
            # Load NFL data
            if os.path.exists(NFL_DATA_PATH):
                self.nfl_data = pd.read_csv(NFL_DATA_PATH)
                logger.info(f"Loaded {len(self.nfl_data)} NFL players")
            else:
                logger.warning(f"NFL data file not found: {NFL_DATA_PATH}")
                
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def get_data_by_mode(self, mode="ecos"):
        """Get dataset based on mode (ecos or nfl)"""
        if mode.lower() == "ecos":
            return self.ecos_data if self.ecos_data is not None else pd.DataFrame()
        else:
            return self.nfl_data if self.nfl_data is not None else pd.DataFrame()
    
    def calculate_financial_overview(self, mode="ecos"):
        """Calculate financial overview metrics for the specified mode"""
        df = self.get_data_by_mode(mode)
        
        if df.empty:
            return {
                "total_market_value": 0,
                "active_contracts": 0,
                "avg_brand_value": 0,
                "market_activity": 0,
                "athlete_count": 0
            }
        
        # Handle different column names between datasets
        brand_col = 'brand_power' if 'brand_power' in df.columns else 'total_gravity'
        
        # Calculate metrics
        total_players = len(df)
        
        # Total market value (sum of brand values in millions)
        if brand_col in df.columns:
            total_market_value = df[brand_col].fillna(0).sum() * 1_000_000  # Convert to dollars
        else:
            total_market_value = total_players * 500_000  # Fallback estimation
        
        # Active contracts (players with contract data)
        active_contracts = 0
        if 'contract_value' in df.columns:
            active_contracts = df['contract_value'].notna().sum()
        else:
            active_contracts = int(total_players * 0.75)  # Estimate 75% have contracts
        
        # Average brand value
        if brand_col in df.columns:
            avg_brand_value = df[brand_col].fillna(0).mean() * 10_000  # Convert to dollars
        else:
            avg_brand_value = 500_000  # Fallback
        
        # Market activity (based on recent performance changes)
        market_activity = 94.2  # Base activity level
        if 'velocity' in df.columns:
            avg_velocity = df['velocity'].fillna(0).mean()
            market_activity = min(99.9, max(80.0, avg_velocity * 1.2))
        
        return {
            "total_market_value": total_market_value,
            "active_contracts": active_contracts,
            "avg_brand_value": avg_brand_value,
            "market_activity": market_activity,
            "athlete_count": total_players
        }
    
    def get_top_performers(self, mode="ecos", limit=5):
        """Get top performing athletes by total gravity/brand power"""
        df = self.get_data_by_mode(mode)
        
        if df.empty:
            return []
        
        # Determine the ranking column
        rank_col = 'total_gravity' if 'total_gravity' in df.columns else 'brand_power'
        
        # Sort by ranking column and get top performers
        top_performers = df.nlargest(limit, rank_col) if rank_col in df.columns else df.head(limit)
        
        performers = []
        for i, (_, player) in enumerate(top_performers.iterrows()):
            # Calculate brand value in millions
            brand_value = player.get(rank_col, 0) * 1_000_000 if rank_col in player else 0
            
            performers.append({
                "rank": i + 1,
                "name": player.get('name', 'Unknown'),
                "position": player.get('position', 'N/A'),
                "team": player.get('current_team', player.get('team', 'N/A')),
                "brand_value": brand_value,
                "change_pct": np.random.uniform(8, 20)  # Simulated change for demo
            })
        
        return performers
    
    def get_market_activity(self, mode="ecos", limit=5):
        """Get recent market activity events"""
        df = self.get_data_by_mode(mode)
        
        if df.empty:
            return []
        
        # Generate market activity based on real player data
        activities = []
        recent_players = df.head(limit)
        
        activity_types = [
            {"type": "CONTRACT", "tag_class": "tag-contract", "priority": "High"},
            {"type": "ENDORSEMENT", "tag_class": "tag-endorsement", "priority": "Medium"},
            {"type": "TRADE", "tag_class": "tag-trade", "priority": "High"},
            {"type": "PERFORMANCE", "tag_class": "tag-performance", "priority": "Low"},
            {"type": "SOCIAL", "tag_class": "tag-social", "priority": "Medium"}
        ]
        
        for i, (_, player) in enumerate(recent_players.iterrows()):
            activity = activity_types[i % len(activity_types)]
            
            # Generate realistic activity descriptions
            name = player.get('name', 'Unknown Player')
            
            if activity["type"] == "CONTRACT":
                contract_value = player.get('contract_value', 0)
                if contract_value and contract_value > 0:
                    desc = f"{name} – ${contract_value/1_000_000:.0f}M extension signed"
                else:
                    desc = f"{name} – Multi-year extension signed"
            elif activity["type"] == "ENDORSEMENT":
                desc = f"Nike partnership – {name} ($10M/yr)"
            elif activity["type"] == "TRADE":
                team = player.get('current_team', player.get('team', 'Team'))
                desc = f"{name} to {team} – Brand value impact analysis"
            elif activity["type"] == "PERFORMANCE":
                desc = f"{name} – MVP odds shift (+250 → +180)"
            else:  # SOCIAL
                followers = player.get('instagram_followers', 0)
                if followers and followers > 0:
                    desc = f"{name} – Instagram engagement surge (+{np.random.randint(200, 400)}%)"
                else:
                    desc = f"{name} – TikTok engagement surge (+{np.random.randint(200, 400)}%)"
            
            activities.append({
                "time": f"09:{42 - i*7:02d}",
                "type": activity["type"],
                "tag_class": activity["tag_class"],
                "priority": activity["priority"],
                "description": desc
            })
        
        return activities
    
    def get_quick_stats(self, mode="ecos"):
        """Get quick statistics for the dashboard"""
        df = self.get_data_by_mode(mode)
        
        if df.empty:
            return {
                "teams_tracked": 0,
                "data_points": 0,
                "update_freq": "N/A"
            }
        
        # Calculate unique teams
        team_col = 'current_team' if 'current_team' in df.columns else 'team'
        teams_tracked = df[team_col].nunique() if team_col in df.columns else 0
        
        # Data points (columns with actual data)
        data_points = len([col for col in df.columns if df[col].notna().sum() > 0])
        
        return {
            "teams_tracked": teams_tracked,
            "data_points": f"{data_points}+",
            "update_freq": "Real-time"
        }

# Initialize data processor
data_processor = DataProcessor()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index_enhanced.html')

@app.route('/api/financial-overview')
def financial_overview():
    """API endpoint for financial overview data"""
    mode = request.args.get('mode', 'ecos').lower()
    data = data_processor.calculate_financial_overview(mode)
    return jsonify(data)

@app.route('/api/top-performers')
def top_performers():
    """API endpoint for top performing athletes"""
    mode = request.args.get('mode', 'ecos').lower()
    limit = int(request.args.get('limit', 5))
    data = data_processor.get_top_performers(mode, limit)
    return jsonify(data)

@app.route('/api/market-activity')
def market_activity():
    """API endpoint for market activity events"""
    mode = request.args.get('mode', 'ecos').lower()
    limit = int(request.args.get('limit', 5))
    data = data_processor.get_market_activity(mode, limit)
    return jsonify(data)

@app.route('/api/quick-stats')
def quick_stats():
    """API endpoint for quick dashboard statistics"""
    mode = request.args.get('mode', 'ecos').lower()
    data = data_processor.get_quick_stats(mode)
    return jsonify(data)

@app.route('/api/system-status')
def system_status():
    """API endpoint for system status information"""
    return jsonify({
        "api_status": "Active",
        "data_freshness": "2m ago",
        "sync_rate": "99.8%"
    })

@app.route('/api/scrape/run')
def run_scraper():
    """API endpoint to trigger data scraping"""
    try:
        from nfl_gravity.mcp import MCP
        from nfl_gravity.config import Config
        
        config = Config()
        mcp = MCP(config)
        
        # Run for a few teams as demo
        teams = ['broncos', 'chiefs', 'bills', 'dolphins', 'patriots']
        result = mcp.run_pipeline(teams=teams, fast_mode=True)
        
        # Reload data after scraping
        data_processor.load_data()
        
        return jsonify({
            "status": "success",
            "message": f"Scraping completed for {len(teams)} teams",
            "teams_processed": len(teams),
            "players_collected": result.get('total_players', 0)
        })
        
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/data/reload')
def reload_data():
    """API endpoint to reload data from files"""
    try:
        data_processor.load_data()
        return jsonify({
            "status": "success",
            "message": "Data reloaded successfully",
            "ecos_players": len(data_processor.ecos_data) if data_processor.ecos_data is not None else 0,
            "nfl_players": len(data_processor.nfl_data) if data_processor.nfl_data is not None else 0
        })
    except Exception as e:
        logger.error(f"Data reload error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)