# Unified Scraper - NFL & NBA Player Data Collector

A unified command-line interface for collecting player data from both NFL and NBA.

## Features

- **Sport Selection**: Choose between NFL or NBA
- **Collection Modes**:
  1. **Individual Player**: Collect data for a single player
  2. **Team Roster**: Collect data for all players on a team
  3. **All Teams**: Collect data for all players from all teams
  4. **Test Mode**: Collect data for one well-known player from each team (great for testing!)

## Usage

### Interactive Mode (Recommended)

Simply run the script and follow the prompts:

```bash
python gravity/unified_scraper.py
```

You'll be prompted to:
1. Select sport (NFL or NBA)
2. Select collection mode
3. Enter player/team information as needed

### Command Line Mode

#### Single Player

**NFL:**
```bash
python gravity/unified_scraper.py nfl player "Patrick Mahomes" "Kansas City Chiefs" "QB"
```

**NBA:**
```bash
python gravity/unified_scraper.py nba player "LeBron James" "Los Angeles Lakers" "SF"
```

#### Team Roster

**NFL:**
```bash
python gravity/unified_scraper.py nfl team "KC"
# or
python gravity/unified_scraper.py nfl team "Kansas City Chiefs"
```

**NBA:**
```bash
python gravity/unified_scraper.py nba team "LAL"
# or
python gravity/unified_scraper.py nba team "Los Angeles Lakers"
```

#### All Teams

**NFL:**
```bash
python gravity/unified_scraper.py nfl all
```

**NBA:**
```bash
python gravity/unified_scraper.py nba all
```

#### Test Mode (One Player Per Team)

**NFL:**
```bash
python gravity/unified_scraper.py nfl test
```

**NBA:**
```bash
python gravity/unified_scraper.py nba test
```

## Environment Variables

You can also use environment variables for configuration:

```bash
export FIRECRAWL_API_KEY="fc-your-key-here"
export OPENAI_API_KEY="sk-your-key-here"  # Optional, for faster LLM parsing
export SPORT="nfl"  # or "nba"
export SCRAPE_MODE="test"  # player, team, all, test, or interactive
export PLAYER_NAME="Patrick Mahomes"
export PLAYER_TEAM="Kansas City Chiefs"
export PLAYER_POSITION="QB"
export TEAM_NAME="KC"
```

## Output

All collected data is saved to:
- `scrapes/YYYYMMDD_HHMMSS/` directory
- Individual JSON files per player: `{Player_Name}_{timestamp}.json`
- Individual CSV files per player: `{Player_Name}_{timestamp}.csv`
- Combined files for multiple players (if collecting team/all)

## Data Collected

### For Both Sports:
- **Identity**: Age, birth date, nationality, hometown, college, draft info, height, weight, etc.
- **Brand**: Social media handles, followers, engagement, news mentions, sentiment
- **Proximity**: Endorsements, brand partnerships, media appearances
- **Velocity**: Follower growth, performance trends, media buzz
- **Risk**: Injury history, controversies, contract status

### NFL-Specific Stats:
- Passing yards, touchdowns, completions, interceptions
- Rushing yards, receiving yards
- Sacks, tackles, interceptions (defensive)
- Pro Bowls, All-Pro selections, Super Bowl wins

### NBA-Specific Stats:
- Points, rebounds, assists per game
- Steals, blocks
- Field goal %, three-point %, free throw %
- All-Star selections, All-NBA selections, Championships
- Advanced stats: PER, Usage Rate, Win Shares

## Requirements

- Python 3.8+
- Firecrawl API key (required)
- OpenAI API key (optional, for faster LLM parsing)
- See `requirements.txt` for Python dependencies

## Examples

### Quick Test (Recommended First Run)

Test with one player per team to verify everything works:

```bash
python gravity/unified_scraper.py nfl test
```

This will collect data for one well-known player from each NFL team (32 players total).

### Collect Your Favorite Team

```bash
python gravity/unified_scraper.py nfl team "Kansas City Chiefs"
```

### Collect All NBA Players

```bash
python gravity/unified_scraper.py nba all
```

**Note**: This will take a long time! Consider using test mode first.

