"""
CFB integration helpers (NIL stubs).

Player ingestion runs from the external scrapers repository.
"""

import logging
from typing import Dict, Any, Optional
import uuid
from datetime import date

from gravity.nil import calculate_and_store_features, run_nil_collection
from gravity.nil.entity_resolution import EntityResolver
from gravity.scoring import calculate_gravity_score

logger = logging.getLogger(__name__)


def _normalize_nil_stub(collection_results: Dict[str, Any], athlete_id: str) -> Dict[str, Any]:
    """Placeholder — gravity.nil.normalization was removed with connector stack."""
    return {"athlete_id": str(athlete_id), "records_created": 0}


def integrate_nil_pipeline(
    player_name: str,
    team: str,
    sport: str = 'football',
    player_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Integrate NIL pipeline into CFB scraper workflow
    
    Intended to run after external CFB scraper produces player payloads.
    
    Args:
        player_name: Name of player
        team: Team/school name
        sport: Sport type
        player_data: Optional existing player data from scraper
    
    Returns:
        Dict with NIL data, Gravity score, and valuation
    """
    logger.info(f"Running NIL pipeline integration for {player_name} ({team})")
    
    result = {
        'player_name': player_name,
        'team': team,
        'success': False,
        'nil_data': None,
        'athlete_id': None,
        'gravity_score': None,
        'valuation': None
    }
    
    try:
        # Step 1: Collect NIL data from all sources
        logger.info(f"Step 1: Collecting NIL data...")
        collection_results = run_nil_collection(player_name, team, sport)
        
        # Step 2: Resolve or create athlete entity
        logger.info(f"Step 2: Resolving athlete entity...")
        resolver = EntityResolver()
        athlete_id, is_new, confidence = resolver.create_or_resolve_athlete(
            name=player_name,
            school=team,
            sport=sport
        )
        result['athlete_id'] = str(athlete_id)
        logger.info(f"Athlete resolved: {athlete_id} (new={is_new}, confidence={confidence:.2f})")
        
        # Step 3: Normalize and store NIL data
        logger.info(f"Step 3: Normalizing and storing NIL data...")
        normalization_summary = _normalize_nil_stub(collection_results, athlete_id)
        result['nil_data'] = {
            'collection_summary': collection_results.get('summary', {}),
            'normalization_summary': normalization_summary
        }
        
        # Step 4: Calculate features
        logger.info(f"Step 4: Calculating features...")
        season_id = "2024-25"  # Get from player_data or config
        try:
            snapshot_id = calculate_and_store_features(athlete_id, season_id)
            logger.info(f"Features calculated: {snapshot_id}")
        except Exception as e:
            logger.warning(f"Feature calculation skipped: {e}")
        
        # Step 5: Calculate Gravity score
        logger.info(f"Step 5: Calculating Gravity score...")
        try:
            gravity_result = calculate_gravity_score(athlete_id, season_id, date.today())
            result['gravity_score'] = {
                'gravity_conf': gravity_result.get('gravity_conf'),
                'components': gravity_result.get('components'),
                'average_confidence': gravity_result.get('average_confidence')
            }
            logger.info(f"Gravity score: {gravity_result.get('gravity_conf', 0):.2f}")
        except Exception as e:
            logger.warning(f"Gravity calculation skipped: {e}")
        
        # Step 6: Calculate valuation (optional)
        logger.info(f"Step 6: Calculating valuation...")
        try:
            from gravity.valuation import calculate_iacv
            valuation = calculate_iacv(athlete_id, season_id)
            result['valuation'] = {
                'iacv_p50': valuation.get('iacv_p50'),
                'iacv_p25': valuation.get('iacv_p25'),
                'iacv_p75': valuation.get('iacv_p75')
            }
            logger.info(f"IACV (P50): ${valuation.get('iacv_p50', 0):,.0f}")
        except Exception as e:
            logger.warning(f"Valuation calculation skipped: {e}")
        
        result['success'] = True
        logger.info(f"NIL pipeline integration completed for {player_name}")
        
    except Exception as e:
        logger.error(f"NIL pipeline integration failed for {player_name}: {e}")
        result['error'] = str(e)
    
    return result


# Call integrate_nil_pipeline() from your external CFB scraper after each player payload is built.
