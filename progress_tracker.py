"""
Enhanced Progress Tracking System for NFL Gravity Scraping
Provides real-time progress updates for comprehensive data collection
"""

import threading
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

class ScrapingProgressTracker:
    """Thread-safe progress tracker for scraping operations."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._progress_data = {
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
            "start_time": None,
            "completed_teams": [],
            "error_count": 0,
            "errors": []
        }
        
    def start_scraping(self, teams: List[str], mode: str):
        """Initialize scraping progress."""
        with self._lock:
            self._progress_data.update({
                "status": "running",
                "overall_progress": 0,
                "current_team": None,
                "current_player": None,
                "teams_completed": 0,
                "total_teams": len(teams),
                "players_processed": 0,
                "current_team_progress": 0,
                "current_team_total": 0,
                "eta_seconds": 0,
                "avg_quality": 0.0,
                "scraping_mode": mode,
                "start_time": datetime.now().isoformat(),
                "completed_teams": [],
                "error_count": 0,
                "errors": []
            })
    
    def update_team_progress(self, team: str, player_index: int, total_players: int):
        """Update progress for current team."""
        with self._lock:
            self._progress_data.update({
                "current_team": team,
                "current_team_progress": player_index,
                "current_team_total": total_players,
                "overall_progress": self._calculate_overall_progress()
            })
    
    def update_player_progress(self, player_name: str):
        """Update current player being processed."""
        with self._lock:
            self._progress_data["current_player"] = player_name
            self._progress_data["players_processed"] += 1
    
    def complete_team(self, team: str, player_count: int, avg_quality: float = 0.0):
        """Mark team as completed."""
        with self._lock:
            self._progress_data["completed_teams"].append({
                "team": team,
                "players": player_count,
                "quality": avg_quality,
                "completed_at": datetime.now().isoformat()
            })
            self._progress_data["teams_completed"] = len(self._progress_data["completed_teams"])
            self._progress_data["current_team"] = None
            self._progress_data["current_player"] = None
            self._progress_data["overall_progress"] = self._calculate_overall_progress()
            
            # Update average quality
            if self._progress_data["completed_teams"]:
                total_quality = sum(t["quality"] for t in self._progress_data["completed_teams"])
                self._progress_data["avg_quality"] = total_quality / len(self._progress_data["completed_teams"])
    
    def add_error(self, team: str, error: str):
        """Add error to tracking."""
        with self._lock:
            self._progress_data["error_count"] += 1
            self._progress_data["errors"].append({
                "team": team,
                "error": error,
                "timestamp": datetime.now().isoformat()
            })
    
    def finish_scraping(self, success: bool = True):
        """Mark scraping as completed."""
        with self._lock:
            self._progress_data["status"] = "completed" if success else "failed"
            self._progress_data["overall_progress"] = 100 if success else self._progress_data["overall_progress"]
    
    def _calculate_overall_progress(self) -> float:
        """Calculate overall progress percentage."""
        if self._progress_data["total_teams"] == 0:
            return 0
        
        # Progress from completed teams
        completed_progress = (self._progress_data["teams_completed"] / self._progress_data["total_teams"]) * 100
        
        # Progress from current team
        if self._progress_data["current_team_total"] > 0:
            current_team_progress = (self._progress_data["current_team_progress"] / self._progress_data["current_team_total"]) * (100 / self._progress_data["total_teams"])
            return min(completed_progress + current_team_progress, 99)  # Never show 100% until actually done
        
        return completed_progress
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress data."""
        with self._lock:
            # Calculate ETA
            if self._progress_data["start_time"] and self._progress_data["overall_progress"] > 0:
                start_time = datetime.fromisoformat(self._progress_data["start_time"])
                elapsed = (datetime.now() - start_time).total_seconds()
                if self._progress_data["overall_progress"] > 5:  # Only calculate ETA after 5% progress
                    eta = (elapsed / self._progress_data["overall_progress"]) * (100 - self._progress_data["overall_progress"])
                    self._progress_data["eta_seconds"] = max(0, int(eta))
            
            return self._progress_data.copy()

# Global progress tracker instance
progress_tracker = ScrapingProgressTracker()