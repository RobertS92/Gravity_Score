"""
Event Processor
Processes crawler events and triggers automatic score recalculation
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from gravity.storage import get_storage_manager
from gravity.db.models import AthleteEvent

logger = logging.getLogger(__name__)


class EventProcessor:
    """
    Processes new events and determines which component scores need recalculation
    """
    
    # Event type to component score mapping
    EVENT_SCORE_MAPPING = {
        'news_contract_extension': ['proof'],
        'news_trade': ['proximity', 'risk'],
        'news_performance': ['proof'],
        'news_roster_change': ['proximity'],
        'news_nil_deal': ['brand', 'proof'],
        'social_brand_mention': ['brand'],
        'social_nil_partnership': ['brand', 'proof'],
        'social_engagement_spike': ['brand', 'velocity'],
        'social_general_post': ['brand'],
        'transfer_portal_entry': ['risk', 'proximity'],
        'transfer_commitment': ['proximity'],
        'transfer_withdrawal': ['risk'],
        'sentiment_mention': ['brand'],
        'sentiment_spike': ['brand'],
        'injury': ['risk', 'proof'],
        'injury_recovery': ['risk'],
        'injury_status_change': ['risk'],
        'brand_endorsement': ['brand', 'proof'],
        'brand_partnership_announced': ['brand', 'proof'],
        'game_stats': ['proof', 'velocity'],
        'performance_milestone': ['proof'],
        'record_achievement': ['proof'],
        'trade_announced': ['proximity', 'risk', 'proof'],
        'trade_completed': ['proximity', 'risk', 'proof'],
        'trade_rumor': ['risk']
    }
    
    def __init__(self):
        self.storage = get_storage_manager()
        logger.info("Event processor initialized")
    
    async def process_new_event(self, event_id: uuid.UUID) -> None:
        """
        Process a new event and trigger score recalculation
        
        Args:
            event_id: Event UUID
        """
        try:
            # Get event from database
            with self.storage.get_session() as session:
                event = session.query(AthleteEvent).filter(
                    AthleteEvent.event_id == event_id
                ).first()
                
                if not event:
                    logger.warning(f"Event not found: {event_id}")
                    return
                
                if event.processed:
                    logger.debug(f"Event already processed: {event_id}")
                    return
                
                # Process event
                await self.process_new_event_by_type(
                    event.athlete_id,
                    event.event_type
                )
                
                # Mark as processed
                event.processed = True
                session.commit()
                
        except Exception as e:
            logger.error(f"Event processing failed for {event_id}: {e}")
    
    async def process_new_event_by_type(
        self,
        athlete_id: uuid.UUID,
        event_type: str
    ) -> None:
        """
        Process event by type and trigger score recalculation
        
        Args:
            athlete_id: Athlete UUID
            event_type: Event type
        """
        try:
            # Determine which component scores need recalculation
            affected_components = self.EVENT_SCORE_MAPPING.get(event_type, [])
            
            if not affected_components:
                logger.debug(f"No score recalculation needed for event type: {event_type}")
                return
            
            logger.info(f"Processing {event_type} for athlete {athlete_id}, "
                       f"recalculating: {affected_components}")
            
            # Trigger score recalculation
            await self.recalculate_affected_scores(athlete_id, affected_components)
            
        except Exception as e:
            logger.error(f"Event type processing failed: {e}")
    
    async def recalculate_affected_scores(
        self,
        athlete_id: uuid.UUID,
        components: List[str]
    ) -> None:
        """
        Recalculate affected component scores
        
        Args:
            athlete_id: Athlete UUID
            components: List of component names to recalculate
        """
        try:
            # Import score recalculator (to avoid circular imports)
            from gravity.crawlers.score_recalculator import ScoreRecalculator
            
            recalculator = ScoreRecalculator()
            await recalculator.recalculate_scores(athlete_id, components)
            
        except ImportError:
            # Score recalculator not yet implemented, log and continue
            logger.debug(f"Score recalculator not available, skipping recalculation for {athlete_id}")
        except Exception as e:
            logger.error(f"Score recalculation failed: {e}")
    
    async def batch_recalculate(
        self,
        athlete_ids: List[uuid.UUID],
        components: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Batch recalculate scores for multiple athletes
        
        Args:
            athlete_ids: List of athlete UUIDs
            components: Optional list of components (if None, recalculates all)
        
        Returns:
            Results dict
        """
        results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for athlete_id in athlete_ids:
            try:
                if components:
                    await self.recalculate_affected_scores(athlete_id, components)
                else:
                    # Recalculate all components
                    await self.recalculate_affected_scores(
                        athlete_id,
                        ['brand', 'proof', 'proximity', 'velocity', 'risk']
                    )
                results['successful'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{athlete_id}: {e}")
        
        return results
    
    def get_affected_components(self, event_type: str) -> List[str]:
        """
        Get list of component scores affected by an event type
        
        Args:
            event_type: Event type
        
        Returns:
            List of component names
        """
        return self.EVENT_SCORE_MAPPING.get(event_type, [])
