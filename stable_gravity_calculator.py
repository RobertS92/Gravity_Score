"""
STABLE Gravity Score Calculator - NEVER CHANGE THIS IMPLEMENTATION
This is the final, production-ready gravity scoring system that should remain consistent.
"""

import pandas as pd
import numpy as np
from typing import Dict
import re

class StableGravityCalculator:
    """
    FINAL STABLE GRAVITY CALCULATOR - DO NOT MODIFY
    This implementation must remain consistent forever.
    """
    
    def __init__(self):
        # These weights are FINAL and should never change
        self.component_weights = {
            'brand_power': 0.20,
            'proof': 0.25, 
            'proximity': 0.20,
            'velocity': 0.15,
            'risk': 0.20
        }
        
        # Position multipliers are FINAL
        self.position_multipliers = {
            'QB': 1.3,
            'RB': 1.1,
            'WR': 1.1,
            'TE': 1.0,
            'LB': 1.0,
            'CB': 1.0,
            'S': 1.0,
            'DE': 1.0,
            'DT': 1.0
        }
    
    def calculate_gravity_score(self, player_data: Dict) -> float:
        """Calculate final gravity score using stable methodology."""
        
        # Brand Power (0-100)
        brand_power = self._calculate_brand_power(player_data)
        
        # Proof (0-100) 
        proof = self._calculate_proof(player_data)
        
        # Proximity (0-100)
        proximity = self._calculate_proximity(player_data)
        
        # Velocity (0-100)
        velocity = self._calculate_velocity(player_data)
        
        # Risk (0-100, lower is better)
        risk = self._calculate_risk(player_data)
        
        # Calculate weighted total
        total = (
            brand_power * self.component_weights['brand_power'] +
            proof * self.component_weights['proof'] +
            proximity * self.component_weights['proximity'] + 
            velocity * self.component_weights['velocity'] +
            (100 - risk) * self.component_weights['risk']  # Invert risk
        )
        
        # Apply position multiplier
        position = str(player_data.get('position', '')).upper()
        multiplier = self.position_multipliers.get(position, 1.0)
        
        final_score = total * multiplier
        
        return min(final_score, 100.0)  # Cap at 100
    
    def _calculate_brand_power(self, player_data: Dict) -> float:
        """Calculate brand power component."""
        score = 0.0
        
        # Social media followers
        twitter_followers = self._parse_number(player_data.get('twitter_followers', 0))
        instagram_followers = self._parse_number(player_data.get('instagram_followers', 0))
        
        # Twitter scoring (0-30 points)
        if twitter_followers > 1000000:
            score += 30
        elif twitter_followers > 500000:
            score += 20
        elif twitter_followers > 100000:
            score += 10
        elif twitter_followers > 10000:
            score += 5
            
        # Instagram scoring (0-30 points)
        if instagram_followers > 1000000:
            score += 30
        elif instagram_followers > 500000:
            score += 20
        elif instagram_followers > 100000:
            score += 10
        elif instagram_followers > 10000:
            score += 5
        
        # Pro Bowls (0-20 points)
        pro_bowls = self._parse_number(player_data.get('pro_bowls', 0))
        score += min(pro_bowls * 5, 20)
        
        # All-Pros (0-20 points)
        all_pros = self._parse_number(player_data.get('all_pros', 0))
        score += min(all_pros * 10, 20)
        
        return min(score, 100.0)
    
    def _calculate_proof(self, player_data: Dict) -> float:
        """Calculate proof component."""
        score = 0.0
        
        # Championships (0-40 points)
        championships = self._parse_number(player_data.get('championships', 0))
        score += min(championships * 20, 40)
        
        # Pro Bowls (0-25 points)
        pro_bowls = self._parse_number(player_data.get('pro_bowls', 0))
        score += min(pro_bowls * 5, 25)
        
        # All-Pros (0-35 points)
        all_pros = self._parse_number(player_data.get('all_pros', 0))
        score += min(all_pros * 10, 35)
        
        return min(score, 100.0)
    
    def _calculate_proximity(self, player_data: Dict) -> float:
        """Calculate proximity component."""
        score = 0.0
        
        # Team success score (0-50 points)
        team = str(player_data.get('current_team', '')).upper()
        championship_teams = ['KC', 'TB', 'LAR', 'DEN', 'SEA', 'BAL', 'NE']
        playoff_teams = ['BUF', 'CIN', 'MIA', 'SF', 'DAL', 'PHI', 'MIN']
        
        if any(t in team for t in championship_teams):
            score += 50
        elif any(t in team for t in playoff_teams):
            score += 30
        else:
            score += 10
            
        # Market size (0-30 points) 
        large_markets = ['DAL', 'NYG', 'NYJ', 'LAR', 'CHI', 'PHI', 'SF']
        if any(t in team for t in large_markets):
            score += 30
        else:
            score += 15
            
        # Personal achievements (0-20 points)
        championships = self._parse_number(player_data.get('championships', 0))
        score += min(championships * 20, 20)
        
        return min(score, 100.0)
    
    def _calculate_velocity(self, player_data: Dict) -> float:
        """Calculate velocity component."""
        score = 0.0
        
        # Age factor (0-40 points, peak at 25-28)
        age = self._parse_number(player_data.get('age', 30))
        if 25 <= age <= 28:
            score += 40
        elif 23 <= age <= 30:
            score += 30
        elif 21 <= age <= 32:
            score += 20
        else:
            score += 10
            
        # Experience factor (0-30 points)
        experience = self._parse_number(player_data.get('experience', 0))
        if 3 <= experience <= 8:
            score += 30
        elif 1 <= experience <= 10:
            score += 20
        else:
            score += 10
            
        # Recent achievements (0-30 points)
        recent_pro_bowls = self._parse_number(player_data.get('pro_bowls', 0))
        score += min(recent_pro_bowls * 10, 30)
        
        return min(score, 100.0)
    
    def _calculate_risk(self, player_data: Dict) -> float:
        """Calculate risk component (higher = more risky)."""
        risk = 0.0
        
        # Age risk (0-40 points)
        age = self._parse_number(player_data.get('age', 25))
        if age > 32:
            risk += 40
        elif age > 29:
            risk += 20
        elif age < 23:
            risk += 15
        else:
            risk += 5
            
        # Position risk (0-20 points)
        position = str(player_data.get('position', '')).upper()
        high_risk_positions = ['RB', 'WR', 'LB']
        if position in high_risk_positions:
            risk += 20
        else:
            risk += 5
            
        # Contract/injury risk (0-40 points)
        # Base risk for all players
        risk += 15
        
        return min(risk, 100.0)
    
    def _parse_number(self, value) -> float:
        """Parse number from various formats."""
        if pd.isna(value) or value is None:
            return 0.0
            
        if isinstance(value, (int, float)):
            return float(value)
            
        # Parse string numbers
        value_str = str(value).strip()
        if not value_str:
            return 0.0
            
        # Remove common text and symbols
        value_str = re.sub(r'[^\d.]', '', value_str)
        
        try:
            return float(value_str) if value_str else 0.0
        except:
            return 0.0

# Create global stable calculator instance
stable_calculator = StableGravityCalculator()