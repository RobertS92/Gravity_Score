"""
Perplexity API Fallback for Missing Data
Uses Perplexity's web-search-enabled LLM to find missing player data
Only called after all other collection methods (ESPN, PFR, Wikipedia, DuckDuckGo) fail

Cost: ~$0.001 per field search
Expected usage: ~$8-10 for full NFL scrape (2,600 players)
"""
import os
import re
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PerplexityFallback:
    """
    Ultimate fallback for missing player data using Perplexity AI
    Only called after all other collection methods fail
    """
    
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        self.enabled = bool(self.api_key)
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.calls_made = 0
        self.cost_per_call = 0.001  # $0.001 per search
        
        if not self.enabled:
            logger.warning("⚠️  Perplexity API key not set. AI fallback disabled.")
            logger.warning("   Set PERPLEXITY_API_KEY environment variable to enable.")
        else:
            # Validate API key format
            if not self.api_key.startswith('pplx-'):
                logger.warning("⚠️  API key doesn't start with 'pplx-'. This may not be a valid Perplexity API key.")
                logger.warning(f"   Key starts with: '{self.api_key[:10]}...'")
            
            if len(self.api_key) < 20:
                logger.warning("⚠️  API key seems too short. Expected 40+ characters.")
                logger.warning(f"   Key length: {len(self.api_key)}")
            
            logger.info("✅ Perplexity AI fallback enabled")
            logger.info(f"   API key: {self.api_key[:10]}...{self.api_key[-4:]}")
    
    def search_missing_field(self, player_name: str, field_name: str, 
                            sport: str = "NFL", context: Dict[str, Any] = None) -> Optional[Any]:
        """
        Search for a missing field value using Perplexity AI
        
        Args:
            player_name: Name of the player
            field_name: Name of the missing field (e.g., 'draft_year', 'hometown')
            sport: Sport (NFL, NBA, etc.)
            context: Additional context about the player (team, position, etc.)
        
        Returns:
            The found value or None if not found
        """
        if not self.enabled:
            return None
        
        # Build context string
        context_str = ""
        if context:
            if context.get('position'):
                context_str += f"{context['position']}, "
            if context.get('team'):
                context_str += f"{context['team']}, "
            if context.get('college'):
                context_str += f"College: {context['college']}"
        
        # Create specific query based on field type
        query = self._build_query(player_name, field_name, sport, context_str)
        
        logger.info(f"🔍 Perplexity AI searching: {player_name} → {field_name}")
        
        try:
            result = self._call_perplexity(query)
            parsed_value = self._parse_response(result, field_name)
            
            if parsed_value:
                self.calls_made += 1
                cost = self.calls_made * self.cost_per_call
                logger.info(f"   ✅ Found via AI: {field_name} = {parsed_value}")
                logger.debug(f"   💰 Total AI cost: ${cost:.3f} ({self.calls_made} calls)")
                return parsed_value
            else:
                logger.warning(f"   ⚠️  AI could not find: {field_name}")
                return None
                
        except Exception as e:
            logger.error(f"   ❌ Perplexity API error: {e}")
            return None
    
    def search_endorsements(self, player_name: str, sport: str = "NFL", 
                           context: Dict = None) -> Dict:
        """
        Search for player endorsements and brand partnerships
        
        Returns:
            Dict with 'endorsements' (list) and 'endorsement_value' (int)
        """
        if not self.enabled:
            return {'endorsements': [], 'endorsement_value': None}
        
        query = f"""List all known endorsement deals and brand partnerships for {player_name} ({sport} player).

Return in this format:
- Brand names (Nike, Adidas, etc.)
- Estimated total endorsement value if available
- Be specific and factual. Only confirmed deals."""
        
        logger.info(f"🔍 Perplexity AI searching endorsements for {player_name}")
        
        try:
            result = self._call_perplexity(query)
            content = result['choices'][0]['message']['content']
            
            brands = []
            total_value = None
            
            # Extract brand names
            major_brands = ['Nike', 'Adidas', 'Gatorade', 'State Farm', 'Subway', 
                           'McDonald\'s', 'EA Sports', 'Panini', 'Google', 'Apple',
                           'Under Armour', 'Puma', 'New Balance', 'Jordan', 'Bose',
                           'Pepsi', 'Coca-Cola', 'BodyArmor', 'Beats', 'Samsung']
            
            for brand in major_brands:
                if brand.lower() in content.lower():
                    brands.append(brand)
            
            # Extract total value
            value_match = re.search(r'\$\s*(\d+(?:\.\d+)?)\s*(million|M)', content, re.IGNORECASE)
            if value_match:
                total_value = float(value_match.group(1)) * 1_000_000
            
            self.calls_made += 1
            
            if brands or total_value:
                logger.info(f"   ✅ Found via AI: {len(brands)} endorsements, ${total_value or 0:,.0f}")
            
            return {
                'endorsements': brands,
                'endorsement_value': int(total_value) if total_value else None
            }
            
        except Exception as e:
            logger.error(f"   ❌ Endorsement search error: {e}")
            return {'endorsements': [], 'endorsement_value': None}
    
    def check_all_missing_fields(self, player_data, player_name: str, 
                                 sport: str = "NFL", max_cost: float = 0.01) -> int:
        """
        Check ALL missing fields and fill with AI if possible
        
        Args:
            player_data: PlayerData object
            player_name: Player's name
            sport: Sport
            max_cost: Maximum cost to spend per player (default $0.01)
        
        Returns:
            Number of fields filled
        """
        if not self.enabled:
            return 0
        
        fields_filled = 0
        starting_calls = self.calls_made
        max_calls = int(max_cost / self.cost_per_call)
        
        context = {
            'position': getattr(player_data, 'position', None),
            'team': getattr(player_data, 'team', None),
            'college': player_data.identity.college if player_data.identity else None
        }
        
        # Define fields to check (in priority order)
        check_fields = [
            # Priority 1: Critical Identity (always check)
            ('identity', 'draft_year', ['draft_year']),
            ('identity', 'draft_round', ['draft_round']),
            ('identity', 'draft_pick', ['draft_pick']),
            ('identity', 'height', ['height']),
            ('identity', 'weight', ['weight']),
            ('identity', 'hometown', ['hometown']),
            ('identity', 'college', ['college']),
            ('identity', 'nationality', ['nationality']),
            ('identity', 'birth_date', ['birth_date']),
            ('identity', 'years_pro', ['years_pro', 'experience']),
            
            # Priority 2: Market Data
            ('identity', 'contract_value', ['contract_value', 'current_contract_length']),
            ('identity', 'agent', ['agent']),
            ('proximity', 'endorsements', ['endorsements']),
            ('proximity', 'endorsement_value', ['endorsement_value']),
            
            # Priority 3: Social Media
            ('brand', 'instagram_handle', ['instagram_handle']),
            ('brand', 'twitter_handle', ['twitter_handle']),
            ('brand', 'tiktok_handle', ['tiktok_handle']),
            ('brand', 'youtube_channel', ['youtube_channel']),
            
            # Priority 4: Optional (if cost allows)
            ('proximity', 'charitable_organizations', ['charitable_organizations']),
            ('proximity', 'business_ventures', ['business_ventures']),
            ('identity', 'management_company', ['management_company']),
        ]
        
        for section_name, field_name, field_variations in check_fields:
            # Check if we've exceeded max cost
            if (self.calls_made - starting_calls) >= max_calls:
                logger.info(f"   ⚠️  Reached max AI cost limit (${max_cost:.2f})")
                break
            
            # Get the section object
            section = getattr(player_data, section_name, None)
            if not section:
                continue
            
            # Check all field variations
            current_value = None
            for field_var in field_variations:
                current_value = getattr(section, field_var, None)
                if current_value:
                    break
            
            # Check if missing
            is_missing = (
                current_value is None or
                current_value == "" or
                current_value == "Unknown" or
                (field_name == 'draft_year' and current_value == "Undrafted") or
                current_value == 0 or
                (isinstance(current_value, list) and len(current_value) == 0)
            )
            
            if not is_missing:
                continue
            
            logger.debug(f"   🔍 AI checking: {section_name}.{field_name}")
            
            # Special handling for endorsements
            if 'endorsement' in field_name:
                endorsement_data = self.search_endorsements(player_name, sport, context)
                if endorsement_data['endorsements']:
                    setattr(section, 'endorsements', endorsement_data['endorsements'])
                    fields_filled += 1
                if endorsement_data['endorsement_value']:
                    setattr(section, 'endorsement_value', endorsement_data['endorsement_value'])
                    fields_filled += 1
            else:
                # Generic field search
                ai_value = self.search_missing_field(player_name, field_name, sport, context)
                if ai_value:
                    setattr(section, field_name, ai_value)
                    fields_filled += 1
        
        if fields_filled > 0:
            cost_spent = (self.calls_made - starting_calls) * self.cost_per_call
            logger.info(f"   ✅ AI filled {fields_filled} fields (${cost_spent:.3f} spent)")
        
        return fields_filled
    
    def _build_query(self, player_name: str, field_name: str, 
                     sport: str, context: str) -> str:
        """Build an optimized query for the specific field type"""
        
        # Field-specific query templates
        queries = {
            'draft_year': f"What year was {player_name} ({context}) drafted in the {sport} draft? Return only the 4-digit year number or the word 'Undrafted'.",
            'draft_round': f"What round was {player_name} ({context}) drafted in the {sport} draft? Return only the round number (1-7) or 'Undrafted'.",
            'draft_pick': f"What overall pick number was {player_name} ({context}) in the {sport} draft? Return only the pick number or 'Undrafted'.",
            'hometown': f"What is {player_name}'s ({context}) hometown or birthplace city?",
            'high_school': f"What high school did {player_name} ({context}) attend?",
            'college': f"What college or university did {player_name} ({context}) attend? Return just the school name.",
            'nationality': f"What is {player_name}'s ({context}) nationality or country of origin?",
            'birth_date': f"What is {player_name}'s ({context}) birth date or date of birth? Return in format: Month Day, Year (e.g., January 15, 1995).",
            'years_pro': f"How many years has {player_name} ({context}) been a professional {sport} player? Return just the number.",
            'agent': f"Who is {player_name}'s ({context}) current agent or sports representation?",
            'contract_value': f"What is {player_name}'s ({context}) current {sport} contract total value in dollars?",
            'height': f"What is {player_name}'s ({context}) height in feet and inches?",
            'weight': f"What is {player_name}'s ({context}) weight in pounds?",
            'instagram_handle': f"What is {player_name}'s ({context}) official verified Instagram handle (username only, no @)?",
            'twitter_handle': f"What is {player_name}'s ({context}) official verified Twitter/X handle (username only, no @)?",
            'tiktok_handle': f"What is {player_name}'s ({context}) official TikTok handle (username only, no @)?",
            'youtube_channel': f"What is {player_name}'s ({context}) official YouTube channel name?",
            'management_company': f"What is {player_name}'s ({context}) management company or agency?",
        }
        
        # Use specific query if available, otherwise generic
        if field_name in queries:
            query = queries[field_name]
        else:
            query = f"What is {player_name}'s ({context}) {field_name.replace('_', ' ')}? Be specific and factual."
        
        query += " Answer concisely with just the fact, no explanation."
        return query
    
    def _call_perplexity(self, query: str) -> Dict:
        """Make API call to Perplexity"""
        payload = {
            "model": "sonar-pro",  # Updated model name (web search enabled)
            "messages": [
                {
                    "role": "system",
                    "content": "You are a sports data researcher. Provide only factual, verifiable information from the web. Be concise and precise."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "return_citations": True,
            "temperature": 0.1,  # Low temperature for factual responses
            "max_tokens": 150
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)
        
        # Log detailed error if request fails
        if response.status_code != 200:
            try:
                error_detail = response.json()
                logger.error(f"   ❌ API Error ({response.status_code}): {error_detail}")
            except:
                logger.error(f"   ❌ API Error ({response.status_code}): {response.text[:200]}")
        
        response.raise_for_status()
        return response.json()
    
    def _parse_response(self, response: Dict, field_name: str) -> Optional[Any]:
        """Parse the AI response and extract the value"""
        try:
            content = response['choices'][0]['message']['content'].strip()
            
            # Field-specific parsing
            if 'draft_year' in field_name:
                # Extract 4-digit year
                match = re.search(r'\b(19|20)\d{2}\b', content)
                if match:
                    year = int(match.group(0))
                    # Validate year is reasonable (1936 = first NFL draft)
                    if 1936 <= year <= datetime.now().year:
                        return year
                # Check if it says undrafted
                if re.search(r'\bundrafted\b', content, re.IGNORECASE):
                    return "Undrafted"
                    
            elif 'draft_round' in field_name:
                # Extract round number - look for "1st", "2nd", "3rd", "4th" etc or just "1", "2" etc
                match = re.search(r'\b(\d)(?:st|nd|rd|th)?\s+round', content, re.IGNORECASE)
                if match:
                    return int(match.group(1))
                # Also try standalone digit
                match = re.search(r'\b([1-7])\b', content)
                if match:
                    return int(match.group(0))
                if re.search(r'\bundrafted\b', content, re.IGNORECASE):
                    return "Undrafted"
                    
            elif 'draft_pick' in field_name:
                # Extract overall pick number - look for "10th overall", "pick 10", etc
                match = re.search(r'(?:pick\s+)?(\d{1,3})(?:th|st|nd|rd)?\s+(?:overall|pick)', content, re.IGNORECASE)
                if match:
                    pick = int(match.group(1))
                    if 1 <= pick <= 300:
                        return pick
                # Also try standalone number
                match = re.search(r'\b(\d{1,3})\b', content)
                if match:
                    pick = int(match.group(0))
                    if 1 <= pick <= 300:  # Reasonable range
                        return pick
                if re.search(r'\bundrafted\b', content, re.IGNORECASE):
                    return "Undrafted"
            
            elif 'height' in field_name:
                # Extract height (e.g., "6'3\"", "6 feet 3 inches", "6-3")
                # Try feet-inches format first
                match = re.search(r'(\d+)\s*(?:feet|ft|\')\s*(\d+)\s*(?:inches|in|\")?', content, re.IGNORECASE)
                if match:
                    return f"{match.group(1)}' {match.group(2)}\""
                # Try hyphenated format
                match = re.search(r"(\d+)['-](\d+)", content)
                if match:
                    return f"{match.group(1)}' {match.group(2)}\""
            
            elif 'weight' in field_name:
                # Extract weight in pounds
                match = re.search(r'(\d{2,3})\s*(?:lbs?|pounds?)', content, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            
            elif 'college' in field_name:
                # Extract college name - look for "University", "College", "State", etc.
                # Common patterns: "University of X", "X State", "X College"
                match = re.search(r'(?:University of |College of )?([A-Z][A-Za-z\s&-]+(?:University|College|State|Tech|Institute))', content)
                if match:
                    college = match.group(0).strip()
                    # Clean up common prefixes
                    college = re.sub(r'^(?:attended|played at|went to)\s+', '', college, flags=re.IGNORECASE)
                    return college
            
            elif 'nationality' in field_name:
                # Extract nationality/country
                countries = ['American', 'Canadian', 'Mexican', 'Nigerian', 'Samoan', 'Tongan', 
                            'Australian', 'British', 'French', 'German', 'Italian', 'Spanish',
                            'Brazilian', 'Argentine', 'Colombian', 'Jamaican', 'Haitian']
                for country in countries:
                    if country.lower() in content.lower():
                        return country
                # Also check for "USA", "U.S.", "United States"
                if re.search(r'\b(USA|U\.S\.|United States)\b', content, re.IGNORECASE):
                    return "American"
            
            elif 'birth_date' in field_name:
                # Extract birth date - various formats
                # Format 1: Month Day, Year (e.g., "January 15, 1995")
                match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', content, re.IGNORECASE)
                if match:
                    return f"{match.group(1)} {match.group(2)}, {match.group(3)}"
                # Format 2: MM/DD/YYYY
                match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', content)
                if match:
                    return content  # Return as found
                # Format 3: YYYY-MM-DD
                match = re.search(r'(\d{4})-(\d{2})-(\d{2})', content)
                if match:
                    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            
            elif 'years_pro' in field_name or 'experience' in field_name:
                # Extract years of experience - look for numbers
                match = re.search(r'(\d{1,2})\s*(?:years?|seasons?)', content, re.IGNORECASE)
                if match:
                    years = int(match.group(1))
                    if 0 <= years <= 25:  # Reasonable range
                        return years
                # Also try standalone number if context suggests it's years
                match = re.search(r'\b(\d{1,2})\b', content)
                if match:
                    years = int(match.group(1))
                    if 0 <= years <= 25:
                        return years
            
            elif 'handle' in field_name or 'channel' in field_name:
                # Extract social media handle - look for @ followed by handle
                match = re.search(r'@([a-zA-Z0-9_\.]{1,30})', content)
                if match:
                    handle = match.group(1)
                    # Filter out common false positives
                    if handle.lower() not in ['the', 'his', 'her', 'nfl', 'espn', 'handle', 'username']:
                        return handle
                # If no @ found, try "handle is X" or "username: X"
                match = re.search(r'(?:handle|username)(?:\s+is)?\s*:?\s*([a-zA-Z0-9_\.]{1,30})', content, re.IGNORECASE)
                if match:
                    handle = match.group(1)
                    if handle.lower() not in ['the', 'his', 'her', 'nfl', 'espn', 'handle', 'username']:
                        return handle
            
            elif 'contract_value' in field_name:
                # Extract dollar amount
                match = re.search(r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion|M|B)?', content, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    multiplier = match.group(2)
                    if multiplier and ('million' in multiplier.lower() or 'm' in multiplier.lower()):
                        value *= 1_000_000
                    elif multiplier and ('billion' in multiplier.lower() or 'b' in multiplier.lower()):
                        value *= 1_000_000_000
                    return int(value)
            
            # Generic: return the cleaned content if it's reasonable length
            if len(content) < 100 and content.lower() not in ['unknown', 'n/a', 'not found', 'unavailable']:
                return content
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing response: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get usage statistics"""
        return {
            'calls_made': self.calls_made,
            'estimated_cost': self.calls_made * self.cost_per_call,
            'enabled': self.enabled
        }

