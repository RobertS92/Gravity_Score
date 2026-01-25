"""
NCAA Basketball (NCAAB) specific data models
Supports both Men's and Women's college basketball
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class NCAABProofData:
    """NCAA Basketball Performance and achievements"""
    career_stats: Dict = field(default_factory=dict)
    current_season_stats: Dict = field(default_factory=dict)
    last_season_stats: Dict = field(default_factory=dict)
    
    # Year-by-year breakdowns
    career_stats_by_year: Dict[int, Dict] = field(default_factory=dict)
    
    # Awards list
    awards: List[Dict] = field(default_factory=list)
    
    # College basketball awards
    all_american: int = 0  # All-American selections
    all_american_first_team: int = 0
    conference_player_of_year: int = 0
    conference_first_team: int = 0
    conference_awards: List[str] = field(default_factory=list)
    tournament_mvp: int = 0  # NCAA Tournament MOP
    final_four_appearances: int = 0
    national_championships: int = 0
    wooden_award: bool = False
    naismith_award: bool = False
    
    # Draft projection
    draft_projection_round: Optional[int] = None
    draft_projection_pick: Optional[int] = None
    mock_draft_ranking: Optional[int] = None
    nba_comparison: Optional[str] = None
    
    # NIL (Name, Image, Likeness)
    nil_valuation: Optional[float] = None
    nil_deals: List[Dict] = field(default_factory=list)
    nil_ranking: Optional[int] = None
    
    # Career totals
    career_points: Optional[int] = None
    career_rebounds: Optional[int] = None
    career_assists: Optional[int] = None
    career_steals: Optional[int] = None
    career_blocks: Optional[int] = None
    career_turnovers: Optional[int] = None
    
    # Career averages
    career_ppg: Optional[float] = None
    career_rpg: Optional[float] = None
    career_apg: Optional[float] = None
    career_spg: Optional[float] = None
    career_bpg: Optional[float] = None
    
    # Shooting
    career_fg_pct: Optional[float] = None
    career_3pt_pct: Optional[float] = None
    career_ft_pct: Optional[float] = None
    
    # Games
    career_games: Optional[int] = None
    career_games_started: Optional[int] = None
    career_minutes: Optional[int] = None
    
    # Milestones
    career_double_doubles: Optional[int] = None
    career_triple_doubles: Optional[int] = None
    
    # Off-field
    off_field_achievements: List[str] = field(default_factory=list)
    community_involvement: List[str] = field(default_factory=list)


@dataclass
class NCAABIdentityData:
    """NCAA Basketball player identity"""
    age: Optional[int] = None
    birth_date: Optional[str] = None
    nationality: Optional[str] = None
    hometown: Optional[str] = None
    high_school: Optional[str] = None
    
    # College info
    college: Optional[str] = None
    conference: Optional[str] = None  # ACC, SEC, Big Ten, etc.
    class_year: Optional[str] = None  # Freshman, Sophomore, etc.
    eligibility_year: Optional[int] = None
    
    # Recruiting info
    recruiting_stars: Optional[int] = None
    recruiting_ranking: Optional[int] = None
    recruiting_state_ranking: Optional[int] = None
    recruiting_position_ranking: Optional[int] = None
    
    # Physical
    height: Optional[str] = None
    weight: Optional[int] = None
    wingspan: Optional[str] = None  # Important for basketball
    jersey_number: Optional[str] = None
    
    # Transfer info
    transfer_portal: bool = False
    previous_schools: List[str] = field(default_factory=list)
    
    # NIL
    nil_agent: Optional[str] = None


@dataclass 
class NCAABPlayerData:
    """Complete NCAA Basketball player data structure"""
    # Basic info
    player_name: str
    team: str  # College team
    position: str  # PG, SG, SF, PF, C
    conference: str = ""
    gender: str = "mens"  # mens or womens
    collection_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Comprehensive data sections
    identity: NCAABIdentityData = field(default_factory=NCAABIdentityData)
    brand: Any = None  # Shared BrandData
    proof: NCAABProofData = field(default_factory=NCAABProofData)
    proximity: Any = None  # Shared ProximityData
    velocity: Any = None  # Shared VelocityData
    risk: Any = None  # Shared RiskData
    
    # Metadata
    data_quality_score: Optional[float] = None
    collection_errors: List[str] = field(default_factory=list)

