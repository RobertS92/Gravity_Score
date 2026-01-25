"""
Demo Simulation - Standalone NIL Pipeline Demo
Simulates scraping 3 CFB athletes without database dependencies
"""

import json
import logging
import sys
from datetime import date
from pathlib import Path
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Test athletes
TEST_ATHLETES = [
    {
        'name': 'Shedeur Sanders',
        'school': 'Colorado',
        'sport': 'football',
        'position': 'QB',
        'conference': 'Big 12',
        'jersey_number': 2,
        'class_year': 'Senior'
    },
    {
        'name': 'Arch Manning',
        'school': 'Texas',
        'sport': 'football',
        'position': 'QB',
        'conference': 'SEC',
        'jersey_number': 16,
        'class_year': 'Sophomore'
    },
    {
        'name': 'Travis Hunter',
        'school': 'Colorado',
        'sport': 'football',
        'position': 'WR/CB',
        'conference': 'Big 12',
        'jersey_number': 12,
        'class_year': 'Junior'
    }
]


def simulate_nil_collection(athlete):
    """Simulate NIL data collection"""
    # Simulate data from different sources
    sources = ['on3', 'opendorse', 'inflcr', '247sports', 'rivals']
    successful_sources = random.randint(3, 5)
    
    # Simulate NIL deals
    brands = ['Nike', 'Gatorade', 'State Farm', 'EA Sports', 'Panini']
    deal_count = random.randint(2, 8)
    deals = []
    
    for i in range(deal_count):
        deals.append({
            'brand': random.choice(brands),
            'type': random.choice(['Endorsement', 'Appearance', 'Content', 'Licensing']),
            'value': random.randint(10000, 150000),
            'source': random.choice(sources[:successful_sources])
        })
    
    # Simulate valuation
    base_valuation = 250000 if athlete['position'] == 'QB' else 150000
    valuation = base_valuation + random.randint(-50000, 100000)
    
    return {
        'sources_successful': successful_sources,
        'sources_total': len(sources),
        'data_quality_score': 0.7 + (successful_sources / len(sources)) * 0.25,
        'deals': deals,
        'valuation': valuation,
        'nil_ranking': random.randint(1, 50)
    }


def calculate_gravity_score(athlete, nil_data):
    """Simulate Gravity score calculation"""
    # Simulate Brand score
    brand_score = random.randint(60, 90)
    
    # Simulate Proof score (QB premium)
    proof_base = 75 if athlete['position'] == 'QB' else 65
    proof_score = proof_base + random.randint(-10, 15)
    
    # Simulate Proximity score (based on deals)
    proximity_score = min(90, 40 + len(nil_data['deals']) * 5)
    
    # Simulate Velocity score
    velocity_score = random.randint(50, 80)
    
    # Simulate Risk score
    risk_score = random.randint(10, 30)
    
    # Calculate weighted Gravity score
    weights = {'B': 0.25, 'P': 0.25, 'X': 0.20, 'V': 0.15, 'R': 0.15}
    gravity_raw = (
        weights['B'] * brand_score +
        weights['P'] * proof_score +
        weights['X'] * proximity_score +
        weights['V'] * velocity_score -
        weights['R'] * risk_score
    )
    
    return {
        'gravity_conf': gravity_raw,
        'components': {
            'brand': brand_score,
            'proof': proof_score,
            'proximity': proximity_score,
            'velocity': velocity_score,
            'risk': risk_score
        },
        'confidences': {
            'brand': 0.8,
            'proof': 0.85,
            'proximity': 0.75,
            'velocity': 0.7,
            'risk': 0.65
        },
        'average_confidence': 0.75
    }


def calculate_iacv(athlete, gravity_score):
    """Simulate IACV calculation"""
    # Base market multiplier
    M_base = 50000 if 'SEC' in athlete.get('conference', '') else 45000
    
    # Scaling function: f(g) = exp(k * (g - 0.5))
    import math
    g = gravity_score['gravity_conf'] / 100
    k = 3.0
    scaling = math.exp(k * (g - 0.5))
    
    # Market adjustment (elite schools)
    elite_schools = ['Texas', 'Alabama', 'Ohio State', 'Georgia']
    market_adj = 1.5 if athlete['school'] in elite_schools else 1.25
    
    # Role adjustment (QB premium)
    role_adj = 1.4 if athlete['position'] == 'QB' else 1.1
    
    # Calculate IACV
    iacv_base = M_base * scaling * market_adj * role_adj
    
    # Calculate variance
    sigma = 0.15 + 0.30 * (1 - gravity_score['average_confidence'])
    
    return {
        'iacv_p25': iacv_base * (1 - sigma),
        'iacv_p50': iacv_base,
        'iacv_p75': iacv_base * (1 + sigma),
        'sigma': sigma
    }


def underwrite_deal(athlete, valuation):
    """Simulate deal underwriting"""
    # Create deal proposal at P50
    proposed_price = valuation['iacv_p50']
    
    # Calculate DSUV
    eff_structure = 1.0
    mult_rights = 1.3  # National + exclusive
    prob_exec = 0.85
    
    dsuv = valuation['iacv_p50'] * eff_structure * mult_rights * prob_exec
    
    # Calculate RADV
    loss_rate = 0.10  # 10% risk adjustment
    radv = dsuv * (1 - loss_rate)
    
    # Make decision
    ratio = radv / proposed_price
    
    if ratio >= 1.2:
        decision = 'approve'
    elif ratio >= 0.8:
        decision = 'counter'
        counter_price = radv * 0.9
    else:
        decision = 'no-go'
        counter_price = None
    
    return {
        'proposed_price': proposed_price,
        'dsuv': dsuv,
        'radv': radv,
        'decision': decision,
        'counter_price': counter_price if decision == 'counter' else None,
        'negotiation': {
            'anchor_price': valuation['iacv_p50'] * 1.25,
            'target_price': radv,
            'walk_away_price': radv * 0.75
        }
    }


def run_simulation():
    """Run complete simulation"""
    print("\n" + "=" * 90)
    print("GRAVITY NIL PIPELINE - DEMONSTRATION SIMULATION")
    print("Simulating 3 CFB Athletes from 2025-2026 Season")
    print("=" * 90 + "\n")
    
    results = []
    output_dir = Path('data/demo_simulation')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for i, athlete in enumerate(TEST_ATHLETES, 1):
        print(f"\n{'='*90}")
        print(f"ATHLETE {i}/3: {athlete['name']} - {athlete['school']} {athlete['position']}")
        print("="*90)
        
        # Step 1: NIL Data Collection
        print("\n📊 Step 1: Collecting NIL data...")
        nil_data = simulate_nil_collection(athlete)
        print(f"   ✓ Collected from {nil_data['sources_successful']}/{nil_data['sources_total']} sources")
        print(f"   ✓ Data quality: {nil_data['data_quality_score']:.2f}")
        print(f"   ✓ Found {len(nil_data['deals'])} NIL deals")
        print(f"   ✓ Source valuation: ${nil_data['valuation']:,.0f}")
        
        # Step 2: Gravity Score
        print("\n⭐ Step 2: Calculating Gravity score...")
        gravity_score = calculate_gravity_score(athlete, nil_data)
        print(f"   ✓ Gravity Score: {gravity_score['gravity_conf']:.2f}/100")
        print(f"   ✓ Components:")
        print(f"      • Brand (B): {gravity_score['components']['brand']:.1f}")
        print(f"      • Proof (P): {gravity_score['components']['proof']:.1f}")
        print(f"      • Proximity (X): {gravity_score['components']['proximity']:.1f}")
        print(f"      • Velocity (V): {gravity_score['components']['velocity']:.1f}")
        print(f"      • Risk (R): {gravity_score['components']['risk']:.1f}")
        
        # Step 3: IACV Valuation
        print("\n💰 Step 3: Calculating IACV valuation...")
        valuation = calculate_iacv(athlete, gravity_score)
        print(f"   ✓ IACV (P50): ${valuation['iacv_p50']:,.0f}")
        print(f"   ✓ Confidence Range:")
        print(f"      • P25 (Conservative): ${valuation['iacv_p25']:,.0f}")
        print(f"      • P50 (Expected): ${valuation['iacv_p50']:,.0f}")
        print(f"      • P75 (Optimistic): ${valuation['iacv_p75']:,.0f}")
        
        # Step 4: Deal Underwriting
        print("\n📋 Step 4: Underwriting sample deal...")
        underwriting = underwrite_deal(athlete, valuation)
        print(f"   ✓ Proposed Deal: ${underwriting['proposed_price']:,.0f} / 12 months")
        print(f"   ✓ RADV (Risk-Adjusted): ${underwriting['radv']:,.0f}")
        print(f"   ✓ Decision: {underwriting['decision'].upper()}")
        if underwriting['counter_price']:
            print(f"   ✓ Counter Offer: ${underwriting['counter_price']:,.0f}")
        
        # Step 5: Negotiation Strategy
        print("\n💼 Step 5: Negotiation strategy...")
        neg = underwriting['negotiation']
        print(f"   ✓ Anchor Price: ${neg['anchor_price']:,.0f}")
        print(f"   ✓ Target Price: ${neg['target_price']:,.0f}")
        print(f"   ✓ Walk-Away Price: ${neg['walk_away_price']:,.0f}")
        
        # Store results
        result = {
            'athlete': athlete,
            'nil_data': {
                'sources': nil_data['sources_successful'],
                'deals': len(nil_data['deals']),
                'valuation': nil_data['valuation']
            },
            'gravity_score': gravity_score['gravity_conf'],
            'components': gravity_score['components'],
            'iacv': {
                'p25': valuation['iacv_p25'],
                'p50': valuation['iacv_p50'],
                'p75': valuation['iacv_p75']
            },
            'underwriting': {
                'decision': underwriting['decision'],
                'radv': underwriting['radv']
            },
            'negotiation': underwriting['negotiation']
        }
        results.append(result)
        
        print(f"\n{'─'*90}\n")
    
    # Generate summary report
    print("\n" + "=" * 90)
    print("FINAL SUMMARY REPORT")
    print("=" * 90 + "\n")
    
    print(f"{'Athlete':<20} {'School':<12} {'Pos':<6} {'Gravity':<10} {'IACV':<15} {'Decision':<10}")
    print("─" * 90)
    
    for result in results:
        print(f"{result['athlete']['name']:<20} "
              f"{result['athlete']['school']:<12} "
              f"{result['athlete']['position']:<6} "
              f"{result['gravity_score']:<10.2f} "
              f"${result['iacv']['p50']:<14,.0f} "
              f"{result['underwriting']['decision']:<10}")
    
    # Save to JSON
    summary_file = output_dir / 'demo_results.json'
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n" + "=" * 90)
    print(f"📊 Results saved to: {summary_file.absolute()}")
    print("=" * 90)
    
    print("\n✅ DEMONSTRATION COMPLETE!\n")
    print("This simulation demonstrates:")
    print("  ✓ NIL data collection from 6 sources")
    print("  ✓ 5-factor Gravity scoring (B, P, X, V, R)")
    print("  ✓ IACV valuation with confidence intervals")
    print("  ✓ Deal underwriting with risk adjustment")
    print("  ✓ Negotiation strategy generation")
    print("\nFull implementation includes:")
    print("  • PostgreSQL database for data persistence")
    print("  • Real web scraping from NIL sources")
    print("  • Entity resolution and confidence scoring")
    print("  • PDF pack generation with WeasyPrint")
    print("  • FastAPI REST endpoints")
    print("  • Celery async job processing\n")


if __name__ == '__main__':
    run_simulation()
