"""
Anomaly Detector
Detects suspicious or anomalous data patterns
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
import statistics
import uuid
from datetime import datetime, timedelta

from gravity.storage import get_storage_manager
from gravity.db.models import NILValuation, NILDeal

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detects anomalies in athlete data
    
    Anomaly types:
    - Statistical outliers (Z-score > 3)
    - Sudden jumps (> 3 std devs from recent average)
    - Logical inconsistencies (deal value > total valuation)
    - Suspicious patterns (too many deals, unrealistic growth)
    """
    
    # Thresholds
    ZSCORE_THRESHOLD = 3.0
    SUDDEN_JUMP_THRESHOLD = 3.0
    MAX_REASONABLE_VALUATION = 10_000_000  # $10M (very high but possible)
    MAX_DEAL_VALUE_RATIO = 0.8  # Single deal shouldn't exceed 80% of total valuation
    MAX_DEALS_PER_MONTH = 10  # More than 10 deals/month is suspicious
    
    def __init__(self):
        """Initialize anomaly detector"""
        self.storage = get_storage_manager()
        logger.info("Anomaly detector initialized")
    
    # ========================================================================
    # DETECTION METHODS
    # ========================================================================
    
    def detect_valuation_anomalies(
        self,
        athlete_id: uuid.UUID,
        new_valuation: float,
        source: str
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in NIL valuation
        
        Args:
            athlete_id: Athlete UUID
            new_valuation: New valuation amount
            source: Source of valuation
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check if valuation is unreasonably high
        if new_valuation > self.MAX_REASONABLE_VALUATION:
            anomalies.append({
                'type': 'unreasonable_value',
                'severity': 'high',
                'message': f'Valuation ${new_valuation:,.0f} exceeds reasonable maximum',
                'field': 'nil_valuation',
                'value': new_valuation
            })
        
        # Get historical valuations
        historical = self._get_historical_valuations(athlete_id)
        
        if len(historical) >= 3:
            # Check for statistical outlier
            outlier_info = self._check_statistical_outlier(new_valuation, historical)
            if outlier_info:
                anomalies.append(outlier_info)
            
            # Check for sudden jump
            jump_info = self._check_sudden_jump(new_valuation, historical)
            if jump_info:
                anomalies.append(jump_info)
        
        return anomalies
    
    def detect_deal_anomalies(
        self,
        athlete_id: uuid.UUID,
        deal_value: Optional[float],
        brand: str,
        athlete_valuation: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in NIL deal
        
        Args:
            athlete_id: Athlete UUID
            deal_value: Deal value
            brand: Brand name
            athlete_valuation: Athlete's total valuation
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check deal value vs total valuation
        if deal_value and athlete_valuation:
            if deal_value > athlete_valuation * self.MAX_DEAL_VALUE_RATIO:
                anomalies.append({
                    'type': 'deal_exceeds_valuation',
                    'severity': 'medium',
                    'message': f'Deal value ${deal_value:,.0f} exceeds {self.MAX_DEAL_VALUE_RATIO*100}% of total valuation ${athlete_valuation:,.0f}',
                    'field': 'deal_value',
                    'value': deal_value
                })
        
        # Check deal frequency
        recent_deals_count = self._count_recent_deals(athlete_id, days=30)
        if recent_deals_count > self.MAX_DEALS_PER_MONTH:
            anomalies.append({
                'type': 'excessive_deals',
                'severity': 'medium',
                'message': f'Athlete has {recent_deals_count} deals in past 30 days (threshold: {self.MAX_DEALS_PER_MONTH})',
                'field': 'deal_count',
                'value': recent_deals_count
            })
        
        # Check for duplicate deals with same brand
        duplicate_info = self._check_duplicate_deals(athlete_id, brand)
        if duplicate_info:
            anomalies.append(duplicate_info)
        
        return anomalies
    
    def detect_social_metric_anomalies(
        self,
        athlete_id: uuid.UUID,
        metric_name: str,
        new_value: int,
        platform: str
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in social media metrics
        
        Args:
            athlete_id: Athlete UUID
            metric_name: Metric name (e.g., 'followers')
            new_value: New metric value
            platform: Social platform
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check for unrealistic growth
        # (e.g., gaining 100K followers overnight)
        # This would require historical social metrics tracking
        # For now, we'll implement basic checks
        
        # Check for unreasonably high engagement rates
        if 'engagement' in metric_name.lower():
            if new_value > 50:  # >50% engagement rate is suspicious
                anomalies.append({
                    'type': 'unrealistic_engagement',
                    'severity': 'high',
                    'message': f'Engagement rate {new_value}% is unusually high (possible bot activity)',
                    'field': metric_name,
                    'value': new_value
                })
        
        return anomalies
    
    def detect_all_anomalies(
        self,
        athlete_id: uuid.UUID,
        data: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect all anomalies in athlete data
        
        Args:
            athlete_id: Athlete UUID
            data: Complete athlete data dict
        
        Returns:
            Dict of field_name -> list of anomalies
        """
        all_anomalies = {}
        
        # Check NIL valuation
        if data.get('nil_valuation'):
            valuation_anomalies = self.detect_valuation_anomalies(
                athlete_id,
                data['nil_valuation'],
                data.get('nil_valuation_source', 'unknown')
            )
            if valuation_anomalies:
                all_anomalies['nil_valuation'] = valuation_anomalies
        
        # Check NIL deals
        for i, deal in enumerate(data.get('nil_deals', [])):
            deal_anomalies = self.detect_deal_anomalies(
                athlete_id,
                deal.get('value'),
                deal.get('brand', 'Unknown'),
                data.get('nil_valuation')
            )
            if deal_anomalies:
                all_anomalies[f'nil_deal_{i}'] = deal_anomalies
        
        # Check social metrics
        for platform, metrics in data.get('social_metrics', {}).items():
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    social_anomalies = self.detect_social_metric_anomalies(
                        athlete_id, metric_name, value, platform
                    )
                    if social_anomalies:
                        all_anomalies[f'{platform}_{metric_name}'] = social_anomalies
        
        return all_anomalies
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_historical_valuations(self, athlete_id: uuid.UUID) -> List[float]:
        """Get historical valuations for athlete"""
        try:
            with self.storage.get_session() as session:
                valuations = session.query(NILValuation).filter(
                    NILValuation.athlete_id == athlete_id
                ).order_by(NILValuation.as_of_date.desc()).limit(20).all()
                
                return [float(v.valuation_amount) for v in valuations if v.valuation_amount]
        except Exception as e:
            logger.error(f"Failed to get historical valuations: {e}")
            return []
    
    def _check_statistical_outlier(
        self,
        new_value: float,
        historical_values: List[float]
    ) -> Optional[Dict[str, Any]]:
        """Check if value is statistical outlier using Z-score"""
        if len(historical_values) < 3:
            return None
        
        mean = statistics.mean(historical_values)
        std_dev = statistics.stdev(historical_values)
        
        if std_dev == 0:
            return None
        
        z_score = abs((new_value - mean) / std_dev)
        
        if z_score > self.ZSCORE_THRESHOLD:
            return {
                'type': 'statistical_outlier',
                'severity': 'medium',
                'message': f'Value ${new_value:,.0f} is {z_score:.1f} standard deviations from mean ${mean:,.0f}',
                'field': 'nil_valuation',
                'value': new_value,
                'z_score': z_score
            }
        
        return None
    
    def _check_sudden_jump(
        self,
        new_value: float,
        historical_values: List[float]
    ) -> Optional[Dict[str, Any]]:
        """Check for sudden jump from recent average"""
        if len(historical_values) < 2:
            return None
        
        # Use last 3 values as recent
        recent = historical_values[:3]
        recent_avg = statistics.mean(recent)
        
        if recent_avg == 0:
            return None
        
        # Calculate percentage change
        pct_change = abs((new_value - recent_avg) / recent_avg)
        
        # If more than 200% jump (3x), flag it
        if pct_change > 2.0:
            return {
                'type': 'sudden_jump',
                'severity': 'medium',
                'message': f'Value ${new_value:,.0f} represents {pct_change*100:.0f}% change from recent average ${recent_avg:,.0f}',
                'field': 'nil_valuation',
                'value': new_value,
                'percent_change': pct_change * 100
            }
        
        return None
    
    def _count_recent_deals(self, athlete_id: uuid.UUID, days: int = 30) -> int:
        """Count deals in recent period"""
        try:
            cutoff_date = datetime.utcnow().date() - timedelta(days=days)
            
            with self.storage.get_session() as session:
                count = session.query(NILDeal).filter(
                    NILDeal.athlete_id == athlete_id,
                    NILDeal.announced_date >= cutoff_date
                ).count()
                
                return count
        except Exception as e:
            logger.error(f"Failed to count recent deals: {e}")
            return 0
    
    def _check_duplicate_deals(
        self,
        athlete_id: uuid.UUID,
        brand: str
    ) -> Optional[Dict[str, Any]]:
        """Check for duplicate deals with same brand"""
        try:
            with self.storage.get_session() as session:
                # Look for recent deals with same brand
                cutoff_date = datetime.utcnow().date() - timedelta(days=180)
                
                existing_deals = session.query(NILDeal).filter(
                    NILDeal.athlete_id == athlete_id,
                    NILDeal.brand.ilike(brand),
                    NILDeal.announced_date >= cutoff_date
                ).count()
                
                if existing_deals > 1:
                    return {
                        'type': 'duplicate_deal',
                        'severity': 'low',
                        'message': f'Multiple recent deals with {brand} (count: {existing_deals})',
                        'field': 'brand',
                        'value': brand
                    }
        except Exception as e:
            logger.error(f"Failed to check duplicate deals: {e}")
        
        return None
    
    # ========================================================================
    # REPORTING
    # ========================================================================
    
    def generate_anomaly_report(
        self,
        athlete_id: uuid.UUID,
        anomalies: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Generate human-readable anomaly report
        
        Args:
            athlete_id: Athlete UUID
            anomalies: Dict from detect_all_anomalies()
        
        Returns:
            Report dict
        """
        total_anomalies = sum(len(v) for v in anomalies.values())
        
        # Count by severity
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        for field_anomalies in anomalies.values():
            for anomaly in field_anomalies:
                severity = anomaly.get('severity', 'low')
                severity_counts[severity] += 1
        
        # Generate summary
        report = {
            'athlete_id': str(athlete_id),
            'generated_at': datetime.utcnow().isoformat(),
            'total_anomalies': total_anomalies,
            'severity_counts': severity_counts,
            'requires_review': severity_counts['high'] > 0,
            'anomalies_by_field': anomalies,
            'recommendations': self._generate_recommendations(anomalies)
        }
        
        return report
    
    def _generate_recommendations(
        self,
        anomalies: Dict[str, List[Dict[str, Any]]]
    ) -> List[str]:
        """Generate recommendations based on detected anomalies"""
        recommendations = []
        
        # Check for high severity anomalies
        has_high_severity = any(
            anomaly.get('severity') == 'high'
            for field_anomalies in anomalies.values()
            for anomaly in field_anomalies
        )
        
        if has_high_severity:
            recommendations.append("Manual review required due to high-severity anomalies")
        
        # Check for valuation anomalies
        if 'nil_valuation' in anomalies:
            recommendations.append("Verify NIL valuation with additional sources")
        
        # Check for deal anomalies
        deal_anomalies = [k for k in anomalies.keys() if k.startswith('nil_deal_')]
        if deal_anomalies:
            recommendations.append(f"Review {len(deal_anomalies)} flagged NIL deals")
        
        # Check for social metric anomalies
        social_anomalies = [k for k in anomalies.keys() if any(p in k for p in ['instagram', 'twitter', 'tiktok'])]
        if social_anomalies:
            recommendations.append("Investigate social media metrics for potential bot activity")
        
        if not recommendations:
            recommendations.append("No major concerns detected")
        
        return recommendations


# Convenience function
def detect_anomalies(athlete_id: uuid.UUID, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect anomalies in athlete data
    
    Args:
        athlete_id: Athlete UUID
        data: Athlete data dict
    
    Returns:
        Anomaly report
    """
    detector = AnomalyDetector()
    anomalies = detector.detect_all_anomalies(athlete_id, data)
    return detector.generate_anomaly_report(athlete_id, anomalies)
