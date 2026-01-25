"""
Proximity Data Collector - Endorsements, Community, Media, Business
Collects all proximity-related data from free sources
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional
from urllib.parse import quote
import time

logger = logging.getLogger(__name__)


class ProximityCollector:
    """Collect endorsements, community involvement, media appearances, and business ventures"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        # Set default timeout for all requests
        self.default_timeout = 3  # 3 second timeout per request
        
        # Major brands list for verification
        self.major_brands = [
            # Sports & Athletic
            'Nike', 'Adidas', 'Under Armour', 'Puma', 'New Balance', 'Reebok', 'Jordan Brand',
            # Beverages
            'Gatorade', 'Powerade', 'BodyArmor', 'Coca-Cola', 'Pepsi', 'Red Bull', 'Monster Energy',
            # Food & Restaurants
            'McDonald\'s', 'Subway', 'Pizza Hut', 'Chipotle', 'Wendy\'s', 'Taco Bell',
            # Tech
            'Apple', 'Samsung', 'Microsoft', 'Google', 'Amazon', 'Bose', 'Beats by Dre',
            # Insurance
            'State Farm', 'Allstate', 'Geico', 'Progressive', 'Nationwide',
            # Financial
            'Visa', 'Mastercard', 'American Express', 'Chase', 'Bank of America',
            # Gaming & Entertainment
            'EA Sports', 'Madden', 'FIFA', '2K Sports', 'Panini', 'Topps',
            # Other
            'Subway', 'FanDuel', 'DraftKings', 'Fanatics'
        ]
    
    def collect_all_proximity_data(self, player_name: str, sport: str = 'nfl') -> Dict:
        """Collect all proximity data for a player - optimized with parallel collection"""
        logger.info(f"🎯 Collecting proximity data for {player_name}...")
        
        data = {
            'endorsements': [],
            'endorsement_value': None,
            'brand_partnerships': [],
            'upcoming_media': [],
            'recent_interviews': [],
            'podcast_appearances': [],
            'business_ventures': [],
            'investments': [],
            'off_field_achievements': [],
            'community_involvement': [],
            'charitable_organizations': []
        }
        
        # Collect categories in parallel for speed
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all tasks
            endorsement_future = executor.submit(self.get_endorsements, player_name, sport)
            community_future = executor.submit(self.get_community_involvement, player_name)
            media_future = executor.submit(self.get_media_appearances, player_name)
            business_future = executor.submit(self.get_business_ventures, player_name)
            
            # Collect results with individual timeouts
            try:
                endorsement_data = endorsement_future.result(timeout=5)
                data['endorsements'] = endorsement_data.get('endorsements', [])
                data['endorsement_value'] = endorsement_data.get('estimated_value')
                data['brand_partnerships'] = endorsement_data.get('partnerships', [])
            except (FuturesTimeoutError, Exception) as e:
                logger.debug(f"Endorsement collection failed: {e}")
            
            try:
                community_data = community_future.result(timeout=5)
                data['community_involvement'] = community_data.get('activities', [])
                data['charitable_organizations'] = community_data.get('organizations', [])
                data['off_field_achievements'] = community_data.get('achievements', [])
            except (FuturesTimeoutError, Exception) as e:
                logger.debug(f"Community collection failed: {e}")
            
            try:
                media_data = media_future.result(timeout=5)
                data['recent_interviews'] = media_data.get('interviews', [])
                data['podcast_appearances'] = media_data.get('podcasts', [])
                data['upcoming_media'] = media_data.get('upcoming', [])
            except (FuturesTimeoutError, Exception) as e:
                logger.debug(f"Media collection failed: {e}")
            
            try:
                business_data = business_future.result(timeout=5)
                data['business_ventures'] = business_data.get('ventures', [])
                data['investments'] = business_data.get('investments', [])
            except (FuturesTimeoutError, Exception) as e:
                logger.debug(f"Business collection failed: {e}")
        
        # Summary
        total_items = (len(data['endorsements']) + len(data['community_involvement']) + 
                      len(data['recent_interviews']) + len(data['business_ventures']))
        logger.info(f"✅ Collected {total_items} proximity data points for {player_name}")
        
        return data
    
    def get_endorsements(self, player_name: str, sport: str = 'nfl') -> Dict:
        """
        Get endorsement deals from multiple sources
        Sources: Wikipedia, Forbes, Instagram, Google News
        """
        logger.info(f"   💼 Collecting endorsements for {player_name}...")
        
        endorsements = []
        partnerships = []
        estimated_value = None
        
        # 1. Wikipedia - "Endorsements" section
        wiki_endorsements = self._get_wikipedia_endorsements(player_name)
        endorsements.extend(wiki_endorsements)
        
        # 2. Forbes - Off-field earnings
        forbes_data = self._get_forbes_earnings(player_name, sport)
        if forbes_data:
            estimated_value = forbes_data.get('off_field_earnings')
            endorsements.extend(forbes_data.get('brands', []))
        
        # 3. Google News - Search for endorsement deals
        news_endorsements = self._search_news_endorsements(player_name)
        endorsements.extend(news_endorsements)
        
        # 4. Instagram Bio - Brand mentions
        instagram_brands = self._get_instagram_brand_mentions(player_name)
        partnerships.extend(instagram_brands)
        
        # Deduplicate and verify against major brands list
        verified_endorsements = []
        for endorsement in endorsements:
            brand = endorsement if isinstance(endorsement, str) else endorsement.get('brand', '')
            for major_brand in self.major_brands:
                if major_brand.lower() in brand.lower():
                    if major_brand not in verified_endorsements:
                        verified_endorsements.append(major_brand)
                    break
        
        logger.info(f"      ✅ Found {len(verified_endorsements)} verified endorsements")
        
        return {
            'endorsements': verified_endorsements,
            'partnerships': list(set(partnerships)),
            'estimated_value': estimated_value
        }
    
    def _get_wikipedia_endorsements(self, player_name: str) -> List[str]:
        """Extract endorsements from Wikipedia"""
        try:
            url = f"https://en.wikipedia.org/wiki/{quote(player_name.replace(' ', '_'))}"
            response = self.session.get(url, timeout=self.default_timeout)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for "Endorsements" section
                endorsements = []
                for heading in soup.find_all(['h2', 'h3']):
                    if 'endorsement' in heading.get_text().lower() or 'sponsorship' in heading.get_text().lower():
                        # Get the content after this heading
                        sibling = heading.find_next_sibling()
                        while sibling and sibling.name not in ['h2', 'h3']:
                            text = sibling.get_text()
                            # Look for brand names
                            for brand in self.major_brands:
                                if brand.lower() in text.lower():
                                    endorsements.append(brand)
                            sibling = sibling.find_next_sibling()
                
                if endorsements:
                    logger.info(f"      📚 Wikipedia: Found {len(endorsements)} endorsements")
                
                return list(set(endorsements))
        except Exception as e:
            logger.debug(f"Wikipedia endorsements failed: {e}")
        
        return []
    
    def _get_forbes_earnings(self, player_name: str, sport: str) -> Optional[Dict]:
        """Search Forbes for off-field earnings"""
        try:
            # Search Forbes
            search_query = f"{player_name} {sport} earnings"
            search_url = f"https://www.forbes.com/search/?q={quote(search_query)}"
            
            response = self.session.get(search_url, timeout=self.default_timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for articles about earnings
                for link in soup.find_all('a', href=True):
                    if 'highest-paid' in link['href'].lower() or 'earnings' in link['href'].lower():
                        article_url = link['href']
                        if not article_url.startswith('http'):
                            article_url = f"https://www.forbes.com{article_url}"
                        
                        # Get the article
                        article_response = self.session.get(article_url, timeout=self.default_timeout)
                        if article_response.status_code == 200:
                            article_soup = BeautifulSoup(article_response.content, 'html.parser')
                            text = article_soup.get_text()
                            
                            # Look for off-field earnings pattern
                            earnings_match = re.search(r'off[- ]field.*?\$\s*([\d.]+)\s*(million|billion)?', text, re.I)
                            if earnings_match:
                                value = float(earnings_match.group(1))
                                multiplier = earnings_match.group(2)
                                if multiplier and 'million' in multiplier.lower():
                                    value *= 1_000_000
                                elif multiplier and 'billion' in multiplier.lower():
                                    value *= 1_000_000_000
                                
                                # Extract brands mentioned
                                brands = []
                                for brand in self.major_brands:
                                    if brand.lower() in text.lower():
                                        brands.append(brand)
                                
                                logger.info(f"      💰 Forbes: ${int(value):,} off-field earnings")
                                return {
                                    'off_field_earnings': int(value),
                                    'brands': brands
                                }
        except Exception as e:
            logger.debug(f"Forbes earnings failed: {e}")
        
        return None
    
    def _search_news_endorsements(self, player_name: str) -> List[str]:
        """Search Google News for endorsement announcements"""
        endorsements = []
        try:
            search_query = f"{player_name} endorsement deal"
            search_url = f"https://www.google.com/search?q={quote(search_query)}&tbm=nws"
            
            response = self.session.get(search_url, timeout=self.default_timeout)
            if response.status_code == 200:
                text = response.text
                
                # Look for brand names in news results
                for brand in self.major_brands:
                    # Pattern: "[Brand] signs [Player]" or "[Player] signs with [Brand]"
                    if brand.lower() in text.lower():
                        endorsements.append(brand)
                
                if endorsements:
                    logger.info(f"      📰 Google News: Found {len(endorsements)} endorsements")
        except Exception as e:
            logger.debug(f"News endorsements search failed: {e}")
        
        return list(set(endorsements))
    
    def _get_instagram_brand_mentions(self, player_name: str) -> List[str]:
        """Extract brand partnerships from Instagram bio (if available)"""
        # This would require Instagram handle, which we get from social collector
        # For now, return empty - can be integrated later
        return []
    
    def get_community_involvement(self, player_name: str) -> Dict:
        """
        Get community involvement and charitable work
        Sources: Wikipedia, Team website, Google News
        """
        logger.info(f"   🤲 Collecting community involvement for {player_name}...")
        
        activities = []
        organizations = []
        achievements = []
        
        # 1. Wikipedia - "Philanthropy" or "Personal life" sections
        wiki_data = self._get_wikipedia_philanthropy(player_name)
        activities.extend(wiki_data.get('activities', []))
        organizations.extend(wiki_data.get('organizations', []))
        
        # 2. Google News - Search for charity work
        news_charity = self._search_charity_news(player_name)
        activities.extend(news_charity)
        
        # Deduplicate
        activities = list(set(activities))
        organizations = list(set(organizations))
        
        logger.info(f"      ✅ Found {len(organizations)} charitable organizations, {len(activities)} activities")
        
        return {
            'activities': activities,
            'organizations': organizations,
            'achievements': achievements
        }
    
    def _get_wikipedia_philanthropy(self, player_name: str) -> Dict:
        """Extract philanthropy info from Wikipedia"""
        try:
            url = f"https://en.wikipedia.org/wiki/{quote(player_name.replace(' ', '_'))}"
            response = self.session.get(url, timeout=self.default_timeout)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                activities = []
                organizations = []
                
                # Look for philanthropy/charity/community sections
                keywords = ['philanthropy', 'charity', 'charitable', 'community', 'foundation']
                for heading in soup.find_all(['h2', 'h3']):
                    heading_text = heading.get_text().lower()
                    if any(keyword in heading_text for keyword in keywords):
                        # Get content after this heading
                        sibling = heading.find_next_sibling()
                        while sibling and sibling.name not in ['h2', 'h3']:
                            text = sibling.get_text()
                            
                            # Extract foundation/organization names
                            org_patterns = [
                                r'([A-Z][A-Za-z\s]+Foundation)',
                                r'([A-Z][A-Za-z\s]+Charity)',
                                r'([A-Z][A-Za-z\s]+Fund)',
                            ]
                            for pattern in org_patterns:
                                matches = re.findall(pattern, text)
                                organizations.extend(matches)
                            
                            # Extract activities (sentences mentioning charity work)
                            sentences = text.split('.')
                            for sentence in sentences:
                                if any(keyword in sentence.lower() for keyword in keywords):
                                    if len(sentence) > 20 and len(sentence) < 200:
                                        activities.append(sentence.strip())
                            
                            sibling = sibling.find_next_sibling()
                
                return {
                    'activities': list(set(activities))[:5],  # Top 5
                    'organizations': list(set(organizations))
                }
        except Exception as e:
            logger.debug(f"Wikipedia philanthropy failed: {e}")
        
        return {'activities': [], 'organizations': []}
    
    def _search_charity_news(self, player_name: str) -> List[str]:
        """Search for charity work in news"""
        activities = []
        try:
            search_query = f"{player_name} charity OR foundation OR donation"
            search_url = f"https://www.google.com/search?q={quote(search_query)}&tbm=nws"
            
            response = self.session.get(search_url, timeout=self.default_timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract headlines that mention charity work
                for heading in soup.find_all(['h3', 'div'], class_=re.compile('heading|title', re.I)):
                    text = heading.get_text()
                    if any(word in text.lower() for word in ['charity', 'donation', 'foundation', 'community']):
                        if len(text) > 20 and len(text) < 150:
                            activities.append(text.strip())
                
                return list(set(activities))[:3]  # Top 3 recent
        except Exception as e:
            logger.debug(f"Charity news search failed: {e}")
        
        return []
    
    def get_media_appearances(self, player_name: str) -> Dict:
        """
        Get media appearances (interviews, podcasts)
        Sources: YouTube, Spotify, Google search
        """
        logger.info(f"   🎙️ Collecting media appearances for {player_name}...")
        
        interviews = []
        podcasts = []
        upcoming = []
        
        # 1. YouTube - Search for recent interviews
        youtube_interviews = self._search_youtube_interviews(player_name)
        interviews.extend(youtube_interviews)
        
        # 2. Spotify - Search for podcast appearances
        spotify_podcasts = self._search_spotify_podcasts(player_name)
        podcasts.extend(spotify_podcasts)
        
        # 3. Google News - Search for interview announcements
        news_interviews = self._search_news_interviews(player_name)
        interviews.extend(news_interviews)
        
        logger.info(f"      ✅ Found {len(interviews)} interviews, {len(podcasts)} podcasts")
        
        return {
            'interviews': list(set(interviews))[:10],  # Top 10 recent
            'podcasts': list(set(podcasts))[:10],
            'upcoming': upcoming
        }
    
    def _search_youtube_interviews(self, player_name: str) -> List[str]:
        """Search YouTube for interviews"""
        interviews = []
        try:
            # YouTube search (without API - just scrape search results)
            search_query = f"{player_name} interview"
            search_url = f"https://www.youtube.com/results?search_query={quote(search_query)}"
            
            response = self.session.get(search_url, timeout=self.default_timeout)
            if response.status_code == 200:
                # Extract video titles from search results
                title_pattern = r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]'
                matches = re.findall(title_pattern, response.text)
                
                # Filter for interviews
                for match in matches:
                    if 'interview' in match.lower() and player_name.split()[0].lower() in match.lower():
                        interviews.append(match)
                
                return list(set(interviews))[:5]  # Top 5
        except Exception as e:
            logger.debug(f"YouTube search failed: {e}")
        
        return []
    
    def _search_spotify_podcasts(self, player_name: str) -> List[str]:
        """Search Spotify for podcast appearances"""
        podcasts = []
        try:
            # Spotify search (web scraping - no API needed)
            search_query = f"{player_name} podcast"
            search_url = f"https://open.spotify.com/search/{quote(search_query)}/episodes"
            
            response = self.session.get(search_url, timeout=self.default_timeout)
            if response.status_code == 200:
                # Extract episode titles
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Spotify uses dynamic content, but we can try to extract from HTML
                for div in soup.find_all('div'):
                    text = div.get_text()
                    if player_name.split()[0] in text and len(text) > 10 and len(text) < 150:
                        podcasts.append(text.strip())
                
                return list(set(podcasts))[:5]
        except Exception as e:
            logger.debug(f"Spotify search failed: {e}")
        
        return []
    
    def _search_news_interviews(self, player_name: str) -> List[str]:
        """Search news for interview announcements"""
        interviews = []
        try:
            search_query = f"{player_name} interview"
            search_url = f"https://www.google.com/search?q={quote(search_query)}&tbm=nws"
            
            response = self.session.get(search_url, timeout=self.default_timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                for heading in soup.find_all(['h3', 'div'], class_=re.compile('heading|title', re.I)):
                    text = heading.get_text()
                    if 'interview' in text.lower() and len(text) > 20 and len(text) < 150:
                        interviews.append(text.strip())
                
                return list(set(interviews))[:5]
        except Exception as e:
            logger.debug(f"News interview search failed: {e}")
        
        return []
    
    def get_business_ventures(self, player_name: str) -> Dict:
        """
        Get business ventures and investments
        Sources: LinkedIn, Crunchbase, Wikipedia, Google News
        """
        logger.info(f"   💼 Collecting business ventures for {player_name}...")
        
        ventures = []
        investments = []
        
        # 1. Wikipedia - "Business career" section
        wiki_business = self._get_wikipedia_business(player_name)
        ventures.extend(wiki_business.get('ventures', []))
        investments.extend(wiki_business.get('investments', []))
        
        # 2. Google News - Search for business launches
        news_business = self._search_business_news(player_name)
        ventures.extend(news_business)
        
        # Deduplicate
        ventures = list(set(ventures))
        investments = list(set(investments))
        
        logger.info(f"      ✅ Found {len(ventures)} ventures, {len(investments)} investments")
        
        return {
            'ventures': ventures,
            'investments': investments
        }
    
    def _get_wikipedia_business(self, player_name: str) -> Dict:
        """Extract business info from Wikipedia"""
        try:
            url = f"https://en.wikipedia.org/wiki/{quote(player_name.replace(' ', '_'))}"
            response = self.session.get(url, timeout=self.default_timeout)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                ventures = []
                investments = []
                
                # Look for business sections
                keywords = ['business', 'venture', 'investment', 'entrepreneur', 'company']
                for heading in soup.find_all(['h2', 'h3']):
                    heading_text = heading.get_text().lower()
                    if any(keyword in heading_text for keyword in keywords):
                        sibling = heading.find_next_sibling()
                        while sibling and sibling.name not in ['h2', 'h3']:
                            text = sibling.get_text()
                            
                            # Extract company/venture names
                            # Pattern: Founded [Company Name] or invested in [Company Name]
                            if 'founded' in text.lower() or 'co-founded' in text.lower():
                                company_match = re.search(r'(?:founded|co-founded)\s+([A-Z][A-Za-z\s&]+)', text)
                                if company_match:
                                    ventures.append(company_match.group(1).strip())
                            
                            if 'invested' in text.lower() or 'investment' in text.lower():
                                company_match = re.search(r'(?:invested in|investment in)\s+([A-Z][A-Za-z\s&]+)', text)
                                if company_match:
                                    investments.append(company_match.group(1).strip())
                            
                            sibling = sibling.find_next_sibling()
                
                return {
                    'ventures': list(set(ventures)),
                    'investments': list(set(investments))
                }
        except Exception as e:
            logger.debug(f"Wikipedia business failed: {e}")
        
        return {'ventures': [], 'investments': []}
    
    def _search_business_news(self, player_name: str) -> List[str]:
        """Search for business ventures in news"""
        ventures = []
        try:
            search_query = f"{player_name} launches OR invests OR business venture"
            search_url = f"https://www.google.com/search?q={quote(search_query)}&tbm=nws"
            
            response = self.session.get(search_url, timeout=self.default_timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                for heading in soup.find_all(['h3', 'div'], class_=re.compile('heading|title', re.I)):
                    text = heading.get_text()
                    keywords = ['launches', 'invests', 'business', 'company', 'startup']
                    if any(word in text.lower() for word in keywords):
                        if len(text) > 20 and len(text) < 150:
                            ventures.append(text.strip())
                
                return list(set(ventures))[:5]
        except Exception as e:
            logger.debug(f"Business news search failed: {e}")
        
        return []


# Standalone usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    collector = ProximityCollector()
    
    # Test with Patrick Mahomes
    data = collector.collect_all_proximity_data("Patrick Mahomes", "nfl")
    print(f"\nProximity Data:")
    print(f"Endorsements: {data['endorsements']}")
    print(f"Endorsement Value: ${data['endorsement_value']:,}" if data['endorsement_value'] else "Endorsement Value: Unknown")
    print(f"Community: {data['community_involvement'][:3] if data['community_involvement'] else 'None'}")
    print(f"Charities: {data['charitable_organizations']}")
    print(f"Business Ventures: {data['business_ventures']}")
    print(f"Interviews: {data['recent_interviews'][:3] if data['recent_interviews'] else 'None'}")
    print(f"Podcasts: {data['podcast_appearances'][:3] if data['podcast_appearances'] else 'None'}")

