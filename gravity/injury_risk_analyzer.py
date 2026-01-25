"""
Injury Risk Analyzer - FREE (No Firecrawl needed)
Analyzes injury history and calculates injury risk scores
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class InjuryRiskAnalyzer:
    """Analyze injury history and calculate risk scores"""
    
    # Injury severity weights
    INJURY_SEVERITY = {
        # High severity (season-ending, long recovery)
        'acl': 10, 'achilles': 10, 'concussion': 9, 'torn': 9,
        'fracture': 8, 'broken': 8, 'surgery': 8,
        
        # Medium severity
        'sprain': 6, 'strain': 6, 'hamstring': 6, 'groin': 6,
        'ankle': 5, 'knee': 5, 'shoulder': 5, 'back': 5,
        
        # Lower severity
        'bruise': 3, 'contusion': 3, 'soreness': 2, 'rest': 2
    }
    
    # Position-specific injury risks (based on historical data)
    POSITION_INJURY_RATES = {
        # NFL
        'RB': 85, 'WR': 70, 'TE': 75, 'QB': 60,
        'OL': 65, 'DL': 70, 'LB': 75, 'DB': 65,
        'K': 20, 'P': 15,
        
        # NBA
        'PG': 55, 'SG': 60, 'SF': 65, 'PF': 70, 'C': 75
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def analyze_injury_risk(self, player_name: str, position: str, age: int = None, sport: str = 'nfl') -> Dict:
        """
        Comprehensive injury risk analysis
        
        Args:
            player_name: Player's name
            position: Player's position
            age: Player's age
            sport: 'nfl' or 'nba'
        
        Returns:
            Dict with injury risk analysis
        """
        logger.info(f"🏥 Analyzing injury risk for {player_name}...")
        
        risk_data = {
            'injury_history_count': 0,
            'injury_history': [],
            'current_injury_status': None,
            'injury_risk_score': 0,
            'injury_severity_score': 0,
            'position_injury_rate': 0,
            'age_risk_factor': 0,
            'games_missed_career': 0,
            'games_missed_last_season': 0,
            'injury_prone': False,
            'recovery_status': None
        }
        
        # 1. Get injury history
        injury_history = self._get_injury_history(player_name, sport)
        if injury_history:
            risk_data['injury_history'] = injury_history
            risk_data['injury_history_count'] = len(injury_history)
            
            # Calculate severity score
            risk_data['injury_severity_score'] = self._calculate_severity_score(injury_history)
            
            # Check current injury
            if injury_history:
                latest = injury_history[0]
                if latest.get('status') in ['Out', 'Questionable', 'Doubtful', 'Day-to-Day']:
                    risk_data['current_injury_status'] = latest.get('injury_type', 'Unknown')
                    risk_data['recovery_status'] = latest.get('status')
        
        # 2. Get games missed data
        games_missed = self._estimate_games_missed(injury_history)
        risk_data['games_missed_career'] = games_missed['career']
        risk_data['games_missed_last_season'] = games_missed['last_season']
        
        # 3. Position risk factor
        risk_data['position_injury_rate'] = self.POSITION_INJURY_RATES.get(position, 50)
        
        # 4. Age risk factor (older players = higher risk)
        if age:
            risk_data['age_risk_factor'] = self._calculate_age_risk(age, sport)
        
        # 5. Calculate overall injury risk score (0-100)
        risk_data['injury_risk_score'] = self._calculate_overall_risk(risk_data)
        
        # 6. Determine if injury prone (multiple significant injuries)
        if risk_data['injury_history_count'] >= 3 and risk_data['injury_severity_score'] > 15:
            risk_data['injury_prone'] = True
        
        logger.info(f"✅ Injury risk: {risk_data['injury_risk_score']}/100, "
                   f"{risk_data['injury_history_count']} injuries, "
                   f"current: {risk_data['current_injury_status'] or 'Healthy'}")
        
        return risk_data
    
    def _get_injury_history(self, player_name: str, sport: str) -> List[Dict]:
        """
        Get injury history from multiple sources
        """
        injuries = []
        
        # Try Pro Football Reference / Basketball Reference
        if sport == 'nfl':
            injuries.extend(self._get_pfr_injuries(player_name))
        else:
            injuries.extend(self._get_bbref_injuries(player_name))
        
        # Try news search for recent injuries
        injuries.extend(self._search_injury_news(player_name))
        
        # Deduplicate and sort by date (most recent first)
        injuries = self._deduplicate_injuries(injuries)
        injuries.sort(key=lambda x: x.get('date') or datetime.min, reverse=True)
        
        return injuries
    
    def _get_pfr_injuries(self, player_name: str) -> List[Dict]:
        """Get injury data from Pro Football Reference"""
        try:
            injuries = []
            
            # Clean player name for URL
            name_parts = player_name.replace('.', '').replace("'", '').split()
            if len(name_parts) >= 2:
                # PFR format: last_name + first 2 letters of first name + 00
                last_name = name_parts[-1].lower()
                first_initial = name_parts[0][:2].lower()
                player_slug = f"{last_name}{first_initial}00"
                
                url = f"https://www.pro-football-reference.com/players/{last_name[0]}/{player_slug}.htm"
                
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for injury information in page text
                    text = soup.get_text()
                    
                    # Common injury patterns
                    injury_patterns = [
                        r'injured\s+reserve',
                        r'(\w+)\s+injury',
                        r'missed\s+(\d+)\s+games?',
                        r'(\w+)\s+surgery'
                    ]
                    
                    for pattern in injury_patterns:
                        matches = re.finditer(pattern, text, re.IGNORECASE)
                        for match in matches:
                            injury_type = match.group(1) if match.lastindex >= 1 else 'Unknown'
                            injuries.append({
                                'injury_type': injury_type,
                                'date': datetime.now(),  # Approximate
                                'source': 'pro-football-reference',
                                'status': 'Past'
                            })
            
            return injuries[:10]  # Limit to 10 most relevant
            
        except Exception as e:
            logger.debug(f"PFR injury scraping failed: {e}")
            return []
    
    def _get_bbref_injuries(self, player_name: str) -> List[Dict]:
        """Get injury data from Basketball Reference"""
        try:
            # Similar to PFR but for NBA
            # Implementation similar to _get_pfr_injuries
            return []
        except Exception as e:
            logger.debug(f"Basketball Reference injury scraping failed: {e}")
            return []
    
    def _search_injury_news(self, player_name: str) -> List[Dict]:
        """Search news for injury reports"""
        try:
            injuries = []
            
            search_query = f'"{player_name}" injury OR injured'
            url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}&df=m"  # Last month
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find_all('a', class_='result__a')
                
                for result in results[:20]:
                    title = result.get_text().lower()
                    
                    # Extract injury type
                    injury_type = None
                    for injury, severity in self.INJURY_SEVERITY.items():
                        if injury in title:
                            injury_type = injury.title()
                            break
                    
                    if injury_type:
                        # Determine status from headline
                        status = 'Unknown'
                        if any(word in title for word in ['out', 'miss', 'sidelined']):
                            status = 'Out'
                        elif 'questionable' in title:
                            status = 'Questionable'
                        elif 'return' in title or 'back' in title:
                            status = 'Recovering'
                        
                        injuries.append({
                            'injury_type': injury_type,
                            'date': datetime.now() - timedelta(days=7),  # Approximate
                            'source': 'news',
                            'status': status,
                            'headline': title
                        })
            
            return injuries
            
        except Exception as e:
            logger.debug(f"Injury news search failed: {e}")
            return []
    
    def _deduplicate_injuries(self, injuries: List[Dict]) -> List[Dict]:
        """Remove duplicate injury reports"""
        seen = set()
        unique_injuries = []
        
        for injury in injuries:
            # Create unique key based on injury type and approximate date
            key = (
                injury.get('injury_type', '').lower(),
                injury.get('date', datetime.min).year,
                injury.get('date', datetime.min).month
            )
            
            if key not in seen:
                seen.add(key)
                unique_injuries.append(injury)
        
        return unique_injuries
    
    def _calculate_severity_score(self, injuries: List[Dict]) -> int:
        """Calculate total severity score based on injury history"""
        total_severity = 0
        
        for injury in injuries:
            injury_type = injury.get('injury_type', '').lower()
            
            # Find matching severity weight
            for key, weight in self.INJURY_SEVERITY.items():
                if key in injury_type:
                    total_severity += weight
                    break
        
        return total_severity
    
    def _estimate_games_missed(self, injuries: List[Dict]) -> Dict[str, int]:
        """Estimate games missed based on injuries"""
        # Simplified estimation
        games_missed = {
            'career': 0,
            'last_season': 0
        }
        
        current_year = datetime.now().year
        last_season_start = datetime(current_year - 1, 9, 1)  # Approximate season start
        
        for injury in injuries:
            injury_type = injury.get('injury_type', '').lower()
            injury_date = injury.get('date')
            
            # Estimate games missed based on severity
            if any(severe in injury_type for severe in ['acl', 'achilles', 'torn', 'fracture']):
                games = 10  # Season-ending
            elif any(medium in injury_type for medium in ['sprain', 'strain', 'hamstring']):
                games = 3
            else:
                games = 1
            
            games_missed['career'] += games
            
            if injury_date and injury_date > last_season_start:
                games_missed['last_season'] += games
        
        return games_missed
    
    def _calculate_age_risk(self, age: int, sport: str) -> int:
        """Calculate age-related injury risk (0-100)"""
        if sport == 'nfl':
            # NFL players: risk increases after 28
            if age < 25:
                return 20
            elif age < 28:
                return 40
            elif age < 31:
                return 60
            elif age < 34:
                return 80
            else:
                return 95
        else:  # NBA
            # NBA players: risk increases after 30
            if age < 27:
                return 20
            elif age < 30:
                return 40
            elif age < 33:
                return 60
            elif age < 36:
                return 80
            else:
                return 95
    
    def _calculate_overall_risk(self, risk_data: Dict) -> int:
        """
        Calculate overall injury risk score (0-100)
        Weighted combination of factors
        """
        # Weights
        weights = {
            'injury_count': 0.25,
            'severity': 0.30,
            'position': 0.20,
            'age': 0.15,
            'recent': 0.10
        }
        
        # Normalize factors to 0-100 scale
        injury_count_score = min(risk_data['injury_history_count'] * 20, 100)
        severity_score = min(risk_data['injury_severity_score'] * 3, 100)
        position_score = risk_data['position_injury_rate']
        age_score = risk_data['age_risk_factor']
        recent_score = 100 if risk_data['current_injury_status'] else 0
        
        # Weighted sum
        overall_risk = (
            injury_count_score * weights['injury_count'] +
            severity_score * weights['severity'] +
            position_score * weights['position'] +
            age_score * weights['age'] +
            recent_score * weights['recent']
        )
        
        return int(overall_risk)


# Standalone usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    analyzer = InjuryRiskAnalyzer()
    
    # Test with a player
    risk = analyzer.analyze_injury_risk("Christian McCaffrey", "RB", 28, "nfl")
    print(f"\nInjury Risk Data: {risk}")

