# Player Data Scrapers - Separated by Sport

## Overview

The player data collection system is now **fully separated** into sport-specific scrapers:

- **NFL Scraper** (`gravity/nfl_scraper.py`) - Dedicated to NFL players only
- **NBA Scraper** (`gravity/nba_scraper.py`) - Dedicated to NBA players only
- **Unified Scraper** (`gravity/unified_scraper.py`) - Legacy/optional unified interface

## 🏈 NFL Data Collection

### Quick Start
```bash
# Collect ALL NFL players (recommended)
python collect_all_nfl_players.py

# Or use the scraper directly
python gravity/nfl_scraper.py all
```

### NFL-Specific Commands
```bash
# Single NFL player
python gravity/nfl_scraper.py player "Patrick Mahomes" "Kansas City Chiefs" "QB"

# NFL team roster
python gravity/nfl_scraper.py team "KC"

# All NFL teams
python gravity/nfl_scraper.py all

# Test mode (one player per NFL team)
python gravity/nfl_scraper.py test

# Interactive mode
python gravity/nfl_scraper.py
```

### NFL Output
- Location: `scrapes/NFL/{timestamp}/`
- Combined file: `nfl_players_{timestamp}.csv`
- ~1,700 players, 150+ fields each

---

## 🏀 NBA Data Collection

### Quick Start
```bash
# Collect ALL NBA players (recommended)
python collect_all_nba_players.py

# Or use the scraper directly
python gravity/nba_scraper.py all
```

### NBA-Specific Commands
```bash
# Single NBA player
python gravity/nba_scraper.py player "LeBron James" "Los Angeles Lakers" "SF"

# NBA team roster
python gravity/nba_scraper.py team "LAL"

# All NBA teams
python gravity/nba_scraper.py all

# Test mode (one player per NBA team)
python gravity/nba_scraper.py test

# Interactive mode
python gravity/nba_scraper.py
```

### NBA Output
- Location: `scrapes/NBA/{timestamp}/`
- Combined file: `nba_players_{timestamp}.csv`
- ~450 players, 150+ fields each

---

## Why Separate Scrapers?

### Benefits of Separation

1. **Clean Code** - Each scraper focuses on one sport
2. **Independent Development** - Update NFL without affecting NBA
3. **Clear Organization** - No confusion about which sport you're collecting
4. **Dedicated Output** - Separate folders (`scrapes/NFL/` vs `scrapes/NBA/`)
5. **Sport-Specific Features** - Each scraper can have unique optimizations

### Sport-Specific Differences

#### NFL Scraper Features:
- Pro Football Reference integration
- ESPN NFL stats
- NFL.com data
- Pro Bowl, All-Pro selections
- Super Bowl wins tracking
- Position-specific stats (QB, RB, WR, etc.)

#### NBA Scraper Features:
- NBA.com stats integration
- Basketball Reference data
- All-Star selections
- All-NBA team selections
- Championships tracking
- Position-specific stats (PG, SG, SF, PF, C)

---

## File Structure

```
Gravity_Score/
├── gravity/
│   ├── nfl_scraper.py          ← NFL-only scraper
│   ├── nba_scraper.py          ← NBA-only scraper
│   ├── unified_scraper.py      ← Legacy unified (optional)
│   ├── scrape                  ← Shared NFL infrastructure
│   ├── nba_stats_collector.py  ← NBA stats collector
│   └── nba_data_models.py      ← NBA data models
│
├── collect_all_nfl_players.py  ← Quick NFL collection
├── collect_all_nba_players.py  ← Quick NBA collection
│
└── scrapes/
    ├── NFL/                     ← NFL data output
    │   └── {timestamp}/
    │       └── nfl_players_{timestamp}.csv
    └── NBA/                     ← NBA data output
        └── {timestamp}/
            └── nba_players_{timestamp}.csv
```

---

## Configuration

### Required Environment Variables

```bash
# Required for both
export FIRECRAWL_API_KEY="fc-your-api-key"

# Optional (for better parsing)
export OPENAI_API_KEY="sk-your-openai-key"
```

### Optional Environment Variables

```bash
# Performance tuning
export MAX_CONCURRENT_PLAYERS=3           # Players processed in parallel
export MAX_CONCURRENT_DATA_COLLECTORS=4   # Data collectors per player
export REQUEST_DELAY=1.5                  # Seconds between requests

# Feature flags
export USE_LLM_PARSING=true               # Use OpenAI for parsing (if key set)

# Mode selection (alternative to command line args)
export SCRAPE_MODE=all                    # player, team, all, test, interactive
```

---

## Which Scraper Should I Use?

### Use `nfl_scraper.py` when:
- ✅ You only need NFL data
- ✅ You want dedicated NFL features
- ✅ You're building NFL-specific tools

### Use `nba_scraper.py` when:
- ✅ You only need NBA data
- ✅ You want dedicated NBA features
- ✅ You're building NBA-specific tools

### Use `unified_scraper.py` when:
- ⚠️ You need to switch between sports frequently
- ⚠️ You want one interface for both (legacy support)
- ⚠️ You're maintaining old scripts

**Recommendation**: Use the sport-specific scrapers (`nfl_scraper.py` or `nba_scraper.py`) for better organization and performance.

---

## Data Output Comparison

### NFL Players CSV Columns (150+)
- Identity: name, age, college, draft info, height, weight
- Career Stats: games, touchdowns, yards, completions, interceptions
- Season Stats: current and previous season breakdowns
- Awards: Pro Bowls, All-Pro, Super Bowl wins
- Social: Instagram, Twitter, TikTok, YouTube
- Contract: value, status, earnings
- Performance: trends, ratings, risk scores

### NBA Players CSV Columns (150+)
- Identity: name, age, college, draft info, height, weight
- Career Stats: points, rebounds, assists, games
- Season Stats: current and previous season breakdowns
- Awards: All-Star, All-NBA, Championships, MVP
- Social: Instagram, Twitter, TikTok, YouTube
- Contract: value, status, earnings
- Performance: trends, ratings, risk scores

---

## Migrating from Unified Scraper

If you were using `unified_scraper.py`:

### Old Way (Unified)
```bash
python gravity/unified_scraper.py nfl all
python gravity/unified_scraper.py nba all
```

### New Way (Separated)
```bash
# NFL
python gravity/nfl_scraper.py all
# or
python collect_all_nfl_players.py

# NBA
python gravity/nba_scraper.py all
# or
python collect_all_nba_players.py
```

---

## Support

- **NFL Documentation**: See `README_NFL_DATA_COLLECTION.md`
- **Quick Start**: See `QUICK_START.md`
- **Issues**: Check logs in `scrapes/NFL/` or `scrapes/NBA/`

---

**Last Updated**: December 2, 2025  
**Version**: Separated v2.0

