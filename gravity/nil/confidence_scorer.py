"""
Confidence Scoring System
Calculates field-level confidence scores based on:
- Source reliability
- Recency decay
- Cross-source agreement
- Anomaly detection
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
from datetime import datetime, timedelta
import math
import statistics
import uuid

from gravity.nil.source_reliability import get_source_reliability, get_source_tier
from gravity.storage import get_storage_manager
from gravity.db.models import DataQualityMetric, ProvenanceMap

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """
    Calculates confidence scores for data fields
    
    Confidence formula:
    confidence = (reliability * recency * agreement) / (1 + anomaly)
    
    Where:
    - reliability: Source reliability weight (0-1)
    - recency: Time decay factor (0-1)
    - agreement: Cross-source agreement (0-1)
    - anomaly: Anomaly score (0+, higher = more anomalous)
    """
    
    # Configuration
    RECENCY_HALF_LIFE_DAYS = 90  # Data loses half its recency weight after 90 days
    ANOMALY_ZSCORE_THRESHOLD = 3.0  # Z-score threshold for anomalies
    MIN_SOURCES_FOR_AGREEMENT = 2  # Minimum sources needed to calculate agreement
    
    def __init__(self):
        """Initialize confidence scorer"""
        self.storage = get_storage_manager()
        logger.info("Confidence scorer initialized")
    
    # ========================================================================
    # MAIN SCORING METHODS
    # ========================================================================
    
    def calculate_field_confidence(
        self,
        field_value: Any,
        sources: List[Dict[str, Any]],
        field_category: str,
        field_name: str,
        historical_values: Optional[List[float]] = None
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate overall confidence score for a field
        
        Args:
            field_value: The field value
            sources: List of source dicts with 'source', 'timestamp', 'value'
            field_category: Category (e.g., 'brand', 'proof', 'proximity')
            field_name: Field name (e.g., 'nil_valuation', 'followers')
            historical_values: Optional historical values for anomaly detection
        
        Returns:
            Tuple of (overall_confidence, component_scores)
        """
        if not sources:
            return 0.0, {}
        
        # Calculate component scores
        reliability_score = self._calculate_source_reliability(sources)
        recency_score = self._calculate_recency_score(sources)
        agreement_score = self._calculate_cross_source_agreement(sources)
        anomaly_score = self._calculate_anomaly_score(field_value, historical_values)
        
        # Calculate overall confidence
        confidence = (reliability_score * recency_score * agreement_score) / (1 + anomaly_score)
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        
        component_scores = {
            'source_reliability': reliability_score,
            'recency_score': recency_score,
            'cross_source_agreement': agreement_score,
            'anomaly_score': anomaly_score,
            'overall_confidence': confidence
        }
        
        logger.debug(f"Field confidence for {field_name}: {confidence:.3f} "
                    f"(rel={reliability_score:.2f}, rec={recency_score:.2f}, "
                    f"agr={agreement_score:.2f}, anom={anomaly_score:.2f})")
        
        return confidence, component_scores
    
    def score_athlete_data(
        self,
        athlete_id: uuid.UUID,
        data: Dict[str, Any],
        source_mappings: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Score all fields for an athlete
        
        Args:
            athlete_id: Athlete UUID
            data: Dict of field_name -> value
            source_mappings: Dict of field_name -> list of source dicts
        
        Returns:
            Dict of field_name -> confidence_info
        """
        scores = {}
        
        for field_name, field_value in data.items():
            if field_value is None:
                continue
            
            sources = source_mappings.get(field_name, [])
            if not sources:
                # No source info, assign default low confidence
                scores[field_name] = {
                    'value': field_value,
                    'confidence': 0.3,
                    'source_count': 0
                }
                continue
            
            # Calculate confidence
            confidence, components = self.calculate_field_confidence(
                field_value=field_value,
                sources=sources,
                field_category=self._categorize_field(field_name),
                field_name=field_name
            )
            
            scores[field_name] = {
                'value': field_value,
                'confidence': confidence,
                'source_count': len(sources),
                'components': components
            }
        
        return scores
    
    # ========================================================================
    # COMPONENT CALCULATIONS
    # ========================================================================
    
    def _calculate_source_reliability(self, sources: List[Dict[str, Any]]) -> float:
        """
        Calculate weighted average of source reliability
        
        Args:
            sources: List of source dicts
        
        Returns:
            Weighted reliability score (0-1)
        """
        if not sources:
            return 0.0
        
        # Get reliability for each source
        reliabilities = [get_source_reliability(s.get('source', 'unknown')) for s in sources]
        
        # If single source, return its reliability
        if len(reliabilities) == 1:
            return reliabilities[0]
        
        # Multiple sources: use weighted average (higher weights get more influence)
        total_weight = sum(reliabilities)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(r * r for r in reliabilities)  # Weight by reliability itself
        return weighted_sum / total_weight
    
    def _calculate_recency_score(self, sources: List[Dict[str, Any]]) -> float:
        """
        Calculate recency score using exponential decay
        
        Args:
            sources: List of source dicts with 'timestamp'
        
        Returns:
            Recency score (0-1)
        """
        if not sources:
            return 0.0
        
        now = datetime.utcnow()
        recency_scores = []
        
        for source in sources:
            timestamp = source.get('timestamp')
            if not timestamp:
                continue
            
            # Parse timestamp if string
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    continue
            
            # Calculate age in days
            age_days = (now - timestamp).days
            
            # Exponential decay: score = 2^(-age / half_life)
            decay_factor = math.pow(2, -age_days / self.RECENCY_HALF_LIFE_DAYS)
            recency_scores.append(decay_factor)
        
        if not recency_scores:
            return 0.5  # Default if no timestamps
        
        # Return max recency (most recent source)
        return max(recency_scores)
    
    def _calculate_cross_source_agreement(self, sources: List[Dict[str, Any]]) -> float:
        """
        Calculate agreement across multiple sources
        
        Args:
            sources: List of source dicts with 'value'
        
        Returns:
            Agreement score (0-1)
        """
        if len(sources) < self.MIN_SOURCES_FOR_AGREEMENT:
            # Not enough sources for agreement, return neutral
            return 0.7
        
        # Extract numeric values if possible
        values = []
        for source in sources:
            value = source.get('value')
            if value is not None:
                try:
                    values.append(float(value))
                except (ValueError, TypeError):
                    pass
        
        if len(values) < 2:
            # Can't compare non-numeric values, return neutral
            return 0.7
        
        # Calculate coefficient of variation (CV)
        mean_value = statistics.mean(values)
        if mean_value == 0:
            # All zeros or perfect agreement
            return 1.0 if all(v == 0 for v in values) else 0.5
        
        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        cv = std_dev / abs(mean_value)
        
        # Convert CV to agreement score
        # CV = 0 -> perfect agreement (score = 1.0)
        # CV = 0.5 -> moderate disagreement (score = 0.5)
        # CV = 1.0+ -> high disagreement (score = 0.2)
        if cv < 0.1:
            agreement = 1.0
        elif cv < 0.3:
            agreement = 0.9 - (cv - 0.1) * 2.5  # Linear interpolation
        elif cv < 0.5:
            agreement = 0.7 - (cv - 0.3) * 1.5
        else:
            agreement = max(0.2, 0.6 - cv)
        
        return agreement
    
    def _calculate_anomaly_score(
        self,
        field_value: Any,
        historical_values: Optional[List[float]] = None
    ) -> float:
        """
        Calculate anomaly score using Z-score
        
        Args:
            field_value: Current value
            historical_values: Historical values for comparison
        
        Returns:
            Anomaly score (0+ where 0 = no anomaly)
        """
        if not historical_values or len(historical_values) < 3:
            # Not enough history, no anomaly detection
            return 0.0
        
        # Try to convert to numeric
        try:
            numeric_value = float(field_value)
        except (ValueError, TypeError):
            return 0.0  # Can't detect anomalies in non-numeric data
        
        # Calculate mean and standard deviation
        mean = statistics.mean(historical_values)
        std_dev = statistics.stdev(historical_values) if len(historical_values) > 1 else 0
        
        if std_dev == 0:
            # No variation in historical data
            return 1.0 if numeric_value != mean else 0.0
        
        # Calculate Z-score
        z_score = abs((numeric_value - mean) / std_dev)
        
        # Convert Z-score to anomaly score
        if z_score < self.ANOMALY_ZSCORE_THRESHOLD:
            return 0.0  # No anomaly
        
        # Anomaly detected: return scaled score
        anomaly = (z_score - self.ANOMALY_ZSCORE_THRESHOLD) / 2
        return min(anomaly, 3.0)  # Cap at 3.0
    
    # ========================================================================
    # PERSISTENCE
    # ========================================================================
    
    def store_data_quality_metrics(
        self,
        athlete_id: uuid.UUID,
        field_scores: Dict[str, Any]
    ):
        """
        Store data quality metrics in database
        
        Args:
            athlete_id: Athlete UUID
            field_scores: Dict from score_athlete_data()
        """
        try:
            with self.storage.get_session() as session:
                for field_name, score_info in field_scores.items():
                    components = score_info.get('components', {})
                    
                    metric = DataQualityMetric(
                        athlete_id=athlete_id,
                        field_category=self._categorize_field(field_name),
                        field_name=field_name,
                        field_value=str(score_info.get('value')),
                        source_reliability=components.get('source_reliability'),
                        recency_score=components.get('recency_score'),
                        cross_source_agreement=components.get('cross_source_agreement'),
                        anomaly_score=components.get('anomaly_score'),
                        overall_confidence=score_info.get('confidence'),
                        as_of_date=datetime.utcnow().date()
                    )
                    
                    session.add(metric)
                
                session.commit()
                logger.info(f"Stored {len(field_scores)} quality metrics for athlete {athlete_id}")
                
        except Exception as e:
            logger.error(f"Failed to store quality metrics: {e}")
    
    def store_provenance(
        self,
        athlete_id: uuid.UUID,
        field_name: str,
        field_value: Any,
        sources: List[Dict[str, Any]],
        confidence: float
    ):
        """
        Store provenance information
        
        Args:
            athlete_id: Athlete UUID
            field_name: Field name
            field_value: Field value
            sources: List of source dicts
            confidence: Overall confidence score
        """
        try:
            with self.storage.get_session() as session:
                # Check if provenance exists
                existing = session.query(ProvenanceMap).filter(
                    ProvenanceMap.athlete_id == athlete_id,
                    ProvenanceMap.field_name == field_name
                ).first()
                
                if existing:
                    # Update existing
                    existing.field_value = str(field_value)
                    existing.sources = sources
                    existing.confidence = confidence
                    existing.last_updated = datetime.utcnow()
                    existing.version += 1
                else:
                    # Create new
                    provenance = ProvenanceMap(
                        athlete_id=athlete_id,
                        field_name=field_name,
                        field_value=str(field_value),
                        sources=sources,
                        confidence=confidence
                    )
                    session.add(provenance)
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store provenance for {field_name}: {e}")
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _categorize_field(self, field_name: str) -> str:
        """Categorize field into component (B, P, X, V, R)"""
        field_lower = field_name.lower()
        
        # Brand (B)
        if any(x in field_lower for x in ['follower', 'social', 'engagement', 'brand', 'mention']):
            return 'brand'
        
        # Proof (P)
        if any(x in field_lower for x in ['stats', 'performance', 'award', 'ranking', 'recruit']):
            return 'proof'
        
        # Proximity (X)
        if any(x in field_lower for x in ['nil', 'deal', 'endorsement', 'sponsor', 'partnership']):
            return 'proximity'
        
        # Velocity (V)
        if any(x in field_lower for x in ['growth', 'trend', 'momentum', 'velocity']):
            return 'velocity'
        
        # Risk (R)
        if any(x in field_lower for x in ['risk', 'injury', 'controversy', 'violation']):
            return 'risk'
        
        # Default to identity
        return 'identity'


# Convenience function
def calculate_confidence(
    field_value: Any,
    sources: List[Dict[str, Any]],
    field_name: str
) -> float:
    """
    Calculate confidence score for a field
    
    Args:
        field_value: The field value
        sources: List of source dicts
        field_name: Field name
    
    Returns:
        Confidence score (0-1)
    """
    scorer = ConfidenceScorer()
    confidence, _ = scorer.calculate_field_confidence(
        field_value, sources, 'unknown', field_name
    )
    return confidence
