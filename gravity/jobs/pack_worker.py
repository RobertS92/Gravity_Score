"""
Celery Worker for Async Pack Generation
"""

from celery import Celery
import logging
import uuid
from datetime import date
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Initialize Celery
app = Celery(
    'gravity_jobs',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@app.task(name='generate_negotiation_pack')
def generate_negotiation_pack(
    athlete_id: str,
    season_id: str,
    deal_proposal: Optional[Dict[str, Any]] = None,
    as_of_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async task to generate negotiation pack
    
    Args:
        athlete_id: Athlete UUID string
        season_id: Season identifier
        deal_proposal: Optional deal proposal dict
        as_of_date: Optional date string
    
    Returns:
        Dict with JSON and PDF URLs
    """
    try:
        from gravity.packs import aggregate_pack_data, export_pack_json, generate_pack_pdf
        
        logger.info(f"Generating pack for athlete {athlete_id}")
        
        # Convert strings to proper types
        athlete_uuid = uuid.UUID(athlete_id)
        date_obj = date.fromisoformat(as_of_date) if as_of_date else None
        
        # Aggregate data
        pack_data = aggregate_pack_data(athlete_uuid, season_id, deal_proposal, date_obj)
        
        # Generate file paths
        pack_id = str(uuid.uuid4())
        json_path = f"data/packs/{pack_id}.json"
        pdf_path = f"data/packs/{pack_id}.pdf"
        
        # Export files
        json_file = export_pack_json(pack_data, json_path)
        pdf_file = generate_pack_pdf(pack_data, pdf_path)
        
        logger.info(f"Pack generated successfully: {pack_id}")
        
        return {
            'pack_id': pack_id,
            'json_url': f"/downloads/{pack_id}.json",
            'pdf_url': f"/downloads/{pack_id}.pdf",
            'json_file': json_file,
            'pdf_file': pdf_file,
            'status': 'completed'
        }
        
    except Exception as e:
        logger.error(f"Pack generation failed: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@app.task(name='collect_nil_data')
def collect_nil_data_task(
    athlete_name: str,
    school: Optional[str] = None,
    sport: str = 'football'
) -> Dict[str, Any]:
    """
    Async task to collect NIL data
    
    Args:
        athlete_name: Name of athlete
        school: School name
        sport: Sport type
    
    Returns:
        Collection results dict
    """
    try:
        from gravity.nil import run_nil_collection
        
        logger.info(f"Collecting NIL data for {athlete_name}")
        
        result = run_nil_collection(athlete_name, school, sport)
        
        logger.info(f"NIL data collected for {athlete_name}")
        
        return {
            'status': 'completed',
            'result': result
        }
        
    except Exception as e:
        logger.error(f"NIL collection failed: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


if __name__ == '__main__':
    app.start()
