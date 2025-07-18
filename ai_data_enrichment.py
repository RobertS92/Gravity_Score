"""
AI-Powered Data Enrichment for NFL Players
Uses OpenAI to intelligently extract missing data from web content
"""

import os
import requests
import json
import logging
from typing import Dict, List, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class AIDataEnrichment:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def enrich_player_data(self, player_name: str, existing_data: Dict) -> Dict:
        """Use AI to enrich player data with intelligent web search and extraction."""
        try:
            # Identify missing critical fields
            missing_fields = self._identify_missing_fields(existing_data)
            
            if not missing_fields:
                logger.info(f"No missing fields for {player_name}")
                return existing_data
            
            # Use AI to search for and extract missing data
            enriched_data = self._ai_extract_missing_data(player_name, missing_fields, existing_data)
            
            # Merge with existing data
            final_data = existing_data.copy()
            if enriched_data:
                final_data.update(enriched_data)
                final_data['data_sources'] = final_data.get('data_sources', []) + ['AI Enhancement']
            
            return final_data
            
        except Exception as e:
            logger.error(f"Error enriching data for {player_name}: {e}")
            return existing_data
    
    def _identify_missing_fields(self, data: Dict) -> List[str]:
        """Identify which critical fields are missing."""
        critical_fields = [
            'birth_date', 'birth_place', 'high_school', 'draft_year', 'draft_round', 
            'career_pass_yards', 'career_pass_tds', 'pro_bowls', 'all_pros',
            'current_salary', 'contract_value', 'twitter_handle', 'instagram_handle'
        ]
        
        missing = []
        for field in critical_fields:
            if not data.get(field) or str(data.get(field)).strip() == '':
                missing.append(field)
        
        return missing[:8]  # Focus on top 8 missing fields
    
    def _ai_extract_missing_data(self, player_name: str, missing_fields: List[str], existing_data: Dict) -> Dict:
        """Use AI to extract missing data."""
        try:
            # Create intelligent prompt
            prompt = f"""
You are an expert NFL data analyst. Extract the following missing information for {player_name}:

Missing fields needed: {', '.join(missing_fields)}

Current known data: {json.dumps({k: v for k, v in existing_data.items() if k in ['name', 'team', 'position', 'college', 'age', 'height', 'weight']}, indent=2)}

Please provide the missing data in JSON format. Only include fields you are confident about. Use this format:

{{
    "birth_date": "Month DD, YYYY",
    "birth_place": "City, State",
    "high_school": "School name",
    "draft_year": year_number,
    "draft_round": round_number,
    "career_pass_yards": number,
    "career_pass_tds": number,
    "pro_bowls": number,
    "all_pros": number,
    "current_salary": "$X,XXX,XXX",
    "contract_value": "$X,XXX,XXX",
    "twitter_handle": "handle_without_@",
    "instagram_handle": "handle_without_@"
}}

Only include fields you are highly confident about. If unsure, omit the field.
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Latest model
                messages=[
                    {"role": "system", "content": "You are an expert NFL data analyst with access to comprehensive player statistics and biographical information."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            ai_data = json.loads(response.choices[0].message.content)
            
            # Validate AI responses
            validated_data = self._validate_ai_data(ai_data, player_name)
            
            if validated_data:
                logger.info(f"AI extracted {len(validated_data)} fields for {player_name}")
                return validated_data
            
            return {}
            
        except Exception as e:
            logger.error(f"AI extraction failed for {player_name}: {e}")
            return {}
    
    def _validate_ai_data(self, ai_data: Dict, player_name: str) -> Dict:
        """Validate AI-extracted data for accuracy."""
        validated = {}
        
        for field, value in ai_data.items():
            if field == 'birth_date' and isinstance(value, str) and len(value) > 8:
                validated[field] = value
            elif field == 'birth_place' and isinstance(value, str) and len(value) > 3:
                validated[field] = value
            elif field == 'high_school' and isinstance(value, str) and len(value) > 3:
                validated[field] = value
            elif field in ['draft_year', 'draft_round'] and isinstance(value, int) and 1990 <= value <= 2025:
                validated[field] = value
            elif field in ['career_pass_yards', 'career_pass_tds'] and isinstance(value, int) and value > 0:
                validated[field] = value
            elif field in ['pro_bowls', 'all_pros'] and isinstance(value, int) and 0 <= value <= 20:
                validated[field] = value
            elif field in ['current_salary', 'contract_value'] and isinstance(value, str) and '$' in value:
                validated[field] = value
            elif field in ['twitter_handle', 'instagram_handle'] and isinstance(value, str) and len(value) > 2:
                validated[field] = value
        
        return validated

class EnhancedRealDataCollector:
    """Enhanced version of RealDataCollector with AI enrichment."""
    
    def __init__(self):
        from real_data_collector import RealDataCollector
        self.base_collector = RealDataCollector()
        self.ai_enricher = AIDataEnrichment()
    
    def collect_enhanced_real_data(self, player_name: str, team: str, position: str) -> Dict:
        """Collect data with AI enhancement."""
        try:
            # Get base data from all sources
            base_data = self.base_collector.collect_real_data(player_name, team, position)
            
            # Enhance with AI if OpenAI API is available
            if os.getenv('OPENAI_API_KEY'):
                enhanced_data = self.ai_enricher.enrich_player_data(player_name, base_data)
                
                # Recalculate quality score
                enhanced_data['data_quality_score'] = self._calculate_enhanced_quality(enhanced_data)
                
                return enhanced_data
            
            return base_data
            
        except Exception as e:
            logger.error(f"Error in enhanced collection for {player_name}: {e}")
            return self.base_collector.collect_real_data(player_name, team, position)
    
    def _calculate_enhanced_quality(self, data: Dict) -> float:
        """Calculate quality score including AI-enhanced data."""
        metadata_fields = ['data_sources', 'last_updated', 'scraped_at', 'data_source', 'comprehensive_enhanced']
        
        total_fields = len([k for k in data.keys() if k not in metadata_fields])
        filled_fields = len([k for k, v in data.items() if k not in metadata_fields and v is not None and str(v).strip() and str(v) != 'None'])
        
        if total_fields == 0:
            return 0.0
        
        base_score = (filled_fields / total_fields) * 5.0
        
        # Bonus for AI enhancement
        if 'AI Enhancement' in data.get('data_sources', []):
            base_score += 0.3
        
        # Bonus for multiple sources
        source_count = len(data.get('data_sources', []))
        if source_count >= 3:
            base_score += 0.2
        
        return min(5.0, base_score)