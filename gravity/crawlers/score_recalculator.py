"""
Score Recalculator
Automatically recalculates Gravity scores when crawler events occur
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import date, datetime

from gravity.storage import get_storage_manager
from gravity.db.models import GravityScore, FeatureSnapshot

logger = logging.getLogger(__name__)


class ScoreRecalculator:
    """
    Recalculates component scores and Gravity scores based on new events
    """
    
    def __init__(self):
        self.storage = get_storage_manager()
        logger.info("Score recalculator initialized")
    
    async def recalculate_scores(
        self,
        athlete_id: uuid.UUID,
        components: Optional[List[str]] = None,
        season_id: Optional[str] = None,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Recalculate scores for an athlete
        
        Args:
            athlete_id: Athlete UUID
            components: Optional list of components to recalculate (if None, recalculates all)
            season_id: Optional season ID (defaults to current season)
            as_of_date: Optional date (defaults to today)
        
        Returns:
            Recalculation results dict
        """
        try:
            if not as_of_date:
                as_of_date = date.today()
            
            if not season_id:
                # Determine current season based on date
                season_id = self._get_current_season(as_of_date)
            
            logger.info(f"Recalculating scores for athlete {athlete_id}, "
                       f"components: {components or 'all'}")
            
            # Step 1: Recalculate features if needed
            await self._recalculate_features(athlete_id, season_id, as_of_date)
            
            # Step 2: Get latest features
            features = await self._get_latest_features(athlete_id, season_id, as_of_date)
            
            if not features:
                logger.warning(f"No features found for athlete {athlete_id}")
                return {'success': False, 'error': 'No features found'}
            
            # Step 3: Recalculate component scores
            component_results = {}
            
            if components:
                # Recalculate only specified components
                for component_name in components:
                    score, confidence, explanation = await self._recalculate_component(
                        athlete_id,
                        component_name,
                        features,
                        as_of_date
                    )
                    component_results[component_name] = {
                        'score': score,
                        'confidence': confidence,
                        'explanation': explanation
                    }
            else:
                # Recalculate all components
                all_components = ['brand', 'proof', 'proximity', 'velocity', 'risk']
                for component_name in all_components:
                    score, confidence, explanation = await self._recalculate_component(
                        athlete_id,
                        component_name,
                        features,
                        as_of_date
                    )
                    component_results[component_name] = {
                        'score': score,
                        'confidence': confidence,
                        'explanation': explanation
                    }
            
            # Step 4: Recalculate Gravity score
            gravity_result = await self._recalculate_gravity_score(
                athlete_id,
                season_id,
                as_of_date,
                component_results
            )
            
            # Step 5: Store recalculation record
            await self._store_recalculation_record(
                athlete_id,
                components or ['all'],
                gravity_result
            )
            
            return {
                'success': True,
                'components': component_results,
                'gravity_score': gravity_result
            }
            
        except Exception as e:
            logger.error(f"Score recalculation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _recalculate_features(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> None:
        """Recalculate features from events"""
        try:
            from gravity.nil.feature_calculator import FeatureCalculator
            
            feature_calc = FeatureCalculator()
            
            # Recalculate all features
            features = feature_calc.calculate_all_features(
                athlete_id,
                season_id,
                as_of_date
            )
            
            # Store updated features
            feature_calc.store_features(
                athlete_id,
                season_id,
                features,
                as_of_date
            )
            
            logger.debug(f"Features recalculated for athlete {athlete_id}")
            
        except Exception as e:
            logger.error(f"Feature recalculation failed: {e}")
    
    async def _get_latest_features(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date
    ) -> Optional[Dict[str, Any]]:
        """Get latest feature snapshot"""
        try:
            with self.storage.get_session() as session:
                feature_snapshot = session.query(FeatureSnapshot).filter(
                    FeatureSnapshot.athlete_id == athlete_id,
                    FeatureSnapshot.season_id == season_id,
                    FeatureSnapshot.as_of_date <= as_of_date
                ).order_by(FeatureSnapshot.as_of_date.desc()).first()
                
                if feature_snapshot:
                    return {
                        'raw_metrics': feature_snapshot.raw_metrics or {},
                        'derived_metrics': feature_snapshot.derived_metrics or {},
                        'fraud_adjusted_metrics': feature_snapshot.fraud_adjusted_metrics or {}
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get latest features: {e}")
            return None
    
    async def _recalculate_component(
        self,
        athlete_id: uuid.UUID,
        component_name: str,
        features: Dict[str, Any],
        as_of_date: date
    ) -> tuple:
        """
        Recalculate a single component score
        
        Args:
            athlete_id: Athlete UUID
            component_name: Component name (brand, proof, proximity, velocity, risk)
            features: Feature snapshot
            as_of_date: Date for scoring
        
        Returns:
            Tuple of (score, confidence, explanation)
        """
        try:
            from gravity.scoring.component_scorers import get_component_scorers
            
            scorers = get_component_scorers()
            scorer = scorers.get(component_name)
            
            if not scorer:
                logger.warning(f"Scorer not found for component: {component_name}")
                return 0.0, 0.0, {}
            
            # Calculate score
            score, confidence, explanation = scorer.score(
                athlete_id,
                features,
                as_of_date
            )
            
            return score, confidence, explanation
            
        except Exception as e:
            logger.error(f"Component recalculation failed for {component_name}: {e}")
            return 0.0, 0.0, {}
    
    async def _recalculate_gravity_score(
        self,
        athlete_id: uuid.UUID,
        season_id: str,
        as_of_date: date,
        component_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Recalculate final Gravity score
        
        Args:
            athlete_id: Athlete UUID
            season_id: Season ID
            as_of_date: Date for scoring
            component_results: Component score results
        
        Returns:
            Gravity score result dict
        """
        try:
            from gravity.scoring.gravity_calculator import GravityCalculator
            
            gravity_calc = GravityCalculator()
            
            # Calculate Gravity score
            gravity_result = gravity_calc.calculate_gravity_score(
                athlete_id,
                season_id,
                as_of_date
            )
            
            # Store Gravity score
            gravity_calc.store_gravity_score(
                athlete_id,
                season_id,
                gravity_result,
                as_of_date
            )
            
            return gravity_result
            
        except Exception as e:
            logger.error(f"Gravity score recalculation failed: {e}")
            return {}
    
    async def _store_recalculation_record(
        self,
        athlete_id: uuid.UUID,
        components: List[str],
        gravity_result: Dict[str, Any]
    ) -> None:
        """
        Store score recalculation record
        
        Args:
            athlete_id: Athlete UUID
            components: List of components recalculated
            gravity_result: Gravity score result
        """
        try:
            # This would store in score_recalculations table
            # For now, just log - table will be created in database schema phase
            logger.debug(f"Score recalculation record: athlete={athlete_id}, "
                       f"components={components}, "
                       f"gravity={gravity_result.get('gravity_conf', 0)}")
            
        except Exception as e:
            logger.error(f"Failed to store recalculation record: {e}")
    
    def _get_current_season(self, as_of_date: date) -> str:
        """
        Get current season ID based on date
        
        Args:
            as_of_date: Date
        
        Returns:
            Season ID string (e.g., "2024-25")
        """
        year = as_of_date.year
        month = as_of_date.month
        
        # CFB/NCAAB: Season starts in fall, spans calendar years
        # NFL/NBA: Season starts in fall/winter, spans calendar years
        if month >= 8:  # August-December
            return f"{year}-{str(year+1)[-2:]}"
        else:  # January-July
            return f"{year-1}-{str(year)[-2:]}"
