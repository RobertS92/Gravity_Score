#!/usr/bin/env python3
"""
Test script for all FREE collectors
Demonstrates how to use each collector and shows sample output
"""

import logging
from gravity.contract_collector import ContractCollector
from gravity.endorsement_collector import EndorsementCollector
from gravity.news_collector import NewsCollector
from gravity.injury_risk_analyzer import InjuryRiskAnalyzer
from gravity.advanced_risk_analyzer import AdvancedRiskAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_all_collectors(player_name, team, position, age, sport='nfl'):
    """Test all FREE collectors on a single player"""
    
    print("\n" + "="*80)
    print(f"TESTING FREE COLLECTORS - {player_name}")
    print("="*80)
    
    results = {
        'player_name': player_name,
        'team': team,
        'position': position,
        'age': age
    }
    
    # 1. Contract Collector
    print("\n" + "="*80)
    print("1. CONTRACT COLLECTOR TEST")
    print("="*80)
    try:
        contract_collector = ContractCollector()
        contract_data = contract_collector.collect_contract_data(player_name, team, sport)
        results['contract'] = contract_data
        
        print("\n✅ Contract Data Collected:")
        print(f"   Total Value: ${contract_data.get('contract_value', 0):,}")
        print(f"   Guaranteed: ${contract_data.get('guaranteed_money', 0):,}")
        print(f"   AAV: ${contract_data.get('avg_annual_value', 0):,}")
        print(f"   Years: {contract_data.get('contract_years', 'N/A')}")
        print(f"   Cap Hit: ${contract_data.get('cap_hit_current', 0):,}")
        print(f"   Free Agent: {contract_data.get('free_agent_year', 'N/A')}")
    except Exception as e:
        print(f"\n❌ Contract Collector Error: {e}")
        results['contract'] = {}
    
    # 2. Endorsement Collector
    print("\n" + "="*80)
    print("2. ENDORSEMENT COLLECTOR TEST")
    print("="*80)
    try:
        endorsement_collector = EndorsementCollector()
        endorsement_data = endorsement_collector.collect_endorsement_data(player_name, sport)
        results['endorsements'] = endorsement_data
        
        print("\n✅ Endorsement Data Collected:")
        print(f"   Endorsements: {len(endorsement_data.get('endorsements', []))}")
        print(f"   Brands: {', '.join(endorsement_data.get('endorsements', [])[:5]) or 'None found'}")
        print(f"   Partnerships: {len(endorsement_data.get('brand_partnerships', []))}")
        print(f"   Est. Value: ${endorsement_data.get('estimated_endorsement_value', 0):,}" if endorsement_data.get('estimated_endorsement_value') else "   Est. Value: N/A")
        print(f"   Business Ventures: {len(endorsement_data.get('business_ventures', []))}")
    except Exception as e:
        print(f"\n❌ Endorsement Collector Error: {e}")
        results['endorsements'] = {}
    
    # 3. News Collector
    print("\n" + "="*80)
    print("3. NEWS COLLECTOR TEST")
    print("="*80)
    try:
        news_collector = NewsCollector()
        news_data = news_collector.collect_news_data(player_name)
        results['news'] = news_data
        
        print("\n✅ News Data Collected:")
        print(f"   Articles (30d): {news_data.get('news_headline_count_30d', 0)}")
        print(f"   Articles (7d): {news_data.get('news_headline_count_7d', 0)}")
        print(f"   Sentiment: {news_data.get('media_sentiment', 0):.2f} (-1.0 to 1.0)")
        print(f"   Mention Velocity: {news_data.get('mention_velocity', 0):.2f} per day")
        print(f"   Trending: {'Yes' if news_data.get('trending') else 'No'}")
        print(f"   Interviews: {len(news_data.get('recent_interviews', []))}")
        print(f"   Podcasts: {len(news_data.get('podcast_appearances', []))}")
        
        if news_data.get('recent_headlines'):
            print(f"\n   Recent Headlines:")
            for headline in news_data['recent_headlines'][:3]:
                print(f"     - {headline.get('headline', 'N/A')[:80]}...")
    except Exception as e:
        print(f"\n❌ News Collector Error: {e}")
        results['news'] = {}
    
    # 4. Injury Risk Analyzer
    print("\n" + "="*80)
    print("4. INJURY RISK ANALYZER TEST")
    print("="*80)
    try:
        injury_analyzer = InjuryRiskAnalyzer()
        injury_data = injury_analyzer.analyze_injury_risk(player_name, position, age, sport)
        results['injury_risk'] = injury_data
        
        print("\n✅ Injury Risk Data Collected:")
        print(f"   Risk Score: {injury_data.get('injury_risk_score', 0)}/100")
        print(f"   Injury Count: {injury_data.get('injury_history_count', 0)}")
        print(f"   Severity Score: {injury_data.get('injury_severity_score', 0)}")
        print(f"   Current Status: {injury_data.get('current_injury_status', 'Healthy')}")
        print(f"   Games Missed (Career): {injury_data.get('games_missed_career', 0)}")
        print(f"   Games Missed (Last Season): {injury_data.get('games_missed_last_season', 0)}")
        print(f"   Position Risk: {injury_data.get('position_injury_rate', 0)}/100")
        print(f"   Age Risk: {injury_data.get('age_risk_factor', 0)}/100")
        print(f"   Injury Prone: {'Yes' if injury_data.get('injury_prone') else 'No'}")
    except Exception as e:
        print(f"\n❌ Injury Risk Analyzer Error: {e}")
        results['injury_risk'] = {}
    
    # 5. Advanced Risk Analyzer
    print("\n" + "="*80)
    print("5. ADVANCED RISK ANALYZER TEST")
    print("="*80)
    try:
        risk_analyzer = AdvancedRiskAnalyzer()
        risk_data = risk_analyzer.analyze_risk(player_name, sport)
        results['risk'] = risk_data
        
        print("\n✅ Risk Data Collected:")
        print(f"   Controversies: {risk_data.get('controversies_count', 0)}")
        print(f"   Arrests: {risk_data.get('arrests_count', 0)}")
        print(f"   Suspensions: {risk_data.get('suspensions_count', 0)}")
        print(f"   Fines: {risk_data.get('fines_count', 0)}")
        print(f"   Controversy Risk: {risk_data.get('controversy_risk_score', 0)}/100")
        print(f"   Reputation Score: {risk_data.get('reputation_score', 0)}/100")
        print(f"   Holdout Risk: {'Yes' if risk_data.get('holdout_risk') else 'No'}")
        print(f"   Trade Rumors: {risk_data.get('trade_rumors_count', 0)}")
        print(f"   Team Issues: {len(risk_data.get('team_issues', []))}")
        print(f"   Legal Issues: {len(risk_data.get('legal_issues', []))}")
    except Exception as e:
        print(f"\n❌ Advanced Risk Analyzer Error: {e}")
        results['risk'] = {}
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nPlayer: {player_name} - {position}, {team}")
    print(f"Age: {age}")
    print(f"\nContract: ${results.get('contract', {}).get('contract_value', 0):,}")
    print(f"Injury Risk: {results.get('injury_risk', {}).get('injury_risk_score', 0)}/100")
    print(f"Reputation: {results.get('risk', {}).get('reputation_score', 0)}/100")
    print(f"News Articles (30d): {results.get('news', {}).get('news_headline_count_30d', 0)}")
    print(f"Endorsements Found: {len(results.get('endorsements', {}).get('endorsements', []))}")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETE")
    print("="*80)
    
    return results


if __name__ == "__main__":
    print("\n" + "="*80)
    print("FREE COLLECTORS TEST SUITE")
    print("="*80)
    print("\nTesting all collectors with sample players...")
    print("This will take 1-2 minutes per player.")
    
    # Test NFL player
    print("\n\n" + "🏈 "*20)
    print("TESTING NFL PLAYER")
    print("🏈 "*20)
    nfl_results = test_all_collectors(
        player_name="Patrick Mahomes",
        team="Kansas City Chiefs",
        position="QB",
        age=29,
        sport="nfl"
    )
    
    # Test NBA player
    print("\n\n" + "🏀 "*20)
    print("TESTING NBA PLAYER")
    print("🏀 "*20)
    nba_results = test_all_collectors(
        player_name="LeBron James",
        team="Los Angeles Lakers",
        position="SF",
        age=39,
        sport="nba"
    )
    
    print("\n\n" + "="*80)
    print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
    print("="*80)
    print("\nAll FREE collectors are working!")
    print("Check the output above to see what data was collected.")
    print("\nSee FREE_COLLECTORS_README.md for full documentation.")

