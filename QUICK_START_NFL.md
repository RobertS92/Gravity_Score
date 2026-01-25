# Quick Start: NFL Scrape with AI Fallback

## Step 1: Get Your Perplexity API Key (Optional but Recommended)

1. Go to **https://www.perplexity.ai/**
2. Sign up or log in
3. Navigate to the API section
4. Copy your API key (starts with `pplx-...`)

**Benefits of using the API:**
- Fills missing player data (hometown, endorsements, social handles, etc.)
- Improves data completeness from ~72% to ~90%+
- Only costs ~$8-10 for full NFL scrape (~$0.003 per player)

**Without the API:**
- Scrape still works fine
- Some fields may be missing for less prominent players
- No additional cost

## Step 2: Run the Scrape

### Option A: Interactive Script (Easiest)

```bash
./setup_and_run_nfl.sh
```

This will:
- Prompt you for your API key (or skip if you don't have one)
- Ask which mode: Test (5 players) or Full (2600+ players)
- Run the complete scrape and scoring pipeline
- Save results to `Gravity_Final_Scores/NFL/NFL_Final_XXX.csv`

### Option B: Command Line with API Key

```bash
# Test mode (5 players, ~2 minutes)
PERPLEXITY_API_KEY="pplx-your-key" python3 run_pipeline.py --scrape nfl --scrape-mode test

# Full scrape - Fast mode (~4 hours)
PERPLEXITY_API_KEY="pplx-your-key" ./run_fast_nfl_scrape.sh

# Full scrape - Ultra-fast mode (~2-3 hours)
PERPLEXITY_API_KEY="pplx-your-key" ./run_ultra_fast_nfl_scrape.sh
```

### Option C: Without API Key

```bash
# Test mode
python3 run_pipeline.py --scrape nfl --scrape-mode test

# Full scrape
./run_fast_nfl_scrape.sh
```

## Step 3: View Your Results

```bash
# List all results (newest first)
ls -lth Gravity_Final_Scores/NFL/

# View the latest file
head $(ls -t Gravity_Final_Scores/NFL/NFL_Final_*.csv | head -1)

# Count players
wc -l $(ls -t Gravity_Final_Scores/NFL/NFL_Final_*.csv | head -1)
```

## What You'll Get

**Output File:** `Gravity_Final_Scores/NFL/NFL_Final_XXX.csv`

**Columns include:**
- Player name, team, position
- Gravity Score (0-100)
- Gravity Tier (Superstar, Elite, High Impact, etc.)
- Performance score
- Market value score
- Social media score
- Velocity score (trajectory)
- Risk score
- All underlying data (stats, contracts, endorsements, social media, etc.)

## Understanding the Output

**Gravity Tiers:**
- 🌟 **Superstar** (90-100): Top 1% of players
- ⭐ **Elite** (80-89): Top 5% of players
- 🔥 **High Impact** (70-79): Top 15% of players
- ✅ **Solid Contributor** (60-69): Top 30% of players
- 📊 **Role Player** (50-59): Average players
- ⚠️ **Developing/Backup** (40-49): Below average
- 🔻 **Limited Impact** (<40): Bottom tier

**Score Components:**
- **Performance**: Career stats, awards, Pro Bowls
- **Market**: Contract value, career earnings
- **Social**: Instagram/Twitter/TikTok followers, engagement
- **Velocity**: Recent trends, news mentions, momentum
- **Risk**: Injury history, age, performance decline

## Time Estimates

| Mode | Players | Time | AI Cost |
|------|---------|------|---------|
| Test | 5 | ~2 min | $0.02 |
| Fast | 2600+ | ~4 hours | $8-10 |
| Ultra-Fast | 2600+ | ~2-3 hours | $8-10 |

## Monitoring the Scrape

**Watch for these log symbols:**
- 🤖 = AI fallback activated
- 💰 = AI cost tracking
- ✅ = Success
- ⚠️ = Warning (non-critical)
- ❌ = Error

**Example AI fallback log:**
```
🤖 AI verifying draft status for Brock Purdy...
   ✅ Found via AI: draft_year = 2022
   ✅ AI corrected draft: 2022 Rd 7

💰 AI Fallback: Filled 3 fields, $0.003 total cost, 3 API calls
```

## Troubleshooting

**"Module not found" errors:**
```bash
pip3 install -r requirements.txt --user
```

**Rate limit errors (429):**
```bash
# Reduce concurrent requests
export MAX_CONCURRENT_PLAYERS=50
./run_fast_nfl_scrape.sh
```

**Timeout errors:**
```bash
# Increase timeout
export PLAYER_TIMEOUT=60
./run_fast_nfl_scrape.sh
```

## Next Steps After Scraping

1. **Analyze top players:**
   ```bash
   python3 run_pipeline.py Gravity_Final_Scores/NFL/NFL_Final_001.csv --show-top 20
   ```

2. **Filter by position:**
   ```bash
   python3 run_pipeline.py Gravity_Final_Scores/NFL/NFL_Final_001.csv output.csv --filter-position QB
   ```

3. **Filter by team:**
   ```bash
   python3 run_pipeline.py Gravity_Final_Scores/NFL/NFL_Final_001.csv output.csv --filter-team "Chiefs"
   ```

4. **Convert to Excel:**
   ```bash
   python3 run_pipeline.py Gravity_Final_Scores/NFL/NFL_Final_001.csv output.xlsx --output-format excel
   ```

## Questions?

- **Perplexity API docs:** `PERPLEXITY_FALLBACK_README.md`
- **Auto-numbering system:** `AUTO_NUMBERING_SYSTEM.md`
- **Fast mode guide:** `FAST_MODE_GUIDE.md`
- **Full folder docs:** `Gravity_Final_Scores/README.md`

