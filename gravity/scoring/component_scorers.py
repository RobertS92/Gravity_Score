"""
Component Scorers (B, P, X, V, R)
Each component scores from 0-100 with confidence score 0-1
"""

from typing import Dict, Any, Tuple, Optional
import logging
import math
import uuid
from datetime import date

from gravity.storage import get_storage_manager
from gravity.db.models import FeatureSnapshot, Athlete

logger = logging.getLogger(__name__)


class ComponentScorer:
    """Base class for component scorers"""
    
    def __init__(self):
        self.storage = get_storage_manager()
    
    def score(
        self,
        athlete_id: uuid.UUID,
        features: Dict[str, Any],
        as_of_date: date
    ) -> Tuple[float, float, Dict[str, Any]]:
        """
        Calculate component score
        
        Args:
            athlete_id: Athlete UUID
            features: Feature snapshot
            as_of_date: Date for scoring
        
        Returns:
            Tuple of (score 0-100, confidence 0-1, explanation_dict)
        """
        raise NotImplementedError


class BrandScorer(ComponentScorer):
    """
    Brand (B) Component - Social presence and recognition
    
    Factors:
    - Social media followers (Instagram, Twitter, TikTok)
    - Engagement rate
    - Wikipedia views/mentions
    - News mentions
    - Name recognition
    """
    
    def score(
        self,
        athlete_id: uuid.UUID,
        features: Dict[str, Any],
        as_of_date: date
    ) -> Tuple[float, float, Dict[str, Any]]:
        
        raw = features.get('raw_metrics', {})
        derived = features.get('derived_metrics', {})
        
        # Extract metrics
        social_followers = raw.get('social_followers', 0)
        engagement_rate = raw.get('social_engagement_rate', 0)
        
        # Calculate sub-scores
        follower_score = self._score_followers(social_followers)
        engagement_score = self._score_engagement(engagement_rate)
        
        # Weighted combination
        score = (
            follower_score * 0.6 +
            engagement_score * 0.4
        )
        
        # Confidence based on data availability
        confidence = self._calculate_confidence(raw)
        
        explanation = {
            'follower_score': follower_score,
            'engagement_score': engagement_score,
            'social_followers': social_followers,
            'engagement_rate': engagement_rate
        }
        
        return min(100, max(0, score)), confidence, explanation
    
    def _score_followers(self, followers: int) -> float:
        """Score based on follower count (logarithmic scale)"""
        if followers <= 0:
            return 0
        
        # Log scale: 10K = 30, 100K = 60, 1M = 90, 10M = 100
        score = 30 * math.log10(max(1, followers / 10_000) + 1)
        return min(100, score)
    
    def _score_engagement(self, rate: float) -> float:
        """Score based on engagement rate"""
        # 1% = 20, 3% = 60, 5% = 80, 10% = 100
        if rate <= 0:
            return 0
        
        score = 20 * rate
        return min(100, score)
    
    def _calculate_confidence(self, raw: Dict) -> float:
        """Calculate confidence based on data availability"""
        has_social = raw.get('social_followers', 0) > 0
        has_engagement = raw.get('social_engagement_rate', 0) > 0
        
        if has_social and has_engagement:
            return 0.8
        elif has_social:
            return 0.6
        else:
            return 0.3


class ProofScorer(ComponentScorer):
    """
    Proof (P) Component - Performance and achievements
    
    Factors:
    - On-field performance statistics
    - Awards and honors
    - Team success
    - Position value
    - Draft/recruiting ranking
    """
    
    def score(
        self,
        athlete_id: uuid.UUID,
        features: Dict[str, Any],
        as_of_date: date
    ) -> Tuple[float, float, Dict[str, Any]]:
        
        raw = features.get('raw_metrics', {})
        
        # Extract metrics
        performance_score = raw.get('performance_score', 0)
        team_ranking = raw.get('team_ranking', 0)
        
        # For now, use placeholders
        # In full implementation, these would come from stats collectors
        score = min(100, performance_score)
        confidence = 0.7 if performance_score > 0 else 0.3
        
        explanation = {
            'performance_score': performance_score,
            'team_ranking': team_ranking
        }
        
        return score, confidence, explanation


class ProximityScorer(ComponentScorer):
    """
    Proximity (X) Component - Commercial readiness and deal activity
    
    Factors:
    - Existing NIL deals (count and value)
    - Brand partnerships
    - Market attractiveness (school location, brand)
    - Agent/representation
    """
    
    def score(
        self,
        athlete_id: uuid.UUID,
        features: Dict[str, Any],
        as_of_date: date
    ) -> Tuple[float, float, Dict[str, Any]]:
        
        raw = features.get('raw_metrics', {})
        
        # Extract NIL metrics
        deal_count = raw.get('nil_deal_count', 0)
        total_deal_value = raw.get('nil_total_deal_value', 0)
        unique_brands = raw.get('nil_unique_brands', 0)
        verification_rate = raw.get('nil_verification_rate', 0)
        
        # Calculate sub-scores
        deal_count_score = min(100, deal_count * 15)  # 7 deals = 100
        deal_value_score = self._score_deal_value(total_deal_value)
        brand_diversity_score = min(100, unique_brands * 20)  # 5 brands = 100
        
        # Weighted combination
        score = (
            deal_count_score * 0.4 +
            deal_value_score * 0.4 +
            brand_diversity_score * 0.2
        )
        
        # Confidence based on verification
        confidence = 0.5 + (verification_rate * 0.4)  # 0.5 - 0.9 range
        
        explanation = {
            'deal_count': deal_count,
            'total_deal_value': total_deal_value,
            'unique_brands': unique_brands,
            'deal_count_score': deal_count_score,
            'deal_value_score': deal_value_score
        }
        
        return min(100, max(0, score)), confidence, explanation
    
    def _score_deal_value(self, total_value: float) -> float:
        """Score based on total deal value"""
        if total_value <= 0:
            return 0
        
        # Log scale: $10K = 30, $100K = 60, $1M = 90
        score = 30 * math.log10(max(1, total_value / 10_000) + 1)
        return min(100, score)


class VelocityScorer(ComponentScorer):
    """
    Velocity (V) Component - Momentum and growth
    
    Factors:
    - Follower growth rate
    - Valuation trend
    - Deal velocity (recent vs historical)
    - Google Trends momentum
    - Performance trajectory
    """
    
    def score(
        self,
        athlete_id: uuid.UUID,
        features: Dict[str, Any],
        as_of_date: date
    ) -> Tuple[float, float, Dict[str, Any]]:
        
        derived = features.get('derived_metrics', {})
        
        # Extract trend metrics
        valuation_trend = derived.get('valuation_trend_slope', 0)
        growth_60d = derived.get('valuation_growth_60d', 0)
        deal_acceleration = derived.get('deal_acceleration', 1.0)
        
        # Calculate sub-scores
        trend_score = self._score_trend(valuation_trend)
        growth_score = self._score_growth(growth_60d)
        acceleration_score = self._score_acceleration(deal_acceleration)
        
        # Weighted combination
        score = (
            trend_score * 0.4 +
            growth_score * 0.4 +
            acceleration_score * 0.2
        )
        
        # Confidence based on data stability
        volatility = derived.get('valuation_volatility', 0)
        confidence = max(0.3, 0.9 - volatility)  # High volatility = lower confidence
        
        explanation = {
            'valuation_trend': valuation_trend,
            'growth_60d': growth_60d * 100,  # As percentage
            'deal_acceleration': deal_acceleration,
            'trend_score': trend_score,
            'growth_score': growth_score
        }
        
        return min(100, max(0, score)), confidence, explanation
    
    def _score_trend(self, slope: float) -> float:
        """Score based on trend slope"""
        # Positive slope = positive score, negative = negative score
        # Normalize to 0-100 scale
        score = 50 + (slope * 10)  # Adjust scale as needed
        return min(100, max(0, score))
    
    def _score_growth(self, growth_rate: float) -> float:
        """Score based on growth rate"""
        # 0% = 50, +50% = 100, -50% = 0
        score = 50 + (growth_rate * 100)
        return min(100, max(0, score))
    
    def _score_acceleration(self, acceleration: float) -> float:
        """Score based on deal acceleration"""
        # acceleration = 1.0 (steady) = 50
        # acceleration > 1.0 (accelerating) = higher
        # acceleration < 1.0 (decelerating) = lower
        score = 50 * acceleration
        return min(100, max(0, score))


class RiskScorer(ComponentScorer):
    """
    Risk (R) Component - Risk factors (negative component)
    
    Factors:
    - Injury history
    - Controversies/legal issues
    - Academic standing/eligibility
    - Transfer portal risk
    - Fraud score
    - Data quality issues
    """
    
    def score(
        self,
        athlete_id: uuid.UUID,
        features: Dict[str, Any],
        as_of_date: date
    ) -> Tuple[float, float, Dict[str, Any]]:
        
        fraud_adj = features.get('fraud_adjusted_metrics', {})
        
        # Extract risk signals
        fraud_score = fraud_adj.get('fraud_score', 0)
        
        # Risk score (0 = no risk, 100 = high risk)
        # Fraud contributes to risk
        fraud_risk = fraud_score * 30  # Max 30 points from fraud
        
        # Placeholder for other risk factors
        # Would need injury data, controversy tracking, etc.
        injury_risk = 0
        controversy_risk = 0
        
        score = min(100, fraud_risk + injury_risk + controversy_risk)
        
        # Confidence based on data availability
        confidence = 0.6  # Medium confidence without full risk data
        
        explanation = {
            'fraud_score': fraud_score,
            'fraud_risk': fraud_risk,
            'injury_risk': injury_risk,
            'controversy_risk': controversy_risk
        }
        
        return score, confidence, explanation


# Factory function
def get_component_scorers() -> Dict[str, ComponentScorer]:
    """Get all component scorers"""
    return {
        'brand': BrandScorer(),
        'proof': ProofScorer(),
        'proximity': ProximityScorer(),
        'velocity': VelocityScorer(),
        'risk': RiskScorer()
    }
