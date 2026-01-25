# Complete Testing Guide - All Recent Changes

## Overview

This guide helps you test all the fixes and improvements we've made:
1. **NFL Proof Data** - Awards, stats, career totals (Main fix)
2. **NBA/WNBA Contract Data** - Contract length and values
3. **Risk Data** - Injury history, controversies, suspensions
4. **Data Quality** - Hometown validation, draft data, age collection
5. **Recruiting Data** - College recruiting stats

---

## Quick Start (2 Minutes)

### Option 1: Quick Test Script
```bash
./quick_test.sh
```

This runs a fast validation that:
- ✅ Tests NFL proof data with Patrick Mahomes
- ✅ Checks CSV output exists and has correct columns
- ✅ Shows sample data from latest scrape

### Option 2: Comprehensive Test Suite
```bash
python3 test_all_changes.py
```

This runs a complete test suite that:
- ✅ Tests NFL proof data (awards, stats, career totals)
- ✅ Tests NBA contract data
- ✅ Analyzes data quality across all fields
- ✅ Validates specific bug fixes
- ✅ Provides detailed pass/fail report

**Expected runtime:** 5-10 minutes

---

## Manual Testing

### Test 1: NFL Proof Data (Main Fix)

**Test with star players who have lots of awards:**

```bash
# Patrick Mahomes (QB) - Should have 6+ Pro Bowls
python3 gravity/nfl_scraper.py player "Patrick Mahomes" "Chiefs" "QB"

# Christian McCaffrey (RB) - Should have 4+ Pro Bowls  
python3 gravity/nfl_scraper.py player "Christian McCaffrey" "49ers" "RB"

# Travis Kelce (TE) - Should have 9+ Pro Bowls
python3 gravity/nfl_scraper.py player "Travis Kelce" "Chiefs" "TE"
```

**What to look for in console output:**
```
📊 Proof Data: 6 Pro Bowls, 3 All-Pro, 8 awards, 219 TDs, 28424 yards
   Awards: 6 Pro Bowls, 3 All-Pro, 3 Super Bowls, 8 total awards
   Career Stats: 219 TDs, 28424 yards, 0 rec, 0 sacks
   Year-by-year: 8 seasons, 6 Pro Bowl years
```

**What to check in CSV:**
| Field | Expected Value (Mahomes) |
|-------|-------------------------|
| `pro_bowls` | 6 |
| `all_pro_selections` | 3 |
| `super_bowl_wins` | 3 |
| `awards` | "Pro Bowl; All-Pro 1st Team; Super Bowl LVII" |
| `career_touchdowns` | 219 |
| `career_yards` | 28424 |
| `career_completions` | 2105 |
| `pro_bowls_by_year` | `{"2019": true, "2020": true, ...}` |
| `career_stats_by_year` | `{"2024": {...}, "2023": {...}}` |

---

### Test 2: NBA Contract Data

**Test with high-paid players:**

```bash
# LeBron James - Should have 2-year contract ~$97M
python3 gravity/nba_scraper.py player "LeBron James" "Lakers" "SF"

# Stephen Curry - Should have multi-year contract $200M+
python3 gravity/nba_scraper.py player "Stephen Curry" "Warriors" "PG"
```

**What to look for in console output:**
```
💰 Contract: 2 years, $97,100,000
```

**What to check in CSV:**
| Field | Expected Value (LeBron) |
|-------|------------------------|
| `current_contract_length` | 2 |
| `contract_value` | 97100000 |

---

### Test 3: WNBA Contract Data

```bash
# A'ja Wilson - Should have contract data
python3 gravity/wnba_scraper.py player "A'ja Wilson" "Aces" "F"

# Breanna Stewart - Should have contract data
python3 gravity/wnba_scraper.py player "Breanna Stewart" "Liberty" "F"
```

**Note:** WNBA contracts are smaller (max ~$250K-$400K)

---

### Test 4: Risk Data Collection

```bash
# Test with a player who has had injuries
python3 gravity/nfl_scraper.py player "Aaron Rodgers" "Jets" "QB"
```

**What to look for in console output:**
```
📊 Risk: 3 injuries, 1 controversies, Injury=25.0, Reputation=95.0
```

**What to check in CSV:**
| Field | Expected |
|-------|----------|
| `injury_history` | `[{"type": "Achilles", "date": "2023", ...}]` |
| `current_injury_status` | "healthy" or specific injury |
| `games_missed_career` | > 0 |
| `controversies` | [] or list |
| `suspensions` | [] or list |
| `fines` | [] or list |

---

### Test 5: Data Quality Fixes

**Test hometown validation (no more "Tuesday" values):**
```bash
# Scrape multiple players and check hometowns
python3 gravity/nfl_scraper.py team "Chiefs"
```

Then check CSV for `hometown` column - should NOT contain:
- ❌ Days of week (Monday, Tuesday, etc.)
- ❌ Positions (QB, RB, WR)
- ❌ UI elements ("Big left arrow icon")
- ❌ Pure numbers ("2024")

**Test draft data (should be "Undrafted" not empty):**

Check CSV for `draft_year`, `draft_round`, `draft_pick` columns:
- ✅ Should say "Undrafted" for undrafted players
- ❌ Should NOT be empty/null

**Test years in league (should not all be 0):**

Check CSV for `years_in_league` column:
- ✅ Most players should have > 0
- ✅ Only rookies should have 0-1

---

## Interpreting Test Results

### ✅ Good Results

**Console output shows:**
- Pro Bowls, All-Pro counts logged
- Career touchdowns and yards logged
- Contract values logged ($XXX,XXX,XXX)
- Injury history and risk scores logged

**CSV shows:**
- 80%+ of known Pro Bowlers have `pro_bowls` > 0
- 90%+ of players have `career_stats` populated
- 100% of players have `age` and `years_in_league`
- Star players have `contract_value` > $50M
- Valid `hometown` values (no "Tuesday")

### ❌ Red Flags

**Console output shows:**
- No awards logged (all 0s)
- No contract values
- No career stats

**CSV shows:**
- All `pro_bowls` = 0 (even for Mahomes/Kelce)
- All `contract_value` empty
- `injury_history` = [] for everyone
- `hometown` contains "Tuesday", "quarterback", etc.

---

## Test Specific Features

### Year-by-Year Awards Tracking

Open CSV and check `pro_bowls_by_year` column:
```json
{"2019": true, "2020": true, "2021": true, "2022": true, "2023": true, "2024": true}
```

This shows which years the player made the Pro Bowl.

### Year-by-Year Stats

Check `career_stats_by_year` column:
```json
{
  "2024": {"rushing_yards": 1200, "rushing_touchdowns": 12, ...},
  "2023": {"rushing_yards": 1100, "rushing_touchdowns": 10, ...}
}
```

### Comprehensive Career Stats

Check individual stat columns:
- `career_touchdowns` - Total TDs (rushing + receiving + passing)
- `career_yards` - Total yards
- `career_receptions` - Total catches (RB/WR/TE)
- `career_completions` - Passing completions (QB)
- `career_sacks` - Total sacks (DL/LB)
- `career_interceptions` - INTs thrown (QB) or caught (DB)

---

## CSV Location

CSVs are saved to:
```
scrapes/NFL/YYYY-MM-DD/player_data_TIMESTAMP.csv
scrapes/NBA/YYYY-MM-DD/player_data_TIMESTAMP.csv
scrapes/WNBA/YYYY-MM-DD/player_data_TIMESTAMP.csv
```

**Find latest CSV:**
```bash
# NFL
find scrapes/NFL -name "*.csv" -type f | xargs ls -t | head -1

# NBA
find scrapes/NBA -name "*.csv" -type f | xargs ls -t | head -1

# WNBA
find scrapes/WNBA -name "*.csv" -type f | xargs ls -t | head -1
```

**Open CSV:**
```bash
# Mac
open path/to/file.csv

# Linux
xdg-open path/to/file.csv

# Or use Excel, Google Sheets, Numbers, etc.
```

---

## Automated Test Output Example

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                 AUTOMATED TEST SUITE - ALL RECENT CHANGES                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Testing:
  1. NFL Proof Data (awards, stats, career totals)
  2. NBA Contract Data
  3. Data Quality Metrics
  4. Specific Bug Fixes

════════════════════════════════════════════════════════════════════════════════
TEST 1: NFL Proof Data (Awards, Stats, Career Totals)
════════════════════════════════════════════════════════════════════════════════

Running: python3 gravity/nfl_scraper.py player Patrick Mahomes Chiefs QB
✅ PASS: NFL Scraper Execution
✅ PASS: NFL Proof Data Logging - Awards logged
✅ PASS: NFL Career Totals Logging - Career stats logged
✅ PASS: NFL CSV Creation - scrapes/NFL/2024-12-08/player_data_123456.csv
✅ PASS: NFL Pro Bowls - Mahomes: 6 Pro Bowls
✅ PASS: NFL All-Pro - Mahomes: 3 All-Pro
✅ PASS: NFL Awards List - 125 chars
✅ PASS: NFL Career TDs - Mahomes: 219 TDs
✅ PASS: NFL Career Yards - Mahomes: 28424 yards

════════════════════════════════════════════════════════════════════════════════
TEST SUMMARY
════════════════════════════════════════════════════════════════════════════════
Passed: 28
Failed: 0
Warnings: 2
════════════════════════════════════════════════════════════════════════════════
```

---

## Troubleshooting

### Issue: "No CSV found"
**Solution:** Run a scraper first to generate data
```bash
python3 gravity/nfl_scraper.py player "Patrick Mahomes" "Chiefs" "QB"
```

### Issue: "All fields empty/zero"
**Solution:** 
1. Check internet connection (ESPN API needs network access)
2. Check logs for errors
3. Verify environment setup

### Issue: "Test script fails"
**Solution:**
1. Make sure scripts are executable: `chmod +x *.sh *.py`
2. Check Python version: `python3 --version` (need 3.8+)
3. Install dependencies if missing

### Issue: "Timeout errors"
**Solution:**
1. Test scripts have 3-minute timeout per player
2. If network is slow, tests might timeout
3. Run manual tests instead of automated suite

---

## What Each Test Validates

### `test_all_changes.py` - Comprehensive Suite
- ✅ NFL proof data properly collected from ESPN
- ✅ Awards extracted and counted correctly
- ✅ Career totals calculated (TDs, yards, etc.)
- ✅ Year-by-year stats and awards tracked
- ✅ NBA contract data collected from Spotrac
- ✅ Contract length and value extracted
- ✅ Data quality across all fields
- ✅ Hometown validation working
- ✅ Draft data handling ("Undrafted")
- ✅ Years in league calculation
- ✅ Age collection with fallback

### `quick_test.sh` - Fast Validation
- ✅ Basic scraper execution
- ✅ CSV creation
- ✅ Key columns exist
- ✅ Sample data preview

---

## Success Criteria

**All tests pass if:**
1. Patrick Mahomes has 6+ Pro Bowls
2. Patrick Mahomes has 3+ All-Pro selections
3. Patrick Mahomes has 200+ career TDs
4. Patrick Mahomes has $450M contract
5. LeBron James has contract data
6. No invalid hometowns
7. Draft data properly marked
8. 80%+ field coverage

---

## Next Steps After Testing

If tests pass ✅:
- You're ready to scrape full rosters!
- All data will be properly collected

If tests fail ❌:
- Check logs for specific errors
- Verify API access (ESPN, Spotrac)
- Run individual player tests to isolate issues

---

## Full Roster Testing

Once individual tests pass, test with full teams:

```bash
# NFL full team (53 players)
python3 gravity/nfl_scraper.py team "Chiefs"

# NBA full team (15-17 players)
python3 gravity/nba_scraper.py team "Lakers"

# WNBA full team (12 players)
python3 gravity/wnba_scraper.py team "Aces"

# NFL all players (1700+ players) - BE CAREFUL!
python3 gravity/nfl_scraper.py all
```

**Expected times:**
- Single player: 30-60 seconds
- Team (NFL): 10-20 minutes
- Team (NBA): 5-10 minutes
- All NFL: 8-12 hours

---

## Contact / Issues

If tests fail unexpectedly:
1. Check logs in console output
2. Verify CSV file exists and is readable
3. Check network connectivity
4. Review TESTING_GUIDE.md for troubleshooting

**All tests should pass!** We've thoroughly fixed:
✅ Proof data collection
✅ Contract data collection  
✅ Risk data collection
✅ Data quality issues
✅ Validation logic

Happy testing! 🚀

