#!/usr/bin/env python3
"""
Debug script to test risk score calculation with sample player data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gravity_score_system import GravityScoreCalculator

def test_risk_scores():
    """Test risk score calculation with various player profiles"""
    gss = GravityScoreCalculator()
    
    # Test players with different profiles
    test_players = [
        {
            'name': 'Young QB',
            'position': 'QB',
            'age': '24',
            'experience': '2',
            'contract_years': '4'
        },
        {
            'name': 'Veteran RB',
            'position': 'RB',
            'age': '30',
            'experience': '8',
            'contract_years': '1'
        },
        {
            'name': 'Mid-Career WR',
            'position': 'WR',
            'age': '27',
            'experience': '5',
            'contract_years': '3'
        },
        {
            'name': 'Missing Data Player',
            'position': 'LB',
            'age': '',
            'experience': '',
            'contract_years': ''
        },
        {
            'name': 'High Risk RB',
            'position': 'RB',
            'age': '32',
            'experience': '10',
            'contract_years': '1'
        },
        {
            'name': 'Star QB (low jersey)',
            'position': 'QB',
            'age': '',
            'experience': '',
            'jersey_number': '12'
        },
        {
            'name': 'Backup RB (high jersey)', 
            'position': 'RB',
            'age': '',
            'experience': '',
            'jersey_number': '84'
        }
    ]
    
    print("=== RISK SCORE DEBUG ===")
    print()
    
    for player in test_players:
        risk_score = gss.calculate_risk(player)
        gravity_components = gss.calculate_total_gravity(player)
        
        print(f"Player: {player['name']}")
        print(f"  Position: {player['position']}")
        print(f"  Age: {player['age'] or 'Unknown'}")
        print(f"  Experience: {player['experience'] or 'Unknown'}")
        print(f"  Contract Years: {player.get('contract_years', '') or 'Unknown'}")
        print(f"  Jersey Number: {player.get('jersey_number', '') or 'Unknown'}")
        print(f"  Risk Score: {risk_score:.3f}")
        print(f"  Total Gravity: {gravity_components.total_gravity:.1f}")
        print()

if __name__ == "__main__":
    test_risk_scores()