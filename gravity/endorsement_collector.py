"""
Endorsement Data Collector - FREE (No Firecrawl needed)
Collects endorsement data from Instagram bios, Google News, and Forbes
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EndorsementCollector:
    """Collect endorsement and brand partnership data from free sources"""
    
    # Common brand keywords to look for
    BRAND_KEYWORDS = [
        'nike', 'adidas', 'jordan', 'under armour', 'puma', 'reebok',
        'gatorade', 'pepsi', 'coca-cola', 'sprite', 'mountain dew',
        'subway', 'mcdonalds', 'burger king', 'pizza hut',
        'state farm', 'geico', 'progressive', 'allstate',
        'amazon', 'apple', 'samsung', 'sony', 'microsoft',
        'beats', 'bose', 'skullcandy', 'jbl',
        'madden', 'nba 2k', 'mlb the show',
        'rolex', 'omega', 'tag heuer', 'hublot',
        'head & shoulders', 'old spice', 'dove', 'axe'
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def collect_endorsement_data(self, player_name: str, sport: str = 'nfl') -> Dict:
        """
        Collect endorsement and brand partnership data
        
        Args:
            player_name: Player's name
            sport: 'nfl' or 'nba'
        
        Returns:
            Dict with endorsement details
        """
        logger.info(f"🤝 Collecting endorsement data for {player_name}...")
        
        endorsement_data = {
            'endorsements': [],
            'brand_partnerships': [],
            'estimated_endorsement_value': None,
            'business_ventures': [],
            'investments': []
        }
        
        # 1. Try to get Instagram bio partnerships
        instagram_brands = self._get_instagram_bio_brands(player_name)
        if instagram_brands:
            endorsement_data['brand_partnerships'].extend(instagram_brands)
        
        # 2. Search Google News for endorsement deals
        news_endorsements = self._search_news_for_endorsements(player_name)
        if news_endorsements:
            endorsement_data['endorsements'].extend(news_endorsements)
        
        # 2.5. Try Wikipedia for endorsement mentions
        wiki_endorsements = self._get_wikipedia_endorsements(player_name)
        if wiki_endorsements:
            endorsement_data['endorsements'].extend(wiki_endorsements)
        
        # 3. Try Forbes for off-field earnings
        forbes_data = self._get_forbes_earnings(player_name, sport)
        if forbes_data:
            endorsement_data['estimated_endorsement_value'] = forbes_data.get('off_field_earnings')
            if forbes_data.get('endorsements'):
                endorsement_data['endorsements'].extend(forbes_data['endorsements'])
        
        # 4. Search for business ventures
        business_ventures = self._search_business_ventures(player_name)
        if business_ventures:
            endorsement_data['business_ventures'] = business_ventures
        
        # Deduplicate
        endorsement_data['endorsements'] = list(set(endorsement_data['endorsements']))
        endorsement_data['brand_partnerships'] = list(set(endorsement_data['brand_partnerships']))
        
        count = len(endorsement_data['endorsements']) + len(endorsement_data['brand_partnerships'])
        if count > 0:
            logger.info(f"✅ Found {count} endorsements/partnerships for {player_name}")
        else:
            logger.info(f"ℹ️  No endorsement data found for {player_name}")
        
        return endorsement_data
    
    def _get_instagram_bio_brands(self, player_name: str) -> List[str]:
        """
        Search for brand partnerships mentioned in player search results
        (Instagram bios are often indexed by search engines)
        """
        try:
            brands_found = []
            
            # Search DuckDuckGo for player + "partnership" or "ambassador"
            search_terms = [
                f'"{player_name}" brand ambassador',
                f'"{player_name}" partnership',
                f'"{player_name}" sponsored by'
            ]
            
            for term in search_terms:
                url = f"https://duckduckgo.com/html/?q={term.replace(' ', '+')}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    text = response.text.lower()
                    # Look for brand keywords in search results
                    for brand in self.BRAND_KEYWORDS:
                        if brand in text and brand not in brands_found:
                            brands_found.append(brand.title())
                
                time.sleep(1)  # Rate limiting
            
            return brands_found[:10]  # Limit to top 10
            
        except Exception as e:
            logger.debug(f"Instagram bio search failed: {e}")
            return []
    
    def _search_news_for_endorsements(self, player_name: str) -> List[str]:
        """Search Google News RSS for endorsement announcements"""
        endorsements = []
        
        try:
            # Search for "{player} endorsement deal" OR "{player} signs with"
            search_terms = [
                f"{player_name} endorsement deal",
                f"{player_name} signs with",
                f"{player_name} partnership",
                f"{player_name} ambassador"
            ]
            
            for term in search_terms:
                try:
                    # Use Google News RSS (free, no API key)
                    from urllib.parse import quote_plus
                    encoded_term = quote_plus(term)
                    url = f"https://news.google.com/rss/search?q={encoded_term}&hl=en-US&gl=US&ceid=US:en"
                    response = self.session.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        # Parse RSS feed for brand mentions
                        content = response.text.lower()
                        for brand in self.BRAND_KEYWORDS:
                            if brand.lower() in content:
                                brand_title = brand.title()
                                if brand_title not in endorsements:
                                    endorsements.append(brand_title)
                except Exception as e:
                    logger.debug(f"News search for '{term}' failed: {e}")
                    continue
            
            # Deduplicate
            return list(set(endorsements))
        except Exception as e:
            logger.warning(f"News endorsement search failed for {player_name}: {e}")
            return []
    
    def _get_wikipedia_endorsements(self, player_name: str) -> List[str]:
        """Parse Wikipedia for endorsement mentions with enhanced section and table parsing"""
        try:
            import wikipedia
            page = wikipedia.page(player_name, auto_suggest=False)
            content = page.content.lower()
            
            endorsements = []
            
            # Enhanced: Try to get HTML for section and table parsing
            try:
                html = page.html()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 1. Parse dedicated Endorsements/Sponsors sections
                for heading in soup.find_all(['h2', 'h3']):
                    heading_text = heading.get_text().lower()
                    if re.search(r'endorsement|sponsor|business|brand|partnership', heading_text, re.I):
                        logger.info(f"   📖 Found endorsement section in Wikipedia: {heading.get_text()}")
                        
                        # Get content after this heading until next heading
                        section_content = []
                        for sibling in heading.find_next_siblings():
                            if sibling.name in ['h2', 'h3']:
                                break
                            section_content.append(sibling.get_text())
                        
                        section_text = ' '.join(section_content)
                        
                        # Extract brand names from section
                        for brand in self.BRAND_KEYWORDS:
                            if brand.lower() in section_text.lower():
                                brand_title = brand.title()
                                if brand_title not in endorsements:
                                    endorsements.append(brand_title)
                                    logger.info(f"      ✓ Found brand in section: {brand_title}")
                
                # 2. Parse tables for endorsement deals
                for table in soup.find_all('table', class_=['wikitable', 'infobox']):
                    table_text = table.get_text().lower()
                    if any(keyword in table_text for keyword in ['sponsor', 'endorsement', 'brand', 'deal']):
                        for brand in self.BRAND_KEYWORDS:
                            if brand.lower() in table_text:
                                brand_title = brand.title()
                                if brand_title not in endorsements:
                                    endorsements.append(brand_title)
                                    logger.info(f"      ✓ Found brand in table: {brand_title}")
                
                # 3. Check infobox for sponsor information
                infobox = soup.find('table', class_='infobox')
                if infobox:
                    infobox_text = infobox.get_text().lower()
                    for brand in self.BRAND_KEYWORDS:
                        if brand.lower() in infobox_text:
                            brand_title = brand.title()
                            if brand_title not in endorsements:
                                endorsements.append(brand_title)
                                logger.info(f"      ✓ Found brand in infobox: {brand_title}")
            except Exception as e:
                logger.debug(f"Enhanced Wikipedia parsing failed, falling back to text search: {e}")
            
            # 4. Fallback: Original text-based search in full content
            for brand in self.BRAND_KEYWORDS:
                # Look for brand mentions near keywords like "endorses", "partnership", "ambassador"
                if brand.lower() in content:
                    # Verify it's in an endorsement context (within 100 chars of endorsement keywords)
                    context_pattern = f"({brand}.*?(endorsement|partnership|ambassador|deal|signs|sponsor)|(endorsement|partnership|ambassador|deal|signs|sponsor).*?{brand})"
                    if re.search(context_pattern, content, re.IGNORECASE):
                        brand_title = brand.title()
                        if brand_title not in endorsements:
                            endorsements.append(brand_title)
            
            if endorsements:
                logger.info(f"   📖 Wikipedia: Found {len(endorsements)} total endorsements for {player_name}")
            return endorsements
        except wikipedia.exceptions.DisambiguationError as e:
            # Try the first suggestion
            try:
                if e.options:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                    content = page.content.lower()
                    endorsements = []
                    for brand in self.BRAND_KEYWORDS:
                        if brand.lower() in content:
                            context_pattern = f"({brand}.*?(endorsement|partnership|ambassador|deal|signs|sponsor)|(endorsement|partnership|ambassador|deal|signs|sponsor).*?{brand})"
                            if re.search(context_pattern, content, re.IGNORECASE):
                                endorsements.append(brand.title())
                    return endorsements
            except Exception:
                pass
            return []
        except Exception as e:
            logger.debug(f"Wikipedia endorsement search failed for {player_name}: {e}")
            return []
    
    def _get_forbes_earnings(self, player_name: str, sport: str) -> Optional[Dict]:
        """
        Try to find player on Forbes highest-paid athletes list
        """
        try:
            # Forbes publishes annual lists - try to scrape current year
            current_year = datetime.now().year
            
            # Search Forbes for player
            search_url = f"https://www.forbes.com/search/?q={player_name.replace(' ', '%20')}+earnings"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for earnings data in search results
                earnings_text = soup.get_text()
                
                # Try to extract off-field earnings
                # Pattern: "off-field: $XX million" or similar
                off_field_match = re.search(r'off[- ]field[:\s]+\$?([\d.]+)\s*(million|m)', earnings_text, re.IGNORECASE)
                if off_field_match:
                    value = float(off_field_match.group(1))
                    multiplier = off_field_match.group(2).lower()
                    if 'million' in multiplier or 'm' == multiplier:
                        value *= 1_000_000
                    
                    return {
                        'off_field_earnings': int(value),
                        'endorsements': []  # Could parse from article
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Forbes scraping failed: {e}")
            return None
    
    def _search_business_ventures(self, player_name: str) -> List[str]:
        """Search for business ventures and investments"""
        try:
            ventures = []
            
            search_terms = [
                f'"{player_name}" owns business',
                f'"{player_name}" founded company',
                f'"{player_name}" restaurant',
                f'"{player_name}" investment'
            ]
            
            for term in search_terms[:2]:  # Limit searches
                url = f"https://duckduckgo.com/html/?q={term.replace(' ', '+')}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    results = soup.find_all('a', class_='result__a')
                    
                    for result in results[:5]:
                        snippet = result.get_text()
                        # Extract business names (simplified)
                        # Look for patterns like "owns XYZ" or "founded ABC"
                        own_match = re.search(r'owns?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', snippet)
                        founded_match = re.search(r'founded\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', snippet)
                        
                        if own_match:
                            ventures.append(own_match.group(1))
                        if founded_match:
                            ventures.append(founded_match.group(1))
                
                time.sleep(1)
            
            return list(set(ventures))[:10]  # Dedupe and limit
            
        except Exception as e:
            logger.debug(f"Business venture search failed: {e}")
            return []


# Standalone usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    collector = EndorsementCollector()
    
    # Test with LeBron James
    endorsements = collector.collect_endorsement_data("LeBron James", "nba")
    print(f"\nEndorsement Data: {endorsements}")

