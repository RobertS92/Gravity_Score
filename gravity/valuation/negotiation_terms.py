"""
Negotiation Terms Generator
Generates anchor/target/walk-away prices and recommended clauses
"""

from typing import Dict, Any, List, Optional
import logging
import uuid
from datetime import date

from gravity.storage import get_storage_manager
from gravity.db.models import GravityScore

logger = logging.getLogger(__name__)


class NegotiationTermsGenerator:
    """
    Generates negotiation strategy for NIL deals
    
    Components:
    - Anchor price (initial ask)
    - Target price (ideal outcome)
    - Walk-away price (minimum acceptable)
    - Concession ladder (3-step negotiation)
    - Contract clauses (based on risk profile)
    """
    
    def __init__(self):
        """Initialize negotiation terms generator"""
        self.storage = get_storage_manager()
        logger.info("Negotiation terms generator initialized")
    
    def generate_negotiation_terms(
        self,
        athlete_id: uuid.UUID,
        underwriting_result: Dict[str, Any],
        deal_proposal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete negotiation strategy
        
        Args:
            athlete_id: Athlete UUID
            underwriting_result: Result from DealUnderwriter
            deal_proposal: Original deal proposal
        
        Returns:
            Negotiation terms dict
        """
        logger.info(f"Generating negotiation terms for athlete {athlete_id}")
        
        IACV = underwriting_result['iacv_p50']
        RADV = underwriting_result['radv']
        
        # Calculate pricing strategy
        anchor = IACV * 1.25  # Start 25% above IACV
        target = RADV  # Aim for risk-adjusted value
        walk_away = RADV * 0.75  # Don't go below 75% of RADV
        
        # Generate concession ladder
        concession_ladder = self._generate_concession_ladder(anchor, target, walk_away)
        
        # Get risk-based clauses
        risk_score = self._get_risk_score(athlete_id)
        recommended_clauses = self._generate_contract_clauses(risk_score, deal_proposal)
        
        # Generate negotiation talking points
        talking_points = self._generate_talking_points(underwriting_result, deal_proposal)
        
        terms = {
            'anchor_price': anchor,
            'target_price': target,
            'walk_away_price': walk_away,
            'concession_ladder': concession_ladder,
            'recommended_clauses': recommended_clauses,
            'talking_points': talking_points,
            'negotiation_leverage': self._assess_leverage(underwriting_result),
            'generated_at': date.today().isoformat()
        }
        
        logger.info(f"Negotiation terms: Anchor=${anchor:,.0f}, Target=${target:,.0f}, Walk-away=${walk_away:,.0f}")
        
        return terms
    
    def _generate_concession_ladder(
        self,
        anchor: float,
        target: float,
        walk_away: float
    ) -> List[Dict[str, Any]]:
        """Generate 3-step concession ladder"""
        step1 = anchor
        step2 = (anchor + target) / 2
        step3 = target * 0.95  # Slight discount from target
        
        return [
            {
                'step': 1,
                'price': step1,
                'description': 'Initial position - hold firm',
                'concession_pct': 0
            },
            {
                'step': 2,
                'price': step2,
                'description': 'First concession - show flexibility',
                'concession_pct': ((anchor - step2) / anchor) * 100
            },
            {
                'step': 3,
                'price': step3,
                'description': 'Final offer - last concession',
                'concession_pct': ((anchor - step3) / anchor) * 100
            }
        ]
    
    def _generate_contract_clauses(
        self,
        risk_score: float,
        deal_proposal: Dict[str, Any]
    ) -> List[str]:
        """Generate recommended contract clauses based on risk"""
        clauses = []
        
        # Standard clauses (always include)
        clauses.extend([
            'Force majeure clause for unforeseen circumstances',
            'Termination for convenience with 30-day notice',
            'Confidentiality and non-disclosure provisions'
        ])
        
        # Medium risk clauses (R > 20)
        if risk_score > 20:
            clauses.extend([
                'Performance-based milestone payments (30% holdback)',
                'Content approval rights for brand protection',
                'Injury clause with partial payment provisions'
            ])
        
        # High risk clauses (R > 40)
        if risk_score > 40:
            clauses.extend([
                'Conduct clause with reputation triggers',
                'Escrow holdback 20% until deliverables complete',
                'Right of first refusal on contract renewal',
                'Liquidated damages for material breach'
            ])
        
        # Very high risk clauses (R > 60)
        if risk_score > 60:
            clauses.extend([
                'Insurance requirement for key person coverage',
                'Social media content pre-approval required',
                'Performance bond or guarantee',
                'Termination for NCAA eligibility issues'
            ])
        
        # Deal-specific clauses
        if deal_proposal.get('is_exclusive'):
            clauses.append('Exclusive category protection with competitor restrictions')
        
        if deal_proposal.get('term_months', 0) > 24:
            clauses.append('Annual performance review with adjustment provisions')
        
        return clauses
    
    def _generate_talking_points(
        self,
        underwriting_result: Dict[str, Any],
        deal_proposal: Dict[str, Any]
    ) -> List[str]:
        """Generate negotiation talking points"""
        points = []
        
        # Value proposition
        IACV = underwriting_result['iacv_p50']
        points.append(f"Athlete's annual commercial value is ${IACV:,.0f} based on comprehensive market analysis")
        
        # Upside potential
        IACV_p75 = underwriting_result['iacv_p75']
        upside = IACV_p75 - IACV
        points.append(f"Potential upside of ${upside:,.0f} with strong performance")
        
        # Market positioning
        points.append("Valuation reflects current market conditions and comparable deals")
        
        # Risk mitigation
        if underwriting_result.get('components', {}).get('loss_rate', 0) > 0.1:
            points.append("Risk-adjusted pricing accounts for identified risk factors")
        
        # Win-win structure
        points.append("Proposed structure aligns incentives for mutual success")
        
        return points
    
    def _assess_leverage(self, underwriting_result: Dict[str, Any]) -> str:
        """Assess negotiation leverage"""
        decision = underwriting_result.get('decision', 'unknown')
        
        ratio = underwriting_result.get('radv', 0) / max(1, underwriting_result.get('proposed_price', 1))
        
        if decision == 'approve' and ratio > 1.5:
            return 'strong'  # Deal is very favorable
        elif decision == 'approve':
            return 'moderate'  # Deal is good
        elif decision == 'counter':
            return 'balanced'  # Fair negotiation
        else:
            return 'weak'  # Not a good deal
    
    def _get_risk_score(self, athlete_id: uuid.UUID) -> float:
        """Get latest risk score for athlete"""
        try:
            with self.storage.get_session() as session:
                latest_score = session.query(GravityScore).filter(
                    GravityScore.athlete_id == athlete_id
                ).order_by(GravityScore.as_of_date.desc()).first()
                
                if latest_score:
                    return latest_score.risk_score or 0
                
        except Exception as e:
            logger.error(f"Failed to get risk score: {e}")
        
        return 30  # Default moderate risk


# Convenience function
def generate_negotiation_terms(
    athlete_id: uuid.UUID,
    underwriting_result: Dict[str, Any],
    deal_proposal: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate negotiation terms
    
    Args:
        athlete_id: Athlete UUID
        underwriting_result: Underwriting result
        deal_proposal: Deal proposal
    
    Returns:
        Negotiation terms dict
    """
    generator = NegotiationTermsGenerator()
    return generator.generate_negotiation_terms(athlete_id, underwriting_result, deal_proposal)
