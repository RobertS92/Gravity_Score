#!/usr/bin/env python3
"""
Quick Manual Scorer for Top NFL Players
========================================
Simple, explicit scoring for players with social + contract data
Enhanced for 200 players with error handling, confidence scores, and tiers
"""

import pandas as pd
import numpy as np
from tqdm import tqdm

# Position-based default stats for missing data
POSITION_DEFAULTS = {
    'QB': {'career_touchdowns': 50, 'career_yards': 15000, 'pro_bowls': 1},
    'WR': {'career_touchdowns': 30, 'career_yards': 5000, 'pro_bowls': 1},
    'RB': {'career_touchdowns': 40, 'career_yards': 4000, 'pro_bowls': 1},
    'TE': {'career_touchdowns': 20, 'career_yards': 3000, 'pro_bowls': 1},
    'EDGE': {'career_sacks': 30, 'pro_bowls': 1},
    'CB': {'career_interceptions': 10, 'pro_bowls': 1},
    'LB': {'career_tackles': 400, 'pro_bowls': 1},
    'S': {'career_interceptions': 8, 'pro_bowls': 1},
    'DT': {'career_sacks': 25, 'pro_bowls': 1},
    'DE': {'career_sacks': 30, 'pro_bowls': 1},
    'OL': {'pro_bowls': 1},
}

def get_position_defaults(position):
    """Get default stats for a position"""
    if pd.isna(position):
        return {}
    
    position = str(position).upper()
    for pos_key, defaults in POSITION_DEFAULTS.items():
        if pos_key in position:
            return defaults
    return {}

def calculate_commercial_score(row):
    """Calculate commercial value score with explicit logic and confidence tracking"""
    
    scores = {
        'performance': 0,
        'market': 0,
        'social': 0,
        'velocity': 0,
        'risk': 0,
        'total': 0,
        'confidence': 'low'  # Track data completeness
    }
    
    confidence_indicators = []
    
    # Get position defaults
    position = row.get('position', '')
    defaults = get_position_defaults(position)
    
    # PERFORMANCE SCORE (0-20 points)
    # Based on career stats and current season
    perf_indicators = []
    
    # Try career touchdowns
    if pd.notna(row.get('career_touchdowns')):
        td_score = min(row['career_touchdowns'] / 50, 1.0) * 7  # Max 7 pts
        perf_indicators.append(td_score)
        confidence_indicators.append('perf_td')
    elif 'career_touchdowns' in defaults:
        td_score = min(defaults['career_touchdowns'] / 50, 1.0) * 7 * 0.5  # Half credit for defaults
        perf_indicators.append(td_score)
    
    # Try career yards
    if pd.notna(row.get('career_yards')):
        yards_score = min(row['career_yards'] / 10000, 1.0) * 7  # Max 7 pts
        perf_indicators.append(yards_score)
        confidence_indicators.append('perf_yards')
    elif 'career_yards' in defaults:
        yards_score = min(defaults['career_yards'] / 10000, 1.0) * 7 * 0.5
        perf_indicators.append(yards_score)
    
    # Try pro bowls
    if pd.notna(row.get('pro_bowls')):
        pb_score = min(row['pro_bowls'] / 5, 1.0) * 6  # Max 6 pts
        perf_indicators.append(pb_score)
        confidence_indicators.append('perf_pb')
    elif 'pro_bowls' in defaults:
        pb_score = min(defaults['pro_bowls'] / 5, 1.0) * 6 * 0.5
        perf_indicators.append(pb_score)
    
    scores['performance'] = sum(perf_indicators) if perf_indicators else 10  # Default to 10 if no stats
    scores['performance'] = min(scores['performance'], 20)  # Cap at 20
    
    # MARKET SCORE (0-25 points)
    market_indicators = []
    
    if pd.notna(row.get('contract_value')) and row['contract_value'] > 0:
        # $100M+ = full points, scale down
        contract_score = min(row['contract_value'] / 100_000_000, 1.0) * 15  # Max 15 pts
        market_indicators.append(contract_score)
        confidence_indicators.append('market_contract')
    
    if pd.notna(row.get('endorsement_value')) and row['endorsement_value'] > 0:
        endorsement_score = min(row['endorsement_value'] / 20_000_000, 1.0) * 10  # Max 10 pts
        market_indicators.append(endorsement_score)
        confidence_indicators.append('market_endorsement')
    
    scores['market'] = sum(market_indicators) if market_indicators else 0
    scores['market'] = min(scores['market'], 25)
    
    # SOCIAL SCORE (0-30 points)
    social_indicators = []
    
    if pd.notna(row.get('instagram_followers')) and row['instagram_followers'] > 0:
        # 5M+ followers = full points
        ig_score = min(row['instagram_followers'] / 5_000_000, 1.0) * 15  # Max 15 pts
        social_indicators.append(ig_score)
        confidence_indicators.append('social_ig')
    
    if pd.notna(row.get('twitter_followers')) and row['twitter_followers'] > 0:
        # 2M+ followers = full points
        tw_score = min(row['twitter_followers'] / 2_000_000, 1.0) * 10  # Max 10 pts
        social_indicators.append(tw_score)
        confidence_indicators.append('social_tw')
    
    # Celebrity connection boost (Taylor Swift effect, etc.)
    if pd.notna(row.get('instagram_followers')) and row['instagram_followers'] > 3_000_000:
        social_indicators.append(5)  # Bonus 5 pts for mega stars
    
    scores['social'] = sum(social_indicators) if social_indicators else 0
    scores['social'] = min(scores['social'], 30)
    
    # VELOCITY SCORE (0-15 points)
    # Growth trajectory and career phase
    age = row.get('age', 28)
    
    if 24 <= age <= 29:
        velocity_base = 12  # Prime years
    elif age < 24:
        velocity_base = 10  # Still developing
    else:
        velocity_base = 8   # Veteran phase
    
    # Adjust for performance trend
    if pd.notna(row.get('pro_bowls')) and row['pro_bowls'] >= 3:
        velocity_base += 3  # Sustained excellence
    
    scores['velocity'] = min(velocity_base, 15)
    
    # RISK SCORE (0-10 points, higher is better)
    risk_base = 10  # Start with perfect score
    
    # Deduct for controversies
    if pd.notna(row.get('controversies')) and row['controversies'] > 0:
        risk_base -= min(row['controversies'] * 2, 5)  # -2 pts each, max -5
    
    # Deduct for injury history
    if pd.notna(row.get('games_missed_career')) and row['games_missed_career'] > 20:
        risk_base -= 2
    
    # Deduct for age risk
    if age > 32:
        risk_base -= 1
    
    scores['risk'] = max(risk_base, 0)
    
    # TOTAL SCORE (weighted sum)
    scores['total'] = (
        scores['performance'] * 1.0 +   # 20% weight, already scaled to 20
        scores['market'] * 1.0 +        # 25% weight, already scaled to 25
        scores['social'] * 1.0 +        # 30% weight, already scaled to 30
        scores['velocity'] * 1.0 +      # 15% weight, already scaled to 15
        scores['risk'] * 1.0            # 10% weight, already scaled to 10
    )
    
    # Determine confidence level
    confidence_count = len(confidence_indicators)
    if confidence_count >= 5:
        scores['confidence'] = 'high'
    elif confidence_count >= 3:
        scores['confidence'] = 'medium'
    else:
        scores['confidence'] = 'low'
    
    # Determine tier
    if scores['total'] >= 70:
        scores['tier'] = 'Elite'
    elif scores['total'] >= 55:
        scores['tier'] = 'Star'
    elif scores['total'] >= 40:
        scores['tier'] = 'Solid'
    else:
        scores['tier'] = 'Emerging'
    
    return pd.Series(scores)


def main():
    import sys
    
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'nfl_players_with_social.csv'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'final_scores/NFL_TOP_200_COMMERCIAL.csv'
    max_players = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    
    print("\n" + "="*100)
    print(f"🚀 QUICK MANUAL SCORER - TOP {max_players} NFL PLAYERS WITH SOCIAL DATA")
    print("="*100 + "\n")
    
    # Load data
    try:
        df = pd.read_csv(input_file)
        print(f"📂 Loaded {len(df)} NFL players from {input_file}")
    except FileNotFoundError:
        print(f"❌ Error: {input_file} not found")
        return
    
    # Filter to players with social data
    df_social = df[df['instagram_followers'].notna() | df['contract_value'].notna()].copy()
    if len(df_social) == 0:
        print("⚠️  No players with social/contract data found")
        return
    
    # Limit to top N players
    df_social = df_social.head(max_players)
    print(f"🎯 Processing {len(df_social)} players with social/contract data\n")
    
    # Calculate scores with progress bar
    print("⚡ Calculating commercial value scores...")
    score_rows = []
    
    for idx, row in tqdm(df_social.iterrows(), total=len(df_social), desc="Scoring"):
        try:
            scores = calculate_commercial_score(row)
            score_rows.append(scores)
        except Exception as e:
            print(f"\n⚠️  Error scoring {row.get('player_name', 'Unknown')}: {e}")
            # Add default scores on error
            default_scores = pd.Series({
                'performance': 10, 'market': 0, 'social': 0, 'velocity': 10, 'risk': 8,
                'total': 28, 'confidence': 'low', 'tier': 'Emerging'
            })
            score_rows.append(default_scores)
    
    score_df = pd.DataFrame(score_rows)
    
    # Add scores to dataframe
    for col in ['performance', 'market', 'social', 'velocity', 'risk', 'total', 'confidence', 'tier']:
        df_social[f'commercial_{col}'] = score_df[col]
    
    # Sort by total
    df_social = df_social.sort_values('commercial_total', ascending=False)
    
    # Save
    df_social.to_csv(output_file, index=False)
    print(f"\n💾 Saved to {output_file}\n")
    
    # Summary statistics
    print("="*100)
    print("📊 SCORING SUMMARY")
    print("="*100)
    print(f"   Total Players Scored: {len(df_social)}")
    print(f"   Score Range: {df_social['commercial_total'].min():.1f} - {df_social['commercial_total'].max():.1f}")
    print(f"   Average Score: {df_social['commercial_total'].mean():.1f}")
    print(f"\n   Tier Distribution:")
    tier_counts = df_social['commercial_tier'].value_counts()
    for tier, count in tier_counts.items():
        print(f"     {tier:10s}: {count:3d} players ({count/len(df_social)*100:.1f}%)")
    print(f"\n   Confidence Distribution:")
    conf_counts = df_social['commercial_confidence'].value_counts()
    for conf, count in conf_counts.items():
        print(f"     {conf:10s}: {count:3d} players ({count/len(df_social)*100:.1f}%)")
    
    # Display top 20
    print("\n" + "="*100)
    print("🏆 TOP 20 NFL PLAYERS - COMMERCIAL VALUE (MANUAL CALCULATION)")
    print("="*100 + "\n")
    
    for i, (_, row) in enumerate(df_social.head(20).iterrows(), 1):
        name = row['player_name']
        total = row['commercial_total']
        perf = row['commercial_performance']
        market = row['commercial_market']
        social = row['commercial_social']
        velocity = row['commercial_velocity']
        risk = row['commercial_risk']
        tier = row['commercial_tier']
        conf = row['commercial_confidence']
        
        ig = row.get('instagram_followers', 0)
        contract = row.get('contract_value', 0)
        
        tier_str = str(tier) if pd.notna(tier) else 'Unknown'
        print(f"{i:2d}. {name:25s} {total:6.2f} [{tier_str:8s}] ", end='')
        conf_str = str(conf) if pd.notna(conf) else 'low'
        print(f"(P:{perf:4.1f} M:{market:4.1f} S:{social:4.1f} V:{velocity:4.1f} R:{risk:4.1f}) [{conf_str}]", end='')
        
        if pd.notna(ig) and ig > 0:
            print(f" 📸{ig/1000000:.1f}M", end='')
        if pd.notna(contract) and contract > 0:
            print(f" 💰${contract/1000000:.0f}M", end='')
        print()
    
    print("\n" + "="*100)
    print("Legend: P=Performance, M=Market, S=Social, V=Velocity, R=Risk")
    print("Tiers: Elite (70+), Star (55-69), Solid (40-54), Emerging (<40)")
    print("="*100 + "\n")


if __name__ == '__main__':
    main()

