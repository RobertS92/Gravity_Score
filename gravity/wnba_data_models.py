"""
WNBA-specific data models
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class WNBAIdentityData:
    """WNBA Player identity information"""
    name: str = ""
    position: str = ""  # G, F, C
    jersey_number: str = ""
    height: str = ""
    weight: str = ""
    age: int = 0
    birth_date: str = ""
    birth_place: str = ""
    team: str = ""
    
    # Education
    college: str = ""
    
    # Career info
    experience_years: int = 0
    draft_year: Optional[int] = None
    draft_round: Optional[int] = None
    draft_pick: Optional[int] = None
    
    # Media
    headshot_url: str = ""


@dataclass
class WNBAProofData:
    """WNBA Performance and achievements"""
    # WNBA Stats
    career_stats: Dict = field(default_factory=dict)
    current_season_stats: Dict = field(default_factory=dict)
    last_season_stats: Dict = field(default_factory=dict)
    
    # Year-by-year breakdowns (WNBA)
    career_stats_by_year: Dict[int, Dict] = field(default_factory=dict)
    all_star_selections_by_year: Dict[int, bool] = field(default_factory=dict)
    all_wnba_selections_by_year: Dict[int, bool] = field(default_factory=dict)
    championships_by_year: Dict[int, bool] = field(default_factory=dict)
    playoff_appearances_by_year: Dict[int, bool] = field(default_factory=dict)
    
    # College Stats (Women's College Basketball)
    college_stats: Dict = field(default_factory=dict)
    college_career_stats: Dict = field(default_factory=dict)
    college_stats_by_year: Dict[int, Dict] = field(default_factory=dict)
    
    awards: List[str] = field(default_factory=list)
    all_star_selections: int = 0  # All-Star game selections
    all_wnba_selections: int = 0  # All-WNBA team selections (1st, 2nd)
    all_wnba_first_team: int = 0  # All-WNBA 1st Team only
    championships: int = 0  # WNBA Championships
    playoff_appearances: int = 0  # Playoff appearances
    mvp_awards: int = 0  # Regular season MVP
    finals_mvp: int = 0  # Finals MVP
    dpoy_awards: int = 0  # Defensive Player of the Year
    all_defensive: int = 0  # All-Defensive Team (1st or 2nd)
    all_defensive_first: int = 0  # All-Defensive 1st Team only
    rookie_of_year: int = 0  # Rookie of the Year
    sixth_woman: int = 0  # Sixth Woman of the Year
    
    # College awards
    college_awards: List[str] = field(default_factory=list)
    all_american_selections: int = 0
    conference_honors: int = 0
    wooden_award: bool = False  # NCAA POY
    naismith_award: bool = False  # NCAA POY
    
    # Career totals (WNBA)
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
    
    # College career totals
    college_career_points: Optional[int] = None
    college_career_rebounds: Optional[int] = None
    college_career_assists: Optional[int] = None
    college_career_games: Optional[int] = None
    college_career_ppg: Optional[float] = None
    college_career_rpg: Optional[float] = None
    college_career_apg: Optional[float] = None
    
    # Milestones
    career_double_doubles: Optional[int] = None
    career_triple_doubles: Optional[int] = None
    career_games: Optional[int] = None
    career_games_started: Optional[int] = None
    
    # Contract and earnings
    career_earnings: Optional[float] = None
    guaranteed_money: Optional[float] = None
    
    # Off-court achievements
    off_court_achievements: List[str] = field(default_factory=list)
    community_involvement: List[str] = field(default_factory=list)
    charitable_organizations: List[str] = field(default_factory=list)


@dataclass
class WNBAPlayerData:
    """Complete WNBA player data structure"""
    # Basic info
    player_name: str
    team: str
    position: str  # G, F, C
    collection_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Comprehensive data sections
    identity: WNBAIdentityData = field(default_factory=WNBAIdentityData)
    brand: Any = None  # Same as other sports
    proof: WNBAProofData = field(default_factory=WNBAProofData)
    proximity: Any = None
    velocity: Any = None
    risk: Any = None
    
    # Metadata
    data_quality_score: Optional[float] = None
    collection_errors: List[str] = field(default_factory=list)

