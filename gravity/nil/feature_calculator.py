"""
Feature Calculator
Computes raw, derived, and fraud-adjusted metrics for feature store
"""

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta, date
import statistics
import uuid

from gravity.storage import get_storage_manager
from gravity.db.models import (
    FeatureSnapshot, NILValuation, NILDeal, GravityScore, AthleteEvent
)

logger = logging.getLogger(__name__)


class FeatureCalculator:
    """
    Calculates features for athlete scoring
    
    Feature types:
    - Raw metrics: Direct measurements (followers, engagement, deal count)
    - Derived metrics: Calculated from raw (growth rate, trend, volatility)
    - Fraud-adjusted metrics: Adjusted for suspicious activity
    """
    
    def __init__(self):
        """Initialize feature calculator"""
        self.storage = get_storage_manager()
        logger.info("Feature calculator initialized")
    
    # ========================================================================
    # MAIN CALCULATION METHODS
    # ========================================================================
    
    def calculate_all_features(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate all features for an athlete
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season identifier
            as_of_date: Date for point-in-time calculation
        
        Returns:
            Complete feature dict
        """
        if not as_of_date:
            as_of_date = date.today()
        
        logger.info(f"Calculating features for athlete {athlete_id} as of {as_of_date}")
        
        features = {
            'calculated_at': datetime.utcnow().isoformat(),
            'as_of_date': as_of_date.isoformat(),
            'raw_metrics': {},
            'derived_metrics': {},
            'fraud_adjusted_metrics': {}
        }
        
        # Calculate raw metrics
        features['raw_metrics'] = self._calculate_raw_metrics(athlete_id, as_of_date)
        
        # Calculate derived metrics
        features['derived_metrics'] = self._calculate_derived_metrics(athlete_id, as_of_date)
        
        # Calculate fraud-adjusted metrics
        features['fraud_adjusted_metrics'] = self._calculate_fraud_adjusted_metrics(
            features['raw_metrics'],
            features['derived_metrics']
        )
        
        return features
    
    def store_features(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        features: Dict[str, Any],
        as_of_date: Optional[date] = None
    ) -> uuid.UUID:
        """
        Store features in database
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season identifier
            features: Features dict from calculate_all_features()
            as_of_date: Date for snapshot
        
        Returns:
            Snapshot UUID
        """
        if not as_of_date:
            as_of_date = date.today()
        
        try:
            with self.storage.get_session() as session:
                # Check if snapshot exists
                existing = session.query(FeatureSnapshot).filter(
                    FeatureSnapshot.athlete_id == athlete_id,
                    FeatureSnapshot.season_id == season_id,
                    FeatureSnapshot.as_of_date == as_of_date
                ).first()
                
                if existing:
                    # Update existing
                    existing.features = features
                    existing.raw_metrics = features.get('raw_metrics')
                    existing.derived_metrics = features.get('derived_metrics')
                    existing.fraud_adjusted_metrics = features.get('fraud_adjusted_metrics')
                    snapshot_id = existing.snapshot_id
                else:
                    # Create new
                    snapshot = FeatureSnapshot(
                        athlete_id=athlete_id,
                        season_id=season_id,
                        as_of_date=as_of_date,
                        features=features,
                        raw_metrics=features.get('raw_metrics'),
                        derived_metrics=features.get('derived_metrics'),
                        fraud_adjusted_metrics=features.get('fraud_adjusted_metrics')
                    )
                    session.add(snapshot)
                    session.flush()
                    snapshot_id = snapshot.snapshot_id
                
                session.commit()
                logger.info(f"Stored features for athlete {athlete_id}: {snapshot_id}")
                return snapshot_id
                
        except Exception as e:
            logger.error(f"Failed to store features: {e}")
            raise
    
    # ========================================================================
    # RAW METRICS
    # ========================================================================
    
    def _calculate_raw_metrics(
        self,
        athlete_id: uuid.UUID,
        as_of_date: date
    ) -> Dict[str, Any]:
        """Calculate raw metrics from database"""
        metrics = {}
        
        # NIL metrics
        nil_metrics = self._get_nil_metrics(athlete_id, as_of_date)
        metrics.update(nil_metrics)
        
        # Social metrics (would come from social collectors)
        # For now, placeholder
        metrics['social_followers'] = 0
        metrics['social_engagement_rate'] = 0
        metrics['social_post_frequency'] = 0
        
        # Performance metrics (would come from stats collectors)
        metrics['performance_score'] = 0
        metrics['team_ranking'] = 0
        
        return metrics
    
    def _get_nil_metrics(
        self,
        athlete_id: uuid.UUID,
        as_of_date: date
    ) -> Dict[str, Any]:
        """Get NIL-specific metrics"""
        metrics = {}
        
        try:
            with self.storage.get_session() as session:
                # Latest valuation
                latest_valuation = session.query(NILValuation).filter(
                    NILValuation.athlete_id == athlete_id,
                    NILValuation.as_of_date <= as_of_date
                ).order_by(NILValuation.as_of_date.desc()).first()
                
                if latest_valuation:
                    metrics['nil_valuation'] = float(latest_valuation.valuation_amount)
                    metrics['nil_ranking'] = latest_valuation.ranking
                else:
                    metrics['nil_valuation'] = 0
                    metrics['nil_ranking'] = None
                
                # Deal counts and total value
                deals = session.query(NILDeal).filter(
                    NILDeal.athlete_id == athlete_id,
                    NILDeal.announced_date <= as_of_date
                ).all()
                
                metrics['nil_deal_count'] = len(deals)
                
                # Total deal value (where available)
                deal_values = [float(d.deal_value) for d in deals if d.deal_value]
                metrics['nil_total_deal_value'] = sum(deal_values)
                metrics['nil_avg_deal_value'] = statistics.mean(deal_values) if deal_values else 0
                
                # Deal diversity (unique brands)
                unique_brands = set(d.brand for d in deals)
                metrics['nil_unique_brands'] = len(unique_brands)
                
                # Deal types
                deal_types = {}
                for deal in deals:
                    deal_type = deal.deal_type or 'Unknown'
                    deal_types[deal_type] = deal_types.get(deal_type, 0) + 1
                metrics['nil_deal_types'] = deal_types
                
                # Verified vs unverified
                verified_count = sum(1 for d in deals if d.is_verified)
                metrics['nil_verified_deal_count'] = verified_count
                metrics['nil_verification_rate'] = verified_count / len(deals) if deals else 0
                
        except Exception as e:
            logger.error(f"Failed to get NIL metrics: {e}")
        
        return metrics
    
    # ========================================================================
    # DERIVED METRICS
    # ========================================================================
    
    def _calculate_derived_metrics(
        self,
        athlete_id: uuid.UUID,
        as_of_date: date
    ) -> Dict[str, Any]:
        """Calculate derived metrics from historical data"""
        metrics = {}
        
        # NIL valuation trends
        valuation_trends = self._calculate_valuation_trends(athlete_id, as_of_date)
        metrics.update(valuation_trends)
        
        # Deal velocity
        deal_velocity = self._calculate_deal_velocity(athlete_id, as_of_date)
        metrics.update(deal_velocity)
        
        # Growth metrics
        growth_metrics = self._calculate_growth_metrics(athlete_id, as_of_date)
        metrics.update(growth_metrics)
        
        return metrics
    
    def _calculate_valuation_trends(
        self,
        athlete_id: uuid.UUID,
        as_of_date: date
    ) -> Dict[str, Any]:
        """Calculate valuation trend metrics"""
        metrics = {}
        
        try:
            with self.storage.get_session() as session:
                # Get last 90 days of valuations
                cutoff = as_of_date - timedelta(days=90)
                valuations = session.query(NILValuation).filter(
                    NILValuation.athlete_id == athlete_id,
                    NILValuation.as_of_date >= cutoff,
                    NILValuation.as_of_date <= as_of_date
                ).order_by(NILValuation.as_of_date).all()
                
                if len(valuations) < 2:
                    metrics['valuation_trend_slope'] = 0
                    metrics['valuation_volatility'] = 0
                    return metrics
                
                values = [float(v.valuation_amount) for v in valuations]
                
                # Calculate trend (simple linear regression slope)
                n = len(values)
                x = list(range(n))
                x_mean = statistics.mean(x)
                y_mean = statistics.mean(values)
                
                numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
                
                slope = numerator / denominator if denominator != 0 else 0
                metrics['valuation_trend_slope'] = slope
                
                # Calculate volatility (coefficient of variation)
                std_dev = statistics.stdev(values) if len(values) > 1 else 0
                mean_val = statistics.mean(values)
                metrics['valuation_volatility'] = std_dev / mean_val if mean_val > 0 else 0
                
                # Median and percentiles
                sorted_values = sorted(values)
                metrics['valuation_median'] = sorted_values[len(sorted_values) // 2]
                metrics['valuation_p90'] = sorted_values[int(len(sorted_values) * 0.9)]
                
        except Exception as e:
            logger.error(f"Failed to calculate valuation trends: {e}")
            metrics['valuation_trend_slope'] = 0
            metrics['valuation_volatility'] = 0
        
        return metrics
    
    def _calculate_deal_velocity(
        self,
        athlete_id: uuid.UUID,
        as_of_date: date
    ) -> Dict[str, Any]:
        """Calculate deal signing velocity"""
        metrics = {}
        
        try:
            with self.storage.get_session() as session:
                # Deals in last 30, 60, 90 days
                for days in [30, 60, 90]:
                    cutoff = as_of_date - timedelta(days=days)
                    count = session.query(NILDeal).filter(
                        NILDeal.athlete_id == athlete_id,
                        NILDeal.announced_date >= cutoff,
                        NILDeal.announced_date <= as_of_date
                    ).count()
                    
                    metrics[f'deals_last_{days}d'] = count
                    metrics[f'deals_per_month_{days}d'] = count / (days / 30.0)
                
                # Calculate acceleration (30d vs 90d)
                if metrics.get('deals_per_month_30d', 0) > 0 and metrics.get('deals_per_month_90d', 0) > 0:
                    metrics['deal_acceleration'] = (
                        metrics['deals_per_month_30d'] / metrics['deals_per_month_90d']
                    )
                else:
                    metrics['deal_acceleration'] = 1.0
                
        except Exception as e:
            logger.error(f"Failed to calculate deal velocity: {e}")
        
        return metrics
    
    def _calculate_growth_metrics(
        self,
        athlete_id: uuid.UUID,
        as_of_date: date
    ) -> Dict[str, Any]:
        """Calculate growth rate metrics"""
        metrics = {}
        
        try:
            with self.storage.get_session() as session:
                # Compare 30d ago vs 90d ago
                date_30d = as_of_date - timedelta(days=30)
                date_90d = as_of_date - timedelta(days=90)
                
                # Get valuations at these points
                val_30d = session.query(NILValuation).filter(
                    NILValuation.athlete_id == athlete_id,
                    NILValuation.as_of_date <= date_30d
                ).order_by(NILValuation.as_of_date.desc()).first()
                
                val_90d = session.query(NILValuation).filter(
                    NILValuation.athlete_id == athlete_id,
                    NILValuation.as_of_date <= date_90d
                ).order_by(NILValuation.as_of_date.desc()).first()
                
                if val_30d and val_90d and val_90d.valuation_amount > 0:
                    growth = (float(val_30d.valuation_amount) - float(val_90d.valuation_amount)) / float(val_90d.valuation_amount)
                    metrics['valuation_growth_60d'] = growth
                else:
                    metrics['valuation_growth_60d'] = 0
                
        except Exception as e:
            logger.error(f"Failed to calculate growth metrics: {e}")
            metrics['valuation_growth_60d'] = 0
        
        return metrics
    
    # ========================================================================
    # FRAUD-ADJUSTED METRICS
    # ========================================================================
    
    def _calculate_fraud_adjusted_metrics(
        self,
        raw_metrics: Dict[str, Any],
        derived_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate fraud-adjusted metrics"""
        adjusted = {}
        
        # Detect potential fraud signals
        fraud_score = self._calculate_fraud_score(raw_metrics, derived_metrics)
        adjusted['fraud_score'] = fraud_score
        
        # Adjust metrics based on fraud score
        # fraud_score = 0 (no fraud) -> no adjustment
        # fraud_score = 1 (high fraud) -> 50% discount
        discount_factor = 1.0 - (fraud_score * 0.5)
        
        # Adjust key metrics
        adjusted['nil_valuation_adj'] = raw_metrics.get('nil_valuation', 0) * discount_factor
        adjusted['social_followers_adj'] = raw_metrics.get('social_followers', 0) * discount_factor
        adjusted['discount_factor'] = discount_factor
        
        return adjusted
    
    def _calculate_fraud_score(
        self,
        raw_metrics: Dict[str, Any],
        derived_metrics: Dict[str, Any]
    ) -> float:
        """
        Calculate fraud risk score (0-1)
        
        Signals:
        - Low engagement despite high followers
        - Excessive deal velocity
        - High valuation volatility
        - Low verification rate
        """
        signals = []
        
        # Low verification rate
        verification_rate = raw_metrics.get('nil_verification_rate', 1.0)
        if verification_rate < 0.3:
            signals.append(0.3)  # Add 0.3 to fraud score
        
        # High volatility
        volatility = derived_metrics.get('valuation_volatility', 0)
        if volatility > 0.5:
            signals.append(0.2)
        
        # Excessive deal velocity
        deals_per_month = derived_metrics.get('deals_per_month_30d', 0)
        if deals_per_month > 5:
            signals.append(0.3)
        
        # Calculate overall fraud score
        fraud_score = min(1.0, sum(signals))
        
        return fraud_score


# Convenience function
def calculate_and_store_features(
    athlete_id: uuid.UUID,
    season_id: str,
    as_of_date: Optional[date] = None
) -> uuid.UUID:
    """
    Calculate and store features for an athlete
    
    Args:
        athlete_id: Athlete UUID
        season_id: Season identifier
        as_of_date: Optional date for snapshot
    
    Returns:
        Snapshot UUID
    """
    calculator = FeatureCalculator()
    features = calculator.calculate_all_features(athlete_id, season_id, as_of_date)
    return calculator.store_features(athlete_id, season_id, features, as_of_date)
