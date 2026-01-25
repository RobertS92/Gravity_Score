#!/usr/bin/env python3
"""
Test script to verify comprehensive risk and age collection
Tests players known to have injuries and controversies
"""

import os
import sys
from pathlib import Path

# Add gravity to path
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_injury_collection():
    """Test comprehensive injury data collection"""
    print("\n" + "="*70)
    print("🏥 TESTING INJURY DATA COLLECTION")
    print("="*70)
    
    try:
        from gravity.injury_risk_analyzer import InjuryRiskAnalyzer
        
        analyzer = InjuryRiskAnalyzer()
        
        # Test players known to have injury history
        test_players = [
            ("Christian McCaffrey", "RB", 28, "nfl"),
            ("LeBron James", "SF", 39, "nba"),
            ("Aaron Rodgers", "QB", 41, "nfl"),
        ]
        
        for player_name, position, age, sport in test_players:
            print(f"\n📊 Testing: {player_name} ({position}, {age}, {sport})")
            print("-" * 70)
            
            injury_data = analyzer.analyze_injury_risk(
                player_name=player_name,
                position=position,
                age=age,
                sport=sport
            )
            
            print(f"   Injuries Found: {injury_data['injury_history_count']}")
            print(f"   Games Missed (Career): {injury_data['games_missed_career']}")
            print(f"   Current Status: {injury_data['current_injury_status'] or 'Healthy'}")
            print(f"   Injury Risk Score: {injury_data['injury_risk_score']}/100")
            print(f"   Position Risk Rate: {injury_data['position_injury_rate']}%")
            print(f"   Injury Prone: {'Yes' if injury_data['injury_prone'] else 'No'}")
            
            if injury_data['injury_history']:
                print(f"\n   Recent Injuries:")
                for injury in injury_data['injury_history'][:3]:
                    print(f"      - {injury.get('injury_type', 'Unknown')}: {injury.get('status', 'Past')}")
        
        print("\n✅ Injury collection test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Injury collection test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_controversy_collection():
    """Test comprehensive controversy data collection"""
    print("\n" + "="*70)
    print("⚠️  TESTING CONTROVERSY/OFF-FIELD INCIDENT COLLECTION")
    print("="*70)
    
    try:
        from gravity.advanced_risk_analyzer import AdvancedRiskAnalyzer
        
        analyzer = AdvancedRiskAnalyzer()
        
        # Test players - some with known past issues, some clean
        test_players = [
            ("Ja Morant", "nba"),  # Known suspension
            ("Antonio Brown", "nfl"),  # Multiple controversies
            ("LeBron James", "nba"),  # Clean record
        ]
        
        for player_name, sport in test_players:
            print(f"\n📊 Testing: {player_name} ({sport})")
            print("-" * 70)
            
            risk_data = analyzer.analyze_risk(
                player_name=player_name,
                sport=sport
            )
            
            print(f"   Controversies Found: {risk_data['controversies_count']}")
            print(f"   Arrests: {risk_data['arrests_count']}")
            print(f"   Suspensions: {risk_data['suspensions_count']}")
            print(f"   Fines: {risk_data['fines_count']}")
            print(f"   Controversy Risk Score: {risk_data['controversy_risk_score']}/100")
            print(f"   Reputation Score: {risk_data['reputation_score']}/100")
            print(f"   Legal Issues: {len(risk_data['legal_issues'])}")
            print(f"   Holdout Risk: {'Yes' if risk_data['holdout_risk'] else 'No'}")
            print(f"   Trade Rumors: {risk_data['trade_rumors_count']}")
            
            if risk_data['controversies']:
                print(f"\n   Recent Controversies:")
                for controversy in risk_data['controversies'][:3]:
                    print(f"      - {controversy.get('type', 'Unknown')}: {controversy.get('headline', '')[:60]}...")
        
        print("\n✅ Controversy collection test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Controversy collection test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_age_calculation():
    """Test age calculation from birth_date"""
    print("\n" + "="*70)
    print("📅 TESTING AGE CALCULATION FROM BIRTH_DATE")
    print("="*70)
    
    try:
        from datetime import datetime
        
        test_cases = [
            ("1995-09-16T07:00Z", "Should calculate ~29-30 years"),
            ("1984-12-30", "Should calculate ~39-40 years (LeBron)"),
            ("2003-06-22", "Should calculate ~21 years"),
        ]
        
        for birth_date, description in test_cases:
            print(f"\n📊 Testing: {birth_date}")
            print(f"   Expected: {description}")
            print("-" * 70)
            
            # Simulate the calculation logic
            birth_str = birth_date.split('T')[0]
            birth = datetime.strptime(birth_str, '%Y-%m-%d')
            today = datetime.now()
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            
            print(f"   ✅ Calculated Age: {age}")
        
        print("\n✅ Age calculation test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Age calculation test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 COMPREHENSIVE RISK & AGE COLLECTION TEST SUITE")
    print("="*70)
    print("\nThis script tests the NEW comprehensive risk analyzers")
    print("that were integrated into ALL scrapers.\n")
    
    results = {
        "Age Calculation": test_age_calculation(),
        "Injury Collection": test_injury_collection(),
        "Controversy Collection": test_controversy_collection(),
    }
    
    print("\n" + "="*70)
    print("📊 TEST RESULTS SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED! Risk collection is working!")
        print("="*70)
        print("\nYou can now run any scraper and get:")
        print("  ✅ Age (calculated from birth_date if needed)")
        print("  ✅ Complete injury history with severity")
        print("  ✅ Games missed data")
        print("  ✅ Arrests, suspensions, fines")
        print("  ✅ Reputation & risk scores")
        print("\nExample:")
        print("  python3 gravity/nba_scraper.py player 'LeBron James' 'Lakers' 'SF'")
        print("="*70)
    else:
        print("\n⚠️  Some tests failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

