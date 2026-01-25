"""
Advanced Risk Analyzer - FREE (No Firecrawl needed)
Analyzes controversies, legal issues, and overall player risk
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class AdvancedRiskAnalyzer:
    """Analyze controversies, legal issues, and reputation risks"""
    
    # Controversy keywords and severity
    CONTROVERSY_KEYWORDS = {
        # Very high severity
        'arrest': 10, 'charged': 10, 'criminal': 10, 'felony': 10,
        'lawsuit': 9, 'sued': 9, 'assault': 10, 'dui': 9,
        
        # High severity
        'suspended': 8, 'suspension': 8, 'banned': 9, 'conduct policy': 8,
        'domestic': 9, 'violence': 9, 'drugs': 8,
        
        # Medium severity
        'fine': 6, 'fined': 6, 'penalty': 6, 'violation': 6,
        'controversy': 7, 'incident': 5, 'altercation': 6,
        
        # Lower severity
        'criticized': 3, 'criticism': 3, 'dispute': 4, 'argument': 3
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def analyze_risk(self, player_name: str, sport: str = 'nfl') -> Dict:
        """
        Comprehensive risk analysis
        
        Args:
            player_name: Player's name
            sport: 'nfl' or 'nba'
        
        Returns:
            Dict with risk analysis
        """
        logger.info(f"⚠️  Analyzing risk factors for {player_name}...")
        
        risk_data = {
            'controversies_count': 0,
            'controversies': [],
            'arrests_count': 0,
            'suspensions_count': 0,
            'fines_count': 0,
            'controversy_risk_score': 0,
            'reputation_score': 100,
            'holdout_risk': False,
            'trade_rumors_count': 0,
            'team_issues': [],
            'legal_issues': []
        }
        
        # 1. Search for controversies
        controversies = self._search_controversies(player_name)
        if controversies:
            risk_data['controversies'] = controversies
            risk_data['controversies_count'] = len(controversies)
            
            # Count specific types
            for controversy in controversies:
                c_type = controversy.get('type', '').lower()
                if 'arrest' in c_type or 'charged' in c_type:
                    risk_data['arrests_count'] += 1
                if 'suspend' in c_type:
                    risk_data['suspensions_count'] += 1
                if 'fine' in c_type:
                    risk_data['fines_count'] += 1
            
            # Calculate controversy risk score
            risk_data['controversy_risk_score'] = self._calculate_controversy_risk(controversies)
        
        # 2. Check for legal issues
        legal_issues = self._search_legal_issues(player_name)
        if legal_issues:
            risk_data['legal_issues'] = legal_issues
        
        # 3. Check for holdout/contract dispute risks
        risk_data['holdout_risk'] = self._check_holdout_risk(player_name)
        
        # 4. Check for trade rumors
        trade_rumors = self._search_trade_rumors(player_name)
        risk_data['trade_rumors_count'] = len(trade_rumors)
        
        # 5. Check for team issues
        team_issues = self._search_team_issues(player_name)
        if team_issues:
            risk_data['team_issues'] = team_issues
        
        # 6. Calculate reputation score (100 = perfect, 0 = very bad)
        risk_data['reputation_score'] = self._calculate_reputation_score(risk_data)
        
        logger.info(f"✅ Risk analysis: {risk_data['controversies_count']} controversies, "
                   f"reputation: {risk_data['reputation_score']}/100, "
                   f"risk score: {risk_data['controversy_risk_score']}/100")
        
        return risk_data
    
    def _search_controversies(self, player_name: str) -> List[Dict]:
        """Search for controversies and incidents"""
        try:
            controversies = []
            
            # Search for various controversy-related terms
            search_terms = [
                f'"{player_name}" arrested',
                f'"{player_name}" suspended',
                f'"{player_name}" fined',
                f'"{player_name}" controversy'
            ]
            
            for term in search_terms:
                url = f"https://duckduckgo.com/html/?q={term.replace(' ', '+')}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    results = soup.find_all('a', class_='result__a')
                    
                    for result in results[:10]:
                        title = result.get_text().lower()
                        url = result.get('href', '')
                        
                        # Check if it matches controversy keywords
                        for keyword, severity in self.CONTROVERSY_KEYWORDS.items():
                            if keyword in title and keyword in term.lower():
                                controversies.append({
                                    'type': keyword.title(),
                                    'headline': title,
                                    'url': url,
                                    'severity': severity,
                                    'date': datetime.now() - timedelta(days=180)  # Approximate
                                })
                                break
                
                time.sleep(1)  # Rate limiting
            
            # Deduplicate based on headline similarity
            unique_controversies = self._deduplicate_controversies(controversies)
            
            return unique_controversies[:15]  # Limit to 15
            
        except Exception as e:
            logger.debug(f"Controversy search failed: {e}")
            return []
    
    def _search_legal_issues(self, player_name: str) -> List[Dict]:
        """Search for legal issues and lawsuits"""
        try:
            legal_issues = []
            
            search_query = f'"{player_name}" lawsuit OR charged OR indicted'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find_all('a', class_='result__a')
                
                for result in results[:10]:
                    title = result.get_text()
                    url = result.get('href', '')
                    
                    if any(word in title.lower() for word in ['lawsuit', 'sued', 'charged', 'indicted', 'court']):
                        legal_issues.append({
                            'headline': title,
                            'url': url
                        })
            
            return legal_issues[:5]
            
        except Exception as e:
            logger.debug(f"Legal issues search failed: {e}")
            return []
    
    def _check_holdout_risk(self, player_name: str) -> bool:
        """Check for contract holdout risk"""
        try:
            search_query = f'"{player_name}" holdout OR "contract dispute" OR "wants new deal"'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}&df=m"  # Last month
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                text = response.text.lower()
                # Check for holdout-related keywords
                if any(word in text for word in ['holdout', 'contract dispute', 'wants new deal', 'holding out']):
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Holdout risk check failed: {e}")
            return False
    
    def _search_trade_rumors(self, player_name: str) -> List[str]:
        """Search for trade rumors"""
        try:
            trade_rumors = []
            
            search_query = f'"{player_name}" trade rumors OR traded OR "on the block"'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}&df=m"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find_all('a', class_='result__a')
                
                for result in results[:10]:
                    title = result.get_text()
                    if any(word in title.lower() for word in ['trade', 'traded', 'rumors', 'could be moved']):
                        trade_rumors.append(title)
            
            return trade_rumors[:5]
            
        except Exception as e:
            logger.debug(f"Trade rumors search failed: {e}")
            return []
    
    def _search_team_issues(self, player_name: str) -> List[str]:
        """Search for team-related issues"""
        try:
            team_issues = []
            
            search_query = f'"{player_name}" team issues OR conflict OR "not happy"'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}&df=m"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find_all('a', class_='result__a')
                
                for result in results[:5]:
                    title = result.get_text()
                    if any(word in title.lower() for word in ['conflict', 'issue', 'unhappy', 'problem']):
                        team_issues.append(title)
            
            return team_issues
            
        except Exception as e:
            logger.debug(f"Team issues search failed: {e}")
            return []
    
    def _deduplicate_controversies(self, controversies: List[Dict]) -> List[Dict]:
        """Remove duplicate controversies"""
        seen_headlines = set()
        unique = []
        
        for controversy in controversies:
            headline = controversy.get('headline', '').lower()
            # Use first 50 chars as key to catch similar headlines
            key = headline[:50]
            
            if key not in seen_headlines:
                seen_headlines.add(key)
                unique.append(controversy)
        
        return unique
    
    def _calculate_controversy_risk(self, controversies: List[Dict]) -> int:
        """Calculate overall controversy risk score (0-100)"""
        if not controversies:
            return 0
        
        total_severity = sum(c.get('severity', 0) for c in controversies)
        
        # Weight recent controversies more heavily
        recent_weight = 1.5
        recency_factor = sum(
            c.get('severity', 0) * recent_weight 
            for c in controversies 
            if c.get('date') and (datetime.now() - c['date']).days < 365
        )
        
        # Combine and normalize to 0-100
        score = min((total_severity + recency_factor) * 2, 100)
        
        return int(score)
    
    def _calculate_reputation_score(self, risk_data: Dict) -> int:
        """Calculate reputation score (100 = perfect, 0 = very bad)"""
        base_score = 100
        
        # Deduct for various factors
        deductions = 0
        
        # Arrests (very serious)
        deductions += risk_data['arrests_count'] * 25
        
        # Suspensions (serious)
        deductions += risk_data['suspensions_count'] * 15
        
        # Fines (moderate)
        deductions += risk_data['fines_count'] * 5
        
        # Other controversies
        other_controversies = max(0, risk_data['controversies_count'] - risk_data['arrests_count'] - risk_data['suspensions_count'])
        deductions += other_controversies * 3
        
        # Legal issues
        deductions += len(risk_data.get('legal_issues', [])) * 20
        
        # Holdout risk
        if risk_data.get('holdout_risk'):
            deductions += 10
        
        # Trade rumors (minor factor)
        deductions += min(risk_data.get('trade_rumors_count', 0), 3) * 2
        
        final_score = max(0, base_score - deductions)
        
        return int(final_score)


# Standalone usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    analyzer = AdvancedRiskAnalyzer()
    
    # Test with a player
    risk = analyzer.analyze_risk("Aaron Rodgers", "nfl")
    print(f"\nRisk Data: {risk}")

