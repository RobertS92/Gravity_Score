"""
Normalization Pipeline
Parses raw payloads into canonical schema and stores in PostgreSQL
"""

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, date
import uuid

from gravity.storage import get_storage_manager
from gravity.db.models import NILDeal, NILValuation, AthleteEvent
from gravity.nil.entity_resolution import EntityResolver

logger = logging.getLogger(__name__)


class NormalizationPipeline:
    """
    Normalizes raw NIL data into canonical schema
    - Parses NIL deals and valuations
    - Validates data types and ranges
    - Stores in PostgreSQL tables
    - Handles entity resolution
    """
    
    def __init__(self):
        """Initialize normalization pipeline"""
        self.storage = get_storage_manager()
        self.resolver = EntityResolver()
        logger.info("Normalization pipeline initialized")
    
    def normalize_collection_results(
        self,
        collection_results: Dict[str, Any],
        athlete_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Normalize results from connector orchestrator
        
        Args:
            collection_results: Results from ConnectorOrchestrator.collect_all()
            athlete_id: Optional existing athlete ID
        
        Returns:
            Normalization summary with created records
        """
        logger.info(f"Normalizing collection results for {collection_results.get('athlete_name')}")
        
        # Resolve or create athlete
        if not athlete_id:
            athlete_id, is_new, confidence = self.resolver.create_or_resolve_athlete(
                name=collection_results['athlete_name'],
                school=collection_results.get('school'),
                sport=collection_results.get('sport')
            )
            logger.info(f"Athlete resolved: {athlete_id} (new={is_new}, confidence={confidence:.2f})")
        
        summary = {
            'athlete_id': str(athlete_id),
            'normalized_at': datetime.utcnow().isoformat(),
            'nil_deals_created': 0,
            'nil_valuations_created': 0,
            'events_created': 0,
            'errors': []
        }
        
        # Normalize NIL valuations
        valuations = self._extract_valuations_from_results(collection_results, athlete_id)
        summary['nil_valuations_created'] = len(valuations)
        
        # Normalize NIL deals
        deals = self._extract_deals_from_results(collection_results, athlete_id)
        summary['nil_deals_created'] = len(deals)
        
        # Create events for tracking
        events = self._create_collection_events(collection_results, athlete_id)
        summary['events_created'] = len(events)
        
        return summary
    
    def _extract_valuations_from_results(
        self,
        results: Dict[str, Any],
        athlete_id: uuid.UUID
    ) -> List[NILValuation]:
        """Extract and store NIL valuations"""
        valuations = []
        
        # Get all valuations from sources
        for source_name, source_data in results.get('sources', {}).items():
            if not source_data.get('success'):
                continue
            
            data = source_data.get('data', {})
            valuation_amount = data.get('nil_valuation')
            
            if valuation_amount:
                valuation = self._create_valuation(
                    athlete_id=athlete_id,
                    amount=valuation_amount,
                    source=source_name,
                    ranking=data.get('nil_ranking'),
                    confidence=source_data.get('reliability', 0.5)
                )
                if valuation:
                    valuations.append(valuation)
        
        return valuations
    
    def _create_valuation(
        self,
        athlete_id: uuid.UUID,
        amount: float,
        source: str,
        ranking: Optional[int] = None,
        confidence: Optional[float] = None
    ) -> Optional[NILValuation]:
        """Create NIL valuation record"""
        try:
            with self.storage.get_session() as session:
                valuation = NILValuation(
                    athlete_id=athlete_id,
                    valuation_amount=amount,
                    valuation_currency='USD',
                    valuation_period='annual',  # Default to annual
                    source=source,
                    ranking=ranking,
                    as_of_date=date.today(),
                    confidence_score=confidence
                )
                
                session.add(valuation)
                session.commit()
                session.refresh(valuation)
                
                logger.debug(f"Created valuation: {source} - ${amount:,.0f}")
                return valuation
                
        except Exception as e:
            logger.error(f"Failed to create valuation: {e}")
            return None
    
    def _extract_deals_from_results(
        self,
        results: Dict[str, Any],
        athlete_id: uuid.UUID
    ) -> List[NILDeal]:
        """Extract and store NIL deals"""
        deals = []
        seen_deals = set()  # Track (brand, source) to avoid duplicates
        
        # Get all deals from sources
        aggregated = results.get('aggregated', {})
        for deal_data in aggregated.get('nil_deals', []):
            brand = deal_data.get('brand', '').strip()
            source = deal_data.get('source', 'unknown')
            
            # Skip if we've already seen this deal
            deal_key = (brand.lower(), source)
            if deal_key in seen_deals:
                continue
            seen_deals.add(deal_key)
            
            # Create deal
            deal = self._create_deal(
                athlete_id=athlete_id,
                brand=brand,
                deal_type=deal_data.get('type'),
                source=source,
                confidence=deal_data.get('reliability', 0.5),
                is_team_deal=deal_data.get('is_team_deal', False),
                deal_value=deal_data.get('value')
            )
            
            if deal:
                deals.append(deal)
        
        return deals
    
    def _create_deal(
        self,
        athlete_id: uuid.UUID,
        brand: str,
        deal_type: Optional[str],
        source: str,
        confidence: float,
        is_team_deal: bool = False,
        deal_value: Optional[float] = None
    ) -> Optional[NILDeal]:
        """Create NIL deal record"""
        try:
            with self.storage.get_session() as session:
                deal = NILDeal(
                    athlete_id=athlete_id,
                    brand=brand,
                    deal_type=deal_type or 'Unknown',
                    deal_value=deal_value,
                    deal_currency='USD',
                    is_national=not is_team_deal,
                    is_local=is_team_deal,
                    announced_date=date.today(),
                    source=source,
                    confidence_score=confidence,
                    is_verified=is_team_deal or source in ['on3', 'opendorse']  # Higher confidence sources
                )
                
                session.add(deal)
                session.commit()
                session.refresh(deal)
                
                logger.debug(f"Created deal: {brand} ({source})")
                return deal
                
        except Exception as e:
            logger.error(f"Failed to create deal for {brand}: {e}")
            return None
    
    def _create_collection_events(
        self,
        results: Dict[str, Any],
        athlete_id: uuid.UUID
    ) -> List[AthleteEvent]:
        """Create tracking events for this collection"""
        events = []
        
        try:
            with self.storage.get_session() as session:
                # Create one event for the collection
                event = AthleteEvent(
                    athlete_id=athlete_id,
                    event_type='nil_data_collection',
                    event_timestamp=datetime.utcnow(),
                    source='connector_orchestrator',
                    raw_data={
                        'sources_successful': len(results.get('sources', {})),
                        'sources_failed': len(results.get('errors', [])),
                        'deals_found': len(results.get('aggregated', {}).get('nil_deals', [])),
                        'valuation_consensus': results.get('aggregated', {}).get('consensus', {}).get('nil_valuation'),
                        'data_quality_score': results.get('summary', {}).get('data_quality_score')
                    },
                    processed=True
                )
                
                session.add(event)
                session.commit()
                session.refresh(event)
                
                events.append(event)
                
        except Exception as e:
            logger.error(f"Failed to create collection event: {e}")
        
        return events
    
    def normalize_single_source(
        self,
        source_name: str,
        source_data: Dict[str, Any],
        athlete_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Normalize data from a single source
        
        Args:
            source_name: Name of source connector
            source_data: Normalized data from connector
            athlete_id: Athlete UUID
        
        Returns:
            Summary of normalized records
        """
        summary = {
            'source': source_name,
            'athlete_id': str(athlete_id),
            'valuations_created': 0,
            'deals_created': 0
        }
        
        # Create valuation if present
        if source_data.get('nil_valuation'):
            valuation = self._create_valuation(
                athlete_id=athlete_id,
                amount=source_data['nil_valuation'],
                source=source_name,
                ranking=source_data.get('nil_ranking'),
                confidence=source_data.get('_metadata', {}).get('source_reliability', 0.5)
            )
            if valuation:
                summary['valuations_created'] = 1
        
        # Create deals
        for deal_data in source_data.get('nil_deals', []):
            deal = self._create_deal(
                athlete_id=athlete_id,
                brand=deal_data.get('brand', 'Unknown'),
                deal_type=deal_data.get('type'),
                source=source_name,
                confidence=source_data.get('_metadata', {}).get('source_reliability', 0.5)
            )
            if deal:
                summary['deals_created'] += 1
        
        return summary
    
    def validate_and_clean(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean normalized data
        
        Args:
            data: Normalized data dict
        
        Returns:
            Cleaned data
        """
        cleaned = {}
        
        # Validate NIL valuation
        if 'nil_valuation' in data:
            val = data['nil_valuation']
            if isinstance(val, (int, float)) and 0 < val < 100_000_000:  # Reasonable range
                cleaned['nil_valuation'] = float(val)
        
        # Validate NIL ranking
        if 'nil_ranking' in data:
            rank = data['nil_ranking']
            if isinstance(rank, int) and 0 < rank < 10000:
                cleaned['nil_ranking'] = rank
        
        # Validate deals
        if 'nil_deals' in data and isinstance(data['nil_deals'], list):
            cleaned['nil_deals'] = []
            for deal in data['nil_deals']:
                if isinstance(deal, dict) and deal.get('brand'):
                    # Clean brand name
                    deal['brand'] = deal['brand'].strip()[:255]
                    cleaned['nil_deals'].append(deal)
        
        # Copy other fields
        for key in ['profile_url', 'social_metrics', 'recruiting_data']:
            if key in data:
                cleaned[key] = data[key]
        
        return cleaned


# Convenience function
def normalize_nil_data(
    collection_results: Dict[str, Any],
    athlete_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    Normalize NIL data collection results
    
    Args:
        collection_results: Results from connector orchestrator
        athlete_id: Optional athlete ID
    
    Returns:
        Normalization summary
    """
    pipeline = NormalizationPipeline()
    return pipeline.normalize_collection_results(collection_results, athlete_id)
