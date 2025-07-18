"""
Enhanced AI Data Extractor for NFL Player Information
Handles draft, contract, achievement, and position-specific statistics
"""

import json
import re
import logging
from typing import Dict, Optional
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

class EnhancedAIExtractor:
    def __init__(self):
        self.openai_client = None
        try:
            api_key = os.environ.get('OPENAI_API_KEY')
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"OpenAI client not available: {e}")
    
    def extract_json_from_response(self, response_text: str) -> Optional[Dict]:
        """Extract JSON from AI response, handling markdown code blocks."""
        try:
            # First try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_text.strip()
            
            return json.loads(json_str)
        except Exception as e:
            logger.debug(f"JSON extraction failed: {e}")
            return None
    
    def extract_draft_data(self, player_name: str, data: Dict) -> Dict:
        """Extract comprehensive draft information using AI enhancement."""
        if not self.openai_client:
            return data
            
        logger.info(f"🏈 AI extracting draft data for {player_name}")
        
        # Check if we already have draft info
        if data.get('draft_year') or data.get('draft_round'):
            logger.info(f"✅ Draft data already available")
            return data
        
        try:
            prompt = f"""
            Find NFL draft information for {player_name}:
            - Draft year
            - Draft round  
            - Draft pick (overall pick number)
            - Draft team (team that drafted him)
            
            Only provide real, verifiable draft information from authentic NFL sources.
            If the player was undrafted, specify "Undrafted" for relevant fields.
            
            Format response as JSON:
            {{
                "draft_year": year_or_null,
                "draft_round": round_or_null,
                "draft_pick": pick_number_or_null,
                "draft_team": "team_name_or_undrafted"
            }}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert NFL draft historian. Only provide real, verifiable draft data. Format your response as valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300
            )
            
            draft_text = response.choices[0].message.content
            draft_data = self.extract_json_from_response(draft_text)
            
            if draft_data:
                for field, value in draft_data.items():
                    if value and str(value).lower() not in ['null', 'none', 'unknown']:
                        data[field] = value
                
                if any(data.get(field) for field in ['draft_year', 'draft_round', 'draft_pick', 'draft_team']):
                    data['data_sources'].append('AI Draft Analysis')
                    logger.info(f"✅ AI draft data extracted: {data.get('draft_year', 'N/A')} Round {data.get('draft_round', 'N/A')}")
            
        except Exception as e:
            logger.debug(f"Error extracting draft data with AI: {e}")
        
        return data
    
    def extract_contract_data(self, player_name: str, data: Dict) -> Dict:
        """Extract comprehensive contract information using AI enhancement."""
        if not self.openai_client:
            return data
            
        logger.info(f"💰 AI extracting contract data for {player_name}")
        
        # Check if we already have significant contract info
        if data.get('current_salary') or data.get('contract_value'):
            logger.info(f"✅ Contract data already available")
            return data
        
        try:
            prompt = f"""
            Find current NFL contract information for {player_name} (2024 season):
            - Current salary/cap hit for 2024
            - Total contract value (if recent contract)
            - Contract length in years
            - Guaranteed money
            
            Only provide real, verifiable contract data from sources like Spotrac, ESPN, NFL.com.
            Use actual dollar amounts, not estimates.
            
            Format response as JSON:
            {{
                "current_salary": dollar_amount_or_null,
                "contract_value": total_value_or_null,
                "contract_years": years_or_null,
                "guaranteed_money": guaranteed_amount_or_null
            }}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an NFL contract specialist. Only provide real, verifiable financial data. Format your response as valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400
            )
            
            contract_text = response.choices[0].message.content
            contract_data = self.extract_json_from_response(contract_text)
            
            if contract_data:
                for field, value in contract_data.items():
                    if isinstance(value, (int, float)) and value > 0:
                        data[field] = int(value)
                
                if any(data.get(field) for field in ['current_salary', 'contract_value', 'contract_years']):
                    data['data_sources'].append('AI Contract Analysis')
                    logger.info(f"✅ AI contract data extracted")
            
        except Exception as e:
            logger.debug(f"Error extracting contract data with AI: {e}")
        
        return data
    
    def extract_achievement_data(self, player_name: str, data: Dict) -> Dict:
        """Extract comprehensive achievement information using AI enhancement."""
        if not self.openai_client:
            return data
            
        logger.info(f"🏆 AI extracting achievement data for {player_name}")
        
        try:
            prompt = f"""
            Find NFL achievements and awards for {player_name}:
            - Super Bowl championships (years)
            - Pro Bowl selections (total count or years)
            - All-Pro selections (years)
            - Major individual awards (MVP, OPOY, DPOY, ROTY with years)
            
            Only include real, verifiable achievements from official NFL records.
            
            Format response as JSON:
            {{
                "championships": "Super Bowl years (comma separated) or empty string",
                "pro_bowls": "number of selections or years",
                "all_pros": "years (comma separated) or empty string",
                "awards": "awards with years (comma separated) or empty string"
            }}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an NFL achievement historian. Only provide real, verifiable awards and honors. Format your response as valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400
            )
            
            achievement_text = response.choices[0].message.content
            achievement_data = self.extract_json_from_response(achievement_text)
            
            if achievement_data:
                for field, value in achievement_data.items():
                    if isinstance(value, str) and value.strip() and value.lower() not in ['unknown', 'none', 'null']:
                        data[field] = value.strip()
                
                if any(data.get(field) for field in ['championships', 'pro_bowls', 'all_pros', 'awards']):
                    data['data_sources'].append('AI Achievement Analysis')
                    logger.info(f"✅ AI achievement data extracted")
            
        except Exception as e:
            logger.debug(f"Error extracting achievement data with AI: {e}")
        
        return data
    
    def extract_position_stats(self, player_name: str, position: str, data: Dict) -> Dict:
        """Extract position-specific statistics using AI enhancement."""
        if not position or not self.openai_client:
            return data
            
        logger.info(f"📊 AI extracting {position} stats for {player_name}")
        
        try:
            # Create position-specific prompts
            if position.upper() == 'QB':
                prompt = f"""
                Find 2023 NFL regular season statistics for quarterback {player_name}:
                - Passing yards
                - Passing touchdowns
                - Passing interceptions
                - Rushing yards
                - Rushing touchdowns
                
                Only provide real 2023 regular season stats from official NFL sources.
                
                Format as JSON:
                {{
                    "passing_yards_2023": yards_or_null,
                    "passing_tds_2023": tds_or_null,
                    "passing_ints_2023": ints_or_null,
                    "rushing_yards_2023": yards_or_null,
                    "rushing_tds_2023": tds_or_null
                }}
                """
            elif position.upper() in ['RB', 'FB']:
                prompt = f"""
                Find 2023 NFL regular season statistics for {position} {player_name}:
                - Rushing yards
                - Rushing touchdowns
                - Receiving yards
                - Receiving touchdowns
                
                Only provide real 2023 regular season stats.
                
                Format as JSON:
                {{
                    "rushing_yards_2023": yards_or_null,
                    "rushing_tds_2023": tds_or_null,
                    "receiving_yards_2023": yards_or_null,
                    "receiving_tds_2023": tds_or_null
                }}
                """
            elif position.upper() in ['WR', 'TE']:
                prompt = f"""
                Find 2023 NFL regular season statistics for {position} {player_name}:
                - Receiving yards
                - Receiving touchdowns
                - Receptions
                
                Only provide real 2023 regular season stats.
                
                Format as JSON:
                {{
                    "receiving_yards_2023": yards_or_null,
                    "receiving_tds_2023": tds_or_null,
                    "receptions_2023": catches_or_null
                }}
                """
            else:  # Defensive positions
                prompt = f"""
                Find 2023 NFL regular season statistics for {position} {player_name}:
                - Total tackles
                - Sacks
                - Interceptions
                
                Only provide real 2023 regular season defensive stats.
                
                Format as JSON:
                {{
                    "tackles_2023": tackles_or_null,
                    "sacks_2023": sacks_or_null,
                    "interceptions_2023": ints_or_null
                }}
                """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an NFL statistician. Only provide real, verifiable 2023 season statistics. Format your response as valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300
            )
            
            stats_text = response.choices[0].message.content
            stats_data = self.extract_json_from_response(stats_text)
            
            if stats_data:
                for field, value in stats_data.items():
                    if isinstance(value, (int, float)) and value >= 0:  # Allow 0 stats
                        data[field] = int(value)
                
                stats_fields = ['passing_yards_2023', 'rushing_yards_2023', 'receiving_yards_2023', 'tackles_2023', 'sacks_2023']
                if any(data.get(field) is not None for field in stats_fields):
                    data['data_sources'].append('AI 2023 Season Stats')
                    logger.info(f"✅ AI 2023 {position} stats extracted")
            
        except Exception as e:
            logger.debug(f"Error extracting position stats with AI: {e}")
        
        return data