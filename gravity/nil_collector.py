"""
NIL Deal Collector - Comprehensive (100% FREE)
Collects NIL (Name, Image, Likeness) deals, valuations, and rankings
Covers 500+ brands across 20+ categories plus smart pattern matching
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional, Set
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class NILDealCollector:
    """Collect NIL deals for college athletes from multiple sources"""
    
    # Comprehensive brand list across all major categories
    COMPREHENSIVE_NIL_BRANDS = [
        # APPAREL & FOOTWEAR
        'nike', 'adidas', 'jordan', 'under armour', 'puma', 'new balance', 'reebok',
        'lululemon', 'gymshark', 'alphalete', 'youngla', 'rawgear', 'champion',
        'fila', 'asics', 'vans', 'converse', 'skechers', 'crocs', 'ugg',
        
        # FOOD & BEVERAGE - Fast Food
        'mcdonalds', 'burger king', 'wendys', 'chick-fil-a', 'taco bell', 'kfc',
        'subway', 'chipotle', 'panera', 'five guys', 'in-n-out', 'whataburger',
        'raising canes', 'popeyes', 'arbys', 'sonic', 'dairy queen', 'culvers',
        
        # FOOD & BEVERAGE - Pizza
        'dominos', 'pizza hut', 'papa johns', 'little caesars', 'marcos pizza',
        'papa murphys', 'hungry howies', 'jets pizza', 'godfathers',
        
        # FOOD & BEVERAGE - Casual Dining
        'applebees', 'chilis', 'buffalo wild wings', 'wingstop', 'hooters',
        'olive garden', 'red lobster', 'texas roadhouse', 'outback steakhouse',
        
        # SPORTS DRINKS & ENERGY
        'gatorade', 'powerade', 'body armor', 'bodyarmor', 'red bull', 'monster',
        'celsius', 'bang energy', 'prime', 'prime hydration', 'liquid iv',
        'pedialyte', 'vitaminwater', 'vitamin water', 'rockstar', '5-hour energy',
        
        # SOFT DRINKS
        'coca-cola', 'pepsi', 'sprite', 'mountain dew', 'dr pepper', 'fanta',
        'crush', 'sunkist', '7up', 'sierra mist', 'starry',
        
        # COFFEE & TEA
        'starbucks', 'dunkin', 'dutch bros', 'tim hortons', 'caribou coffee',
        'peets coffee', 'costa coffee', 'panera bread',
        
        # ALCOHOL (where legal)
        'budweiser', 'coors', 'miller', 'modelo', 'corona', 'heineken',
        'white claw', 'truly', 'high noon', 'bud light', 'michelob',
        
        # AUTOMOTIVE - Major Brands
        'ford', 'chevy', 'chevrolet', 'gmc', 'toyota', 'honda', 'nissan',
        'hyundai', 'kia', 'mazda', 'subaru', 'volkswagen', 'vw',
        'bmw', 'mercedes', 'mercedes-benz', 'audi', 'lexus', 'acura',
        'infiniti', 'cadillac', 'lincoln', 'buick', 'dodge', 'ram',
        'jeep', 'chrysler', 'tesla', 'porsche', 'volvo', 'land rover',
        
        # CRYPTO & WEB3
        'coinbase', 'ftx', 'crypto.com', 'binance', 'kraken', 'gemini',
        'blockchain', 'nft', 'opensea', 'metamask', 'ledger', 'trezor',
        'bitcoin', 'ethereum', 'dogecoin', 'solana', 'cardano', 'polygon',
        
        # TRADING & INVESTMENT
        'robinhood', 'webull', 'etrade', 'td ameritrade', 'charles schwab',
        'fidelity', 'vanguard', 'acorns', 'stash', 'public', 'sofi',
        'm1 finance', 'betterment', 'wealthfront', 'ally invest',
        
        # SPORTS NUTRITION & SUPPLEMENTS
        'c4', 'c4 energy', 'ghost', 'optimum nutrition', 'bsn', 'cellucor',
        'ryse', 'alani nu', 'bucked up', 'gorilla mode', 'transparent labs',
        'muscle milk', 'premier protein', 'core power', 'fairlife', 'oikos',
        'gnc', 'vitamin shoppe', 'bodybuilding.com', 'creatine', 'protein powder',
        
        # GAMING & ESPORTS
        'twitch', 'youtube gaming', 'kick', 'razer', 'steelseries', 'logitech',
        'logitech g', 'hyperx', 'corsair', 'scuf', 'scuf gaming', 'astro',
        'turtle beach', 'elgato', 'alienware', 'asus rog', 'msi',
        'ea sports', 'madden', 'nba 2k', 'fifa', 'call of duty', 'fortnite',
        
        # SOCIAL MEDIA & CONTENT
        'cameo', 'tiktok', 'instagram', 'youtube', 'snapchat', 'twitter',
        'discord', 'patreon', 'substack', 'onlyfans', 'fantime', 'fanfix',
        'overtime', 'bleacher report', 'the players tribune', 'uninterrupted',
        
        # COLLECTIBLES & TRADING CARDS
        'topps', 'panini', 'upper deck', 'fanatics', 'prizm', 'leaf',
        'donruss', 'bowman', 'sorare', 'dapper labs', 'nba top shot',
        
        # INSURANCE
        'state farm', 'geico', 'progressive', 'allstate', 'farmers', 'usaa',
        'liberty mutual', 'nationwide', 'american family', 'travelers',
        
        # TECH & ELECTRONICS - Major Brands
        'apple', 'samsung', 'microsoft', 'sony', 'google', 'meta', 'amazon',
        'lg', 'panasonic', 'vizio', 'tcl', 'roku', 'fire tv',
        
        # TECH & ELECTRONICS - Audio
        'beats', 'beats by dre', 'bose', 'jbl', 'skullcandy', 'airpods',
        'raycon', 'sony headphones', 'sennheiser', 'audio-technica',
        
        # TECH & ELECTRONICS - Other
        'gopro', 'dji', 'ring', 'nest', 'fitbit', 'garmin', 'polar',
        
        # FINANCIAL SERVICES & BANKING
        'chase', 'bank of america', 'wells fargo', 'citi', 'citibank',
        'capital one', 'discover', 'american express', 'amex',
        'venmo', 'paypal', 'cash app', 'zelle', 'apple pay', 'google pay',
        
        # ONLINE PLATFORMS & MARKETPLACES
        'amazon', 'ebay', 'walmart', 'target', 'best buy', 'costco',
        'sams club', 'etsy', 'shopify', 'grubhub', 'doordash', 'uber eats',
        
        # EDUCATION & LEARNING
        'masterclass', 'skillshare', 'udemy', 'coursera', 'khan academy',
        'duolingo', 'babbel', 'rosetta stone', 'grammarly', 'chegg',
        'course hero', 'quizlet', 'brainly', 'tutor.com',
        
        # HEALTH & WELLNESS - Fitness Tech
        'whoop', 'oura', 'oura ring', 'fitbit', 'apple watch', 'garmin',
        'peloton', 'mirror', 'tonal', 'normatec', 'theragun', 'hyperice',
        
        # HEALTH & WELLNESS - Mental Health
        'calm', 'headspace', 'betterhelp', 'talkspace', 'cerebral',
        
        # HEALTH & WELLNESS - Supplements
        'cbd', 'thc', 'hemp', 'melatonin', 'multivitamin', 'vitamin d',
        'magnesium', 'probiotics', 'collagen', 'fish oil', 'omega-3',
        
        # FASHION & ACCESSORIES - Luxury
        'rolex', 'omega', 'tag heuer', 'hublot', 'audemars piguet',
        'cartier', 'patek philippe', 'breitling', 'iwc', 'panerai',
        
        # FASHION & ACCESSORIES - Designer
        'gucci', 'louis vuitton', 'prada', 'versace', 'balenciaga',
        'fendi', 'givenchy', 'dior', 'saint laurent', 'ysl',
        
        # FASHION & ACCESSORIES - Streetwear
        'supreme', 'bape', 'off-white', 'fear of god', 'yeezy',
        'essentials', 'stussy', 'carhartt', 'dickies', 'palace',
        
        # FASHION & ACCESSORIES - Eyewear
        'oakley', 'ray-ban', 'costa', 'maui jim', 'warby parker',
        
        # STREAMING & ENTERTAINMENT
        'netflix', 'hulu', 'disney+', 'disney plus', 'hbo max', 'max',
        'paramount+', 'paramount plus', 'peacock', 'apple tv+', 'prime video',
        'spotify', 'apple music', 'tidal', 'soundcloud', 'pandora',
        'audible', 'kindle', 'audiobooks',
        
        # TRAVEL & HOSPITALITY
        'airbnb', 'vrbo', 'booking.com', 'expedia', 'hotels.com', 'kayak',
        'hilton', 'marriott', 'hyatt', 'ihg', 'holiday inn', 'best western',
        'delta', 'american airlines', 'united', 'southwest', 'jetblue',
        
        # BETTING & DFS (where legal)
        'draftkings', 'fanduel', 'betmgm', 'caesars', 'caesars sportsbook',
        'bet365', 'pointsbet', 'barstool', 'barstool sportsbook', 'wynn bet',
        'fox bet', 'bovada', 'mybookie', 'prizepicks', 'underdog fantasy',
        'sleeper', 'dfs', 'daily fantasy',
        
        # PERSONAL CARE & GROOMING
        'head & shoulders', 'old spice', 'dove', 'axe', 'degree',
        'gillette', 'harrys', "harry's", 'dollar shave club', 'manscaped',
        'native', 'schmidts', "schmidt's", 'dr squatch', 'cremo',
        'nivea', 'neutrogena', 'cetaphil', 'cerave', 'olay',
        
        # HOME & LIVING
        'ikea', 'wayfair', 'home depot', 'lowes', "lowe's", 'ace hardware',
        'bed bath & beyond', 'williams sonoma', 'crate & barrel', 'pottery barn',
        
        # PET PRODUCTS
        'petsmart', 'petco', 'chewy', 'blue buffalo', 'purina', 'iams',
        
        # GROCERY & RETAIL
        'kroger', 'publix', 'safeway', 'whole foods', 'trader joes', "trader joe's",
        'aldi', 'lidl', 'heb', 'wegmans', 'meijer', 'food lion',
        
        # FAST CASUAL & QSR (Additional)
        'jersey mikes', "jersey mike's", 'jimmy johns', "jimmy john's",
        'firehouse subs', 'which wich', 'potbelly', 'blaze pizza',
        'mod pizza', 'pieology', 'sweetgreen', 'cava', 'shake shack',
        
        # REGIONAL/LOCAL INDICATORS (for pattern matching)
        'dealership', 'law firm', 'attorney', 'real estate', 'realtor',
        'restaurant', 'bar', 'brewery', 'gym', 'fitness',
        'car wash', 'auto repair', 'insurance agency', 'clinic',
        'dental', 'chiropractor', 'physical therapy', 'barbershop',
        'salon', 'boutique', 'jewelry'
    ]
    
    # Patterns for detecting NIL deals
    NIL_DEAL_PATTERNS = [
        r'nil\s+deal',
        r'name.*image.*likeness',
        r'signs?\s+with',
        r'partner(s|ship)?\s+(with|agreement)',
        r'brand\s+ambassador',
        r'sponsored\s+by',
        r'endorsement\s+deal',
        r'multi[- ]year.*agreement',
        r'exclusive.*partnership',
        r'#ad\b',
        r'#sponsored\b',
        r'#partner\b',
        r'#brandambassador',
        r'announces?\s+partnership',
        r'teams\s+up\s+with',
        r'collaboration\s+with',
        r'official\s+partner'
    ]
    
    # Value extraction patterns
    VALUE_PATTERNS = [
        r'\$([0-9,]+(?:\.\d+)?)\s*(million|m\b)',
        r'\$([0-9,]+(?:\.\d+)?)\s*(thousand|k\b)',
        r'\$([0-9,]+(?:\.\d+)?)\s*(?:in|worth)',
        r'([0-9,]+(?:\.\d+)?)\s*million\s+dollar',
        r'([0-9,]+(?:\.\d+)?)\s*thousand\s+dollar'
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        # Pre-compile patterns for performance
        self.compiled_nil_patterns = [re.compile(p, re.IGNORECASE) for p in self.NIL_DEAL_PATTERNS]
        self.compiled_value_patterns = [re.compile(p, re.IGNORECASE) for p in self.VALUE_PATTERNS]
    
    def collect_nil_data(self, player_name: str, college: str, sport: str = 'football') -> Dict:
        """
        Collect comprehensive NIL data from multiple sources
        
        Args:
            player_name: Player's full name
            college: College/university name
            sport: 'football' or 'basketball'
        
        Returns:
            Dict with NIL deals, valuation, ranking, and partners
        """
        logger.info(f"💰 Collecting NIL data for {player_name} ({college})...")
        
        nil_data = {
            'nil_valuation': None,
            'nil_ranking': None,
            'nil_deals': [],
            'nil_deal_count': 0,
            'total_nil_value': None,
            'top_nil_partners': [],
            'local_deals_count': 0,
            'national_deals_count': 0,
            'nil_source': None
        }
        
        # 1. On3.com - Best source for NIL valuations and rankings
        logger.info("   Trying On3.com...")
        on3_data = self._get_on3_nil_data(player_name, college, sport)
        if on3_data:
            nil_data.update(on3_data)
            nil_data['nil_source'] = 'On3'
            if on3_data.get('deals'):
                nil_data['nil_deals'].extend(on3_data['deals'])
        
        # 2. Opendorse - NIL marketplace and athlete directory
        logger.info("   Trying Opendorse...")
        opendorse_data = self._get_opendorse_nil_data(player_name, college)
        if opendorse_data:
            if opendorse_data.get('deals'):
                nil_data['nil_deals'].extend(opendorse_data['deals'])
            if not nil_data['nil_valuation'] and opendorse_data.get('valuation'):
                nil_data['nil_valuation'] = opendorse_data['valuation']
                if not nil_data['nil_source']:
                    nil_data['nil_source'] = 'Opendorse'
        
        # 3. News scraping - Public deal announcements
        logger.info("   Scraping news for deals...")
        news_deals = self._scrape_news_for_nil_deals(player_name, college)
        if news_deals:
            nil_data['nil_deals'].extend(news_deals)
        
        # 4. Social media - Player-announced deals
        logger.info("   Checking social media...")
        social_deals = self._scrape_social_media_deals(player_name)
        if social_deals:
            nil_data['nil_deals'].extend(social_deals)
        
        # 5. School website - Athletic department NIL registry
        logger.info("   Checking school website...")
        school_deals = self._scrape_school_nil_data(player_name, college)
        if school_deals:
            nil_data['nil_deals'].extend(school_deals)
        
        # Post-processing
        nil_data['nil_deals'] = self._deduplicate_deals(nil_data['nil_deals'])
        nil_data['nil_deal_count'] = len(nil_data['nil_deals'])
        
        # Categorize deals
        for deal in nil_data['nil_deals']:
            if deal.get('is_local'):
                nil_data['local_deals_count'] += 1
            else:
                nil_data['national_deals_count'] += 1
        
        # Calculate total disclosed value
        total_value = sum(deal.get('value', 0) for deal in nil_data['nil_deals'] if deal.get('value'))
        if total_value > 0:
            nil_data['total_nil_value'] = total_value
        
        # Get top partners
        nil_data['top_nil_partners'] = self._get_top_partners(nil_data['nil_deals'])
        
        # Log results
        if nil_data['nil_valuation'] or nil_data['nil_deal_count'] > 0:
            val_str = f"${nil_data['nil_valuation']:,}" if nil_data['nil_valuation'] else "N/A"
            logger.info(f"✅ NIL Data: {val_str} valuation, {nil_data['nil_deal_count']} deals found")
            if nil_data['top_nil_partners']:
                logger.info(f"   Top partners: {', '.join(nil_data['top_nil_partners'][:5])}")
        else:
            logger.info(f"ℹ️  No NIL data found for {player_name}")
        
        return nil_data
    
    def _get_on3_nil_data(self, player_name: str, college: str, sport: str) -> Optional[Dict]:
        """Scrape On3.com for NIL valuation and ranking"""
        try:
            # On3 search
            search_url = f"https://www.on3.com/db/search/?q={player_name.replace(' ', '+')}"
            
            response = self.session.get(search_url, timeout=15)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text()
            
            data = {}
            
            # Extract NIL valuation using multiple patterns
            # On3 displays like "$1.2M", "$850K", "$1,200,000"
            val_patterns = [
                r'nil.*\$([0-9,.]+)([KMB])?',
                r'\$([0-9,.]+)([KMB])?\s*nil',
                r'valuation.*\$([0-9,.]+)([KMB])?',
                r'\$([0-9,.]+)([KMB])?\s*valuation'
            ]
            
            for pattern in val_patterns:
                val_match = re.search(pattern, page_text, re.IGNORECASE)
                if val_match:
                    value = float(val_match.group(1).replace(',', ''))
                    multiplier = val_match.group(2)
                    if multiplier:
                        if multiplier.upper() == 'K':
                            value *= 1_000
                        elif multiplier.upper() == 'M':
                            value *= 1_000_000
                        elif multiplier.upper() == 'B':
                            value *= 1_000_000_000
                    data['nil_valuation'] = int(value)
                    break
            
            # Extract On3 NIL ranking
            rank_patterns = [
                r'nil.*rank.*#(\d+)',
                r'#(\d+).*nil.*rank',
                r'ranked?\s+#?(\d+).*nil'
            ]
            
            for pattern in rank_patterns:
                rank_match = re.search(pattern, page_text, re.IGNORECASE)
                if rank_match:
                    data['nil_ranking'] = int(rank_match.group(1))
                    break
            
            # Look for deal mentions
            deals = []
            # On3 sometimes lists deals in athlete profiles
            if 'partnerships' in page_text.lower() or 'deals' in page_text.lower():
                # Try to extract brand names near "partnership" or "deal"
                for brand in self.COMPREHENSIVE_NIL_BRANDS:
                    if brand.lower() in page_text.lower():
                        deals.append({
                            'brand': brand.title(),
                            'type': self._categorize_brand(brand),
                            'source': 'On3',
                            'is_local': False
                        })
            
            if deals:
                data['deals'] = deals[:10]  # Limit to top 10
            
            return data if data else None
            
        except Exception as e:
            logger.debug(f"On3 scraping error: {e}")
            return None
    
    def _get_opendorse_nil_data(self, player_name: str, college: str) -> Optional[Dict]:
        """Scrape Opendorse for NIL deals"""
        try:
            # Opendorse athlete search
            search_url = f"https://opendorse.com/athletes?q={player_name.replace(' ', '+')}"
            
            response = self.session.get(search_url, timeout=15)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text()
            
            data = {}
            deals = []
            
            # Look for valuation
            val_match = re.search(r'\$([0-9,.]+)([KM])?', page_text)
            if val_match:
                value = float(val_match.group(1).replace(',', ''))
                if val_match.group(2) == 'K':
                    value *= 1_000
                elif val_match.group(2) == 'M':
                    value *= 1_000_000
                data['valuation'] = int(value)
            
            # Look for brand mentions
            for brand in self.COMPREHENSIVE_NIL_BRANDS:
                if brand.lower() in page_text.lower():
                    deals.append({
                        'brand': brand.title(),
                        'type': self._categorize_brand(brand),
                        'source': 'Opendorse',
                        'is_local': False
                    })
            
            if deals:
                data['deals'] = deals[:10]
            
            return data if data else None
            
        except Exception as e:
            logger.debug(f"Opendorse scraping error: {e}")
            return None
    
    def _scrape_news_for_nil_deals(self, player_name: str, college: str) -> List[Dict]:
        """Search news for NIL deal announcements"""
        try:
            deals = []
            
            # Search queries
            search_queries = [
                f'"{player_name}" NIL deal',
                f'"{player_name}" name image likeness',
                f'"{player_name}" {college} partnership',
                f'"{player_name}" signs endorsement'
            ]
            
            for query in search_queries[:2]:  # Limit to 2 searches for speed
                url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    page_text = soup.get_text().lower()
                    
                    # Use smart detection
                    detected_deals = self._detect_deals_in_text(page_text, player_name)
                    deals.extend(detected_deals)
                
                time.sleep(1)  # Rate limiting
            
            return deals[:15]  # Return top 15 unique deals
            
        except Exception as e:
            logger.debug(f"News scraping failed: {e}")
            return []
    
    def _scrape_social_media_deals(self, player_name: str) -> List[Dict]:
        """Search for NIL deals announced on social media"""
        try:
            deals = []
            
            # Search for social media posts about deals
            search_queries = [
                f'"{player_name}" #ad',
                f'"{player_name}" #sponsored',
                f'"{player_name}" partnership announcement'
            ]
            
            for query in search_queries[:1]:  # Just one query for speed
                url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    page_text = soup.get_text().lower()
                    
                    # Detect deals
                    detected_deals = self._detect_deals_in_text(page_text, player_name)
                    for deal in detected_deals:
                        deal['source'] = 'Social Media'
                    deals.extend(detected_deals)
                
                time.sleep(1)
            
            return deals[:10]
            
        except Exception as e:
            logger.debug(f"Social media scraping failed: {e}")
            return []
    
    def _scrape_school_nil_data(self, player_name: str, college: str) -> List[Dict]:
        """Search school athletic department for NIL disclosures"""
        try:
            deals = []
            
            # Some schools maintain NIL registries
            search_query = f'"{college}" athletics NIL registry "{player_name}"'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                page_text = soup.get_text().lower()
                
                # Detect deals
                detected_deals = self._detect_deals_in_text(page_text, player_name)
                for deal in detected_deals:
                    deal['source'] = 'School Website'
                deals.extend(detected_deals)
            
            return deals[:5]
            
        except Exception as e:
            logger.debug(f"School website scraping failed: {e}")
            return []
    
    def _detect_deals_in_text(self, text: str, player_name: str) -> List[Dict]:
        """
        Smart deal detection using comprehensive brand matching + pattern recognition
        """
        deals = []
        seen_brands = set()
        
        # 1. Match known brands
        for brand in self.COMPREHENSIVE_NIL_BRANDS:
            if brand.lower() in text and brand.lower() not in seen_brands:
                # Check if it's near NIL deal indicators
                brand_context = self._get_context_around_brand(text, brand)
                if self._is_likely_nil_deal(brand_context):
                    deals.append({
                        'brand': brand.title(),
                        'type': self._categorize_brand(brand),
                        'source': 'Detected',
                        'is_local': self._is_local_business(brand)
                    })
                    seen_brands.add(brand.lower())
        
        # 2. Pattern-based detection for unknown brands
        for pattern in self.compiled_nil_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                # Get context around the match
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]
                
                # Try to extract brand name
                brand = self._extract_brand_from_context(context)
                if brand and brand.lower() not in seen_brands:
                    deals.append({
                        'brand': brand.title(),
                        'type': 'Unknown',
                        'source': 'Pattern Match',
                        'is_local': self._is_local_business(brand)
                    })
                    seen_brands.add(brand.lower())
        
        # 3. Extract deal values
        for deal in deals:
            value = self._extract_deal_value(text, deal['brand'])
            if value:
                deal['value'] = value
        
        return deals
    
    def _get_context_around_brand(self, text: str, brand: str, window: int = 100) -> str:
        """Get text context around a brand mention"""
        try:
            index = text.lower().find(brand.lower())
            if index == -1:
                return ""
            start = max(0, index - window)
            end = min(len(text), index + len(brand) + window)
            return text[start:end]
        except:
            return ""
    
    def _is_likely_nil_deal(self, context: str) -> bool:
        """Check if context suggests this is a NIL deal"""
        nil_keywords = ['nil', 'deal', 'partnership', 'sponsor', 'ambassador', 
                       'endorsement', 'signs', 'announces', 'teams up']
        context_lower = context.lower()
        return any(keyword in context_lower for keyword in nil_keywords)
    
    def _extract_brand_from_context(self, context: str) -> Optional[str]:
        """Extract brand name from context using capitalization and patterns"""
        # Look for capitalized words (brand names are usually capitalized)
        words = context.split()
        for i, word in enumerate(words):
            # Look for sequences of capitalized words (e.g., "State Farm", "Nike")
            if word and word[0].isupper():
                # Check next word too
                if i + 1 < len(words) and words[i + 1][0].isupper():
                    return f"{word} {words[i + 1]}"
                return word
        return None
    
    def _extract_deal_value(self, text: str, brand: str) -> Optional[int]:
        """Extract deal value from text"""
        # Get context around brand
        context = self._get_context_around_brand(text, brand, window=200)
        
        for pattern in self.compiled_value_patterns:
            match = pattern.search(context)
            if match:
                value = float(match.group(1).replace(',', ''))
                multiplier = match.group(2) if len(match.groups()) > 1 else None
                
                if multiplier:
                    mult_lower = multiplier.lower()
                    if 'million' in mult_lower or mult_lower == 'm':
                        value *= 1_000_000
                    elif 'thousand' in mult_lower or mult_lower == 'k':
                        value *= 1_000
                
                return int(value)
        
        return None
    
    def _categorize_brand(self, brand: str) -> str:
        """Categorize brand into type"""
        brand_lower = brand.lower()
        
        # Apparel
        if brand_lower in ['nike', 'adidas', 'jordan', 'under armour', 'puma', 'reebok', 'lululemon', 'gymshark']:
            return 'Apparel'
        # Food & Beverage
        elif brand_lower in ['mcdonalds', 'subway', 'chipotle', 'taco bell', 'pizza hut', 'dominos']:
            return 'Food & Beverage'
        # Sports Drinks
        elif brand_lower in ['gatorade', 'powerade', 'body armor', 'bodyarmor', 'prime']:
            return 'Sports Drink'
        # Automotive
        elif brand_lower in ['ford', 'chevy', 'toyota', 'honda', 'nissan', 'mercedes', 'bmw']:
            return 'Automotive'
        # Tech
        elif brand_lower in ['apple', 'samsung', 'microsoft', 'sony', 'beats']:
            return 'Technology'
        # Crypto
        elif brand_lower in ['coinbase', 'crypto.com', 'ftx', 'binance']:
            return 'Crypto/Web3'
        # Gaming
        elif brand_lower in ['twitch', 'youtube', 'razer', 'madden', 'nba 2k']:
            return 'Gaming'
        # Financial
        elif brand_lower in ['robinhood', 'webull', 'chase', 'venmo', 'cash app']:
            return 'Financial Services'
        else:
            return 'Other'
    
    def _is_local_business(self, brand: str) -> bool:
        """Determine if brand is likely a local business"""
        local_indicators = ['dealership', 'law firm', 'attorney', 'real estate', 
                          'restaurant', 'bar', 'gym', 'car wash', 'clinic']
        brand_lower = brand.lower()
        return any(indicator in brand_lower for indicator in local_indicators)
    
    def _deduplicate_deals(self, deals: List[Dict]) -> List[Dict]:
        """Remove duplicate deals based on brand name"""
        seen_brands = set()
        unique_deals = []
        
        for deal in deals:
            brand = deal.get('brand', '').lower()
            if brand and brand not in seen_brands:
                seen_brands.add(brand)
                unique_deals.append(deal)
        
        return unique_deals
    
    def _get_top_partners(self, deals: List[Dict]) -> List[str]:
        """Get list of top NIL partners"""
        partners = [deal.get('brand') for deal in deals if deal.get('brand')]
        return list(dict.fromkeys(partners))[:15]  # Top 15, preserving order


# Standalone usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    collector = NILDealCollector()
    
    # Test with famous college athletes
    test_athletes = [
        ("Shedeur Sanders", "Colorado", "football"),
        ("Bronny James", "USC", "basketball"),
        ("Arch Manning", "Texas", "football"),
    ]
    
    for player_name, college, sport in test_athletes:
        print(f"\n{'='*80}")
        print(f"Testing: {player_name} ({college} {sport})")
        print(f"{'='*80}")
        
        nil_data = collector.collect_nil_data(player_name, college, sport)
        
        print(f"\nNIL Data:")
        if nil_data['nil_valuation']:
            print(f"  Valuation: ${nil_data['nil_valuation']:,}")
        if nil_data['nil_ranking']:
            print(f"  Ranking: #{nil_data['nil_ranking']}")
        print(f"  Total Deals: {nil_data['nil_deal_count']}")
        print(f"  National: {nil_data['national_deals_count']}, Local: {nil_data['local_deals_count']}")
        if nil_data['top_nil_partners']:
            print(f"  Top Partners: {', '.join(nil_data['top_nil_partners'][:10])}")
        if nil_data['total_nil_value']:
            print(f"  Total Disclosed Value: ${nil_data['total_nil_value']:,}")
        
        time.sleep(2)  # Rate limiting between tests

