# Phase D4: Deploy & Validate - Complete Implementation Guide

## Overview
This document outlines the complete implementation for Phase D4: Deploy & Validate, including synthetic data generation, model training, and hybrid ensemble deployment.

## Prerequisites

### 1. Install ML Dependencies
```bash
pip install -r requirements_ml.txt
```

### 2. Verify CTGAN Installation
```bash
python -c "from sdv.single_table import CTGANSynthesizer; print('✅ CTGAN installed')"
```

## Step-by-Step Execution

### Step 1: Collect Social Data for All Athletes

#### NFL
```bash
# Collect social data for all NFL players
python collect_all_social_data.py nfl \
  scrapes/NFL/20251209_113136/nfl_players_20251209_123629.csv \
  nfl_all_with_social.csv

# Or process in batches (resume from index 1000)
python collect_all_social_data.py nfl \
  scrapes/NFL/20251209_113136/nfl_players_20251209_123629.csv \
  nfl_all_with_social.csv 500 1000
```

#### NBA
```bash
python collect_all_social_data.py nba \
  scrapes/NBA/20251203_214612/nba_players_20251203_231046.csv \
  nba_all_with_social.csv
```

#### CFB
```bash
python collect_all_social_data.py cfb \
  scrapes/CFB/20251203_233730/cfb_power5_players_20251204_193153.csv \
  cfb_all_with_social.csv
```

### Step 2: Generate Synthetic Data

Generate 300K synthetic players (100K each sport):

```bash
# Generate all synthetic data
python generate_synthetic_data.py
```

This will:
- Train CTGAN on real player data
- Generate 100K synthetic NFL players
- Generate 100K synthetic NBA players
- Generate 100K synthetic CFB players
- Save to `synthetic_data/` directory

**Expected Time:** 2-4 hours depending on hardware

### Step 3: Train Neural Networks

Train all 5 specialized neural networks for each sport:

#### NFL
```bash
# Train on real + synthetic data
python ml/train_all_models.py nfl final_scores/NFL_COMPLETE_FIXED.csv cpu
```

#### NBA
```bash
python ml/train_all_models.py nba final_scores/NBA_COMPLETE.csv cpu
```

#### CFB
```bash
python ml/train_all_models.py cfb final_scores/CFB_COMPLETE.csv cpu
```

**Note:** Use `cuda` instead of `cpu` if you have GPU available for faster training.

**Expected Time:** 1-2 hours per sport (CPU) or 15-30 minutes (GPU)

### Step 4: Deploy Hybrid Ensemble

Deploy and validate the hybrid ensemble system:

#### NFL
```bash
python ml/deploy_hybrid_system.py nfl final_scores/NFL_COMPLETE_FIXED.csv cpu
```

#### NBA
```bash
python ml/deploy_hybrid_system.py nba final_scores/NBA_COMPLETE.csv cpu
```

#### CFB
```bash
python ml/deploy_hybrid_system.py cfb final_scores/CFB_COMPLETE.csv cpu
```

This will:
- Load trained neural networks
- Run hybrid predictions (NN + rule-based)
- Compare with rule-based only
- Generate validation reports
- Save final scored datasets

## Output Files

### Social Data Collection
- `nfl_all_with_social.csv` - All NFL players with social data
- `nba_all_with_social.csv` - All NBA players with social data
- `cfb_all_with_social.csv` - All CFB players with social data

### Synthetic Data
- `synthetic_data/nfl_synthetic_100k.csv` - 100K synthetic NFL players
- `synthetic_data/nba_synthetic_100k.csv` - 100K synthetic NBA players
- `synthetic_data/cfb_synthetic_100k.csv` - 100K synthetic CFB players

### Trained Models
- `models/performance_nn_{sport}.pth` - Performance scoring NN
- `models/market_nn_{sport}.pth` - Market value NN
- `models/social_nn_{sport}.pth` - Social media NN
- `models/velocity_nn_{sport}.pth` - Velocity/trajectory NN
- `models/risk_nn_{sport}.pth` - Risk assessment NN

### Final Results
- `final_scores/{SPORT}_HYBRID_FINAL.csv` - Hybrid ensemble scores
- `final_scores/{SPORT}_HYBRID_COMPARISON.csv` - Comparison with rule-based

## Validation Metrics

The deployment script will output:
- **Score Correlation:** How well hybrid scores correlate with rule-based
- **Weight Distribution:** How often NN vs rule-based is used
- **Top Players Comparison:** Side-by-side comparison of top 10 players
- **Average Differences:** Mean difference between hybrid and rule-based

## Troubleshooting

### CTGAN Installation Issues
```bash
# If CTGAN fails to install, try:
pip install sdv[all]
# Or use conda:
conda install -c conda-forge sdv
```

### Out of Memory During Training
- Reduce batch size in `train_all_models.py` (change `batch_size=32` to `batch_size=16`)
- Use CPU instead of GPU if GPU memory is limited
- Process fewer players at once

### Model Loading Errors
- Ensure models are trained first: `python ml/train_all_models.py`
- Check that model files exist in `models/` directory
- Verify sport name matches (nfl, nba, cfb)

## Next Steps

After completing Phase D4:
1. **Evaluate Results:** Review hybrid vs rule-based comparisons
2. **Fine-tune Models:** Adjust hyperparameters if needed
3. **Production Deployment:** Integrate into API/dashboard
4. **Monitor Performance:** Track prediction accuracy over time

## Performance Expectations

- **Social Data Collection:** ~1-2 players/second (rate-limited)
- **Synthetic Data Generation:** ~1000 players/minute (CTGAN)
- **Model Training:** 1-2 hours per sport (CPU), 15-30 min (GPU)
- **Hybrid Deployment:** ~100 players/second (inference)

## Success Criteria

✅ All 3 sports have social data collected
✅ 300K synthetic players generated (100K each)
✅ All 5 neural networks trained for each sport
✅ Hybrid ensemble deployed and validated
✅ Correlation > 0.70 between hybrid and rule-based scores
✅ Top 10 players make sense (expected stars ranked highly)

