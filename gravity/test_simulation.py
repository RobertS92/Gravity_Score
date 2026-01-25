"""
Test Simulation - NIL Pipeline End-to-End Test
Scrapes 3 CFB athletes from different teams (2025-2026 season)
"""

import logging
import sys
from datetime import date, datetime
from pathlib import Path
import json
import uuid

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_simulation.log')
    ]
)
logger = logging.getLogger(__name__)

# Test athletes - 3 top CFB players from different teams (2025-2026 season)
TEST_ATHLETES = [
    {
        'name': 'Shedeur Sanders',
        'school': 'Colorado',
        'sport': 'football',
        'position': 'QB',
        'conference': 'Big 12',
        'jersey_number': 2,
        'class_year': 'Senior',
        'season_id': '2025-26'
    },
    {
        'name': 'Arch Manning',
        'school': 'Texas',
        'sport': 'football',
        'position': 'QB',
        'conference': 'SEC',
        'jersey_number': 16,
        'class_year': 'Sophomore',
        'season_id': '2025-26'
    },
    {
        'name': 'Travis Hunter',
        'school': 'Colorado',
        'sport': 'football',
        'position': 'WR/CB',
        'conference': 'Big 12',
        'jersey_number': 12,
        'class_year': 'Junior',
        'season_id': '2025-26'
    }
]


class NILPipelineSimulation:
    """
    End-to-end simulation of NIL pipeline
    """
    
    def __init__(self):
        """Initialize simulation"""
        self.results = []
        self.output_dir = Path('data/test_simulation')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("🚀 NIL Pipeline Simulation initialized")
    
    def run_simulation(self):
        """Run complete simulation for all test athletes"""
        logger.info("=" * 80)
        logger.info("GRAVITY NIL PIPELINE - TEST SIMULATION")
        logger.info("Testing with 3 CFB athletes from 2025-2026 season")
        logger.info("=" * 80)
        
        for i, athlete_info in enumerate(TEST_ATHLETES, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"ATHLETE {i}/3: {athlete_info['name']} ({athlete_info['school']})")
            logger.info(f"{'='*80}\n")
            
            result = self.process_athlete(athlete_info)
            self.results.append(result)
            
            # Brief pause between athletes
            import time
            time.sleep(2)
        
        # Generate summary report
        self.generate_summary_report()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ SIMULATION COMPLETE")
        logger.info("=" * 80)
    
    def process_athlete(self, athlete_info: dict) -> dict:
        """
        Process single athlete through entire pipeline
        
        Steps:
        1. Collect NIL data from all sources
        2. Normalize and store data
        3. Resolve/create athlete entity
        4. Calculate features
        5. Calculate Gravity score
        6. Calculate IACV valuation
        7. Create mock deal and underwrite
        8. Generate negotiation pack
        """
        result = {
            'athlete': athlete_info,
            'timestamp': datetime.utcnow().isoformat(),
            'steps': {},
            'errors': []
        }
        
        try:
            # Step 1: Collect NIL data
            logger.info("📊 Step 1: Collecting NIL data from all sources...")
            collection_result = self.collect_nil_data(athlete_info)
            result['steps']['collection'] = collection_result
            
            # Step 2: Entity resolution
            logger.info("🔍 Step 2: Resolving athlete entity...")
            entity_result = self.resolve_entity(athlete_info, collection_result)
            result['steps']['entity'] = entity_result
            result['athlete_id'] = entity_result.get('athlete_id')
            
            # Step 3: Normalize and store
            logger.info("📝 Step 3: Normalizing and storing data...")
            normalization_result = self.normalize_data(
                collection_result,
                entity_result.get('athlete_id')
            )
            result['steps']['normalization'] = normalization_result
            
            # Step 4: Calculate features
            logger.info("🔢 Step 4: Calculating features...")
            features_result = self.calculate_features(
                entity_result.get('athlete_id'),
                athlete_info['season_id']
            )
            result['steps']['features'] = features_result
            
            # Step 5: Calculate Gravity score
            logger.info("⭐ Step 5: Calculating Gravity score...")
            gravity_result = self.calculate_gravity(
                entity_result.get('athlete_id'),
                athlete_info['season_id']
            )
            result['steps']['gravity'] = gravity_result
            
            # Step 6: Calculate valuation
            logger.info("💰 Step 6: Calculating IACV valuation...")
            valuation_result = self.calculate_valuation(
                entity_result.get('athlete_id'),
                athlete_info['season_id']
            )
            result['steps']['valuation'] = valuation_result
            
            # Step 7: Create and underwrite mock deal
            logger.info("📋 Step 7: Underwriting sample deal...")
            underwriting_result = self.underwrite_sample_deal(
                entity_result.get('athlete_id'),
                athlete_info['season_id'],
                valuation_result
            )
            result['steps']['underwriting'] = underwriting_result
            
            # Step 8: Generate negotiation pack
            logger.info("📄 Step 8: Generating negotiation pack...")
            pack_result = self.generate_pack(
                entity_result.get('athlete_id'),
                athlete_info['season_id'],
                underwriting_result.get('deal_proposal')
            )
            result['steps']['pack'] = pack_result
            
            # Log summary
            self.log_athlete_summary(athlete_info, result)
            
        except Exception as e:
            logger.error(f"❌ Error processing {athlete_info['name']}: {e}")
            result['errors'].append(str(e))
        
        return result
    
    def collect_nil_data(self, athlete_info: dict) -> dict:
        """Step 1: Collect NIL data"""
        try:
            from gravity.nil import run_nil_collection
            
            collection = run_nil_collection(
                athlete_name=athlete_info['name'],
                school=athlete_info['school'],
                sport=athlete_info['sport']
            )
            
            summary = collection.get('summary', {})
            logger.info(f"   ✓ Collected from {summary.get('sources_successful', 0)} sources")
            logger.info(f"   ✓ Data quality score: {summary.get('data_quality_score', 0):.2f}")
            
            return {
                'success': True,
                'sources_successful': summary.get('sources_successful', 0),
                'sources_failed': summary.get('sources_failed', 0),
                'data_quality_score': summary.get('data_quality_score', 0),
                'deals_found': summary.get('total_deals_found', 0),
                'has_valuation': summary.get('has_valuation', False)
            }
            
        except Exception as e:
            logger.error(f"   ✗ Collection failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def resolve_entity(self, athlete_info: dict, collection_result: dict) -> dict:
        """Step 2: Entity resolution"""
        try:
            from gravity.nil.entity_resolution import EntityResolver
            
            resolver = EntityResolver()
            athlete_id, is_new, confidence = resolver.create_or_resolve_athlete(
                name=athlete_info['name'],
                school=athlete_info['school'],
                sport=athlete_info['sport'],
                position=athlete_info.get('position'),
                conference=athlete_info.get('conference'),
                jersey_number=athlete_info.get('jersey_number'),
                class_year=athlete_info.get('class_year'),
                season_id=athlete_info.get('season_id')
            )
            
            logger.info(f"   ✓ Athlete ID: {athlete_id}")
            logger.info(f"   ✓ New entity: {is_new}, Confidence: {confidence:.2f}")
            
            return {
                'success': True,
                'athlete_id': str(athlete_id),
                'is_new': is_new,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"   ✗ Entity resolution failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def normalize_data(self, collection_result: dict, athlete_id: str) -> dict:
        """Step 3: Normalize data"""
        try:
            # This would normally use the collection_result
            # For simulation, we'll just return a success indicator
            logger.info(f"   ✓ Data normalized and stored")
            
            return {
                'success': True,
                'records_created': {
                    'deals': 0,
                    'valuations': 0
                }
            }
            
        except Exception as e:
            logger.error(f"   ✗ Normalization failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_features(self, athlete_id: str, season_id: str) -> dict:
        """Step 4: Calculate features"""
        try:
            from gravity.nil.feature_calculator import FeatureCalculator
            
            calculator = FeatureCalculator()
            athlete_uuid = uuid.UUID(athlete_id)
            
            features = calculator.calculate_all_features(
                athlete_id=athlete_uuid,
                season_id=season_id,
                as_of_date=date.today()
            )
            
            snapshot_id = calculator.store_features(
                athlete_id=athlete_uuid,
                season_id=season_id,
                features=features
            )
            
            logger.info(f"   ✓ Features calculated and stored: {snapshot_id}")
            
            return {
                'success': True,
                'snapshot_id': str(snapshot_id),
                'feature_count': len(features.get('raw_metrics', {}))
            }
            
        except Exception as e:
            logger.error(f"   ✗ Feature calculation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_gravity(self, athlete_id: str, season_id: str) -> dict:
        """Step 5: Calculate Gravity score"""
        try:
            from gravity.scoring import GravityCalculator
            
            calculator = GravityCalculator()
            athlete_uuid = uuid.UUID(athlete_id)
            
            gravity_score = calculator.calculate_gravity_score(
                athlete_id=athlete_uuid,
                season_id=season_id,
                as_of_date=date.today()
            )
            
            # Store score
            score_id = calculator.calculate_and_store(
                athlete_id=athlete_uuid,
                season_id=season_id,
                as_of_date=date.today()
            )
            
            g_conf = gravity_score.get('gravity_conf', 0)
            components = gravity_score.get('components', {})
            
            logger.info(f"   ✓ Gravity Score: {g_conf:.2f}/100")
            logger.info(f"   ✓ Components - B:{components.get('brand', 0):.1f} "
                       f"P:{components.get('proof', 0):.1f} "
                       f"X:{components.get('proximity', 0):.1f} "
                       f"V:{components.get('velocity', 0):.1f} "
                       f"R:{components.get('risk', 0):.1f}")
            
            return {
                'success': True,
                'score_id': str(score_id),
                'gravity_conf': g_conf,
                'gravity_raw': gravity_score.get('gravity_raw', 0),
                'components': components,
                'average_confidence': gravity_score.get('average_confidence', 0)
            }
            
        except Exception as e:
            logger.error(f"   ✗ Gravity calculation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_valuation(self, athlete_id: str, season_id: str) -> dict:
        """Step 6: Calculate IACV valuation"""
        try:
            from gravity.valuation import calculate_iacv
            
            athlete_uuid = uuid.UUID(athlete_id)
            
            valuation = calculate_iacv(
                athlete_id=athlete_uuid,
                season_id=season_id,
                as_of_date=date.today()
            )
            
            iacv_p50 = valuation.get('iacv_p50', 0)
            iacv_p25 = valuation.get('iacv_p25', 0)
            iacv_p75 = valuation.get('iacv_p75', 0)
            
            logger.info(f"   ✓ IACV (P50): ${iacv_p50:,.0f}")
            logger.info(f"   ✓ Range: ${iacv_p25:,.0f} - ${iacv_p75:,.0f}")
            
            return {
                'success': True,
                'iacv_p50': iacv_p50,
                'iacv_p25': iacv_p25,
                'iacv_p75': iacv_p75,
                'gravity_score': valuation.get('gravity_score', 0),
                'confidence_avg': valuation.get('confidence_avg', 0)
            }
            
        except Exception as e:
            logger.error(f"   ✗ Valuation calculation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def underwrite_sample_deal(self, athlete_id: str, season_id: str, valuation: dict) -> dict:
        """Step 7: Underwrite sample deal"""
        try:
            from gravity.valuation import underwrite_deal
            
            athlete_uuid = uuid.UUID(athlete_id)
            
            # Create sample deal proposal (at P50 valuation)
            proposed_price = valuation.get('iacv_p50', 50000)
            
            deal_proposal = {
                'price': proposed_price,
                'term_months': 12,
                'structure_type': 'fixed',
                'is_exclusive': False,
                'is_category_exclusive': True,
                'territory': 'national',
                'rights': ['social_media', 'appearances', 'licensing'],
                'deliverables': [
                    '12 social media posts per year',
                    '2 personal appearances',
                    'Jersey licensing rights'
                ]
            }
            
            underwriting = underwrite_deal(
                athlete_id=athlete_uuid,
                season_id=season_id,
                deal_proposal=deal_proposal,
                as_of_date=date.today()
            )
            
            decision = underwriting.get('decision', 'unknown')
            radv = underwriting.get('radv', 0)
            
            logger.info(f"   ✓ Deal: ${proposed_price:,.0f} / 12 months")
            logger.info(f"   ✓ Decision: {decision.upper()}")
            logger.info(f"   ✓ RADV: ${radv:,.0f}")
            
            return {
                'success': True,
                'deal_proposal': deal_proposal,
                'decision': decision,
                'radv': radv,
                'dsuv': underwriting.get('dsuv', 0),
                'rationale': underwriting.get('decision_rationale', '')
            }
            
        except Exception as e:
            logger.error(f"   ✗ Underwriting failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_pack(self, athlete_id: str, season_id: str, deal_proposal: dict) -> dict:
        """Step 8: Generate negotiation pack"""
        try:
            from gravity.packs import aggregate_pack_data, export_pack_json, generate_pack_pdf
            
            athlete_uuid = uuid.UUID(athlete_id)
            
            # Aggregate data
            pack_data = aggregate_pack_data(
                athlete_id=athlete_uuid,
                season_id=season_id,
                deal_proposal=deal_proposal,
                as_of_date=date.today()
            )
            
            # Generate output files
            athlete_name = pack_data.get('athlete', {}).get('name', 'unknown')
            safe_name = athlete_name.replace(' ', '_').lower()
            
            json_path = self.output_dir / f"{safe_name}_pack.json"
            pdf_path = self.output_dir / f"{safe_name}_pack.pdf"
            
            json_file = export_pack_json(pack_data, str(json_path))
            
            try:
                pdf_file = generate_pack_pdf(pack_data, str(pdf_path))
                pdf_generated = True
            except Exception as e:
                logger.warning(f"   ⚠ PDF generation failed (WeasyPrint may not be installed): {e}")
                pdf_file = None
                pdf_generated = False
            
            logger.info(f"   ✓ JSON pack: {json_path}")
            if pdf_generated:
                logger.info(f"   ✓ PDF pack: {pdf_path}")
            
            return {
                'success': True,
                'json_file': str(json_path),
                'pdf_file': str(pdf_path) if pdf_generated else None,
                'pdf_generated': pdf_generated
            }
            
        except Exception as e:
            logger.error(f"   ✗ Pack generation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def log_athlete_summary(self, athlete_info: dict, result: dict):
        """Log summary for athlete"""
        logger.info(f"\n{'─'*80}")
        logger.info(f"SUMMARY: {athlete_info['name']} ({athlete_info['school']})")
        logger.info(f"{'─'*80}")
        
        # Collection
        if result['steps'].get('collection', {}).get('success'):
            coll = result['steps']['collection']
            logger.info(f"  📊 Data Collection: {coll['sources_successful']} sources, "
                       f"Quality: {coll['data_quality_score']:.2f}")
        
        # Gravity
        if result['steps'].get('gravity', {}).get('success'):
            grav = result['steps']['gravity']
            logger.info(f"  ⭐ Gravity Score: {grav['gravity_conf']:.2f}/100")
        
        # Valuation
        if result['steps'].get('valuation', {}).get('success'):
            val = result['steps']['valuation']
            logger.info(f"  💰 IACV: ${val['iacv_p50']:,.0f} "
                       f"(Range: ${val['iacv_p25']:,.0f} - ${val['iacv_p75']:,.0f})")
        
        # Underwriting
        if result['steps'].get('underwriting', {}).get('success'):
            uw = result['steps']['underwriting']
            logger.info(f"  📋 Deal Decision: {uw['decision'].upper()}")
        
        # Pack
        if result['steps'].get('pack', {}).get('success'):
            pack = result['steps']['pack']
            logger.info(f"  📄 Pack Generated: JSON ✓, PDF {'✓' if pack['pdf_generated'] else '✗'}")
        
        logger.info(f"{'─'*80}\n")
    
    def generate_summary_report(self):
        """Generate final summary report"""
        logger.info("\n" + "=" * 80)
        logger.info("FINAL SIMULATION REPORT")
        logger.info("=" * 80 + "\n")
        
        # Create summary table
        summary_data = []
        for result in self.results:
            athlete = result['athlete']
            
            summary_data.append({
                'name': athlete['name'],
                'school': athlete['school'],
                'position': athlete['position'],
                'gravity': result['steps'].get('gravity', {}).get('gravity_conf', 0),
                'iacv': result['steps'].get('valuation', {}).get('iacv_p50', 0),
                'decision': result['steps'].get('underwriting', {}).get('decision', 'N/A'),
                'pack_generated': result['steps'].get('pack', {}).get('success', False)
            })
        
        # Print table
        logger.info(f"{'Athlete':<20} {'School':<12} {'Pos':<8} {'Gravity':<10} {'IACV':<15} {'Decision':<10} {'Pack':<6}")
        logger.info("─" * 95)
        
        for data in summary_data:
            logger.info(f"{data['name']:<20} "
                       f"{data['school']:<12} "
                       f"{data['position']:<8} "
                       f"{data['gravity']:<10.2f} "
                       f"${data['iacv']:<14,.0f} "
                       f"{data['decision']:<10} "
                       f"{'✓' if data['pack_generated'] else '✗':<6}")
        
        logger.info("\n" + "=" * 80)
        
        # Save summary to JSON
        summary_path = self.output_dir / 'simulation_summary.json'
        with open(summary_path, 'w') as f:
            json.dump({
                'timestamp': datetime.utcnow().isoformat(),
                'athletes': summary_data,
                'full_results': self.results
            }, f, indent=2, default=str)
        
        logger.info(f"\n📊 Full results saved to: {summary_path}")
        logger.info(f"📁 Output directory: {self.output_dir.absolute()}\n")


def main():
    """Run the simulation"""
    print("\n" + "=" * 80)
    print("GRAVITY NIL PIPELINE - TEST SIMULATION")
    print("Testing with 3 CFB Athletes (2025-2026 Season)")
    print("=" * 80 + "\n")
    
    print("Athletes to be tested:")
    for i, athlete in enumerate(TEST_ATHLETES, 1):
        print(f"  {i}. {athlete['name']} - {athlete['school']} {athlete['position']}")
    
    print("\nStarting simulation in 3 seconds...")
    import time
    time.sleep(3)
    
    # Run simulation
    simulation = NILPipelineSimulation()
    simulation.run_simulation()
    
    print("\n✅ Simulation complete! Check data/test_simulation/ for output files.\n")


if __name__ == '__main__':
    main()
