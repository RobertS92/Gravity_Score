# Output Folder Structure

All scraper outputs are now organized into **date-based folders** for easy tracking and management.

## 📁 Directory Structure

```
Gravity_Score/
│
├── scrapes/                          # Main scraper outputs
│   ├── NFL/
│   │   └── {YYYYMMDD_HHMMSS}/       # Each run gets its own timestamped folder
│   │       ├── nfl_players_*.json
│   │       └── nfl_players_*.csv
│   │
│   ├── NBA/
│   │   └── {YYYYMMDD_HHMMSS}/
│   │       ├── nba_players_*.json
│   │       └── nba_players_*.csv
│   │
│   ├── CFB/
│   │   └── {YYYYMMDD_HHMMSS}/
│   │       ├── cfb_all_players_*.json
│   │       └── cfb_all_players_*.csv
│   │
│   ├── NCAAB_Mens/
│   │   └── {YYYYMMDD_HHMMSS}/
│   │       ├── ncaab_mens_all_players_*.json
│   │       └── ncaab_mens_all_players_*.csv
│   │
│   ├── NCAAB_Womens/
│   │   └── {YYYYMMDD_HHMMSS}/
│   │       ├── ncaab_womens_all_players_*.json
│   │       └── ncaab_womens_all_players_*.csv
│   │
│   └── WNBA/
│       └── {YYYYMMDD_HHMMSS}/
│           ├── wnba_players_*.json
│           └── wnba_players_*.csv
│
└── test_results/                     # Test scraper outputs (2 per team)
    ├── NFL/
    │   └── {YYYYMMDD_HHMMSS}/
    │       ├── nfl_test_2per_team_*.csv
    │       └── nfl_validation_report_*.txt
    │
    ├── NBA/
    │   └── {YYYYMMDD_HHMMSS}/
    │       ├── nba_test_2per_team_*.csv
    │       └── nba_validation_report_*.txt
    │
    └── CFB/
        └── {YYYYMMDD_HHMMSS}/
            ├── cfb_test_2per_team_*.csv
            └── cfb_validation_report_*.txt
```

## 🎯 Benefits

### 1. Easy to Find Latest Results
Folders are sorted chronologically - the most recent folder is always at the top when sorted by name.

```bash
# View most recent NFL scrape
ls -t scrapes/NFL/ | head -n 1
# Output: 20251210_153042

# View most recent NBA test
ls -t test_results/NBA/ | head -n 1
# Output: 20251210_160523
```

### 2. Historical Tracking
Keep track of all your scraping runs without overwriting previous data.

```bash
# Compare data quality over time
scrapes/NFL/20251208_100000/  # First attempt - 65% complete
scrapes/NFL/20251209_140000/  # After fixes - 78% complete
scrapes/NFL/20251210_153000/  # Latest run - 85% complete ✅
```

### 3. Organized by Sport
Separate folders for each sport make it easy to focus on one league at a time.

### 4. Test vs Production Separation
Test results (2 per team) are in `test_results/`, full scrapes are in `scrapes/`.

## 🚀 Quick Access

### Using the Helper Script

The included `view_latest_results.sh` script makes it easy to view your most recent results:

```bash
# Interactive mode (recommended for beginners)
./view_latest_results.sh

# Direct access
./view_latest_results.sh nfl scrapes      # Latest NFL full scrape
./view_latest_results.sh nba test         # Latest NBA test results
./view_latest_results.sh cfb scrapes      # Latest CFB full scrape
```

The script shows:
- Directory path and creation time
- File list with sizes and row counts
- CSV preview (first 5 rows)
- Validation report summary
- Quick open commands

### Manual Access

```bash
# View latest NFL scrape
cd scrapes/NFL
ls -t | head -n 1                    # Get latest folder name
cd $(ls -t | head -n 1)              # Navigate to it
open *.csv                           # Open CSV (macOS)

# View latest NBA test validation report
cd test_results/NBA
cd $(ls -t | head -n 1)
cat *validation*.txt
```

## 📊 Timestamp Format

All timestamps follow the format: `YYYYMMDD_HHMMSS`

Examples:
- `20251210_153042` = December 10, 2025 at 3:30:42 PM
- `20251209_091530` = December 9, 2025 at 9:15:30 AM

This format ensures:
- ✅ Chronological sorting works correctly (lexicographic = chronological)
- ✅ No timezone confusion (always local time)
- ✅ Easy to read and understand
- ✅ Compatible with all filesystems

## 🔄 Workflow Examples

### Example 1: Daily Data Collection

```bash
# Monday morning - scrape NFL
python gravity/nfl_scraper.py all
# Output: scrapes/NFL/20251209_090000/

# Monday afternoon - after fixing bugs
python gravity/nfl_scraper.py all
# Output: scrapes/NFL/20251209_150000/

# Compare results
./view_latest_results.sh nfl scrapes
```

### Example 2: Testing Before Full Scrape

```bash
# Step 1: Test with 2 per team
python test_nfl_2_per_team.py
# Output: test_results/NFL/20251210_100000/

# Step 2: Review validation report
./view_latest_results.sh nfl test

# Step 3: If good, run full scrape
python gravity/nfl_scraper.py all
# Output: scrapes/NFL/20251210_110000/
```

### Example 3: Multi-Sport Collection

```bash
# Collect all sports
python gravity/nfl_scraper.py all      # scrapes/NFL/20251210_080000/
python gravity/nba_scraper.py all      # scrapes/NBA/20251210_100000/
python gravity/cfb_scraper.py all      # scrapes/CFB/20251210_120000/
python gravity/wnba_scraper.py all     # scrapes/WNBA/20251210_140000/

# Each in its own timestamped folder!
```

## 🧹 Cleanup (Optional)

If you want to clean up old results:

```bash
# Delete all but the 3 most recent NFL scrapes
cd scrapes/NFL
ls -t | tail -n +4 | xargs rm -rf

# Delete all test results older than 7 days
find test_results/ -type d -mtime +7 -exec rm -rf {} \;
```

## 📋 Updated Scraper Commands

All scrapers now automatically create date-based folders:

### Main Scrapers

```bash
# NFL
python gravity/nfl_scraper.py all              # scrapes/NFL/{timestamp}/
python gravity/nfl_scraper.py team "Chiefs"    # scrapes/NFL/{timestamp}/
python gravity/nfl_scraper.py player "Patrick Mahomes" "Chiefs" "QB"

# NBA
python gravity/nba_scraper.py all              # scrapes/NBA/{timestamp}/
python gravity/nba_scraper.py team "Lakers"    # scrapes/NBA/{timestamp}/

# CFB
python gravity/cfb_scraper.py all              # scrapes/CFB/{timestamp}/
python gravity/cfb_scraper.py team "Georgia"   # scrapes/CFB/{timestamp}/

# NCAAB
python gravity/ncaab_scraper.py mens all       # scrapes/NCAAB_Mens/{timestamp}/
python gravity/ncaab_scraper.py womens all     # scrapes/NCAAB_Womens/{timestamp}/

# WNBA
python gravity/wnba_scraper.py all             # scrapes/WNBA/{timestamp}/
```

### Test Scrapers

```bash
# NFL Test (64 players - 2 per team)
python test_nfl_2_per_team.py
# Output: test_results/NFL/{timestamp}/
#   ├── nfl_test_2per_team_{timestamp}.csv
#   └── nfl_validation_report_{timestamp}.txt

# NBA Test (60 players - 2 per team)
python test_nba_2_per_team.py
# Output: test_results/NBA/{timestamp}/
#   ├── nba_test_2per_team_{timestamp}.csv
#   └── nba_validation_report_{timestamp}.txt

# CFB Test (60 players - 2 per team)
python test_cfb_2_per_team.py
# Output: test_results/CFB/{timestamp}/
#   ├── cfb_test_2per_team_{timestamp}.csv
#   └── cfb_validation_report_{timestamp}.txt
```

## 💡 Pro Tips

### 1. Symlink to Latest

Create a symlink for easy access to the latest results:

```bash
# Create "latest" symlink pointing to most recent NFL scrape
cd scrapes/NFL
ln -sf $(ls -t | head -n 1) latest

# Now you can always access latest via:
cd scrapes/NFL/latest
```

### 2. Batch Processing

Process all recent scrapes with the pipeline:

```bash
# Find all NFL CSVs from today and score them
for csv in scrapes/NFL/$(date +%Y%m%d)_*/nfl_players_*.csv; do
    python run_pipeline.py "$csv" "${csv%.csv}_scored.csv"
done
```

### 3. Quick Comparison

Compare completeness across multiple runs:

```bash
# Show completion rates for last 5 NFL scrapes
cd scrapes/NFL
for dir in $(ls -t | head -n 5); do
    echo "$dir:"
    grep "Avg completeness" $dir/*validation*.txt 2>/dev/null || echo "  No validation report"
done
```

## 🎯 Summary

**Before:**
- Files scattered in root directory
- Hard to find latest results
- Risk of overwriting data
- No organization by sport

**After:**
- ✅ Organized by sport
- ✅ Date-based folders
- ✅ Easy to find latest
- ✅ Historical tracking
- ✅ Test vs production separation
- ✅ Helper script for quick access

**All your scraper outputs are now beautifully organized and easy to navigate!** 🚀

