"""
Deal Underwriter
Evaluates specific NIL deals and makes underwriting decisions
"""

from typing import Dict, Any, Optional
import logging
import uuid
from datetime import date
from decimal import Decimal

from gravity.storage import get_storage_manager
from gravity.db.models import UnderwritingResult
from gravity.valuation.iacv_calculator import IACVCalculator

logger = logging.getLogger(__name__)


class DealUnderwriter:
    """
    Underwrites specific NIL deals
    
    Formula:
    DSUV = IACV_base * Eff_structure * Mult_rights * Prob_exec
    RADV = DSUV * (1 - LossRate(R))
    
    Decision:
    - RADV >= Price * 1.2 -> approve
    - RADV >= Price * 0.8 -> counter
    - RADV < Price * 0.8 -> no-go
    """
    
    # Decision thresholds
    APPROVE_THRESHOLD = 1.2
    COUNTER_THRESHOLD = 0.8
    
    def __init__(self):
        """Initialize deal underwriter"""
        self.storage = get_storage_manager()
        self.iacv_calculator = IACVCalculator()
        logger.info("Deal underwriter initialized")
    
    def underwrite_deal(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        deal_proposal: Dict[str, Any],
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Underwrite a specific NIL deal
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season identifier
            deal_proposal: Dict with 'price', 'term_months', 'rights', 'deliverables', etc.
            as_of_date: Date for underwriting
        
        Returns:
            Underwriting result dict
        """
        if not as_of_date:
            as_of_date = date.today()
        
        logger.info(f"Underwriting deal for athlete {athlete_id}: ${deal_proposal.get('price', 0):,.0f}")
        
        # Calculate IACV
        iacv_result = self.iacv_calculator.calculate_iacv(athlete_id, season_id, as_of_date)
        IACV_base = iacv_result['iacv_p50']
        
        # Calculate deal-specific components
        Eff_structure = self._calculate_structure_efficiency(deal_proposal)
        Mult_rights = self._calculate_rights_multiplier(deal_proposal)
        Prob_exec = self._calculate_execution_probability(athlete_id, deal_proposal)
        
        # Calculate DSUV (Deal-Specific Underwritten Value)
        DSUV = IACV_base * Eff_structure * Mult_rights * Prob_exec
        
        # Calculate RADV (Risk-Adjusted Deal Value)
        R_score = iacv_result.get('gravity_score', 0) # Get from gravity components
        LossRate = self._calculate_loss_rate(R_score)
        RADV = DSUV * (1 - LossRate)
        
        # Make decision
        price = deal_proposal.get('price', 0)
        decision, rationale, counter_price = self._make_decision(RADV, price, IACV_base)
        
        result = {
            'decision': decision,
            'decision_rationale': rationale,
            'dsuv': DSUV,
            'radv': RADV,
            'iacv_p50': IACV_base,
            'iacv_p25': iacv_result['iacv_p25'],
            'iacv_p75': iacv_result['iacv_p75'],
            'counter_price': counter_price,
            'proposed_price': price,
            'components': {
                'structure_efficiency': Eff_structure,
                'rights_multiplier': Mult_rights,
                'execution_probability': Prob_exec,
                'loss_rate': LossRate
            },
            'underwritten_at': date.today().isoformat()
        }
        
        logger.info(f"Underwriting decision: {decision} (RADV=${RADV:,.0f} vs Price=${price:,.0f})")
        
        return result
    
    def store_underwriting(
        self,
        athlete_id: uuid.UUID,
        deal_proposal: Dict[str, Any],
        result: Dict[str, Any],
        underwritten_by: str = 'system'
    ) -> uuid.UUID:
        """Store underwriting result in database"""
        try:
            with self.storage.get_session() as session:
                underwriting = UnderwritingResult(
                    athlete_id=athlete_id,
                    proposed_price=Decimal(str(result['proposed_price'])),
                    proposed_term_months=deal_proposal.get('term_months'),
                    deal_structure=deal_proposal,
                    iacv_p25=Decimal(str(result['iacv_p25'])),
                    iacv_p50=Decimal(str(result['iacv_p50'])),
                    iacv_p75=Decimal(str(result['iacv_p75'])),
                    dsuv=Decimal(str(result['dsuv'])),
                    radv=Decimal(str(result['radv'])),
                    decision=result['decision'],
                    decision_rationale=result['decision_rationale'],
                    counter_price=Decimal(str(result['counter_price'])) if result['counter_price'] else None,
                    underwritten_by=underwritten_by
                )
                
                session.add(underwriting)
                session.commit()
                session.refresh(underwriting)
                
                logger.info(f"Stored underwriting result: {underwriting.underwriting_id}")
                return underwriting.underwriting_id
                
        except Exception as e:
            logger.error(f"Failed to store underwriting: {e}")
            raise
    
    def _calculate_structure_efficiency(self, deal_proposal: Dict[str, Any]) -> float:
        """Calculate deal structure efficiency (0.5-1.5)"""
        # Check structure type
        structure_type = deal_proposal.get('structure_type', 'fixed')
        
        if structure_type == 'performance':
            return 0.8  # Performance-based deals have execution risk
        elif structure_type == 'hybrid':
            return 0.9  # Hybrid has moderate efficiency
        elif structure_type == 'fixed':
            return 1.0  # Fixed deals are baseline
        elif structure_type == 'equity':
            return 1.2  # Equity deals can have upside
        else:
            return 1.0
    
    def _calculate_rights_multiplier(self, deal_proposal: Dict[str, Any]) -> float:
        """Calculate rights multiplier based on exclusivity and scope (0.5-2.0)"""
        multiplier = 1.0
        
        # Exclusivity premium
        is_exclusive = deal_proposal.get('is_exclusive', False)
        if is_exclusive:
            multiplier *= 1.3
        
        # Category exclusivity
        is_category_exclusive = deal_proposal.get('is_category_exclusive', False)
        if is_category_exclusive:
            multiplier *= 1.2
        
        # Territory
        territory = deal_proposal.get('territory', 'local')
        if territory == 'national':
            multiplier *= 1.5
        elif territory == 'regional':
            multiplier *= 1.2
        
        # Rights scope
        rights = deal_proposal.get('rights', [])
        if isinstance(rights, list):
            if 'social_media' in rights:
                multiplier *= 1.1
            if 'appearances' in rights:
                multiplier *= 1.1
            if 'licensing' in rights:
                multiplier *= 1.2
        
        return min(2.0, multiplier)
    
    def _calculate_execution_probability(
        self,
        athlete_id: uuid.UUID,
        deal_proposal: Dict[str, Any]
    ) -> float:
        """Calculate probability of successful deal execution (0-1)"""
        prob = 0.85  # Base probability
        
        # Adjust for term length
        term_months = deal_proposal.get('term_months', 12)
        if term_months > 24:
            prob *= 0.9  # Longer deals have more execution risk
        elif term_months < 6:
            prob *= 0.95  # Short deals easier to execute
        
        # Adjust for complexity
        deliverables = deal_proposal.get('deliverables', [])
        if isinstance(deliverables, list) and len(deliverables) > 10:
            prob *= 0.9  # Many deliverables = more risk
        
        return max(0.5, min(1.0, prob))
    
    def _calculate_loss_rate(self, R_score: float) -> float:
        """Calculate expected loss rate based on risk score"""
        # R_score is 0-100
        # Convert to loss rate: 0 risk = 0% loss, 100 risk = 30% loss
        loss_rate = (R_score / 100) * 0.30
        return min(0.30, loss_rate)
    
    def _make_decision(
        self,
        RADV: float,
        price: float,
        IACV_base: float
    ) -> Tuple[str, str, Optional[float]]:
        """Make underwriting decision"""
        if price <= 0:
            return 'no-go', 'Invalid price', None
        
        ratio = RADV / price
        
        if ratio >= self.APPROVE_THRESHOLD:
            return (
                'approve',
                f'Strong value: RADV ${RADV:,.0f} vs Price ${price:,.0f} (ratio: {ratio:.2f})',
                None
            )
        elif ratio >= self.COUNTER_THRESHOLD:
            counter_price = RADV * 0.9  # Counter at 90% of RADV
            return (
                'counter',
                f'Marginal value: Counter at ${counter_price:,.0f} (RADV: ${RADV:,.0f})',
                counter_price
            )
        else:
            return (
                'no-go',
                f'Insufficient value: RADV ${RADV:,.0f} vs Price ${price:,.0f} (ratio: {ratio:.2f})',
                None
            )


# Convenience function
def underwrite_deal(
    athlete_id: uuid.UUID,
    season_id: str,
    deal_proposal: Dict[str, Any],
    as_of_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Underwrite a NIL deal
    
    Args:
        athlete_id: Athlete UUID
        season_id: Season identifier
        deal_proposal: Deal proposal dict
        as_of_date: Date for underwriting
    
    Returns:
        Underwriting result dict
    """
    underwriter = DealUnderwriter()
    return underwriter.underwrite_deal(athlete_id, season_id, deal_proposal, as_of_date)
