"""
Crawler Service
Wraps existing crawler orchestrator and provides unified interface
"""

import uuid
from typing import Dict, Any, Optional, List
import logging

# Import existing crawler orchestrator
try:
    from gravity.crawlers.crawler_orchestrator import CrawlerOrchestrator
except ImportError:
    CrawlerOrchestrator = None

logger = logging.getLogger(__name__)


class CrawlerService:
    """
    Service to orchestrate all crawlers
    Wraps the existing CrawlerOrchestrator from gravity.crawlers
    """
    
    def __init__(self):
        """Initialize crawler service"""
        self.orchestrator = CrawlerOrchestrator() if CrawlerOrchestrator else None
        
        if self.orchestrator:
            logger.info("Crawler orchestrator initialized successfully")
        else:
            logger.warning("Crawler orchestrator not available")
    
    async def run_all_crawlers(
        self,
        athlete_id: str,
        sport: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run all crawlers for a given athlete
        
        Args:
            athlete_id: UUID of athlete
            sport: Optional sport filter
            
        Returns:
            Dict with results from all crawlers
        """
        if not self.orchestrator:
            return {
                'success': False,
                'error': 'Crawler orchestrator not available'
            }
        
        try:
            logger.info(f"Running all crawlers for athlete {athlete_id}")
            
            result = await self.orchestrator.run_all_crawlers(
                uuid.UUID(athlete_id),
                sport=sport
            )
            
            logger.info(
                f"Completed all crawlers for athlete {athlete_id} - "
                f"Success: {result.get('success', False)}"
            )
            
            return result
        except Exception as e:
            logger.error(f"Failed to run crawlers for athlete {athlete_id}: {e}")
            return {
                'success': False,
                'athlete_id': athlete_id,
                'error': str(e)
            }
    
    async def run_crawler(
        self,
        crawler_name: str,
        athlete_id: str
    ) -> Dict[str, Any]:
        """
        Run a specific crawler for an athlete
        
        Args:
            crawler_name: Name of crawler to run
            athlete_id: UUID of athlete
            
        Returns:
            Dict with crawler results
        """
        if not self.orchestrator:
            return {
                'success': False,
                'error': 'Crawler orchestrator not available'
            }
        
        try:
            logger.info(f"Running crawler '{crawler_name}' for athlete {athlete_id}")
            
            result = await self.orchestrator.run_crawler(
                crawler_name,
                uuid.UUID(athlete_id)
            )
            
            logger.info(
                f"Completed crawler '{crawler_name}' for athlete {athlete_id} - "
                f"Success: {result.get('success', False)}"
            )
            
            return result
        except Exception as e:
            logger.error(
                f"Failed to run crawler '{crawler_name}' for athlete {athlete_id}: {e}"
            )
            return {
                'success': False,
                'crawler_name': crawler_name,
                'athlete_id': athlete_id,
                'error': str(e)
            }
    
    async def run_sport_crawlers(
        self,
        sport: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run crawlers for all athletes in a sport
        
        Args:
            sport: Sport to run crawlers for
            limit: Optional limit on number of athletes
            
        Returns:
            Dict with results summary
        """
        if not self.orchestrator:
            return {
                'success': False,
                'error': 'Crawler orchestrator not available'
            }
        
        try:
            logger.info(f"Running crawlers for sport '{sport}' (limit: {limit})")
            
            result = await self.orchestrator.run_sport_crawlers(
                sport,
                limit=limit
            )
            
            logger.info(f"Completed crawlers for sport '{sport}'")
            
            return result
        except Exception as e:
            logger.error(f"Failed to run crawlers for sport '{sport}': {e}")
            return {
                'success': False,
                'sport': sport,
                'error': str(e)
            }
    
    def get_crawler_status(self) -> Dict[str, Any]:
        """
        Get status of all crawlers
        
        Returns:
            Dict with crawler status information
        """
        if not self.orchestrator:
            return {
                'available': False,
                'error': 'Crawler orchestrator not available'
            }
        
        try:
            status = self.orchestrator.get_crawler_status()
            return {
                'available': True,
                'status': status
            }
        except Exception as e:
            logger.error(f"Failed to get crawler status: {e}")
            return {
                'available': True,
                'error': str(e)
            }
    
    def get_available_crawlers(self) -> List[str]:
        """
        Get list of available crawler names
        
        Returns:
            List of crawler names
        """
        if not self.orchestrator:
            return []
        
        try:
            # Assuming orchestrator has a method to list crawlers
            # If not, return known crawler names
            return [
                'news_article',
                'social_media',
                'transfer_portal',
                'sentiment',
                'injury_report',
                'brand_partnership',
                'game_stats',
                'trade'
            ]
        except Exception as e:
            logger.error(f"Failed to get available crawlers: {e}")
            return []
