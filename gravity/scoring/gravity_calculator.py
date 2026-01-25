"""
Gravity Score Calculator
Combines B, P, X, V, R components into final Gravity score
"""

from typing import Dict, Any, Tuple
import logging
import uuid
from datetime import date

from gravity.storage import get_storage_manager
from gravity.db.models import GravityScore, FeatureSnapshot
from gravity.scoring.component_scorers import get_component_scorers

logger = logging.getLogger(__name__)


class GravityCalculator:
    """
    Calculates Gravity Score from component scores
    
    Formula:
    G_raw = wB*B + wP*P + wX*X + wV*V - wR*R
    
    G_conf = (wB*cB*B + wP*cP*P + wX*cX*X + wV*cV*V - wR*cR*R) / 
             (wB*cB + wP*cP + wX*cX + wV*cV + wR*cR)
    
    Where:
    - B, P, X, V, R are component scores (0-100)
    - cB, cP, cX, cV, cR are component confidences (0-1)
    - w are weights
    """
    
    # Component weights (should sum to ~1.0)
    WEIGHTS = {
        'brand': 0.25,      # wB
        'proof': 0.25,      # wP
        'proximity': 0.20,  # wX
        'velocity': 0.15,   # wV
        'risk': 0.15        # wR (subtracted)
    }
    
    def __init__(self):
        """Initialize Gravity calculator"""
        self.storage = get_storage_manager()
        self.component_scorers = get_component_scorers()
        logger.info("Gravity calculator initialized")
    
    def calculate_gravity_score(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> Dict[str, Any]:
        """
        Calculate complete Gravity score
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season identifier
            as_of_date: Date for scoring
        
        Returns:
            Complete scoring dict
        """
        logger.info(f"Calculating Gravity score for athlete {athlete_id}")
        
        # Get features
        features = self._get_features(athlete_id, season_id, as_of_date)
        if not features:
            logger.warning(f"No features found for athlete {athlete_id}")
            return self._default_score()
        
        # Calculate component scores
        components = {}
        confidences = {}
        explanations = {}
        
        for name, scorer in self.component_scorers.items():
            score, confidence, explanation = scorer.score(athlete_id, features, as_of_date)
            components[name] = score
            confidences[name] = confidence
            explanations[name] = explanation
        
        # Calculate raw Gravity score
        g_raw = self._calculate_raw_score(components)
        
        # Calculate confidence-weighted Gravity score
        g_conf = self._calculate_confidence_weighted_score(components, confidences)
        
        # Calculate average confidence
        avg_confidence = sum(confidences.values()) / len(confidences)
        
        result = {
            'gravity_raw': g_raw,
            'gravity_conf': g_conf,
            'components': components,
            'confidences': confidences,
            'average_confidence': avg_confidence,
            'explanations': explanations,
            'evidence': self._generate_evidence(components, confidences, explanations)
        }
        
        logger.info(f"Gravity score calculated: G_conf={g_conf:.2f} (raw={g_raw:.2f})")
        
        return result
    
    def calculate_and_store(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> uuid.UUID:
        """
        Calculate and store Gravity score
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season identifier
            as_of_date: Date for scoring
        
        Returns:
            Score UUID
        """
        # Calculate
        result = self.calculate_gravity_score(athlete_id, season_id, as_of_date)
        
        # Store
        return self._store_score(athlete_id, season_id, as_of_date, result)
    
    def _calculate_raw_score(self, components: Dict[str, float]) -> float:
        """Calculate raw Gravity score (without confidence weighting)"""
        score = (
            self.WEIGHTS['brand'] * components['brand'] +
            self.WEIGHTS['proof'] * components['proof'] +
            self.WEIGHTS['proximity'] * components['proximity'] +
            self.WEIGHTS['velocity'] * components['velocity'] -
            self.WEIGHTS['risk'] * components['risk']
        )
        
        return max(0, min(100, score))
    
    def _calculate_confidence_weighted_score(
        self,
        components: Dict[str, float],
        confidences: Dict[str, float]
    ) -> float:
        """Calculate confidence-weighted Gravity score"""
        
        # Numerator: weighted sum of confidence * component * score
        numerator = (
            self.WEIGHTS['brand'] * confidences['brand'] * components['brand'] +
            self.WEIGHTS['proof'] * confidences['proof'] * components['proof'] +
            self.WEIGHTS['proximity'] * confidences['proximity'] * components['proximity'] +
            self.WEIGHTS['velocity'] * confidences['velocity'] * components['velocity'] -
            self.WEIGHTS['risk'] * confidences['risk'] * components['risk']
        )
        
        # Denominator: sum of weighted confidences
        denominator = (
            self.WEIGHTS['brand'] * confidences['brand'] +
            self.WEIGHTS['proof'] * confidences['proof'] +
            self.WEIGHTS['proximity'] * confidences['proximity'] +
            self.WEIGHTS['velocity'] * confidences['velocity'] +
            self.WEIGHTS['risk'] * confidences['risk']
        )
        
        if denominator == 0:
            return 0
        
        score = numerator / denominator
        
        return max(0, min(100, score))
    
    def _get_features(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> Optional[Dict[str, Any]]:
        """Get feature snapshot for athlete"""
        try:
            with self.storage.get_session() as session:
                snapshot = session.query(FeatureSnapshot).filter(
                    FeatureSnapshot.athlete_id == athlete_id,
                    FeatureSnapshot.season_id == season_id,
                    FeatureSnapshot.as_of_date == as_of_date
                ).first()
                
                if snapshot:
                    return snapshot.features
                
                # Try most recent snapshot
                snapshot = session.query(FeatureSnapshot).filter(
                    FeatureSnapshot.athlete_id == athlete_id,
                    FeatureSnapshot.season_id == season_id
                ).order_by(FeatureSnapshot.as_of_date.desc()).first()
                
                return snapshot.features if snapshot else None
                
        except Exception as e:
            logger.error(f"Failed to get features: {e}")
            return None
    
    def _store_score(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date,
        result: Dict[str, Any]
    ) -> uuid.UUID:
        """Store Gravity score in database"""
        try:
            with self.storage.get_session() as session:
                # Check if exists
                existing = session.query(GravityScore).filter(
                    GravityScore.athlete_id == athlete_id,
                    GravityScore.season_id == season_id,
                    GravityScore.as_of_date == as_of_date
                ).first()
                
                if existing:
                    # Update
                    existing.brand_score = result['components']['brand']
                    existing.proof_score = result['components']['proof']
                    existing.proximity_score = result['components']['proximity']
                    existing.velocity_score = result['components']['velocity']
                    existing.risk_score = result['components']['risk']
                    existing.brand_confidence = result['confidences']['brand']
                    existing.proof_confidence = result['confidences']['proof']
                    existing.proximity_confidence = result['confidences']['proximity']
                    existing.velocity_confidence = result['confidences']['velocity']
                    existing.risk_confidence = result['confidences']['risk']
                    existing.gravity_raw = result['gravity_raw']
                    existing.gravity_conf = result['gravity_conf']
                    existing.average_confidence = result['average_confidence']
                    existing.explanations = result['explanations']
                    existing.evidence = result['evidence']
                    score_id = existing.score_id
                else:
                    # Create
                    score = GravityScore(
                        athlete_id=athlete_id,
                        season_id=season_id,
                        as_of_date=as_of_date,
                        brand_score=result['components']['brand'],
                        proof_score=result['components']['proof'],
                        proximity_score=result['components']['proximity'],
                        velocity_score=result['components']['velocity'],
                        risk_score=result['components']['risk'],
                        brand_confidence=result['confidences']['brand'],
                        proof_confidence=result['confidences']['proof'],
                        proximity_confidence=result['confidences']['proximity'],
                        velocity_confidence=result['confidences']['velocity'],
                        risk_confidence=result['confidences']['risk'],
                        gravity_raw=result['gravity_raw'],
                        gravity_conf=result['gravity_conf'],
                        average_confidence=result['average_confidence'],
                        explanations=result['explanations'],
                        evidence=result['evidence']
                    )
                    session.add(score)
                    session.flush()
                    score_id = score.score_id
                
                session.commit()
                logger.info(f"Stored Gravity score: {score_id}")
                return score_id
                
        except Exception as e:
            logger.error(f"Failed to store Gravity score: {e}")
            raise
    
    def _generate_evidence(
        self,
        components: Dict[str, float],
        confidences: Dict[str, float],
        explanations: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate evidence list for Gravity score"""
        evidence = []
        
        # Top drivers (components with highest weighted scores)
        weighted_scores = [
            (name, components[name] * self.WEIGHTS[name], confidences[name])
            for name in components.keys()
        ]
        weighted_scores.sort(key=lambda x: x[1], reverse=True)
        
        for name, weighted_score, confidence in weighted_scores[:3]:
            evidence.append({
                'component': name.title(),
                'score': components[name],
                'weighted_contribution': weighted_score,
                'confidence': confidence,
                'explanation': explanations.get(name, {})
            })
        
        return evidence
    
    def _default_score(self) -> Dict[str, Any]:
        """Return default score when no data available"""
        return {
            'gravity_raw': 0,
            'gravity_conf': 0,
            'components': {
                'brand': 0,
                'proof': 0,
                'proximity': 0,
                'velocity': 0,
                'risk': 0
            },
            'confidences': {
                'brand': 0,
                'proof': 0,
                'proximity': 0,
                'velocity': 0,
                'risk': 0
            },
            'average_confidence': 0,
            'explanations': {},
            'evidence': []
        }


# Convenience function
def calculate_gravity_score(
    athlete_id: uuid.UUID,
    season_id: str,
    as_of_date: date
) -> Dict[str, Any]:
    """
    Calculate Gravity score for athlete
    
    Args:
        athlete_id: Athlete UUID
        season_id: Season identifier
        as_of_date: Date for scoring
    
    Returns:
        Gravity score dict
    """
    calculator = GravityCalculator()
    return calculator.calculate_gravity_score(athlete_id, season_id, as_of_date)
