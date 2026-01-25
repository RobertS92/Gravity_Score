#!/usr/bin/env python3
"""
Phase D4: Complete Execution Script
====================================
Runs all Phase D4 steps: social data collection, synthetic generation, training, deployment
"""

import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_command(cmd, description):
    """Run a command and handle errors"""
    logger.info(f"\n{'='*100}")
    logger.info(f"🚀 {description}")
    logger.info(f"{'='*100}\n")
    logger.info(f"Command: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Command failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        return False


def main():
    """Run all Phase D4 steps"""
    
    print("\n" + "="*100)
    print("🎯 PHASE D4: COMPLETE EXECUTION")
    print("="*100)
    print("\nThis script will:")
    print("  1. Collect social data for all athletes (NFL, NBA, CFB)")
    print("  2. Generate synthetic data (300K players)")
    print("  3. Train all neural networks")
    print("  4. Deploy and validate hybrid ensemble")
    print("\n" + "="*100 + "\n")
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Step 1: Collect Social Data (optional - can skip if already done)
    print("\n" + "="*100)
    print("STEP 1: COLLECT SOCIAL DATA")
    print("="*100)
    response = input("Collect social data for all athletes? This may take several hours. (y/n): ")
    
    if response.lower() == 'y':
        sports = ['nfl', 'nba', 'cfb']
        for sport in sports:
            input_file = f'scrapes/{sport.upper()}/**/*.csv'
            output_file = f'{sport}_all_with_social.csv'
            
            # Find latest scrape file
            from glob import glob
            files = glob(f'scrapes/{sport.upper()}/**/*players*.csv', recursive=True)
            if files:
                input_file = sorted(files)[-1]  # Latest file
                logger.info(f"Using {input_file} for {sport}")
                
                success = run_command(
                    ['python', 'collect_all_social_data.py', sport, input_file, output_file],
                    f"Collecting social data for {sport.upper()}"
                )
                if not success:
                    logger.warning(f"⚠️  Social data collection failed for {sport}. Continuing...")
    else:
        logger.info("⏭️  Skipping social data collection")
    
    # Step 2: Generate Synthetic Data
    print("\n" + "="*100)
    print("STEP 2: GENERATE SYNTHETIC DATA")
    print("="*100)
    response = input("Generate 300K synthetic players? This may take 2-4 hours. (y/n): ")
    
    if response.lower() == 'y':
        success = run_command(
            ['python', 'generate_synthetic_data.py'],
            "Generating synthetic data"
        )
        if not success:
            logger.error("❌ Synthetic data generation failed!")
            return
    else:
        logger.info("⏭️  Skipping synthetic data generation")
    
    # Step 3: Train Neural Networks
    print("\n" + "="*100)
    print("STEP 3: TRAIN NEURAL NETWORKS")
    print("="*100)
    response = input("Train all neural networks? This may take 3-6 hours. (y/n): ")
    
    if response.lower() == 'y':
        sports = ['nfl', 'nba', 'cfb']
        data_files = {
            'nfl': 'final_scores/NFL_COMPLETE_FIXED.csv',
            'nba': 'final_scores/NBA_COMPLETE.csv',
            'cfb': 'final_scores/CFB_COMPLETE.csv'
        }
        
        for sport in sports:
            data_file = data_files.get(sport)
            if not Path(data_file).exists():
                logger.warning(f"⚠️  Data file not found: {data_file}. Skipping {sport}.")
                continue
            
            success = run_command(
                ['python', 'ml/train_all_models.py', sport, data_file, 'cpu'],
                f"Training neural networks for {sport.upper()}"
            )
            if not success:
                logger.warning(f"⚠️  Training failed for {sport}. Continuing...")
    else:
        logger.info("⏭️  Skipping neural network training")
    
    # Step 4: Deploy Hybrid Ensemble
    print("\n" + "="*100)
    print("STEP 4: DEPLOY HYBRID ENSEMBLE")
    print("="*100)
    response = input("Deploy and validate hybrid ensemble? (y/n): ")
    
    if response.lower() == 'y':
        sports = ['nfl', 'nba', 'cfb']
        data_files = {
            'nfl': 'final_scores/NFL_COMPLETE_FIXED.csv',
            'nba': 'final_scores/NBA_COMPLETE.csv',
            'cfb': 'final_scores/CFB_COMPLETE.csv'
        }
        
        for sport in sports:
            data_file = data_files.get(sport)
            if not Path(data_file).exists():
                logger.warning(f"⚠️  Data file not found: {data_file}. Skipping {sport}.")
                continue
            
            success = run_command(
                ['python', 'ml/deploy_hybrid_system.py', sport, data_file, 'cpu'],
                f"Deploying hybrid ensemble for {sport.upper()}"
            )
            if not success:
                logger.warning(f"⚠️  Deployment failed for {sport}. Continuing...")
    else:
        logger.info("⏭️  Skipping hybrid ensemble deployment")
    
    print("\n" + "="*100)
    print("✅ PHASE D4 EXECUTION COMPLETE!")
    print("="*100)
    print("\n📁 Check output files in:")
    print("   • final_scores/ - Final scored datasets")
    print("   • models/ - Trained neural network models")
    print("   • synthetic_data/ - Generated synthetic players")
    print("="*100 + "\n")


if __name__ == '__main__':
    main()

