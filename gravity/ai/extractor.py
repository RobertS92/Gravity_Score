"""
AI-powered structured data extraction for high-value fields
Extracts NIL deals, brand partnerships, contract details, draft info, and dates
when regex extraction fails or returns insufficient results
"""

from typing import Dict, Any, Optional, List
import json
import logging
import os

logger = logging.getLogger(__name__)


class AIExtractor:
    """
    Extract structured data using AI when regex fails
    Focuses on high-value data: deals, brands, contracts, draft info, dates
    """
    
    EXTRACTION_PROMPTS = {
        'nil_deals': """
Extract ALL NIL deals and brand partnerships for {athlete_name} from this text.
Return as a JSON array with the following structure:
[
  {{
    "brand": "Brand name",
    "type": "Deal type (Endorsement/Sponsorship/Partnership/etc)",
    "value": numeric_value_or_null,
    "description": "Brief description"
  }}
]
Return empty array [] if no deals found.

Text: {text}
""",
        
        'brand_partnerships': """
Extract all brand partnerships and sponsorships for {athlete_name} from this text.
Return as JSON array with fields: brand, type, status (active/announced/rumored).
Return empty array [] if none found.

Text: {text}
""",
        
        'contract_details': """
Extract contract details for {athlete_name} from this text.
Return as JSON object with these fields (use null for missing):
{{
  "total_value": numeric_value_or_null,
  "years": number_or_null,
  "guaranteed_money": numeric_value_or_null,
  "signing_bonus": numeric_value_or_null,
  "incentives": "description or null",
  "contract_type": "type description or null"
}}

Text: {text}
""",
        
        'draft_info': """
Extract draft information for {athlete_name} from this text.
Return as JSON object with these fields (use null for missing):
{{
  "draft_year": year_or_null,
  "round": round_number_or_null,
  "pick": pick_number_or_null,
  "overall_pick": overall_pick_or_null,
  "team": "team name or null"
}}

Text: {text}
""",
        
        'trade_info': """
Extract trade information for {athlete_name} from this text.
Return as JSON object with these fields (use null for missing):
{{
  "from_team": "team name or null",
  "to_team": "team name or null",
  "trade_date": "date string (YYYY-MM-DD) or null",
  "trade_type": "trade/waiver/free_agent/buyout or null",
  "involved_players": ["player names"] or null,
  "draft_picks": ["pick descriptions"] or null
}}

Text: {text}
""",
        
        'dates': """
Extract key dates mentioned for {athlete_name} from this text.
Return as JSON object with ISO date strings (YYYY-MM-DD) or null:
{{
  "signing_date": "date or null",
  "announcement_date": "date or null",
  "deal_start_date": "date or null",
  "deal_end_date": "date or null",
  "contract_date": "date or null"
}}

Text: {text}
""",
        
        'athlete_roster': """
Extract all athlete names from this brand roster page.
Return as a JSON array of athlete names (full names only):
["Athlete Name 1", "Athlete Name 2", ...]
Return empty array [] if no athletes found.

Text: {text}
"""
    }
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """
        Initialize AI extractor
        
        Args:
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
            api_key: Optional API key (defaults to OPENAI_API_KEY env var)
        """
        self.model = model
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        # Lazy import OpenAI to avoid dependency issues
        self._client = None
    
    @property
    def client(self):
        """Lazy init OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("openai package not installed. Install with: pip install openai")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise
        return self._client
    
    def extract(
        self, 
        text: str, 
        extraction_type: str,
        context: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Extract structured data using AI
        
        Args:
            text: Text to extract from (limited to 2000 chars to control costs)
            extraction_type: Type of data to extract (nil_deals, contract_details, etc.)
            context: Additional context dict (must include 'athlete_name')
        
        Returns:
            Extracted structured data (dict/list) or None if extraction fails
        """
        if extraction_type not in self.EXTRACTION_PROMPTS:
            logger.warning(f"Unknown extraction type: {extraction_type}")
            return None
        
        if not context.get('athlete_name'):
            logger.warning("athlete_name required in context for AI extraction")
            return None
        
        # Validate API key
        if not self.api_key:
            logger.warning("OpenAI API key not configured. Skipping AI extraction.")
            return None
        
        # Format prompt with context
        prompt = self.EXTRACTION_PROMPTS[extraction_type].format(
            text=text[:2000],  # Limit to 2000 chars
            **context
        )
        
        try:
            logger.debug(f"AI extraction: {extraction_type} for {context['athlete_name']}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You extract structured data from sports text. Always respond with valid JSON. Be precise and only extract explicitly stated information."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for deterministic extraction
                max_tokens=500,    # Limit output to control costs
                response_format={"type": "json_object"} if extraction_type in ['contract_details', 'draft_info', 'dates'] else None
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if result_text.startswith('```json'):
                result_text = result_text.split('```json')[1].split('```')[0]
            elif result_text.startswith('```'):
                result_text = result_text.split('```')[1].split('```')[0]
            
            result = json.loads(result_text)
            
            logger.info(f"AI extraction successful: {extraction_type} for {context['athlete_name']}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"AI returned invalid JSON for {extraction_type}: {e}")
            logger.debug(f"Raw response: {result_text[:200]}")
            return None
        except Exception as e:
            logger.error(f"AI extraction failed for {extraction_type}: {e}")
            return None
    
    def extract_batch(
        self,
        text: str,
        extraction_types: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract multiple data types from the same text
        
        Args:
            text: Text to extract from
            extraction_types: List of extraction types
            context: Additional context
        
        Returns:
            Dict mapping extraction_type to extracted data
        """
        results = {}
        
        for extraction_type in extraction_types:
            result = self.extract(text, extraction_type, context)
            if result:
                results[extraction_type] = result
        
        return results
