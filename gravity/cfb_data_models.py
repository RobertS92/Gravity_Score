"""
College Football (CFB) specific data models
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class CFBProofData:
    """College Football Performance and achievements"""
    career_stats: Dict = field(default_factory=dict)
    current_season_stats: Dict = field(default_factory=dict)
    last_season_stats: Dict = field(default_factory=dict)
    
    # Year-by-year breakdowns
    career_stats_by_year: Dict[int, Dict] = field(default_factory=dict)
    
    # Awards list
    awards: List[Dict] = field(default_factory=list)
    
    # College-specific awards
    heisman_votes: int = 0  # Heisman Trophy votes/finishes
    heisman_winner: bool = False
    all_american: int = 0  # All-American selections
    all_american_first_team: int = 0
    conference_player_of_year: int = 0
    conference_awards: List[str] = field(default_factory=list)
    bowl_game_mvp: int = 0
    freshman_all_american: bool = False
    
    # Draft projection
    draft_projection_round: Optional[int] = None
    draft_projection_pick: Optional[int] = None
    draft_grade: Optional[float] = None
    nfl_comparison: Optional[str] = None
    
    # NIL (Name, Image, Likeness) - College specific
    nil_valuation: Optional[float] = None  # Estimated NIL value
    nil_deals: List[Dict] = field(default_factory=list)  # Known deals
    nil_ranking: Optional[int] = None  # On3/Opendorse ranking
    
    # Career totals (position-dependent)
    career_touchdowns: Optional[int] = None
    career_yards: Optional[int] = None
    career_passing_yards: Optional[int] = None
    career_passing_tds: Optional[int] = None
    career_rushing_yards: Optional[int] = None
    career_rushing_tds: Optional[int] = None
    career_receiving_yards: Optional[int] = None
    career_receiving_tds: Optional[int] = None
    career_receptions: Optional[int] = None
    career_tackles: Optional[int] = None
    career_sacks: Optional[float] = None
    career_interceptions: Optional[int] = None
    
    # Games
    career_games: Optional[int] = None
    career_games_started: Optional[int] = None
    
    # Off-field
    off_field_achievements: List[str] = field(default_factory=list)
    community_involvement: List[str] = field(default_factory=list)


@dataclass
class CFBIdentityData:
    """College Football player identity"""
    age: Optional[int] = None
    birth_date: Optional[str] = None
    nationality: Optional[str] = None
    hometown: Optional[str] = None
    high_school: Optional[str] = None  # CFB specific
    
    # College info
    college: Optional[str] = None
    conference: Optional[str] = None  # SEC, Big Ten, etc.
    class_year: Optional[str] = None  # Freshman, Sophomore, etc.
    eligibility_year: Optional[int] = None  # Years of eligibility remaining
    
    # Recruiting info
    recruiting_stars: Optional[int] = None  # 3-star, 4-star, 5-star
    recruiting_ranking: Optional[int] = None  # National ranking
    recruiting_state_ranking: Optional[int] = None
    recruiting_position_ranking: Optional[int] = None
    
    # Physical
    height: Optional[str] = None
    weight: Optional[int] = None
    jersey_number: Optional[str] = None
    
    # Transfer info
    transfer_portal: bool = False
    previous_schools: List[str] = field(default_factory=list)
    
    # NIL
    nil_agent: Optional[str] = None
    nil_representation: Optional[str] = None


@dataclass 
class CFBPlayerData:
    """Complete College Football player data structure"""
    # Basic info
    player_name: str
    team: str  # College team
    position: str
    conference: str = ""
    collection_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Comprehensive data sections
    identity: CFBIdentityData = field(default_factory=CFBIdentityData)
    brand: Any = None  # Shared BrandData
    proof: CFBProofData = field(default_factory=CFBProofData)
    proximity: Any = None  # Shared ProximityData
    velocity: Any = None  # Shared VelocityData
    risk: Any = None  # Shared RiskData
    
    # Metadata
    data_quality_score: Optional[float] = None
    collection_errors: List[str] = field(default_factory=list)

