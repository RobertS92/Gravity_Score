# NFL Player Data Collection - Complete Guide

## Quick Start: Get ALL NFL Players in ONE CSV

### Option 1: Simple Script (Recommended)
```bash
python collect_all_nfl_players.py
```

### Option 2: Direct Command
```bash
python gravity/unified_scraper.py nfl all
```

## What You Get

When you run either command above, you'll get:
- ✅ **ONE comprehensive CSV file** with ALL NFL players
- ✅ **150+ data fields** per player including:
  - Identity (name, age, college, draft info, height, weight, etc.)
  - Career Stats (games, touchdowns, yards, tackles, sacks, etc.)
  - Current Season Stats
  - Last Season Stats  
  - Year-by-year career breakdown
  - Social Media (Instagram, Twitter, TikTok, YouTube)
  - Brand Partnerships & Endorsements
  - Contract Information
  - Awards & Achievements (Pro Bowls, All-Pro, etc.)
  - Performance Trends & Risk Analysis
  - Injury History
  - News & Media Mentions
  - And much more...

## Output Location

Files are saved to: `scrapes/NFL/{timestamp}/`
- Combined CSV: `nfl_players_{timestamp}.csv`
- Combined JSON: `nfl_players_{timestamp}.json`
- Individual player files (JSON + CSV for each player)

## Other Collection Modes

### Single Player
```bash
python gravity/unified_scraper.py nfl player "Patrick Mahomes" "Kansas City Chiefs" "QB"
```

### Single Team
```bash
python gravity/unified_scraper.py nfl team "KC"
```

### Test Mode (One player per team for testing)
```bash
python gravity/unified_scraper.py nfl test
```

### Interactive Mode
```bash
python gravity/unified_scraper.py nfl
```
Then follow the prompts.

## Requirements

1. **Firecrawl API Key** (set as environment variable)
```bash
export FIRECRAWL_API_KEY="fc-your-api-key-here"
```

2. **OpenAI API Key** (optional, for enhanced LLM parsing)
```bash
export OPENAI_API_KEY="sk-your-openai-key-here"
```

3. **Python Dependencies**
The system uses existing dependencies from your venv.

## Configuration

Environment variables you can set:
```bash
export MAX_CONCURRENT_PLAYERS=3        # Number of players to process in parallel (default: 3)
export MAX_CONCURRENT_DATA_COLLECTORS=4  # Data collectors per player (default: 4)
export REQUEST_DELAY=1.5               # Seconds between requests (default: 1.5)
export USE_LLM_PARSING=true            # Use OpenAI for better parsing (default: true if key set)
```

## Performance

- **Parallel Processing**: Collects multiple players simultaneously
- **Smart Caching**: Reuses data from previous scrapes
- **Estimated Time**: 15-30 minutes for all ~1,700 NFL players
- **API Efficient**: Batches requests and includes delays to respect rate limits

## CSV Output Structure

The final CSV contains one row per player with columns like:
- `player_name`, `team`, `position`
- `age`, `birth_date`, `college`, `hometown`, `nationality`
- `height`, `weight`, `jersey_number`, `draft_year`, `draft_round`, `draft_pick`
- `career_stats_games`, `career_stats_touchdowns`, `career_stats_yards`, etc.
- `current_season_games`, `current_season_pass_tds`, `current_season_rush_yards`, etc.
- `instagram_handle`, `instagram_followers`, `twitter_handle`, `twitter_followers`
- `contract_value`, `contract_status`, `career_earnings`
- `pro_bowls`, `all_pro_selections`, `super_bowl_wins`, `awards`
- `injury_risk_score`, `performance_trend`, `data_quality_score`
- And 100+ more fields!

## Troubleshooting

### "Please set your Firecrawl API key"
Make sure you've set the environment variable:
```bash
export FIRECRAWL_API_KEY="fc-your-actual-key"
```

### Script stops or times out
The script has built-in retry logic and error handling. If a player fails, it logs the error and continues with the next player. Check the logs for details.

### Want to resume after interruption
The system checks for previous scrapes and can merge data. Just run the command again.

### Memory issues
Reduce concurrent players:
```bash
export MAX_CONCURRENT_PLAYERS=1
python collect_all_nfl_players.py
```

## Advanced Usage

### Use with environment file
Create a `.env` file:
```
FIRECRAWL_API_KEY=fc-your-key
OPENAI_API_KEY=sk-your-key
MAX_CONCURRENT_PLAYERS=3
USE_LLM_PARSING=true
```

Then run:
```bash
python collect_all_nfl_players.py
```

### Process specific teams only
Edit the script or use the team mode multiple times.

## Data Quality

Each player record includes a `data_quality_score` (0-100) indicating how complete the data is. Higher scores mean more fields were successfully collected.

## Support

For issues or questions:
1. Check the logs in `scrapes/NFL/{timestamp}/` 
2. Review the error messages in the console
3. Ensure API keys are valid and have sufficient credits

---

**Last Updated**: December 2, 2025  
**Version**: Production-Ready v1.0

