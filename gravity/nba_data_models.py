"""
NBA-specific data models
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class NBAProofData:
    """NBA Performance and achievements"""
    career_stats: Dict = field(default_factory=dict)
    current_season_stats: Dict = field(default_factory=dict)
    last_season_stats: Dict = field(default_factory=dict)
    
    # Game-by-game stats (gamelog)
    current_season_gamelog: List[Dict] = field(default_factory=list)  # All games this season
    gamelog_by_year: Dict[str, List[Dict]] = field(default_factory=dict)  # Historical gamelogs
    recent_games: List[Dict] = field(default_factory=list)  # Last 5 games
    games_played_current_season: int = 0
    
    # Year-by-year breakdowns (NBA)
    career_stats_by_year: Dict[int, Dict] = field(default_factory=dict)  # {2024: {...}, 2023: {...}, ...}
    all_star_selections_by_year: Dict[int, bool] = field(default_factory=dict)  # {2024: True, 2023: False, ...}
    all_nba_selections_by_year: Dict[int, bool] = field(default_factory=dict)  # {2024: True, 2023: False, ...}
    championships_by_year: Dict[int, bool] = field(default_factory=dict)  # {2024: True, 2023: False, ...}
    playoff_appearances_by_year: Dict[int, bool] = field(default_factory=dict)  # {2024: True, 2023: False, ...}
    
    # College Stats (Men's College Basketball)
    college_stats: Dict = field(default_factory=dict)
    college_career_stats: Dict = field(default_factory=dict)
    college_stats_by_year: Dict[int, Dict] = field(default_factory=dict)  # {2020: {...}, 2019: {...}, ...}
    college_career_games: Optional[int] = None
    college_career_points: Optional[int] = None
    college_career_rebounds: Optional[int] = None
    college_career_assists: Optional[int] = None
    college_career_ppg: Optional[float] = None
    college_career_rpg: Optional[float] = None
    college_career_apg: Optional[float] = None
    
    awards: List[str] = field(default_factory=list)
    all_star_selections: int = 0  # All-Star game selections
    all_star_mvp: int = 0  # All-Star Game MVP
    all_nba_selections: int = 0  # All-NBA team selections (1st, 2nd, 3rd)
    all_nba_first_team: int = 0  # All-NBA 1st Team only
    championships: int = 0  # NBA Championships
    playoff_appearances: int = 0  # Playoff appearances
    mvp_awards: int = 0  # Regular season MVP
    finals_mvp: int = 0  # Finals MVP
    dpoy_awards: int = 0  # Defensive Player of the Year
    all_defensive: int = 0  # All-Defensive Team (1st or 2nd)
    all_defensive_first: int = 0  # All-Defensive 1st Team only
    scoring_titles: int = 0  # Scoring champion
    rookie_of_year: int = 0  # Rookie of the Year
    nba_cup_mvp: int = 0  # NBA Cup (In-Season Tournament) MVP
    
    # Career totals (NBA-specific)
    career_points: Optional[int] = None
    career_rebounds: Optional[int] = None
    career_assists: Optional[int] = None
    career_steals: Optional[int] = None
    career_blocks: Optional[int] = None
    career_turnovers: Optional[int] = None
    
    # Career averages (per game)
    career_points_per_game: Optional[float] = None
    career_rebounds_per_game: Optional[float] = None
    career_assists_per_game: Optional[float] = None
    career_steals_per_game: Optional[float] = None
    career_blocks_per_game: Optional[float] = None
    career_turnovers_per_game: Optional[float] = None
    career_minutes_per_game: Optional[float] = None
    
    # Shooting percentages
    career_field_goal_percentage: Optional[float] = None
    career_three_point_percentage: Optional[float] = None
    career_free_throw_percentage: Optional[float] = None
    career_true_shooting_percentage: Optional[float] = None
    
    # Advanced stats
    career_per: Optional[float] = None  # Player Efficiency Rating
    career_usage_rate: Optional[float] = None
    career_win_shares: Optional[float] = None
    
    # Milestones
    career_double_doubles: Optional[int] = None
    career_triple_doubles: Optional[int] = None
    career_games: Optional[int] = None
    career_games_started: Optional[int] = None
    
    # Contract and earnings
    career_earnings: Optional[float] = None
    guaranteed_money: Optional[float] = None
    
    # Off-court achievements
    off_field_achievements: List[str] = field(default_factory=list)
    community_involvement: List[str] = field(default_factory=list)
    charitable_organizations: List[str] = field(default_factory=list)


@dataclass
class NBAPlayerData:
    """Complete NBA player data structure"""
    # Basic info
    player_name: str
    team: str
    position: str  # PG, SG, SF, PF, C
    collection_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Comprehensive data sections
    # Note: Identity, Brand, Proximity, Velocity, Risk are shared between NFL and NBA
    # Only Proof is NBA-specific (NBAProofData)
    # These will be set at runtime from the scrape module
    identity: Any = None
    brand: Any = None
    proof: NBAProofData = field(default_factory=NBAProofData)
    proximity: Any = None
    velocity: Any = None
    risk: Any = None
    
    # Metadata
    data_quality_score: Optional[float] = None
    collection_errors: List[str] = field(default_factory=list)

