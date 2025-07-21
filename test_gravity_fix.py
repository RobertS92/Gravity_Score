
#!/usr/bin/env python3
"""
Test script to verify the fixed gravity score calculations
"""

from gravity_score_system import GravityScoreCalculator
import pandas as pd

def test_fixed_calculations():
    """Test the fixed gravity calculations for Courtland Sutton and Pat Surtain"""
    
    calculator = GravityScoreCalculator()
    
    # Test players with realistic data
    test_players = [
        {
            'name': 'Courtland Sutton',
            'position': 'WR',
            'age': 29,
            'current_team': 'DEN',
            'experience': 6,
            'jersey_number': 14,
            'pro_bowls': 1,
            'all_pros': 0,
            'championships': 0,
            'receiving_yards_2023': 772,
            'receiving_tds_2023': 10,
            'contract_value': '60.8M',
            'twitter_followers': '50K',
            'instagram_followers': '200K'
        },
        {
            'name': 'Pat Surtain II',
            'position': 'CB',
            'age': 24,
            'current_team': 'DEN',
            'experience': 3,
            'jersey_number': 2,
            'pro_bowls': 2,
            'all_pros': 1,
            'championships': 0,
            'interceptions_2023': 0,
            'tackles_2023': 42,
            'contract_value': '68M',
            'twitter_followers': '30K',
            'instagram_followers': '150K'
        }
    ]
    
    print("🧪 Testing Fixed Gravity Score Calculations")
    print("=" * 60)
    
    for player in test_players:
        print(f"\n🏈 {player['name']} ({player['position']}) - {player['current_team']}")
        
        try:
            gravity = calculator.calculate_total_gravity(player)
            
            print(f"   Brand Power:  {gravity.brand_power:5.1f}/100")
            print(f"   Proof:        {gravity.proof:5.1f}/100")
            print(f"   Proximity:    {gravity.proximity:5.1f}/100")
            print(f"   Velocity:     {gravity.velocity:5.1f}/100")
            print(f"   Risk:         {gravity.risk:5.1f}/100")
            print(f"   TOTAL GRAVITY: {gravity.total_gravity:5.1f}/100")
            
            # Detailed risk breakdown
            risk_score = calculator.calculate_risk(player)
            print(f"   Risk Details:")
            print(f"     - Position Risk ({player['position']}): {calculator._get_position_risk(player['position']):.2f}")
            print(f"     - Age Risk (age {player['age']}): {calculator._calculate_age_risk(player['age'], player['position']):.2f}")
            print(f"     - Final Risk Score: {risk_score:.3f} -> {risk_score * 100:.1f}/100")
            
            print("   ✅ Calculation completed successfully")
            
        except Exception as e:
            print(f"   ❌ Error calculating gravity: {e}")
            return False
    
    print("\n✅ Fixed gravity calculation tests COMPLETED")
    return True

if __name__ == "__main__":
    test_fixed_calculations()
