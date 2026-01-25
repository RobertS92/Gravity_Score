"""
Connector Orchestrator
Manages parallel execution of all NIL connectors with rate limiting and result aggregation
"""

from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from datetime import datetime
import uuid
import asyncio

from gravity.nil.connectors import (
    On3Connector,
    OpendorseConnector,
    INFLCRConnector,
    TeamworksConnector,
    Sports247Connector,
    RivalsConnector
)
from gravity.storage import get_storage_manager

logger = logging.getLogger(__name__)


class ConnectorOrchestrator:
    """
    Orchestrates NIL data collection across all sources
    - Parallel execution with rate limiting
    - Raw payload storage
    - Result aggregation
    - Error handling and retry logic
    """
    
    def __init__(self, max_workers: int = 6):
        """
        Initialize orchestrator
        
        Args:
            max_workers: Maximum parallel connectors
        """
        self.max_workers = max_workers
        self.storage = get_storage_manager()
        
        # Initialize all connectors
        self.connectors = {
            'on3': On3Connector(),
            'opendorse': OpendorseConnector(),
            'inflcr': INFLCRConnector(),
            'teamworks': TeamworksConnector(),
            '247sports': Sports247Connector(),
            'rivals': RivalsConnector()
        }
        
        logger.info(f"Connector orchestrator initialized with {len(self.connectors)} connectors")
    
    async def collect_all_async(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = 'football',
        athlete_id: Optional[uuid.UUID] = None,
        save_raw: bool = True
    ) -> Dict[str, Any]:
        """
        Async collect data from all NIL sources in true parallel execution
        All connectors run simultaneously with asyncio.gather
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
            athlete_id: Optional athlete UUID
            save_raw: Whether to save raw payloads
        
        Returns:
            Aggregated results from all sources
        """
        logger.info(f"Starting async NIL collection for {athlete_name} ({school or 'unknown school'})")
        
        results = {
            'athlete_name': athlete_name,
            'school': school,
            'sport': sport,
            'athlete_id': str(athlete_id) if athlete_id else None,
            'collection_timestamp': datetime.utcnow().isoformat(),
            'sources': {},
            'aggregated': {
                'nil_valuations': [],
                'nil_deals': [],
                'nil_rankings': [],
                'social_metrics': {},
                'recruiting_data': {}
            },
            'errors': []
        }
        
        # Create async tasks for all connectors
        tasks = []
        connector_names = []
        
        for name, connector in self.connectors.items():
            # Check if connector has async method
            if hasattr(connector, 'fetch_raw_async'):
                task = self._collect_from_source_async(
                    name, connector, athlete_name, school, sport
                )
            else:
                # Fallback to sync in executor
                loop = asyncio.get_event_loop()
                task = loop.run_in_executor(
                    None,
                    self._collect_from_source,
                    name, connector, athlete_name, school, sport
                )
            
            tasks.append(task)
            connector_names.append(name)
        
        # Wait for all to complete (true parallelism)
        connector_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for name, result in zip(connector_names, connector_results):
            if isinstance(result, Exception):
                logger.error(f"Connector {name} failed with exception: {result}")
                results['errors'].append({'source': name, 'error': str(result)})
            elif result and result.get('success'):
                results['sources'][name] = result
                
                # Save raw payload if requested
                if save_raw and result.get('data'):
                    try:
                        self.storage.write_raw_payload(
                            data=result['data'],
                            source=name,
                            payload_type='nil_collection',
                            athlete_id=athlete_id
                        )
                    except Exception as e:
                        logger.error(f"Failed to save raw payload for {name}: {e}")
            else:
                results['errors'].append({
                    'source': name,
                    'error': result.get('error', 'Unknown error') if result else 'No result'
                })
        
        # Aggregate results
        results['aggregated'] = self._aggregate_results(results['sources'])
        
        # Calculate summary statistics
        results['summary'] = self._calculate_summary(results)
        
        logger.info(f"Async NIL collection complete for {athlete_name}: "
                   f"{len(results['sources'])} sources successful, "
                   f"{len(results['errors'])} errors")
        
        return results
    
    async def _collect_from_source_async(
        self,
        source_name: str,
        connector,
        athlete_name: str,
        school: Optional[str],
        sport: Optional[str]
    ) -> Dict[str, Any]:
        """
        Async collection from single source
        
        Args:
            source_name: Name of source
            connector: Connector instance
            athlete_name: Athlete name
            school: School name
            sport: Sport type
        
        Returns:
            Result dict with success/error info
        """
        start_time = datetime.utcnow()
        
        try:
            # Call async fetch + normalize
            raw_data = await connector.fetch_raw_async(athlete_name, school, sport)
            
            if not raw_data:
                duration = (datetime.utcnow() - start_time).total_seconds()
                return {
                    'success': False,
                    'source': source_name,
                    'error': 'No data found',
                    'duration_seconds': duration
                }
            
            # Normalize (sync operation)
            normalized = connector.normalize(raw_data)
            
            # Add metadata
            normalized['_metadata'] = {
                'source': source_name,
                'source_reliability': connector.get_source_reliability_weight(),
                'fetched_at': datetime.utcnow().isoformat(),
                'athlete_name': athlete_name,
                'school': school,
                'sport': sport
            }
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                'success': True,
                'source': source_name,
                'data': normalized,
                'reliability': connector.get_source_reliability_weight(),
                'duration_seconds': duration,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Async source {source_name} collection failed: {e}")
            return {
                'success': False,
                'source': source_name,
                'error': str(e),
                'duration_seconds': duration
            }
    
    def collect_all(
        self,
        athlete_name: str,
        school: Optional[str] = None,
        sport: Optional[str] = 'football',
        athlete_id: Optional[uuid.UUID] = None,
        save_raw: bool = True
    ) -> Dict[str, Any]:
        """
        Sync wrapper around async collect_all
        Maintained for backward compatibility
        
        Args:
            athlete_name: Name of athlete
            school: School/college name
            sport: Sport type
            athlete_id: Optional athlete UUID
            save_raw: Whether to save raw payloads
        
        Returns:
            Aggregated results from all sources
        """
        return asyncio.run(self.collect_all_async(athlete_name, school, sport, athlete_id, save_raw))
    
    def _collect_from_source(
        self,
        source_name: str,
        connector,
        athlete_name: str,
        school: Optional[str],
        sport: Optional[str]
    ) -> Dict[str, Any]:
        """
        Collect data from a single source
        
        Args:
            source_name: Name of source
            connector: Connector instance
            athlete_name: Athlete name
            school: School name
            sport: Sport type
        
        Returns:
            Result dict with success/error info
        """
        try:
            start_time = datetime.utcnow()
            
            # Collect data
            data = connector.collect(athlete_name, school, sport)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            if data:
                return {
                    'success': True,
                    'source': source_name,
                    'data': data,
                    'reliability': connector.get_source_reliability_weight(),
                    'duration_seconds': duration,
                    'timestamp': end_time.isoformat()
                }
            else:
                return {
                    'success': False,
                    'source': source_name,
                    'error': 'No data found',
                    'duration_seconds': duration
                }
                
        except Exception as e:
            logger.error(f"Source {source_name} collection failed: {e}")
            return {
                'success': False,
                'source': source_name,
                'error': str(e)
            }
    
    def _aggregate_results(self, sources: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate results from all sources
        
        Args:
            sources: Dict of source results
        
        Returns:
            Aggregated data
        """
        aggregated = {
            'nil_valuations': [],
            'nil_deals': [],
            'nil_rankings': [],
            'social_metrics': {},
            'recruiting_data': {}
        }
        
        for source_name, source_result in sources.items():
            if not source_result.get('success'):
                continue
            
            data = source_result.get('data', {})
            reliability = source_result.get('reliability', 0.5)
            
            # Aggregate NIL valuations
            if data.get('nil_valuation'):
                aggregated['nil_valuations'].append({
                    'source': source_name,
                    'value': data['nil_valuation'],
                    'reliability': reliability,
                    'timestamp': source_result.get('timestamp')
                })
            
            # Aggregate NIL deals
            if data.get('nil_deals'):
                for deal in data['nil_deals']:
                    deal['source'] = source_name
                    deal['reliability'] = reliability
                    aggregated['nil_deals'].append(deal)
            
            # Aggregate NIL rankings
            if data.get('nil_ranking'):
                aggregated['nil_rankings'].append({
                    'source': source_name,
                    'ranking': data['nil_ranking'],
                    'reliability': reliability
                })
            
            # Aggregate social metrics
            if data.get('social_metrics'):
                for platform, metrics in data['social_metrics'].items():
                    if platform not in aggregated['social_metrics']:
                        aggregated['social_metrics'][platform] = []
                    aggregated['social_metrics'][platform].append({
                        'source': source_name,
                        'metrics': metrics,
                        'reliability': reliability
                    })
            
            # Aggregate recruiting data
            if data.get('recruiting_ranking'):
                aggregated['recruiting_data']['ranking'] = data['recruiting_ranking']
            if data.get('recruiting_stars'):
                aggregated['recruiting_data']['stars'] = data['recruiting_stars']
        
        # Calculate consensus values
        aggregated['consensus'] = self._calculate_consensus(aggregated)
        
        return aggregated
    
    def _calculate_consensus(self, aggregated: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate consensus values from multiple sources
        
        Args:
            aggregated: Aggregated data
        
        Returns:
            Consensus values
        """
        consensus = {}
        
        # Consensus NIL valuation (weighted by reliability)
        if aggregated['nil_valuations']:
            total_weight = sum(v['reliability'] for v in aggregated['nil_valuations'])
            if total_weight > 0:
                weighted_sum = sum(v['value'] * v['reliability'] for v in aggregated['nil_valuations'])
                consensus['nil_valuation'] = weighted_sum / total_weight
                
                # Also calculate min/max/median
                values = sorted([v['value'] for v in aggregated['nil_valuations']])
                consensus['nil_valuation_min'] = values[0]
                consensus['nil_valuation_max'] = values[-1]
                consensus['nil_valuation_median'] = values[len(values) // 2]
        
        # Consensus NIL ranking (weighted average)
        if aggregated['nil_rankings']:
            total_weight = sum(r['reliability'] for r in aggregated['nil_rankings'])
            if total_weight > 0:
                weighted_sum = sum(r['ranking'] * r['reliability'] for r in aggregated['nil_rankings'])
                consensus['nil_ranking'] = int(weighted_sum / total_weight)
        
        # Deduplicated deals count
        if aggregated['nil_deals']:
            unique_brands = set(deal.get('brand', '').lower() for deal in aggregated['nil_deals'])
            consensus['unique_deals_count'] = len(unique_brands)
        
        return consensus
    
    def _calculate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate summary statistics
        
        Args:
            results: Full results dict
        
        Returns:
            Summary statistics
        """
        summary = {
            'sources_attempted': len(self.connectors),
            'sources_successful': len(results['sources']),
            'sources_failed': len(results['errors']),
            'total_deals_found': len(results['aggregated'].get('nil_deals', [])),
            'has_valuation': bool(results['aggregated'].get('consensus', {}).get('nil_valuation')),
            'has_ranking': bool(results['aggregated'].get('consensus', {}).get('nil_ranking')),
            'data_quality_score': self._calculate_data_quality_score(results)
        }
        
        return summary
    
    def _calculate_data_quality_score(self, results: Dict[str, Any]) -> float:
        """
        Calculate overall data quality score (0-1)
        
        Args:
            results: Full results dict
        
        Returns:
            Quality score
        """
        score = 0.0
        max_score = 0.0
        
        # Points for successful sources (weighted by tier)
        for source_name, source_result in results['sources'].items():
            if source_result.get('success'):
                reliability = source_result.get('reliability', 0.5)
                score += reliability
            max_score += self.connectors[source_name].get_source_reliability_weight()
        
        # Points for having key data
        if results['aggregated'].get('consensus', {}).get('nil_valuation'):
            score += 0.5
        if results['aggregated'].get('consensus', {}).get('nil_ranking'):
            score += 0.3
        if results['aggregated'].get('nil_deals'):
            score += 0.2
        
        max_score += 1.0  # Max points for key data
        
        return min(1.0, score / max_score if max_score > 0 else 0.0)


# Convenience function for easy access
def run_nil_collection(
    athlete_name: str,
    school: Optional[str] = None,
    sport: Optional[str] = 'football',
    athlete_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    Run NIL data collection for an athlete
    
    Args:
        athlete_name: Name of athlete
        school: School/college name
        sport: Sport type
        athlete_id: Optional athlete UUID
    
    Returns:
        Aggregated NIL data
    """
    orchestrator = ConnectorOrchestrator()
    return orchestrator.collect_all(athlete_name, school, sport, athlete_id)
