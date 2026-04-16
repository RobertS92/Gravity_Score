"""
Scraper Service — college NIL / CFB / MCBB; pro league scrapers removed per Gravity NIL Terminal spec.
"""

import asyncio
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client
import logging
from datetime import datetime
import uuid

from app.services.supabase_client import get_supabase_client

try:
    from gravity.nil import ConnectorOrchestrator
except ImportError:
    ConnectorOrchestrator = None

logger = logging.getLogger(__name__)


class ScraperService:
    """
    Service to orchestrate all scrapers across different sports
    Routes requests to appropriate scraper based on league
    """
    
    def __init__(self):
        """Initialize scraper service with all available scrapers"""
        self.supabase: Optional["Client"] = get_supabase_client()
        
        # Initialize scrapers
        self.nil_orchestrator = ConnectorOrchestrator() if ConnectorOrchestrator else None

        logger.info(
            f"Scraper service initialized - "
            f"NIL: {self.nil_orchestrator is not None}, "
            f"college-only (NFL/NBA scrapers removed per Gravity NIL Terminal spec)"
        )
    
    async def scrape_athlete(
        self,
        athlete_id: str,
        league: str,
        store_results: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape data for a single athlete
        
        Args:
            athlete_id: UUID of athlete
            league: Sport league (cfb, nfl, nba, etc.)
            store_results: Whether to store results in database
            
        Returns:
            Dict with scraping results
            
        Raises:
            ValueError: If athlete not found or league not supported
        """
        logger.info(f"Scraping athlete {athlete_id} for league {league}")

        if not self.supabase:
            raise ValueError(
                "Supabase is not configured; set SUPABASE_URL and SUPABASE_SERVICE_KEY "
                "to look up athletes and store results."
            )

        # Fetch athlete info from Supabase
        try:
            athlete_result = self.supabase.table('athletes')\
                .select('*')\
                .eq('athlete_id', athlete_id)\
                .single()\
                .execute()
            
            if not athlete_result.data:
                raise ValueError(f"Athlete {athlete_id} not found")
            
            athlete = athlete_result.data
        except Exception as e:
            logger.error(f"Failed to fetch athlete {athlete_id}: {e}")
            raise ValueError(f"Athlete {athlete_id} not found") from e
        
        # Route to appropriate scraper
        league_lower = league.lower()
        
        if league_lower in ['cfb', 'ncaaf', 'nil', 'mcbb']:
            result = await self._scrape_nil(athlete)
        elif league_lower in ('nfl', 'nba', 'wnba'):
            result = {
                'success': False,
                'error': (
                    'Pro league scrapers removed; use CFB / MCBB (cfb, mcbb, nil) only.'
                ),
            }
        else:
            raise ValueError(f"Unsupported league: {league}")
        
        # Store results if requested
        if store_results and result.get('success'):
            await self._store_scraper_result(athlete['athlete_id'], league, result)
        
        return result
    
    async def _scrape_nil(self, athlete: Dict) -> Dict[str, Any]:
        """Scrape NIL data using existing orchestrator"""
        if not self.nil_orchestrator:
            return {'success': False, 'error': 'NIL scraper not available'}
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.nil_orchestrator.collect_all,
                athlete['canonical_name']
            )
            
            return {
                'success': True,
                'league': 'nil',
                'athlete_id': athlete['athlete_id'],
                'data': result
            }
        except Exception as e:
            logger.error(f"NIL scraper failed for {athlete['canonical_name']}: {e}")
            return {
                'success': False,
                'league': 'nil',
                'athlete_id': athlete['athlete_id'],
                'error': str(e)
            }
    
    async def _store_scraper_result(
        self,
        athlete_id: str,
        league: str,
        result: Dict[str, Any]
    ):
        """Store scraper results in Supabase raw_payloads table"""
        if not self.supabase:
            logger.warning("Skip storing scraper result: Supabase not configured")
            return
        try:
            payload_record = {
                'payload_id': str(uuid.uuid4()),
                'athlete_id': athlete_id,
                'source': f'{league}_scraper',
                'payload_type': 'scraper_result',
                'file_path': f'scraper_{league}_{athlete_id}_{datetime.utcnow().isoformat()}.json',
                'fetched_at': datetime.utcnow().isoformat(),
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.supabase.table('raw_payloads').insert(payload_record).execute()
            logger.info(f"Stored scraper result for athlete {athlete_id}")
        except Exception as e:
            logger.error(f"Failed to store scraper result: {e}")
