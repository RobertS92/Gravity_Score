"""
NBA Stats Collector
Collects NBA-specific statistics (points, rebounds, assists, etc.)
"""

import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Import Config and FirecrawlScraper from the main scrape file
# This assumes they're available in the same module or imported
try:
    from .scrape import Config, FirecrawlScraper, get_direct_api
except ImportError:
    try:
        from scrape import Config, FirecrawlScraper, get_direct_api
    except ImportError:
        # Fallback if running standalone
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from gravity.scrape import Config, FirecrawlScraper, get_direct_api


class NBAStatsCollector:
    """Collect NBA performance statistics and achievements"""
    
    def __init__(self, scraper: FirecrawlScraper):
        self.scraper = scraper
        
        # NBA position groups for stat interpretation
        self.position_groups = {
            'PG': ['assists', 'points', 'steals', 'three_point_percentage', 'free_throw_percentage'],
            'SG': ['points', 'three_point_percentage', 'field_goal_percentage', 'steals'],
            'SF': ['points', 'rebounds', 'field_goal_percentage', 'three_point_percentage'],
            'PF': ['rebounds', 'points', 'blocks', 'field_goal_percentage'],
            'C': ['rebounds', 'blocks', 'points', 'field_goal_percentage', 'double_doubles']
        }
    
    def collect_stats(self, player_name: str, position: str) -> Dict:
        """Collect comprehensive NBA statistics - current year, previous year, and career.
        
        Uses ESPN API ONLY - no Firecrawl scraping for stats.
        """
        
        stats = {}
        
        # =====================================================================
        # ESPN API ONLY (no Firecrawl for stats)
        # =====================================================================
        if Config.USE_DIRECT_APIS:
            logger.info(f"⚡ ESPN API: Collecting NBA stats for {player_name} ({position})...")
            try:
                api = get_direct_api()
                espn_data = api.get_espn_nba_full_stats(player_name)
                
                if espn_data and (espn_data.get("current_season_stats") or espn_data.get("career_stats")):
                    logger.info(f"✅ ESPN API: Got NBA stats for {player_name}")
                    
                    # Map ESPN data to our format
                    if espn_data.get("current_season_stats"):
                        for cat, cat_stats in espn_data["current_season_stats"].items():
                            if isinstance(cat_stats, dict):
                                for stat_name, stat_value in cat_stats.items():
                                    stats[f"current_season_{stat_name}"] = stat_value
                            else:
                                stats[f"current_season_{cat}"] = cat_stats
                    
                    if espn_data.get("career_stats"):
                        for cat, cat_stats in espn_data["career_stats"].items():
                            if isinstance(cat_stats, dict):
                                for stat_name, stat_value in cat_stats.items():
                                    stats[f"career_{stat_name}"] = stat_value
                            else:
                                stats[f"career_{cat}"] = cat_stats
                    
                    # Season by season
                    if espn_data.get("season_by_season"):
                        stats["historical_seasons"] = espn_data["season_by_season"]
                    
                    # Awards and achievements
                    if espn_data.get("awards"):
                        stats["awards"] = espn_data["awards"]
                    if espn_data.get("achievements"):
                        stats["achievements"] = espn_data["achievements"]
                    if espn_data.get("all_star_selections"):
                        stats["all_star_selections"] = espn_data["all_star_selections"]
                    if espn_data.get("all_nba_selections"):
                        stats["all_nba_selections"] = espn_data["all_nba_selections"]
                    if espn_data.get("championships"):
                        stats["championships"] = espn_data["championships"]
                    if espn_data.get("mvp_awards"):
                        stats["mvp_awards"] = espn_data["mvp_awards"]
                    
                    # Recent games for velocity
                    if espn_data.get("recent_games"):
                        stats["weekly_stats"] = espn_data["recent_games"]
                    
                    logger.info(f"✅ ESPN API: Complete NBA stats for {player_name}")
                else:
                    logger.warning(f"⚠️ ESPN API: No stats found for {player_name}")
                        
            except Exception as e:
                logger.warning(f"ESPN API NBA stats failed for {player_name}: {e}")
        
        # =====================================================================
        # NO FIRECRAWL FALLBACK - ESPN only for stats
        # =====================================================================
        if not stats:
            logger.warning(f"⚠️ No ESPN stats available for {player_name} - no fallback (Firecrawl disabled for stats)")
        
        # Organize stats by season
        stats = self._organize_stats_by_season(stats, position)
        
        # Count actual stat values
        stat_count = 0
        for key, value in stats.items():
            if value is not None and value != {} and value != []:
                if isinstance(value, (dict, list)):
                    stat_count += len(value) if value else 0
                else:
                    stat_count += 1
        
        logger.info(f"Stats collected for {player_name}: {stat_count} data points (from {len(stats)} categories)")
        if stat_count == 0:
            logger.warning(f"⚠️  No stats collected for {player_name}! Check scraping sources.")
        
        return stats
    
    def _get_br_stats(self, player_name: str, position: str) -> Dict:
        """Get comprehensive stats from Basketball Reference - career, previous year, current year"""
        data = {}
        
        # Try multiple BR URL patterns
        br_urls = []
        
        # Method 1: Generate player code (first 5 letters of last name + first 2 of first)
        parts = player_name.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            first_name = parts[0]
            code = (last_name[:5] + first_name[:2]).lower() + "01"
            br_urls.append(f"https://www.basketball-reference.com/players/{code[0]}/{code}.html")
            
            # Also try with just first letter of first name
            code2 = (last_name[:5] + first_name[0]).lower() + "01"
            if code2 != code:
                br_urls.append(f"https://www.basketball-reference.com/players/{code2[0]}/{code2}.html")
        
        # Method 2: Try search page
        search_url = f"https://www.basketball-reference.com/search/search.fcgi?search={quote(player_name)}"
        br_urls.append(search_url)
        
        for url in br_urls:
            try:
                # Try LLM extraction first (more reliable)
                if Config.USE_LLM_PARSING:
                    logger.info(f"Attempting LLM extraction from BR for {player_name}")
                    llm_data = self.scraper.scrape_with_llm_parsing(
                        url,
                        extraction_schema=self._get_br_extraction_schema(position)
                    )
                    if llm_data:
                        # Map LLM extracted data to our format
                        for key, value in llm_data.items():
                            if value is not None and value != {} and value != []:
                                if key == 'historical_seasons' and isinstance(value, list):
                                    data['historical_seasons'] = value
                                    logger.info(f"LLM extracted {len(value)} historical seasons")
                                elif key.startswith('career_'):
                                    data[key] = value
                                elif key.startswith('current_season_'):
                                    data[key] = value
                                elif key.startswith('last_season_'):
                                    data[key] = value
                        
                        if any(v is not None and v != {} and v != [] for v in data.values()):
                            logger.info(f"LLM extraction successful for {player_name}")
                            logger.info(f"  Career stats: {len([k for k in data.keys() if k.startswith('career_')])} fields")
                            logger.info(f"  Current season: {len([k for k in data.keys() if k.startswith('current_season_')])} fields")
                            logger.info(f"  Last season: {len([k for k in data.keys() if k.startswith('last_season_')])} fields")
                            if 'historical_seasons' in data and data['historical_seasons']:
                                logger.info(f"  Historical seasons: {len(data['historical_seasons'])} seasons")
                            break
                
                # Fallback to regex extraction
                result = self.scraper.scrape(url)
                
                if result and 'markdown' in result:
                    text = result['markdown']
                    current_year = datetime.now().year
                    previous_year = current_year - 1
                    
                    # Get position-specific stat patterns
                    position_stats = self._get_position_stat_patterns(position)
                    
                    # Extract career totals
                    career_data = self._extract_career_stats_enhanced(text, position, position_stats)
                    data.update(career_data)
                    
                    # Extract previous year stats (last complete season)
                    prev_year_stats = self._extract_season_stats(text, str(previous_year), position, position_stats)
                    for key, value in prev_year_stats.items():
                        if value is not None:
                            data[f'last_season_{key}'] = value
                    
                    # Extract current year stats
                    current_year_stats = self._extract_season_stats(text, str(current_year), position, position_stats)
                    for key, value in current_year_stats.items():
                        if value is not None:
                            data[f'current_season_{key}'] = value
                    
                    # Extract all historical seasons
                    historical_seasons = self._extract_all_seasons(text, position, position_stats)
                    if historical_seasons:
                        data['historical_seasons'] = historical_seasons
                    
                    # If we got good data, break
                    if career_data or prev_year_stats or current_year_stats:
                        break
                
                time.sleep(Config.REQUEST_DELAY)
            except Exception as e:
                logger.debug(f"BR scrape failed for {url[:50]}: {e}")
                continue
        
        return data
    
    def _extract_career_stats_enhanced(self, text: str, position: str, position_stats: Dict) -> Dict:
        """Enhanced career stats extraction with multiple patterns for NBA"""
        data = {}
        
        # Look for career summary section
        career_section_patterns = [
            r'Career[^\n]*(.*?)(?:\n\n[A-Z]|\n\d{4}|$)',
            r'Career Totals[^\n]*(.*?)(?:\n\n[A-Z]|\n\d{4}|$)',
            r'Career Statistics[^\n]*(.*?)(?:\n\n[A-Z]|\n\d{4}|$)'
        ]
        
        career_text = text
        for pattern in career_section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                career_text = match.group(1)
                break
        
        # Extract NBA career stats
        # Points Per Game (PPG)
        data['career_points_per_game'] = self._extract_number_multi(career_text, [
            r'PTS[:\s]+([\d.]+)', r'Points[:\s]+([\d.]+)', r'PPG[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+points.*?per.*?game', r'(\d+\.\d+)[,\s]+ppg'
        ])
        
        # Total Points
        data['career_points'] = self._extract_number_multi(career_text, [
            r'Total Points[:\s]+([\d,]+)', r'PTS[:\s]+([\d,]+)', r'Points[:\s]+([\d,]+)',
            r'(\d+)[,\s]+points'
        ])
        
        # Rebounds Per Game (RPG)
        data['career_rebounds_per_game'] = self._extract_number_multi(career_text, [
            r'TRB[:\s]+([\d.]+)', r'Rebounds[:\s]+([\d.]+)', r'RPG[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+rebounds.*?per.*?game', r'(\d+\.\d+)[,\s]+rpg'
        ])
        
        # Total Rebounds
        data['career_rebounds'] = self._extract_number_multi(career_text, [
            r'Total Rebounds[:\s]+([\d,]+)', r'TRB[:\s]+([\d,]+)', r'Rebounds[:\s]+([\d,]+)',
            r'(\d+)[,\s]+rebounds'
        ])
        
        # Assists Per Game (APG)
        data['career_assists_per_game'] = self._extract_number_multi(career_text, [
            r'AST[:\s]+([\d.]+)', r'Assists[:\s]+([\d.]+)', r'APG[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+assists.*?per.*?game', r'(\d+\.\d+)[,\s]+apg'
        ])
        
        # Total Assists
        data['career_assists'] = self._extract_number_multi(career_text, [
            r'Total Assists[:\s]+([\d,]+)', r'AST[:\s]+([\d,]+)', r'Assists[:\s]+([\d,]+)',
            r'(\d+)[,\s]+assists'
        ])
        
        # Steals Per Game (SPG)
        data['career_steals_per_game'] = self._extract_number_multi(career_text, [
            r'STL[:\s]+([\d.]+)', r'Steals[:\s]+([\d.]+)', r'SPG[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+steals.*?per.*?game', r'(\d+\.\d+)[,\s]+spg'
        ])
        
        # Total Steals
        data['career_steals'] = self._extract_number_multi(career_text, [
            r'Total Steals[:\s]+([\d,]+)', r'STL[:\s]+([\d,]+)', r'Steals[:\s]+([\d,]+)',
            r'(\d+)[,\s]+steals'
        ])
        
        # Blocks Per Game (BPG)
        data['career_blocks_per_game'] = self._extract_number_multi(career_text, [
            r'BLK[:\s]+([\d.]+)', r'Blocks[:\s]+([\d.]+)', r'BPG[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+blocks.*?per.*?game', r'(\d+\.\d+)[,\s]+bpg'
        ])
        
        # Total Blocks
        data['career_blocks'] = self._extract_number_multi(career_text, [
            r'Total Blocks[:\s]+([\d,]+)', r'BLK[:\s]+([\d,]+)', r'Blocks[:\s]+([\d,]+)',
            r'(\d+)[,\s]+blocks'
        ])
        
        # Field Goal Percentage
        data['career_field_goal_percentage'] = self._extract_number_multi(career_text, [
            r'FG%[:\s]+([\d.]+)', r'Field Goal%[:\s]+([\d.]+)', r'FG Percentage[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+field.*?goal.*?percentage'
        ])
        
        # Three Point Percentage
        data['career_three_point_percentage'] = self._extract_number_multi(career_text, [
            r'3P%[:\s]+([\d.]+)', r'3PT%[:\s]+([\d.]+)', r'Three Point%[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+three.*?point.*?percentage'
        ])
        
        # Free Throw Percentage
        data['career_free_throw_percentage'] = self._extract_number_multi(career_text, [
            r'FT%[:\s]+([\d.]+)', r'Free Throw%[:\s]+([\d.]+)', r'FT Percentage[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+free.*?throw.*?percentage'
        ])
        
        # Minutes Per Game (MPG)
        data['career_minutes_per_game'] = self._extract_number_multi(career_text, [
            r'MP[:\s]+([\d.]+)', r'Minutes[:\s]+([\d.]+)', r'MPG[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+minutes.*?per.*?game', r'(\d+\.\d+)[,\s]+mpg'
        ])
        
        # Turnovers Per Game
        data['career_turnovers_per_game'] = self._extract_number_multi(career_text, [
            r'TOV[:\s]+([\d.]+)', r'Turnovers[:\s]+([\d.]+)', r'TOVPG[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+turnovers.*?per.*?game'
        ])
        
        # Games Played
        data['career_games'] = self._extract_number_multi(career_text, [
            r'G[:\s]+(\d+)', r'Games[:\s]+(\d+)', r'GP[:\s]+(\d+)',
            r'(\d+)[,\s]+games'
        ])
        
        # Games Started
        data['career_games_started'] = self._extract_number_multi(career_text, [
            r'GS[:\s]+(\d+)', r'Games Started[:\s]+(\d+)', r'Starts[:\s]+(\d+)'
        ])
        
        # Player Efficiency Rating (PER)
        data['career_per'] = self._extract_number_multi(career_text, [
            r'PER[:\s]+([\d.]+)', r'Player Efficiency Rating[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+per'
        ])
        
        # True Shooting Percentage
        data['career_true_shooting_percentage'] = self._extract_number_multi(career_text, [
            r'TS%[:\s]+([\d.]+)', r'True Shooting%[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+true.*?shooting.*?percentage'
        ])
        
        # Usage Rate
        data['career_usage_rate'] = self._extract_number_multi(career_text, [
            r'USG%[:\s]+([\d.]+)', r'Usage Rate[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+usage.*?rate'
        ])
        
        # Win Shares
        data['career_win_shares'] = self._extract_number_multi(career_text, [
            r'WS[:\s]+([\d.]+)', r'Win Shares[:\s]+([\d.]+)',
            r'(\d+\.\d+)[,\s]+win.*?shares'
        ])
        
        # Double Doubles
        data['career_double_doubles'] = self._extract_number_multi(career_text, [
            r'Double Doubles[:\s]+(\d+)', r'DD[:\s]+(\d+)',
            r'(\d+)[,\s]+double.*?doubles'
        ])
        
        # Triple Doubles
        data['career_triple_doubles'] = self._extract_number_multi(career_text, [
            r'Triple Doubles[:\s]+(\d+)', r'TD[:\s]+(\d+)',
            r'(\d+)[,\s]+triple.*?doubles'
        ])
        
        # Map to expected keys for consistency
        data['career_points'] = data.get('career_points') or (data.get('career_points_per_game') and int(data.get('career_points_per_game') * (data.get('career_games') or 1)))
        data['career_rebounds'] = data.get('career_rebounds') or (data.get('career_rebounds_per_game') and int(data.get('career_rebounds_per_game') * (data.get('career_games') or 1)))
        data['career_assists'] = data.get('career_assists') or (data.get('career_assists_per_game') and int(data.get('career_assists_per_game') * (data.get('career_games') or 1)))
        
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        return data
    
    def _extract_number_multi(self, text: str, patterns: List[str]) -> Optional[float]:
        """Try multiple patterns to extract a number (float)"""
        for pattern in patterns:
            value = self._extract_number(text, pattern)
            if value is not None:
                return value
        return None
    
    def _extract_number(self, text: str, pattern: str) -> Optional[float]:
        """Extract a number from text using regex pattern"""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except (ValueError, IndexError):
                pass
        return None
    
    def _get_position_stat_patterns(self, position: str) -> Dict:
        """Get stat patterns relevant to NBA position"""
        patterns = {
            'PG': {
                'career': {
                    'assists': r'AST[:\s]+([\d.]+)',
                    'points': r'PTS[:\s]+([\d.]+)',
                    'steals': r'STL[:\s]+([\d.]+)',
                    'three_point_percentage': r'3P%[:\s]+([\d.]+)',
                    'free_throw_percentage': r'FT%[:\s]+([\d.]+)'
                },
                'season': {
                    'assists': r'(\d{4})[^\n]*AST[:\s]+([\d.]+)',
                    'points': r'(\d{4})[^\n]*PTS[:\s]+([\d.]+)',
                    'steals': r'(\d{4})[^\n]*STL[:\s]+([\d.]+)'
                }
            },
            'SG': {
                'career': {
                    'points': r'PTS[:\s]+([\d.]+)',
                    'three_point_percentage': r'3P%[:\s]+([\d.]+)',
                    'field_goal_percentage': r'FG%[:\s]+([\d.]+)',
                    'steals': r'STL[:\s]+([\d.]+)'
                },
                'season': {
                    'points': r'(\d{4})[^\n]*PTS[:\s]+([\d.]+)',
                    'three_point_percentage': r'(\d{4})[^\n]*3P%[:\s]+([\d.]+)'
                }
            },
            'SF': {
                'career': {
                    'points': r'PTS[:\s]+([\d.]+)',
                    'rebounds': r'TRB[:\s]+([\d.]+)',
                    'field_goal_percentage': r'FG%[:\s]+([\d.]+)',
                    'three_point_percentage': r'3P%[:\s]+([\d.]+)'
                },
                'season': {
                    'points': r'(\d{4})[^\n]*PTS[:\s]+([\d.]+)',
                    'rebounds': r'(\d{4})[^\n]*TRB[:\s]+([\d.]+)'
                }
            },
            'PF': {
                'career': {
                    'rebounds': r'TRB[:\s]+([\d.]+)',
                    'points': r'PTS[:\s]+([\d.]+)',
                    'blocks': r'BLK[:\s]+([\d.]+)',
                    'field_goal_percentage': r'FG%[:\s]+([\d.]+)'
                },
                'season': {
                    'rebounds': r'(\d{4})[^\n]*TRB[:\s]+([\d.]+)',
                    'points': r'(\d{4})[^\n]*PTS[:\s]+([\d.]+)',
                    'blocks': r'(\d{4})[^\n]*BLK[:\s]+([\d.]+)'
                }
            },
            'C': {
                'career': {
                    'rebounds': r'TRB[:\s]+([\d.]+)',
                    'blocks': r'BLK[:\s]+([\d.]+)',
                    'points': r'PTS[:\s]+([\d.]+)',
                    'field_goal_percentage': r'FG%[:\s]+([\d.]+)',
                    'double_doubles': r'Double Doubles[:\s]+(\d+)'
                },
                'season': {
                    'rebounds': r'(\d{4})[^\n]*TRB[:\s]+([\d.]+)',
                    'blocks': r'(\d{4})[^\n]*BLK[:\s]+([\d.]+)',
                    'points': r'(\d{4})[^\n]*PTS[:\s]+([\d.]+)'
                }
            }
        }
        
        # Default to common stats if position not found
        return patterns.get(position, {
            'career': {
                'games': r'G[:\s]+(\d+)',
                'points': r'PTS[:\s]+([\d.]+)',
                'rebounds': r'TRB[:\s]+([\d.]+)'
            },
            'season': {
                'games': r'(\d{4})[^\n]*G[:\s]+(\d+)',
                'points': r'(\d{4})[^\n]*PTS[:\s]+([\d.]+)'
            }
        })
    
    def _extract_season_stats(self, text: str, year: str, position: str, patterns: Dict) -> Dict:
        """Extract stats for a specific season - enhanced for Basketball Reference table format"""
        stats = {}
        
        # Basketball Reference uses table format - look for year in table rows
        # Pattern: Year | Team | G | GS | MP | FG | FGA | FG% | 3P | 3PA | 3P% | FT | FTA | FT% | ORB | DRB | TRB | AST | STL | BLK | TOV | PF | PTS
        # Try to find the row with this year
        year_patterns = [
            # Table row format: year followed by stats
            rf'{year}[-\s]+[A-Z]{{3}}[^\n]*\n[^\n]*',  # Year, team, then stats row
            rf'{year}\s+\d+[^\n]*',  # Year followed by numbers (games, etc.)
            rf'{year}[^\n]*\n(.*?)(?=\d{{4}}|$)',  # Year then next section
            rf'{year}\s+(.*?)(?=\d{{4}}|$)',  # Year with space then stats
            rf'Season\s+{year}[^\n]*\n(.*?)(?=\d{{4}}|$)',  # "Season 2024" format
            rf'{year}-\d{{2}}[^\n]*\n(.*?)(?=\d{{4}}|$)',  # Year range like 2024-25
        ]
        
        section_text = ""
        for pattern in year_patterns:
            year_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
            if year_match:
                if len(year_match.groups()) > 0:
                    section_text = year_match.group(1)
                else:
                    # If no group, use the full match
                    section_text = year_match.group(0)
                break
        
        # If still no section, try to find table row with year
        if not section_text:
            # Look for table row: year followed by pipe-separated or space-separated stats
            table_row = re.search(rf'{year}[-\s]+[^\n]{{0,200}}', text, re.IGNORECASE)
            if table_row:
                section_text = table_row.group(0)
        
        # If still nothing, try broader search
        if not section_text:
            year_context = re.search(rf'{year}[^\n]{{0,500}}', text, re.IGNORECASE)
            if year_context:
                section_text = year_context.group(0)
        
        if section_text:
            # Extract common NBA stats - comprehensive extraction with multiple patterns
            # Handle both table format (pipe/space separated) and text format
            # Basketball Reference table order: Year | Team | G | GS | MP | FG | FGA | FG% | 3P | 3PA | 3P% | FT | FTA | FT% | ORB | DRB | TRB | AST | STL | BLK | TOV | PF | PTS
            for stat_key, patterns_list in [
                # Points Per Game (PTS column in table)
                ('points_per_game', [
                    r'PTS[:\s]+([\d.]+)', r'Points[:\s]+([\d.]+)', r'PPG[:\s]+([\d.]+)',
                    r'(\d+\.\d+)\s*PTS', r'(\d+\.\d+)\s*PPG', r'Points.*?([\d.]+)',
                    # Table format: look for PTS column (usually last or near end)
                    r'\|[^\|]*([\d.]+)\s*$',  # Last number in pipe-separated row
                    r'\s+([\d.]+)\s*$',  # Last number in space-separated row
                ]),
                # Rebounds Per Game (TRB column)
                ('rebounds_per_game', [
                    r'TRB[:\s]+([\d.]+)', r'Rebounds[:\s]+([\d.]+)', r'RPG[:\s]+([\d.]+)',
                    r'(\d+\.\d+)\s*TRB', r'(\d+\.\d+)\s*RPG', r'Rebounds.*?([\d.]+)',
                ]),
                # Assists Per Game (AST column)
                ('assists_per_game', [
                    r'AST[:\s]+([\d.]+)', r'Assists[:\s]+([\d.]+)', r'APG[:\s]+([\d.]+)',
                    r'(\d+\.\d+)\s*AST', r'(\d+\.\d+)\s*APG', r'Assists.*?([\d.]+)',
                ]),
                # Steals Per Game (STL column)
                ('steals_per_game', [
                    r'STL[:\s]+([\d.]+)', r'Steals[:\s]+([\d.]+)', r'SPG[:\s]+([\d.]+)',
                    r'(\d+\.\d+)\s*STL',
                ]),
                # Blocks Per Game (BLK column)
                ('blocks_per_game', [
                    r'BLK[:\s]+([\d.]+)', r'Blocks[:\s]+([\d.]+)', r'BPG[:\s]+([\d.]+)',
                    r'(\d+\.\d+)\s*BLK',
                ]),
                # Field Goal Percentage (FG% column)
                ('field_goal_percentage', [
                    r'FG%[:\s]+([\d.]+)', r'Field Goal%[:\s]+([\d.]+)', r'FG[:\s]+([\d.]+)%',
                    r'(\d+\.\d+)%?\s*FG', r'FG%[:\s]+([\d.]+)',
                ]),
                # Three Point Percentage (3P% column)
                ('three_point_percentage', [
                    r'3P%[:\s]+([\d.]+)', r'3PT%[:\s]+([\d.]+)', r'3P[:\s]+([\d.]+)%',
                    r'(\d+\.\d+)%?\s*3P',
                ]),
                # Free Throw Percentage (FT% column)
                ('free_throw_percentage', [
                    r'FT%[:\s]+([\d.]+)', r'Free Throw%[:\s]+([\d.]+)', r'FT[:\s]+([\d.]+)%',
                    r'(\d+\.\d+)%?\s*FT',
                ]),
                # Minutes Per Game (MP column)
                ('minutes_per_game', [
                    r'MP[:\s]+([\d.]+)', r'Minutes[:\s]+([\d.]+)', r'MPG[:\s]+([\d.]+)',
                    r'(\d+\.\d+)\s*MP',
                ]),
                # Turnovers Per Game (TOV column)
                ('turnovers_per_game', [
                    r'TOV[:\s]+([\d.]+)', r'Turnovers[:\s]+([\d.]+)', r'TOVPG[:\s]+([\d.]+)',
                    r'(\d+\.\d+)\s*TOV',
                ]),
                # Games (G column)
                ('games', [
                    r'G[:\s]+(\d+)', r'Games[:\s]+(\d+)', r'GP[:\s]+(\d+)',
                    r'\b(\d+)\s*G\b', r'^\s*(\d+)\s+',  # First number in row (often games)
                ]),
                # Games Started (GS column)
                ('games_started', [
                    r'GS[:\s]+(\d+)', r'Games Started[:\s]+(\d+)', r'Starts[:\s]+(\d+)',
                ]),
                # Totals (not per game)
                ('points', [
                    r'(\d+)\s*points', r'PTS[:\s]+(\d+)',
                ]),
                ('rebounds', [
                    r'(\d+)\s*rebounds', r'TRB[:\s]+(\d+)',
                ]),
                ('assists', [
                    r'(\d+)\s*assists', r'AST[:\s]+(\d+)',
                ]),
            ]:
                if stat_key not in stats:
                    for pattern in patterns_list:
                        match = re.search(pattern, section_text, re.IGNORECASE)
                        if match:
                            try:
                                stats[stat_key] = float(match.group(1).replace(',', ''))
                                break
                            except (ValueError, IndexError):
                                pass
        
        return stats
    
    def _extract_all_seasons(self, text: str, position: str, patterns: Dict) -> List[Dict]:
        """Extract stats for all historical seasons - enhanced to match NFL approach"""
        seasons = []
        
        # Find all year entries in stats table - try multiple patterns
        year_patterns = [
            r'(\d{4})\s+',  # Basic year pattern
            r'(\d{4})-\d{2}',  # Year range like 2024-25
            r'(\d{4})\s+[A-Z]',  # Year followed by team abbreviation
            r'Season\s+(\d{4})',  # "Season 2024"
            r'(\d{4})\s+NBA',  # "2024 NBA"
        ]
        
        found_years = set()
        for pattern in year_patterns:
            year_matches = re.finditer(pattern, text)
            for match in year_matches:
                year = match.group(1)
                if year.isdigit() and 2000 <= int(year) <= datetime.now().year:
                    found_years.add(int(year))
        
        # Extract stats for each unique year found
        for year in sorted(found_years, reverse=True):  # Most recent first
            season_stats = self._extract_season_stats(text, str(year), position, patterns)
            if season_stats:
                season_stats['year'] = year
                seasons.append(season_stats)
            else:
                # Even if no stats extracted, add the year entry (might have stats in different format)
                # Try to find any stats near this year
                year_section = re.search(rf'{year}[^\n]*(.*?)(?=\d{{4}}|$)', text, re.DOTALL)
                if year_section:
                    # Try basic extraction from the section
                    basic_stats = {}
                    for stat_key, patterns_list in [
                        ('points_per_game', [r'PTS[:\s]+([\d.]+)', r'Points[:\s]+([\d.]+)', r'PPG[:\s]+([\d.]+)']),
                        ('rebounds_per_game', [r'TRB[:\s]+([\d.]+)', r'Rebounds[:\s]+([\d.]+)', r'RPG[:\s]+([\d.]+)']),
                        ('assists_per_game', [r'AST[:\s]+([\d.]+)', r'Assists[:\s]+([\d.]+)', r'APG[:\s]+([\d.]+)']),
                        ('games', [r'G[:\s]+(\d+)', r'Games[:\s]+(\d+)']),
                    ]:
                        for pattern in patterns_list:
                            match = re.search(pattern, year_section.group(0), re.IGNORECASE)
                            if match:
                                try:
                                    basic_stats[stat_key] = float(match.group(1).replace(',', ''))
                                    break
                                except (ValueError, IndexError):
                                    pass
                    if basic_stats:
                        basic_stats['year'] = year
                        seasons.append(basic_stats)
        
        logger.info(f"Extracted {len(seasons)} historical seasons")
        return seasons
    
    def _organize_stats_by_season(self, stats: Dict, position: str) -> Dict:
        """Organize stats into current_season_stats, last_season_stats, career_stats, and year-by-year breakdowns"""
        organized = {
            'career_stats': {},
            'current_season_stats': {},
            'last_season_stats': {},
            'career_stats_by_year': {},
            'historical_seasons': []
        }
        
        current_year = datetime.now().year
        previous_year = current_year - 1
        
        # Separate stats by prefix
        for key, value in stats.items():
            if value is None or value == {} or value == []:
                continue
                
            if key.startswith('career_'):
                stat_key = key.replace('career_', '')
                organized['career_stats'][stat_key] = value
            elif key.startswith('current_season_'):
                stat_key = key.replace('current_season_', '')
                if stat_key.startswith(f'{current_year}_'):
                    stat_key = stat_key.replace(f'{current_year}_', '')
                organized['current_season_stats'][stat_key] = value
            elif key.startswith('last_season_'):
                stat_key = key.replace('last_season_', '')
                if stat_key.startswith(f'{previous_year}_'):
                    stat_key = stat_key.replace(f'{previous_year}_', '')
                organized['last_season_stats'][stat_key] = value
            elif key == 'historical_seasons' and isinstance(value, list):
                organized['historical_seasons'] = value
                # Also populate career_stats_by_year
                for season in value:
                    if 'year' in season:
                        organized['career_stats_by_year'][season['year']] = {
                            k: v for k, v in season.items() if k != 'year'
                        }
            else:
                organized[key] = value
        
        return organized
    
    def _get_espn_stats(self, player_name: str, position: str) -> Dict:
        """Get current season stats from ESPN"""
        data = {}
        
        espn_urls = [
            f"https://www.espn.com/nba/players?search={quote(player_name)}",
            f"https://www.espn.com/nba/player/_/name/{player_name.lower().replace(' ', '-')}",
            f"https://www.espn.com/search/results?q={quote(player_name + ' NBA')}"
        ]
        
        for search_url in espn_urls:
            try:
                result = self.scraper.scrape(search_url)
                
                if result and 'links' in result:
                    for link in result['links']:
                        if '/player/_/id/' in link or '/nba/player/' in link:
                            player_url = link if link.startswith('http') else f"https://www.espn.com{link}"
                            
                            if Config.USE_LLM_PARSING:
                                llm_data = self.scraper.scrape_with_llm_parsing(
                                    player_url,
                                    extraction_schema=self._get_espn_extraction_schema(position)
                                )
                                if llm_data:
                                    for key, value in llm_data.items():
                                        if value is not None:
                                            data[f'current_season_{key}'] = value
                            
                            player_result = self.scraper.scrape(player_url)
                            
                            if player_result and 'markdown' in player_result:
                                text = player_result['markdown']
                                current_year = datetime.now().year
                                
                                # Extract NBA stats
                                data['current_season_points_per_game'] = self._extract_number_multi(text, [
                                    rf'{current_year}[^\n]*PTS[:\s]+([\d.]+)',
                                    r'PTS[:\s]+([\d.]+)', r'Points[:\s]+([\d.]+)'
                                ])
                                data['current_season_rebounds_per_game'] = self._extract_number_multi(text, [
                                    rf'{current_year}[^\n]*TRB[:\s]+([\d.]+)',
                                    r'TRB[:\s]+([\d.]+)', r'Rebounds[:\s]+([\d.]+)'
                                ])
                                data['current_season_assists_per_game'] = self._extract_number_multi(text, [
                                    rf'{current_year}[^\n]*AST[:\s]+([\d.]+)',
                                    r'AST[:\s]+([\d.]+)', r'Assists[:\s]+([\d.]+)'
                                ])
                                
                            break
                
                time.sleep(Config.REQUEST_DELAY)
            except Exception as e:
                logger.debug(f"ESPN scrape failed for {search_url[:50]}: {e}")
                continue
        
        return data
    
    def _get_nba_stats(self, player_name: str) -> Dict:
        """Get basic stats from NBA.com"""
        data = {}
        
        nba_urls = [
            f"https://www.nba.com/search?q={quote(player_name)}",
            f"https://www.nba.com/players/{player_name.lower().replace(' ', '/')}"
        ]
        
        for url in nba_urls:
            try:
                result = self.scraper.scrape(url)
                if result and 'markdown' in result:
                    text = result['markdown']
                    # Basic extraction from NBA.com
                    # This would need to be customized based on NBA.com's actual structure
                    pass
                
                time.sleep(Config.REQUEST_DELAY)
            except Exception as e:
                logger.debug(f"NBA.com scrape failed for {url[:50]}: {e}")
                continue
        
        return data
    
    def _get_wikipedia_achievements(self, player_name: str) -> Dict:
        """Get awards and achievements from Wikipedia"""
        data = {
            'awards': [],
            'all_star_selections': 0,
            'all_nba_selections': 0,
            'championships': 0,
            'mvp_awards': 0,
            'all_star_selections_by_year': {},
            'all_nba_selections_by_year': {},
            'championships_by_year': {}
        }
        
        wiki_url = f"https://en.wikipedia.org/wiki/{quote(player_name.replace(' ', '_'))}"
        
        try:
            result = self.scraper.scrape(wiki_url)
            if result and 'markdown' in result:
                text = result['markdown']
                
                # Extract NBA-specific awards
                # All-Star selections
                all_star_matches = re.finditer(r'(\d{4})\s+.*?All-Star', text, re.IGNORECASE)
                for match in all_star_matches:
                    year = int(match.group(1))
                    if 2000 <= year <= datetime.now().year:
                        data['all_star_selections_by_year'][year] = True
                        data['all_star_selections'] = len(data['all_star_selections_by_year'])
                
                # All-NBA selections
                all_nba_matches = re.finditer(r'(\d{4})\s+.*?All-NBA', text, re.IGNORECASE)
                for match in all_nba_matches:
                    year = int(match.group(1))
                    if 2000 <= year <= datetime.now().year:
                        data['all_nba_selections_by_year'][year] = True
                        data['all_nba_selections'] = len(data['all_nba_selections_by_year'])
                
                # Championships
                champ_matches = re.finditer(r'(\d{4})\s+.*?NBA.*?Champion', text, re.IGNORECASE)
                for match in champ_matches:
                    year = int(match.group(1))
                    if 2000 <= year <= datetime.now().year:
                        data['championships_by_year'][year] = True
                        data['championships'] = len(data['championships_by_year'])
                
                # MVP awards - extract unique years only to avoid duplicates
                mvp_years = set()
                mvp_matches = re.finditer(r'(\d{4})\s+.*?NBA.*?MVP', text, re.IGNORECASE)
                for match in mvp_matches:
                    year = int(match.group(1))
                    if 2000 <= year <= datetime.now().year:
                        mvp_years.add(year)
                
                # Add unique MVP awards only
                data['mvp_awards'] = len(mvp_years)
                for year in sorted(mvp_years, reverse=True):
                    data['awards'].append(f"{year} NBA MVP")
                
                # Extract other NBA awards with years
                nba_awards = [
                    ('Defensive Player of the Year', r'(\d{4})\s+.*?Defensive Player of the Year', 'DPOY'),
                    ('Rookie of the Year', r'(\d{4})\s+.*?Rookie of the Year', 'ROY'),
                    ('Sixth Man of the Year', r'(\d{4})\s+.*?Sixth Man of the Year', '6MOY'),
                    ('Most Improved Player', r'(\d{4})\s+.*?Most Improved Player', 'MIP'),
                    ('Finals MVP', r'(\d{4})\s+.*?Finals MVP', 'FMVP'),
                    ('All-Star Game MVP', r'(\d{4})\s+.*?All-Star.*?MVP', 'ASG MVP'),
                    ('All-Defensive Team', r'(\d{4})\s+.*?All-Defensive', 'All-Defensive'),
                    ('All-Rookie Team', r'(\d{4})\s+.*?All-Rookie', 'All-Rookie'),
                    ('Scoring Champion', r'(\d{4})\s+.*?Scoring.*?Champion', 'Scoring Title'),
                    ('Assists Leader', r'(\d{4})\s+.*?Assists.*?Leader', 'Assists Leader'),
                    ('Rebounds Leader', r'(\d{4})\s+.*?Rebounds.*?Leader', 'Rebounds Leader'),
                ]
                
                for award_name, pattern, short_name in nba_awards:
                    award_years = set()
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        year = int(match.group(1))
                        if 2000 <= year <= datetime.now().year:
                            award_years.add(year)
                    
                    # Add awards with years
                    for year in sorted(award_years, reverse=True):
                        data['awards'].append(f"{year} NBA {award_name}")
        
        except Exception as e:
            logger.debug(f"Wikipedia scrape failed for {player_name}: {e}")
        
        return data
    
    def _get_br_extraction_schema(self, position: str) -> Dict:
        """Get LLM extraction schema for Basketball Reference - comprehensive stats extraction"""
        current_year = datetime.now().year
        previous_year = current_year - 1
        
        return {
            "type": "object",
            "properties": {
                # Career stats
                "career_points_per_game": {"type": "number"},
                "career_rebounds_per_game": {"type": "number"},
                "career_assists_per_game": {"type": "number"},
                "career_steals_per_game": {"type": "number"},
                "career_blocks_per_game": {"type": "number"},
                "career_field_goal_percentage": {"type": "number"},
                "career_three_point_percentage": {"type": "number"},
                "career_free_throw_percentage": {"type": "number"},
                "career_games": {"type": "integer"},
                "career_points": {"type": "number"},
                "career_rebounds": {"type": "number"},
                "career_assists": {"type": "number"},
                # Current season stats
                "current_season_points_per_game": {"type": "number"},
                "current_season_rebounds_per_game": {"type": "number"},
                "current_season_assists_per_game": {"type": "number"},
                "current_season_steals_per_game": {"type": "number"},
                "current_season_blocks_per_game": {"type": "number"},
                "current_season_field_goal_percentage": {"type": "number"},
                "current_season_three_point_percentage": {"type": "number"},
                "current_season_free_throw_percentage": {"type": "number"},
                "current_season_games": {"type": "integer"},
                "current_season_minutes_per_game": {"type": "number"},
                # Last season stats
                "last_season_points_per_game": {"type": "number"},
                "last_season_rebounds_per_game": {"type": "number"},
                "last_season_assists_per_game": {"type": "number"},
                "last_season_steals_per_game": {"type": "number"},
                "last_season_blocks_per_game": {"type": "number"},
                "last_season_field_goal_percentage": {"type": "number"},
                "last_season_three_point_percentage": {"type": "number"},
                "last_season_free_throw_percentage": {"type": "number"},
                "last_season_games": {"type": "integer"},
                "last_season_minutes_per_game": {"type": "number"},
                # Historical seasons - comprehensive stats for each year
                "historical_seasons": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "year": {"type": "integer"},
                            "points_per_game": {"type": "number"},
                            "rebounds_per_game": {"type": "number"},
                            "assists_per_game": {"type": "number"},
                            "steals_per_game": {"type": "number"},
                            "blocks_per_game": {"type": "number"},
                            "field_goal_percentage": {"type": "number"},
                            "three_point_percentage": {"type": "number"},
                            "free_throw_percentage": {"type": "number"},
                            "games": {"type": "integer"},
                            "games_started": {"type": "integer"},
                            "minutes_per_game": {"type": "number"},
                            "turnovers_per_game": {"type": "number"},
                            "points": {"type": "number"},
                            "rebounds": {"type": "number"},
                            "assists": {"type": "number"}
                        }
                    }
                }
            }
        }
    
    def _get_espn_extraction_schema(self, position: str) -> Dict:
        """Get LLM extraction schema for ESPN"""
        return {
            "type": "object",
            "properties": {
                "points_per_game": {"type": "number"},
                "rebounds_per_game": {"type": "number"},
                "assists_per_game": {"type": "number"},
                "field_goal_percentage": {"type": "number"},
                "three_point_percentage": {"type": "number"}
            }
        }

