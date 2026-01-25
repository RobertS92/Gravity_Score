# Gravity Score - Sports Player Data Collection System

## 🎯 Quick Start

### Collect ALL NFL Players
```bash
python collect_all_nfl_players.py
```
**Output**: ONE CSV with ~1,700 NFL players and 150+ data fields per player  
**Location**: `scrapes/NFL/{timestamp}/nfl_players_{timestamp}.csv`

### Collect ALL NBA Players
```bash
python collect_all_nba_players.py
```
**Output**: ONE CSV with ~450 NBA players and 150+ data fields per player  
**Location**: `scrapes/NBA/{timestamp}/nba_players_{timestamp}.csv`

---

## 📁 System Architecture

### Separated by Sport

The system is **fully separated** into sport-specific scrapers:

```
🏈 NFL Scraper (gravity/nfl_scraper.py)
   └── Dedicated NFL data collection
   └── Output: scrapes/NFL/

🏀 NBA Scraper (gravity/nba_scraper.py)
   └── Dedicated NBA data collection
   └── Output: scrapes/NBA/
```

### Why Separated?

✅ **Clean Organization** - No confusion between sports  
✅ **Independent Updates** - Update NFL without affecting NBA  
✅ **Sport-Specific Features** - Optimized for each league  
✅ **Clear Output** - Separate folders for each sport  
✅ **Production Ready** - Each scraper is self-contained  

---

## 🏈 NFL Data Collection

### Commands
```bash
# Get ALL NFL players (one CSV with everything)
python collect_all_nfl_players.py

# Or use scraper directly
python gravity/nfl_scraper.py all                              # All teams
python gravity/nfl_scraper.py team "KC"                       # One team
python gravity/nfl_scraper.py player "Patrick Mahomes" "Kansas City Chiefs" "QB"
python gravity/nfl_scraper.py test                            # One player per team
python gravity/nfl_scraper.py                                 # Interactive mode
```

### What You Get (150+ Fields)
- **Identity**: Name, age, college, draft info, height, weight, jersey #
- **Career Stats**: Games, touchdowns, yards, completions, interceptions, sacks, tackles
- **Current Season**: This year's performance stats
- **Last Season**: Previous year's performance stats
- **Year-by-Year**: Career breakdown by season
- **Social Media**: Instagram, Twitter, TikTok, YouTube (followers, engagement)
- **Contract**: Value, status, earnings, guaranteed money
- **Awards**: Pro Bowls, All-Pro, Super Bowl wins
- **Performance**: Trends, ratings, PFF grades, QBR
- **Risk Analysis**: Injury risk, controversy risk, age risk
- **Brand**: Endorsements, partnerships, media buzz

### Documentation
- **Full Guide**: `README_NFL_DATA_COLLECTION.md`
- **Quick Reference**: `QUICK_START.md`

---

## 🏀 NBA Data Collection

### Commands
```bash
# Get ALL NBA players (one CSV with everything)
python collect_all_nba_players.py

# Or use scraper directly
python gravity/nba_scraper.py all                              # All teams
python gravity/nba_scraper.py team "LAL"                      # One team
python gravity/nba_scraper.py player "LeBron James" "Los Angeles Lakers" "SF"
python gravity/nba_scraper.py test                            # One player per team
python gravity/nba_scraper.py                                 # Interactive mode
```

### What You Get (150+ Fields)
- **Identity**: Name, age, college, draft info, height, weight, jersey #
- **Career Stats**: Points, rebounds, assists, games, minutes
- **Current Season**: This year's performance stats
- **Last Season**: Previous year's performance stats
- **Year-by-Year**: Career breakdown by season
- **Social Media**: Instagram, Twitter, TikTok, YouTube (followers, engagement)
- **Contract**: Value, status, earnings, guaranteed money
- **Awards**: All-Star selections, All-NBA, Championships, MVP
- **Performance**: Trends, ratings, PER, efficiency
- **Risk Analysis**: Injury risk, controversy risk, age risk
- **Brand**: Endorsements, partnerships, media buzz

---

## ⚙️ Setup

### 1. Required API Key
```bash
export FIRECRAWL_API_KEY="fc-your-api-key-here"
```

### 2. Optional API Key (for better parsing)
```bash
export OPENAI_API_KEY="sk-your-openai-key-here"
```

### 3. Run Collection
```bash
# NFL
python collect_all_nfl_players.py

# NBA
python collect_all_nba_players.py
```

---

## 📊 Output Format

### Combined CSV Structure
Every collection creates **ONE CSV file** with all players:

```csv
player_name,team,position,age,college,height,weight,instagram_followers,contract_value,pro_bowls,...
Patrick Mahomes,Kansas City Chiefs,QB,29,Texas Tech,6'3",230,5420000,450000000,6,...
Josh Allen,Buffalo Bills,QB,28,Wyoming,6'5",237,2180000,258000000,4,...
```

### File Organization
```
scrapes/
├── NFL/
│   └── 20251202_143022/
│       ├── nfl_players_20251202_143022.csv    ← ALL PLAYERS IN ONE FILE
│       ├── nfl_players_20251202_143022.json
│       └── individual_player_files...
└── NBA/
    └── 20251202_143530/
        ├── nba_players_20251202_143530.csv    ← ALL PLAYERS IN ONE FILE
        ├── nba_players_20251202_143530.json
        └── individual_player_files...
```

---

## 🚀 Features

### Parallel Processing
- **3 players at once** (configurable)
- **4 data collectors per player** (identity, stats, social, risk)
- **Smart batching** for API efficiency

### Comprehensive Data Collection
- **150+ fields** per player
- **Multiple sources**: ESPN, Pro Football Reference, NBA.com, Basketball Reference, Wikipedia
- **Social media**: Real-time follower counts and engagement
- **Contracts**: Verified earnings and contract details
- **Performance**: Advanced stats and analytics

### Production Grade
- ✅ Error handling and retry logic
- ✅ Progress tracking and logging
- ✅ Data quality scoring
- ✅ Smart caching (reuses previous scrapes)
- ✅ Rate limiting (respects API limits)
- ✅ Parallel processing (faster collection)

---

## 📖 Documentation

- **Main Scrapers Guide**: `README_SCRAPERS.md` - Comprehensive separation documentation
- **NFL Collection**: `README_NFL_DATA_COLLECTION.md` - Full NFL guide
- **Quick Start**: `QUICK_START.md` - Get started in 2 minutes
- **This File**: `README.md` - Overview and quick reference

---

## 🔧 Advanced Usage

### Environment Variables
```bash
# Performance tuning
export MAX_CONCURRENT_PLAYERS=3           # Players processed in parallel (default: 3)
export MAX_CONCURRENT_DATA_COLLECTORS=4   # Data collectors per player (default: 4)
export REQUEST_DELAY=1.5                  # Seconds between requests (default: 1.5)

# Feature flags
export USE_LLM_PARSING=true              # Use OpenAI for parsing (default: true if key set)

# Mode selection
export SCRAPE_MODE=all                   # player, team, all, test, interactive
```

### Custom Configurations
```bash
# Collect specific team
python gravity/nfl_scraper.py team "Kansas City Chiefs"
python gravity/nba_scraper.py team "Los Angeles Lakers"

# Test with one player per team (faster)
python gravity/nfl_scraper.py test
python gravity/nba_scraper.py test
```

---

## 📈 Performance

### NFL Collection (~1,700 players)
- **Time**: 15-30 minutes
- **Parallel**: 3 players simultaneously
- **API Calls**: ~20,000 (with smart batching)

### NBA Collection (~450 players)
- **Time**: 10-20 minutes
- **Parallel**: 3 players simultaneously
- **API Calls**: ~5,000 (with smart batching)

---

## 🎓 Use Cases

### Sports Analytics
- Player comparison and rankings
- Contract value analysis
- Performance trend analysis
- Draft prospect evaluation

### Fantasy Sports
- Draft rankings with comprehensive stats
- Player valuation models
- Injury risk assessment
- Performance predictions

### Media & Marketing
- Social media influence analysis
- Brand partnership opportunities
- Engagement tracking
- Trend identification

### Data Science
- Machine learning datasets
- Predictive modeling
- Statistical analysis
- Research projects

---

## 🆘 Troubleshooting

### "Please set your Firecrawl API key"
```bash
export FIRECRAWL_API_KEY="fc-your-actual-key"
```

### Script stops or times out
- Built-in retry logic will handle most issues
- Check logs in `scrapes/NFL/` or `scrapes/NBA/`
- Resume by running the command again (caches previous data)

### Memory issues
```bash
export MAX_CONCURRENT_PLAYERS=1
python collect_all_nfl_players.py
```

---

## 📝 License & Credits

**Created**: December 2, 2025  
**Version**: 2.0 (Separated Scrapers)  
**Status**: Production Ready ✅

### Technologies Used
- **Firecrawl**: Web scraping and data extraction
- **OpenAI**: Enhanced LLM parsing (optional)
- **Python**: Data processing and orchestration
- **Parallel Processing**: ThreadPoolExecutor for speed

---

## 🎯 Summary

### For NFL Data:
```bash
python collect_all_nfl_players.py
```
→ Get `scrapes/NFL/{timestamp}/nfl_players_{timestamp}.csv` with ~1,700 players

### For NBA Data:
```bash
python collect_all_nba_players.py
```
→ Get `scrapes/NBA/{timestamp}/nba_players_{timestamp}.csv` with ~450 players

**That's it!** Each command gives you **ONE comprehensive CSV** with **ALL players** and **ALL data fields** ready for analysis.

