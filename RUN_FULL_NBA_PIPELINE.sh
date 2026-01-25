#!/bin/bash
# Full NBA Pipeline with VERIFIED ROSTERS
# Collects all 425 players from 30 teams + ML Scoring

cd /Users/robcseals/Gravity_Score && \
FAST_MODE=true \
USE_AI_FALLBACK=false \
MAX_CONCURRENT_PLAYERS=10 \
python3 run_nba_pipeline.py

# Output will be saved to:
# /Users/robcseals/Gravity_Score/Gravity_Final_Scores/NBA/nba_gravity_scores_TIMESTAMP.csv


