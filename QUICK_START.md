# 🏈 Quick Start: Get All NFL Players Data

## ONE Command to Get Everything

```bash
python collect_all_nfl_players.py
```

## What You'll Get

**ONE CSV FILE** containing:
- ✅ **~1,700 NFL players** (all teams)
- ✅ **150+ data fields** per player
- ✅ **All data in ONE file** - ready for analysis

### Sample Data Fields (150+ total):

#### 🏃 Identity & Bio
`player_name`, `team`, `position`, `age`, `birth_date`, `college`, `hometown`, `height`, `weight`, `jersey_number`, `draft_year`, `draft_round`, `draft_pick`, `years_in_league`

#### 📊 Career Statistics
`career_stats_games`, `career_stats_touchdowns`, `career_stats_yards`, `career_stats_receptions`, `career_stats_sacks`, `career_stats_tackles`, `career_completions`, `career_interceptions`, `career_yards`

#### 📈 Current Season Stats
`current_season_games`, `current_season_pass_tds`, `current_season_pass_yards`, `current_season_rush_yards`, `current_season_receptions`, `current_season_sacks`, `current_season_tackles`

#### 📉 Last Season Stats  
`last_season_games`, `last_season_pass_tds`, `last_season_pass_yards`, `last_season_rec_yards`, `last_season_receptions`, `last_season_sacks`, `last_season_tackles`

#### 📱 Social Media
`instagram_handle`, `instagram_followers`, `instagram_engagement_rate`, `twitter_handle`, `twitter_followers`, `tiktok_handle`, `tiktok_followers`, `youtube_channel`, `youtube_subscribers`

#### 💰 Contract & Earnings
`contract_value`, `contract_status`, `career_earnings`, `guaranteed_money`, `endorsement_value`, `contract_negotiation_status`

#### 🏆 Awards & Achievements
`pro_bowls`, `all_pro_selections`, `super_bowl_wins`, `awards`, `playoff_appearances`, `passer_rating`, `qbr_rating`, `pff_grade`

#### 📰 Media & Brand
`brand_partnerships`, `endorsements`, `news_headline_count_7d`, `news_headline_count_30d`, `google_trends_score`, `wikipedia_page_views`, `media_buzz_surge`

#### ⚠️ Risk & Performance
`injury_risk_score`, `injury_history_count`, `current_injury_status`, `performance_trend`, `performance_volatility`, `age_risk`, `controversy_risk_score`

#### 📊 Year-by-Year Breakdown
Stats for each year of career stored in structured format

---

## Output Location

```
scrapes/NFL/{timestamp}/
├── nfl_players_{timestamp}.csv      ← ONE FILE WITH ALL PLAYERS
├── nfl_players_{timestamp}.json     ← JSON version
└── individual player files...        ← Detailed per-player files
```

## Example Output

```csv
player_name,team,position,age,college,height,weight,instagram_followers,contract_value,pro_bowls,...
Patrick Mahomes,Kansas City Chiefs,QB,29,Texas Tech,6'3",230,5420000,450000000,6,...
Josh Allen,Buffalo Bills,QB,28,Wyoming,6'5",237,2180000,258000000,4,...
Christian McCaffrey,San Francisco 49ers,RB,28,Stanford,5'11",205,4260000,64000000,4,...
...
```

---

## Prerequisites

**Required:**
```bash
export FIRECRAWL_API_KEY="fc-your-api-key"
```

**Optional (for better parsing):**
```bash
export OPENAI_API_KEY="sk-your-openai-key"
```

---

## Time Estimate

- **~15-30 minutes** for all 1,700 players
- Uses parallel processing (3 players at once)
- Progress updates in real-time

---

## That's It! 🎉

Run the command and come back in 20 minutes to find your complete NFL player database in ONE CSV file with ALL the data.

### Next Steps After Collection

1. **Open the CSV** in Excel, Google Sheets, or your favorite tool
2. **Filter/Sort** by any of the 150+ columns
3. **Analyze** - All players, all data, ready to use
4. **Import** into your database or application

---

**Questions?** See `README_NFL_DATA_COLLECTION.md` for full documentation.

