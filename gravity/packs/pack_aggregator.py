"""
Pack Aggregator
Collects all data for Negotiation Pack generation
"""

from typing import Dict, Any, Optional
import logging
import uuid
from datetime import date, datetime

from gravity.storage import get_storage_manager
from gravity.db.models import Athlete, GravityScore, NILDeal, NILValuation
from gravity.valuation import calculate_iacv, underwrite_deal, generate_negotiation_terms
logger = logging.getLogger(__name__)


class PackAggregator:
    """
    Aggregates all data needed for Negotiation Pack
    """
    
    def __init__(self):
        """Initialize pack aggregator"""
        self.storage = get_storage_manager()
        logger.info("Pack aggregator initialized")
    
    def aggregate_pack_data(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        deal_proposal: Optional[Dict[str, Any]] = None,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Aggregate complete pack data
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season identifier
            deal_proposal: Optional deal to underwrite
            as_of_date: Date for pack
        
        Returns:
            Complete pack data dict
        """
        if not as_of_date:
            as_of_date = date.today()
        
        logger.info(f"Aggregating pack data for athlete {athlete_id}")
        
        pack_data = {
            'pack_version': '1.0',
            'generated_at': datetime.utcnow().isoformat(),
            'as_of_date': as_of_date.isoformat()
        }
        
        # Get athlete info
        pack_data['athlete'] = self._get_athlete_info(athlete_id)
        
        # Get Gravity score
        pack_data['gravity_score'] = self._get_gravity_score(athlete_id, season_id, as_of_date)
        
        # Get valuation
        pack_data['valuation'] = calculate_iacv(athlete_id, season_id, as_of_date)
        
        # Get features
        pack_data['features'] = self._get_features(athlete_id, season_id, as_of_date)
        
        # Get NIL portfolio
        pack_data['nil_portfolio'] = self._get_nil_portfolio(athlete_id)
        
        # If deal proposal provided, run underwriting
        if deal_proposal:
            underwriting = underwrite_deal(athlete_id, season_id, deal_proposal, as_of_date)
            pack_data['underwriting'] = underwriting
            
            # Generate negotiation terms
            negotiation = generate_negotiation_terms(athlete_id, underwriting, deal_proposal)
            pack_data['negotiation'] = negotiation
        else:
            pack_data['underwriting'] = None
            pack_data['negotiation'] = None
        
        logger.info(f"Pack data aggregated for athlete {athlete_id}")
        
        return pack_data
    
    def _get_athlete_info(self, athlete_id: uuid.UUID) -> Dict[str, Any]:
        """Get athlete information"""
        try:
            with self.storage.get_session() as session:
                athlete = session.query(Athlete).filter(
                    Athlete.athlete_id == athlete_id
                ).first()
                
                if not athlete:
                    return {}
                
                return {
                    'id': str(athlete.athlete_id),
                    'name': athlete.canonical_name,
                    'sport': athlete.sport,
                    'school': athlete.school,
                    'position': athlete.position,
                    'conference': athlete.conference,
                    'jersey_number': athlete.jersey_number,
                    'class_year': athlete.class_year,
                    'season_id': athlete.season_id
                }
        except Exception as e:
            logger.error(f"Failed to get athlete info: {e}")
            return {}
    
    def _get_gravity_score(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> Dict[str, Any]:
        """Get Gravity score"""
        try:
            with self.storage.get_session() as session:
                score = session.query(GravityScore).filter(
                    GravityScore.athlete_id == athlete_id,
                    GravityScore.season_id == season_id,
                    GravityScore.as_of_date == as_of_date
                ).first()
                
                if not score:
                    # Try most recent
                    score = session.query(GravityScore).filter(
                        GravityScore.athlete_id == athlete_id
                    ).order_by(GravityScore.as_of_date.desc()).first()
                
                if not score:
                    return {}
                
                return {
                    'gravity_raw': score.gravity_raw,
                    'gravity_conf': score.gravity_conf,
                    'average_confidence': score.average_confidence,
                    'components': {
                        'brand': {'score': score.brand_score, 'confidence': score.brand_confidence},
                        'proof': {'score': score.proof_score, 'confidence': score.proof_confidence},
                        'proximity': {'score': score.proximity_score, 'confidence': score.proximity_confidence},
                        'velocity': {'score': score.velocity_score, 'confidence': score.velocity_confidence},
                        'risk': {'score': score.risk_score, 'confidence': score.risk_confidence}
                    },
                    'explanations': score.explanations or {},
                    'evidence': score.evidence or []
                }
        except Exception as e:
            logger.error(f"Failed to get Gravity score: {e}")
            return {}
    
    def _get_features(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> Dict[str, Any]:
        """FeatureCalculator removed with NIL rebuild; extend with DB reads if needed."""
        _ = (athlete_id, season_id, as_of_date)
        return {}
    
    def _get_nil_portfolio(self, athlete_id: uuid.UUID) -> Dict[str, Any]:
        """Get NIL deal portfolio"""
        try:
            with self.storage.get_session() as session:
                # Get deals
                deals = session.query(NILDeal).filter(
                    NILDeal.athlete_id == athlete_id
                ).order_by(NILDeal.announced_date.desc()).all()
                
                deal_list = []
                for deal in deals:
                    deal_list.append({
                        'brand': deal.brand,
                        'type': deal.deal_type,
                        'value': float(deal.deal_value) if deal.deal_value else None,
                        'currency': deal.deal_currency,
                        'term_months': deal.deal_term_months,
                        'is_national': deal.is_national,
                        'is_verified': deal.is_verified,
                        'announced_date': deal.announced_date.isoformat() if deal.announced_date else None,
                        'source': deal.source
                    })
                
                # Get latest valuation
                valuation = session.query(NILValuation).filter(
                    NILValuation.athlete_id == athlete_id
                ).order_by(NILValuation.as_of_date.desc()).first()
                
                return {
                    'total_deals': len(deals),
                    'deals': deal_list[:20],  # Limit to 20 most recent
                    'latest_valuation': float(valuation.valuation_amount) if valuation else None,
                    'latest_valuation_source': valuation.source if valuation else None
                }
        except Exception as e:
            logger.error(f"Failed to get NIL portfolio: {e}")
            return {}


# Convenience function
def aggregate_pack_data(
    athlete_id: uuid.UUID,
    season_id: str,
    deal_proposal: Optional[Dict[str, Any]] = None,
    as_of_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Aggregate pack data for athlete
    
    Args:
        athlete_id: Athlete UUID
        season_id: Season identifier
        deal_proposal: Optional deal proposal
        as_of_date: Date for pack
    
    Returns:
        Complete pack data dict
    """
    aggregator = PackAggregator()
    return aggregator.aggregate_pack_data(athlete_id, season_id, deal_proposal, as_of_date)
