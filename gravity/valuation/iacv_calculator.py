"""
IACV Calculator
Intrinsic Annual Commercial Value calculator
"""

from typing import Dict, Any, Tuple
import logging
import math
import uuid
from datetime import date

from gravity.storage import get_storage_manager
from gravity.db.models import GravityScore, Athlete
from gravity.scoring.gravity_calculator import GravityCalculator

logger = logging.getLogger(__name__)


class IACVCalculator:
    """
    Calculates Intrinsic Annual Commercial Value (IACV)
    
    Formula:
    IACV_base = M_sport_level * f(G_conf) * Adj_market * Adj_role
    
    Where:
    - M_sport_level: Base market multiplier by sport/level
    - f(G_conf): Exponential scaling function based on Gravity score
    - Adj_market: Market adjustment (school brand, location)
    - Adj_role: Role adjustment (starter vs backup, position value)
    
    Variance for P25/P50/P75:
    sigma = sigma0 + λ*(1-avg_conf) + μ*volatility(V) + ν*R
    """
    
    # Base market multipliers by sport level
    MARKET_MULTIPLIERS = {
        'CFB_P5': 50_000,      # Power 5 football
        'CFB_G5': 25_000,      # Group of 5 football
        'CBB_P6': 40_000,      # Power 6 basketball
        'CBB_MID': 20_000,     # Mid-major basketball
        'DEFAULT': 30_000
    }
    
    # Scaling parameters
    K_SCALING = 3.0  # Exponential scaling factor
    SIGMA_BASE = 0.15  # Base uncertainty
    LAMBDA_CONF = 0.30  # Confidence uncertainty weight
    MU_VOLATILITY = 0.20  # Volatility uncertainty weight
    NU_RISK = 0.10  # Risk uncertainty weight
    
    def __init__(self):
        """Initialize IACV calculator"""
        self.storage = get_storage_manager()
        logger.info("IACV calculator initialized")
    
    def calculate_iacv(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate IACV with confidence intervals
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season identifier
            as_of_date: Date for calculation
        
        Returns:
            IACV dict with P25/P50/P75 values
        """
        if not as_of_date:
            as_of_date = date.today()
        
        logger.info(f"Calculating IACV for athlete {athlete_id}")
        
        # Get Gravity score
        gravity_result = self._get_gravity_score(athlete_id, season_id, as_of_date)
        if not gravity_result:
            logger.warning(f"No Gravity score found for athlete {athlete_id}")
            return self._default_iacv()
        
        # Get athlete info
        athlete = self._get_athlete(athlete_id)
        if not athlete:
            return self._default_iacv()
        
        # Calculate base components
        M_sport_level = self._get_market_multiplier(athlete)
        G_conf = gravity_result['gravity_conf']
        f_g = self._scaling_function(G_conf)
        Adj_market = self._get_market_adjustment(athlete)
        Adj_role = self._get_role_adjustment(athlete)
        
        # Calculate base IACV
        IACV_base = M_sport_level * f_g * Adj_market * Adj_role
        
        # Calculate variance (sigma)
        avg_conf = gravity_result['average_confidence']
        volatility_V = self._get_velocity_volatility(gravity_result)
        R_score = gravity_result['components']['risk']
        
        sigma = (
            self.SIGMA_BASE +
            self.LAMBDA_CONF * (1 - avg_conf) +
            self.MU_VOLATILITY * volatility_V +
            self.NU_RISK * (R_score / 100)
        )
        
        # Calculate P25/P50/P75
        P25 = IACV_base * (1 - sigma)
        P50 = IACV_base
        P75 = IACV_base * (1 + sigma)
        
        result = {
            'iacv_p25': max(0, P25),
            'iacv_p50': max(0, P50),
            'iacv_p75': max(0, P75),
            'gravity_score': G_conf,
            'confidence_avg': avg_conf,
            'sigma': sigma,
            'components': {
                'market_multiplier': M_sport_level,
                'scaling_factor': f_g,
                'market_adjustment': Adj_market,
                'role_adjustment': Adj_role
            },
            'calculated_at': date.today().isoformat()
        }
        
        logger.info(f"IACV calculated: P50=${P50:,.0f} (P25=${P25:,.0f}, P75=${P75:,.0f})")
        
        return result
    
    def _scaling_function(self, G_conf: float) -> float:
        """
        Exponential scaling function
        
        f(g) = exp(k * (g - 0.5))
        
        Where g = G_conf / 100
        """
        g = G_conf / 100
        return math.exp(self.K_SCALING * (g - 0.5))
    
    def _get_market_multiplier(self, athlete: Athlete) -> float:
        """Get base market multiplier for sport/level"""
        sport = athlete.sport.upper() if athlete.sport else 'UNKNOWN'
        conference = athlete.conference.upper() if athlete.conference else ''
        
        # Determine level
        if 'FOOTBALL' in sport:
            # Check conference for P5 vs G5
            p5_conferences = ['SEC', 'BIG TEN', 'BIG 12', 'ACC', 'PAC-12']
            if any(conf in conference for conf in p5_conferences):
                return self.MARKET_MULTIPLIERS['CFB_P5']
            else:
                return self.MARKET_MULTIPLIERS['CFB_G5']
        
        elif 'BASKETBALL' in sport:
            # Similar for basketball
            p6_conferences = ['SEC', 'BIG TEN', 'BIG 12', 'ACC', 'PAC-12', 'BIG EAST']
            if any(conf in conference for conf in p6_conferences):
                return self.MARKET_MULTIPLIERS['CBB_P6']
            else:
                return self.MARKET_MULTIPLIERS['CBB_MID']
        
        return self.MARKET_MULTIPLIERS['DEFAULT']
    
    def _get_market_adjustment(self, athlete: Athlete) -> float:
        """Calculate market adjustment based on school brand and location"""
        # School brand tiers
        elite_schools = [
            'ALABAMA', 'OHIO STATE', 'GEORGIA', 'MICHIGAN', 'USC',
            'TEXAS', 'NOTRE DAME', 'OKLAHOMA', 'FLORIDA', 'LSU'
        ]
        
        strong_schools = [
            'CLEMSON', 'OREGON', 'PENN STATE', 'WISCONSIN', 'MIAMI',
            'TENNESSEE', 'AUBURN', 'TEXAS A&M', 'FLORIDA STATE'
        ]
        
        school_name = athlete.school.upper() if athlete.school else ''
        
        # Check tier
        if any(elite in school_name for elite in elite_schools):
            return 1.5  # 50% premium
        elif any(strong in school_name for strong in strong_schools):
            return 1.25  # 25% premium
        else:
            return 1.0  # Baseline
    
    def _get_role_adjustment(self, athlete: Athlete) -> float:
        """Calculate role adjustment based on position and playing time"""
        # Position value adjustments
        position = athlete.position.upper() if athlete.position else ''
        
        premium_positions = ['QB', 'QUARTERBACK']
        high_value_positions = ['RB', 'WR', 'EDGE', 'CB']
        
        if any(pos in position for pos in premium_positions):
            return 1.4  # QB premium
        elif any(pos in position for pos in high_value_positions):
            return 1.1  # Skill position premium
        else:
            return 1.0  # Baseline
    
    def _get_velocity_volatility(self, gravity_result: Dict) -> float:
        """Extract velocity volatility from Gravity result"""
        # Check for volatility in explanations
        velocity_explanation = gravity_result.get('explanations', {}).get('velocity', {})
        # For now, return moderate volatility
        # In full implementation, this would come from feature metrics
        return 0.2
    
    def _get_gravity_score(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> Optional[Dict[str, Any]]:
        """Get Gravity score from database"""
        try:
            calculator = GravityCalculator()
            return calculator.calculate_gravity_score(athlete_id, season_id, as_of_date)
        except Exception as e:
            logger.error(f"Failed to get Gravity score: {e}")
            return None
    
    def _get_athlete(self, athlete_id: uuid.UUID) -> Optional[Athlete]:
        """Get athlete from database"""
        try:
            with self.storage.get_session() as session:
                return session.query(Athlete).filter(
                    Athlete.athlete_id == athlete_id
                ).first()
        except Exception as e:
            logger.error(f"Failed to get athlete: {e}")
            return None
    
    def _default_iacv(self) -> Dict[str, Any]:
        """Return default IACV when calculation fails"""
        return {
            'iacv_p25': 0,
            'iacv_p50': 0,
            'iacv_p75': 0,
            'gravity_score': 0,
            'confidence_avg': 0,
            'sigma': 1.0,
            'components': {},
            'calculated_at': date.today().isoformat()
        }


# Convenience function
def calculate_iacv(
    athlete_id: uuid.UUID,
    season_id: str,
    as_of_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Calculate IACV for athlete
    
    Args:
        athlete_id: Athlete UUID
        season_id: Season identifier
        as_of_date: Date for calculation
    
    Returns:
        IACV dict
    """
    calculator = IACVCalculator()
    return calculator.calculate_iacv(athlete_id, season_id, as_of_date)
