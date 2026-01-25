# Gravity Score Pipeline Guide

Complete guide to the Gravity Score data processing pipeline.

---

## 🎯 Overview

The Gravity Score Pipeline transforms raw player data into actionable insights by:

1. **Flattening** nested JSON/dict structures into tabular format
2. **Imputing** missing values using intelligent position-aware defaults
3. **Extracting** derived features from raw data
4. **Calculating** comprehensive Gravity Scores (0-100)

---

## 🚀 Quick Start

### Process Existing Data

```bash
# Process a CSV file
python run_pipeline.py input_players.csv output_gravity_scores.csv

# Process JSON data
python run_pipeline.py data.json output_scores.json

# Show top 10 players
python run_pipeline.py input.csv output.csv --show-top 10
```

### Scrape Fresh Data & Process

```bash
# NFL (test mode - one player per team)
python run_pipeline.py --scrape nfl --output nfl_scores.csv

# NBA (test mode)
python run_pipeline.py --scrape nba --output nba_scores.csv

# NFL (all teams - ~1700 players)
python run_pipeline.py --scrape nfl --scrape-mode all --output nfl_all_scores.csv
```

### Filter Results

```bash
# Filter by position
python run_pipeline.py input.csv output.csv --filter-position QB

# Filter by team
python run_pipeline.py input.csv output.csv --filter-team "Chiefs"

# Combine filters
python run_pipeline.py input.csv output.csv --filter-position WR --filter-team "Cowboys"
```

---

## 📊 Pipeline Components

### 1. Data Flattener

**Purpose**: Convert nested player data into flat tabular format

**Features**:
- Flattens all nested sections (identity, brand, proof, proximity, velocity, risk)
- Limits year-by-year data to recent N years (default: 3)
- Handles complex lists and dictionaries
- Preserves data structure with dot notation (e.g., `proof.career_ppg`)

**Configuration**:
```python
flattener = DataFlattener(max_years=3)  # Keep last 3 years only
```

**Example**:
```python
# Before (nested)
{
  "player_name": "Patrick Mahomes",
  "identity": {
    "age": 28,
    "position": "QB"
  },
  "proof": {
    "career_stats_by_year": {
      "2024": {"yards": 4183},
      "2023": {"yards": 4839},
      "2022": {"yards": 5250}
    }
  }
}

# After (flat)
{
  "player_name": "Patrick Mahomes",
  "identity.age": 28,
  "identity.position": "QB",
  "proof.career_stats_by_year.2024.yards": 4183,
  "proof.career_stats_by_year.2023.yards": 4839,
  "proof.career_stats_by_year.2022.yards": 5250
}
```

---

### 2. Data Imputer

**Purpose**: Fill missing values with intelligent defaults

**Features**:
- Position-aware physical defaults (height, weight)
- Median imputation for numeric fields
- Modal imputation for categorical fields
- Age calculation from birth_date
- Years_in_league calculation from draft_year

**Position Defaults**:
```python
# NFL Examples
QB:  6'2" (74"), 220 lbs
RB:  5'10" (70"), 215 lbs
WR:  6'0" (72"), 200 lbs
TE:  6'5" (77"), 250 lbs

# NBA Examples
PG:  6'2" (74"), 190 lbs
SG:  6'5" (77"), 205 lbs
C:   6'11" (83"), 250 lbs
```

**Imputation Rules**:
- **Height/Weight**: Position-based defaults
- **Stats (yards, points, etc.)**: 0 (no negative stats)
- **Social followers**: Median by position
- **Percentages/Rates**: Position median or 0
- **Categorical**: Most common value or "Unknown"

---

### 3. Feature Extractor

**Purpose**: Create derived features from raw data

**Features Extracted**:

#### Physical Features
- `feature.bmi`: Body Mass Index
- `feature.age_category`: Rookie, Young, Prime, Veteran, Aging

#### Performance Features
- `feature.scoring_level`: Low, Average, Good, High, Elite
- `feature.pro_bowl_rate`: Pro Bowls per year in league
- `feature.total_awards`: Count of all awards/accolades

#### Social Features
- `feature.total_social_reach`: Sum of all social followers
- `feature.avg_engagement_rate`: Average engagement across platforms
- `feature.verified_accounts`: Count of verified social accounts

#### Risk Features
- `feature.injury_risk_composite`: Weighted injury risk score
- `feature.reputation_risk`: Controversy and off-field risk
- `feature.contract_security`: Contract stability (Secure/At-Risk/Uncertain)

#### Velocity Features
- `feature.social_momentum`: Recent follower growth
- `feature.performance_momentum`: Performance trend (improving/stable/declining)
- `feature.media_momentum`: Recent media attention surge

---

### 4. Gravity Score Calculator

**Purpose**: Calculate comprehensive 0-100 Gravity Score

#### Score Components

**Performance Score (40% weight)**
- Career stats (PPG, yards, TDs, etc.)
- Awards & accolades (Pro Bowls, All-Pro, etc.)
- Championships & playoff success

**Market Value Score (25% weight)**
- Contract value (NFL/NBA/WNBA)
- NIL valuation (college athletes)
- Endorsement deals

**Social Influence Score (15% weight)**
- Total social media reach
- Engagement rate
- Media mentions

**Velocity/Momentum Score (10% weight)**
- Social follower growth
- Performance trend
- Media buzz surge

**Risk Score (10% weight - inverse)**
- Injury risk (history, games missed)
- Controversy risk (suspensions, fines, arrests)
- Age risk (peak vs. declining)

#### Score Tiers

| Score Range | Tier | Description |
|------------|------|-------------|
| 90-100 | **Superstar** | Elite, franchise-defining players |
| 80-89 | **Elite** | Top-tier players, All-Pro caliber |
| 65-79 | **Impact** | High-quality starters, Pro Bowl level |
| 50-64 | **Solid** | Reliable contributors, steady value |
| 0-49 | **Developing** | Emerging or declining players |

---

## 📈 Output Columns

### Core Fields
- `player_name`, `team`, `position`
- `collection_timestamp`
- `data_quality_score`

### Identity (identity.*)
- Physical: `age`, `height`, `weight`, `hometown`
- Career: `draft_year`, `draft_round`, `years_in_league`
- Contract: `current_contract_length`, `contract_value`
- Recruiting: `recruiting_stars`, `recruiting_ranking`

### Brand (brand.*)
- Social: `instagram_followers`, `twitter_followers`, `tiktok_followers`
- Engagement: `instagram_engagement_rate`, etc.
- Media: `news_headline_count_30d`, `google_trends_score`

### Proof (proof.*)
- Awards: `pro_bowls`, `all_pro_selections`, `super_bowl_wins`
- Stats: `career_ppg`, `career_yards`, `career_touchdowns`
- Year-by-year: `career_stats_by_year.*`

### Proximity (proximity.*)
- Business: `endorsements`, `endorsement_value`, `brand_partnerships`
- Leadership: `team_captain`, `leadership_role`

### Velocity (velocity.*)
- Growth: `follower_growth_rate_30d`, `performance_trend`
- Momentum: `media_buzz_surge`, `stats_improvement_percentage`

### Risk (risk.*)
- Injury: `injury_risk_score`, `games_missed_career`
- Reputation: `controversies`, `suspensions`, `controversy_risk_score`
- Contract: `free_agency_year`, `contract_status`

### Features (feature.*)
- All extracted features (20+ derived columns)

### Gravity Scores
- `gravity_score`: Final weighted score (0-100)
- `gravity_percentile`: Percentile rank vs. all players
- `gravity_tier`: Tier classification (Developing → Superstar)
- `gravity.performance_score`: Performance component (0-100)
- `gravity.market_score`: Market value component (0-100)
- `gravity.social_score`: Social influence component (0-100)
- `gravity.velocity_score`: Momentum component (0-100)
- `gravity.risk_score`: Risk component (0-100)

---

## 🔧 Advanced Usage

### Python API

```python
from gravity.data_pipeline import GravityPipeline

# Initialize pipeline
pipeline = GravityPipeline(max_years=3)

# Process DataFrame
import pandas as pd
df = pd.read_csv('players.csv')
scored_df = pipeline.process(df, output_format='dataframe')

# Process JSON
with open('players.json') as f:
    data = json.load(f)
scored_df = pipeline.process(data, output_format='dataframe')

# Save results
scored_df.to_csv('gravity_scores.csv', index=False)
```

### Custom Component Usage

```python
from gravity.data_pipeline import DataFlattener, DataImputer, FeatureExtractor, GravityScoreCalculator

# Use individual components
flattener = DataFlattener(max_years=5)  # Keep 5 years
imputer = DataImputer()
extractor = FeatureExtractor()
scorer = GravityScoreCalculator()

# Process step by step
df = pd.read_csv('raw_data.csv')
df = flattener.flatten_dataframe(df)
df = imputer.impute_data(df)
df = extractor.extract_features(df)
df = scorer.calculate_gravity_scores(df)
```

---

## 📊 Example Outputs

### Top Players Display

```
🏆 TOP 10 PLAYERS BY GRAVITY SCORE
================================================================================

 1. Patrick Mahomes        QB  Kansas City Chiefs
    Gravity Score:  96.8/100  [Superstar]  (Top 1%)
    Performance: 98.2 | Market: 95.4 | Social: 92.1 | Velocity: 88.5 | Risk: 12.3

 2. Travis Kelce           TE  Kansas City Chiefs
    Gravity Score:  94.2/100  [Superstar]  (Top 2%)
    Performance: 96.8 | Market: 89.3 | Social: 94.7 | Velocity: 91.2 | Risk: 15.8

 3. Tyreek Hill            WR  Miami Dolphins
    Gravity Score:  92.5/100  [Superstar]  (Top 3%)
    Performance: 94.1 | Market: 88.6 | Social: 96.3 | Velocity: 93.4 | Risk: 18.2
```

### Tier Distribution

```
📊 TIER DISTRIBUTION:
   Superstar   :   15 players ( 1.2%)
   Elite       :   89 players ( 7.1%)
   Impact      :  342 players (27.4%)
   Solid       :  596 players (47.7%)
   Developing  :  208 players (16.6%)
```

---

## 🎯 Use Cases

### 1. Player Valuation
```bash
# Get Gravity Scores for free agents
python run_pipeline.py nfl_players.csv fa_valuation.csv --filter-position QB

# Analyze top performers
python run_pipeline.py input.csv output.csv --show-top 50
```

### 2. Draft Analysis
```bash
# Score college prospects
python run_pipeline.py --scrape cfb --output college_prospects.csv --show-top 25

# Compare draft classes
python run_pipeline.py draft_2024.csv scores_2024.csv
```

### 3. Contract Negotiations
```bash
# Assess player market value
python run_pipeline.py current_roster.csv team_valuations.csv --filter-team "Chiefs"
```

### 4. Social Media Strategy
```bash
# Identify high-engagement players
python run_pipeline.py players.csv social_analysis.csv --show-top 20
# Then sort by gravity.social_score
```

---

## ⚙️ Configuration

### Command-Line Options

```bash
python run_pipeline.py [options] input output

Options:
  --scrape {nfl,nba,wnba,cfb,ncaab,wncaab}
                        Scrape fresh data for sport
  --scrape-mode {test,team,all,player}
                        Scraping mode (default: test)
  --max-years N         Maximum historical years to keep (default: 3)
  --show-top N          Show top N players by Gravity Score
  --filter-position POS Filter by position (e.g., QB, WR)
  --filter-team TEAM    Filter by team
  --output-format {csv,json,excel}
                        Output format (default: csv)
```

### Environment Variables

```bash
# Optional: Configure scraping
export FIRECRAWL_API_KEY="your_key_here"  # Not required
export SKIP_PFR_SCRAPING=true              # Skip PFR if no Firecrawl
```

---

## 🔍 Data Quality

### Quality Score Calculation

The `data_quality_score` field (0-100) indicates completeness:

- **90-100**: Excellent - All core fields populated
- **70-89**: Good - Most important fields present
- **50-69**: Fair - Some gaps in data
- **0-49**: Poor - Significant missing data

### Improving Data Quality

1. **Use multiple sources**: The scrapers pull from ESPN, Wikipedia, social media, etc.
2. **Enable Firecrawl**: For PFR and additional sources (optional)
3. **Manual enrichment**: Edit CSV and re-run pipeline
4. **Frequent updates**: Re-scrape to get latest stats

---

## 📝 Notes

- **Year Limiting**: By default, only last 3 years of stats are kept to prevent CSV explosion. Adjust with `--max-years`.
- **Missing Data**: The imputer intelligently fills gaps, but original data quality matters.
- **Score Normalization**: Gravity Scores are normalized within the dataset, so adding/removing players affects relative scores.
- **Position Bias**: Different positions have different stat ranges. Scores account for this.

---

## 🐛 Troubleshooting

### Pipeline fails with KeyError
- **Cause**: Missing expected columns
- **Fix**: Ensure input data matches expected schema (from scrapers)

### Low data quality scores
- **Cause**: Many missing fields in raw data
- **Fix**: Re-scrape with better sources or manually enrich data

### Scores seem off
- **Cause**: Normalization is relative to dataset
- **Fix**: Ensure dataset has diverse players (not just one team)

### Memory issues with large datasets
- **Cause**: Too many year-by-year columns
- **Fix**: Reduce `--max-years` to 2 or 1

---

## 📚 Related Documentation

- `README.md` - Project overview
- `CONTRACT_COLLECTION_IMPLEMENTATION.md` - Contract data collection
- `NFL_PROOF_DATA_FIX.md` - Awards data collection
- `DATA_QUALITY_FIX_SUMMARY.md` - Data quality improvements
- `TESTING_GUIDE.md` - Testing procedures

---

## 🚀 Next Steps

1. **Run your first pipeline**: 
   ```bash
   python run_pipeline.py --scrape nfl --output test.csv --show-top 10
   ```

2. **Analyze results**: Open `test.csv` in Excel/Sheets

3. **Filter and sort**: Use `gravity_score` and `gravity_tier` columns

4. **Iterate**: Re-scrape with `--scrape-mode all` for complete dataset

---

**Built by the Gravity Score Team** | Production-grade player analytics

