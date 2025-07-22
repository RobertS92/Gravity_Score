"""
Enhanced Scraping System - Robust all-teams scraping with progress tracking
Ensures reliable completion of comprehensive NFL data collection
"""

import logging
import threading
import time
from typing import List, Dict, Any
from datetime import datetime
from real_data_collector import RealDataCollector
from progress_tracker import progress_tracker

logger = logging.getLogger(__name__)

class EnhancedScrapingSystem:
    """Robust scraping system with error handling and progress tracking."""
    
    def __init__(self):
        self.collector = RealDataCollector()
        self.is_running = False
        self.current_operation = None
        
    def scrape_all_teams_comprehensive(self, teams: List[str]) -> Dict[str, Any]:
        """
        Scrape all teams with comprehensive data collection.
        Designed to run to completion without stopping.
        """
        if self.is_running:
            raise RuntimeError("Scraping already in progress")
            
        self.is_running = True
        progress_tracker.start_scraping(teams, "comprehensive")
        
        all_players = []
        results = {}
        total_errors = 0
        
        try:
            logger.info(f"🚀 Starting comprehensive data collection for {len(teams)} teams")
            
            for team_index, team in enumerate(teams):
                try:
                    logger.info(f"📊 Processing team {team_index + 1}/{len(teams)}: {team}")
                    progress_tracker.update_team_progress(team, 0, 92)
                    
                    # Collect team data with progress updates
                    team_players = self._collect_team_with_progress(team, team_index + 1, len(teams))
                    
                    if team_players:
                        all_players.extend(team_players)
                        
                        # Calculate quality metrics
                        avg_quality = sum(p.get('data_quality_score', 0) for p in team_players) / len(team_players)
                        total_sources = sum(len(p.get('data_sources', [])) for p in team_players)
                        
                        results[team] = {
                            "players_found": len(team_players),
                            "avg_quality_score": round(avg_quality, 1),
                            "total_sources_used": total_sources,
                            "status": "success"
                        }
                        
                        progress_tracker.complete_team(team, len(team_players), avg_quality)
                        logger.info(f"✅ {team}: {len(team_players)} players (quality: {avg_quality:.1f})")
                    else:
                        results[team] = {
                            "players_found": 0,
                            "avg_quality_score": 0,
                            "total_sources_used": 0,
                            "status": "no_data"
                        }
                        progress_tracker.complete_team(team, 0, 0)
                        logger.warning(f"⚠️ {team}: No players found")
                        
                except Exception as e:
                    total_errors += 1
                    error_msg = str(e)
                    logger.error(f"❌ Error processing {team}: {error_msg}")
                    
                    progress_tracker.add_error(team, error_msg)
                    results[team] = {
                        "players_found": 0,
                        "avg_quality_score": 0,
                        "total_sources_used": 0,
                        "status": "error",
                        "error": error_msg
                    }
                    progress_tracker.complete_team(team, 0, 0)
                    
                    # Continue to next team even after error
                    continue
            
            # Mark completion
            progress_tracker.finish_scraping(success=True)
            
            # Calculate final metrics
            total_players = len(all_players)
            successful_teams = len([r for r in results.values() if r["status"] == "success"])
            avg_quality = sum(r.get("avg_quality_score", 0) for r in results.values()) / len(results) if results else 0
            
            logger.info(f"🎉 Scraping completed: {total_players} players from {successful_teams} teams")
            
            return {
                "status": "success",
                "total_players": total_players,
                "teams_processed": len(teams),
                "teams_successful": successful_teams,
                "teams_failed": len(teams) - successful_teams,
                "total_errors": total_errors,
                "results": results,
                "avg_quality_score": round(avg_quality, 1),
                "players_data": all_players,
                "message": f"Comprehensive scraping completed: {total_players} players from {successful_teams}/{len(teams)} teams"
            }
            
        except Exception as e:
            logger.error(f"💥 Critical error in scraping system: {e}")
            progress_tracker.finish_scraping(success=False)
            raise
        finally:
            self.is_running = False
    
    def _collect_team_with_progress(self, team: str, team_num: int, total_teams: int) -> List[Dict[str, Any]]:
        """Collect team data with detailed progress tracking."""
        try:
            logger.info(f"🏈 Collecting comprehensive data for {team} ({team_num}/{total_teams})")
            
            # Get team roster with progress updates
            players = self.collector.collect_team_roster(team, limit_players=0)
            
            if not players:
                logger.warning(f"No players found for {team}")
                return []
            
            # Update progress for each player processed
            for i, player in enumerate(players):
                progress_tracker.update_team_progress(team, i + 1, len(players))
                if 'name' in player:
                    progress_tracker.update_player_progress(player['name'])
                
                # Small delay to make progress visible
                time.sleep(0.1)
            
            logger.info(f"📈 Completed {team}: {len(players)} players with comprehensive data")
            return players
            
        except Exception as e:
            logger.error(f"Error collecting data for {team}: {e}")
            raise

# Global instance
enhanced_scraping_system = EnhancedScrapingSystem()