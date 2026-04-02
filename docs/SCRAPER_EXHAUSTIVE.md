# Gravity Score — Exhaustive Scraper Documentation

This document is the single comprehensive reference for all scraping systems in Gravity Score: **player data scrapers** (NFL, NBA, CFB, NCAAB, WNBA) and **NIL connector scrapers** (college NIL data). It covers architecture, configuration, data flow, output, and operations.

---

## Table of Contents

1. [Scope: Two Scraper Families](#1-scope-two-scraper-families)
2. [Part I: Player Data Scrapers](#2-part-i-player-data-scrapers)
3. [Part II: NIL Connector Scrapers](#3-part-ii-nil-connector-scrapers)
4. [Output and Storage](#4-output-and-storage)
5. [Configuration Reference](#5-configuration-reference)
6. [File and Module Reference](#6-file-and-module-reference)
7. [Performance and Tuning](#7-performance-and-tuning)
8. [Troubleshooting and Operations](#8-troubleshooting-and-operations)
9. [Extending the Scrapers](#9-extending-the-scrapers)

---

## 1. Scope: Two Scraper Families

| Family | Purpose | Output | Docs |
|--------|--------|--------|------|
| **Player data scrapers** | Collect 150+ fields per pro/college athlete (identity, stats, social, contract, risk, brand, etc.) for Gravity Score pipeline | CSV/JSON per run in `scrapes/{sport}/{timestamp}/` | This doc (Part I) |
| **NIL connector scrapers** | Collect NIL (Name, Image, Likeness) data from 6+ sources for college athletes; consensus valuation and deals | PostgreSQL + normalized schema; optional raw payloads | This doc (Part II) + [SCRAPER_ARCHITECTURE.md](./SCRAPER_ARCHITECTURE.md) |

Both are “scrapers” in the sense of collecting external data; they differ in scope (one player vs one athlete), output (files vs DB), and orchestration (per-sport scripts vs connector orchestrator).

---

## 2. Part I: Player Data Scrapers

### 2.1 Supported Sports and Entry Points

| Sport | Entry Script / Module | Roster Source | Approx. Players |
|-------|----------------------|---------------|------------------|
| **NFL** | `gravity/nfl_scraper.py`, `collect_all_nfl_players.py` (if present) | NFL.com / ESPN | ~1,700 |
| **NBA** | `gravity/nba_scraper.py`, `collect_all_nba_players.py` (if present) | NBA.com / ESPN | ~450 |
| **CFB** | `gravity/cfb_scraper.py` | College rosters | Varies |
| **NCAAB (M/W)** | `gravity/ncaab_scraper.py`, `gravity/wncaab_scraper.py` | College rosters | Varies |
| **WNBA** | `gravity/wnba_scraper.py` | WNBA/ESPN | ~150+ |

Unified CLI (legacy): `gravity/unified_scraper.py` can drive both NFL and NBA from one interface.

### 2.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MODE: all | team | player | test | interactive                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ROSTER RESOLUTION                                                           │
│  • all: get all teams → get roster per team (ESPN/NFL/NBA APIs or scrape)   │
│  • team: get roster for one team                                             │
│  • player: single player (name, team, position)                              │
│  • test: one player per team (smoke test)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PER-PLAYER COLLECTION (parallel: MAX_CONCURRENT_PLAYERS)                   │
│  For each player:                                                            │
│    1. Identity (ESPN/direct API first; no Firecrawl required)               │
│    2. Parallel data collectors (MAX_CONCURRENT_DATA_COLLECTORS):             │
│       • Brand (social, engagement, recognition)                              │
│       • Proof (stats, awards, performance)                                   │
│       • Proximity (contract, NIL, endorsements)                             │
│       • Velocity (trends, momentum, news)                                    │
│       • Risk (injury, controversy, age)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGGREGATION & OUTPUT                                                        │
│  • Flatten to single row per player                                          │
│  • Write CSV + JSON to scrapes/{sport}/{YYYYMMDD_HHMMSS}/                    │
│  • Optional: per-player JSON files, cache updates                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Core Components (Player Scrapers)

- **Config** (`gravity/scrape` or `scrape.py`): All env-driven settings (Firecrawl, OpenAI, concurrency, delays, timeouts, FAST_MODE, USE_LLM_PARSING, etc.).
- **FirecrawlScraper**: Wrapper around Firecrawl API for URL scraping; used by multiple collectors when a web page must be fetched and parsed.
- **NFLPlayerCollector / NBAPlayerCollector / etc.**: Sport-specific orchestrator. Responsibilities:
  - Resolve roster (teams → player list).
  - For each player: call Identity first, then run Brand, Proof, Proximity, Velocity, Risk in parallel via `ThreadPoolExecutor`.
  - Optionally reuse cached data from previous runs (`_find_previous_player_data`).
  - Assemble final player record and return for writing.
- **Sub-collectors** (live in `gravity/scrape` or shared):
  - **SocialMediaCollector**: Instagram, Twitter/X, TikTok, YouTube (handles, followers, engagement); uses Firecrawl and/or free APIs.
  - **StatsCollector**: Career and season stats (e.g. Pro Football Reference, ESPN, NBA sources).
  - **NewsAnalyzer**: News mentions, sentiment (optional LLM), headline counts.
  - **RiskAnalyzer**: Injury history, controversy signals, age-related risk.
  - **BusinessCollector**: Endorsements, contract-related data, brand deals; optional LLM for parsing.
  - **TrendsAnalyzer**: Momentum, trends (e.g. Google Trends via free APIs), social velocity.
  - **Free APIs**: Wikipedia, Google Trends, optional YouTube; no Firecrawl.
  - **PerplexityFallback**: Optional AI fallback when primary scraping fails or returns empty.
- **Identity**: Usually from ESPN or league API first (no Firecrawl) to get name, team, position, age, etc.; used to drive subsequent collectors.

### 2.4 Data Categories and Typical Fields (150+)

Conceptually each player record is built from:

| Category | Examples of Fields |
|----------|--------------------|
| **Identity** | player_name, team, position, age, college, draft_year, draft_round, height, weight, jersey_number, birth_date, photo_url |
| **Brand** | instagram_followers, twitter_followers, tiktok_followers, youtube_subscribers, engagement rates, verified flags, bio_text, wikipedia_views, news_mentions_30d |
| **Proof** | career stats (games, yards, TDs, etc.), current_season_stats, last_season_stats, year_by_year, pro_bowls, all_pro, championships, awards, PFF grades, QBR (sport-specific) |
| **Proximity** | contract_value, contract_status, cap_hit, guaranteed_money, endorsements, NIL valuation, deal counts, marketplace listing |
| **Velocity** | trend indicators, social growth, recent form, media momentum, news sentiment trend |
| **Risk** | injury_risk, injury_history, controversy_risk, age_risk, contract_security, composite_risk_score |

Exact field names and nesting depend on the sport and the flatten step used downstream (e.g. in `data_pipeline` or run scripts). The scraper output is typically a mix of nested objects and flat keys that get flattened later.

### 2.5 Commands and Modes (NFL / NBA Examples)

```bash
# Required
export FIRECRAWL_API_KEY="fc-your-key"

# Optional
export OPENAI_API_KEY="sk-..."           # LLM parsing
export PERPLEXITY_API_KEY="..."         # AI fallback
export MAX_CONCURRENT_PLAYERS=25        # parallel players
export MAX_CONCURRENT_DATA_COLLECTORS=15
export REQUEST_DELAY=0.1
export USE_LLM_PARSING=true
```

**NFL:**

```bash
python gravity/nfl_scraper.py all                    # All teams, full roster
python gravity/nfl_scraper.py team "KC"              # Kansas City only
python gravity/nfl_scraper.py player "Patrick Mahomes" "Kansas City Chiefs" "QB"
python gravity/nfl_scraper.py test                   # One player per team
python gravity/nfl_scraper.py                        # Interactive menu
```

**NBA:**

```bash
python gravity/nba_scraper.py all
python gravity/nba_scraper.py team "LAL"
python gravity/nba_scraper.py player "LeBron James" "Los Angeles Lakers" "SF"
python gravity/nba_scraper.py test
python gravity/nba_scraper.py
```

**Unified (NFL + NBA):**

```bash
python gravity/unified_scraper.py all                # sport chosen interactively or by arg
python gravity/unified_scraper.py team "LAL"
# etc.
```

### 2.6 Caching and Reuse

- **Cache directory**: `Config.CACHE_DIR` (default `cache`). CACHE_TTL_HOURS (e.g. 24 or 48 in FAST_MODE) controls how long responses are reused.
- **Previous player data**: For a given player name, the collector can look under `scrapes/` for a recent JSON from a prior run and reuse it if quality and age thresholds are met (`_find_previous_player_data`), reducing redundant work.
- **Smart batching**: Firecrawl and API calls are batched and rate-limited via `REQUEST_DELAY` and concurrency limits to stay within provider limits.

### 2.7 Optional: Direct APIs and FAST_MODE

- **USE_DIRECT_APIS**: When true, ESPN (and sport-specific) direct APIs are used for identity and stats where possible, reducing Firecrawl usage and speeding runs.
- **FAST_MODE**: When `FAST_MODE=true`, defaults shift toward higher concurrency (e.g. 100 players, 30 data collectors), lower delays (e.g. 0.02s), shorter timeouts, and longer cache TTL. Use with care to avoid rate limits and API cost spikes.

---

## 3. Part II: NIL Connector Scrapers

The NIL system collects NIL valuations, rankings, deals, and related data from **6+ sources** for college athletes, runs them in parallel, and produces **consensus values** and normalized records stored in PostgreSQL.

### 3.1 Architecture Summary

- **ConnectorOrchestrator** (`gravity/nil/connector_orchestrator.py`): Runs all connectors in parallel (e.g. `ThreadPoolExecutor`), aggregates results, computes consensus (e.g. weighted average NIL valuation by source reliability), deduplicates deals, and optionally passes results to the normalization pipeline.
- **Connectors** (each implements `BaseNILConnector`):
  - **On3** (Tier 1, reliability 0.95): NIL valuations, rankings, deal announcements.
  - **Opendorse** (Tier 1, 0.90): Athlete profiles, marketplace, social metrics.
  - **INFLCR** (Tier 2, 0.85): Social analytics, engagement.
  - **Teamworks** (Tier 2, 0.80): Limited NIL deal mentions.
  - **247Sports** (Tier 3, 0.75): Recruiting, NIL news, transfer portal.
  - **Rivals** (Tier 3, 0.70): Recruiting, NIL coverage.
- **BaseNILConnector** (`gravity/nil/connectors/base.py`): Abstract class with `fetch_raw()`, `normalize()`, rate limiting, HTTP retries, and helpers (e.g. parse_currency_value, extract_ranking).
- **Normalization pipeline**: Entity resolution (athlete_id), extraction of valuations and deals into canonical schema, persistence to DB (e.g. NILValuation, NILDeal, raw_data, athlete_events).

### 3.2 Usage (NIL)

```python
from gravity.nil.connector_orchestrator import run_nil_collection

results = run_nil_collection(
    athlete_name="Shedeur Sanders",
    school="Colorado",
    sport="football"
)

# Consensus
valuation = results['aggregated']['consensus']['nil_valuation']
deals = results['aggregated']['nil_deals']
quality = results['summary']['data_quality_score']
```

### 3.3 Canonical Schema (NIL)

All connectors normalize to a common shape: `nil_valuation`, `nil_ranking`, `nil_deals` (list of brand/type/value/source), `social_metrics`, `recruiting_ranking`, `recruiting_stars`, `profile_url`, plus `_metadata` (source, reliability, fetched_at, athlete_name, school).

For full connector-by-connector detail, consensus math, DB tables, and extension instructions, see **[SCRAPER_ARCHITECTURE.md](./SCRAPER_ARCHITECTURE.md)** and **[SCRAPER_DATA_FLOW.md](./SCRAPER_DATA_FLOW.md)**.

---

## 4. Output and Storage

### 4.1 Player Scraper Output

- **Directory**: `scrapes/{sport}/{YYYYMMDD_HHMMSS}/` (e.g. `scrapes/NFL/20251210_153042/`).
- **Files**:
  - `{sport}_players_{timestamp}.csv` — main flat/wide CSV (one row per player, 150+ columns).
  - `{sport}_players_{timestamp}.json` — same data as JSON (often list of player objects).
  - Optional: per-player JSON files in the same folder or under subfolders, depending on implementation.
- **Test runs**: `test_results/{sport}/{timestamp}/` with test CSVs and validation reports (e.g. 2 players per team).

### 4.2 NIL Output

- **PostgreSQL**: Normalized tables (e.g. athletes, nil_valuations, nil_deals, raw_data, athlete_events). Schema and migrations under `gravity/db/`.
- **In-memory / return**: Orchestrator returns the aggregated dict (sources, consensus, summary, errors) for API or scripting use.

### 4.3 Other Output Locations

- **Gravity_Final_Scores**: Used by `OutputManager` for pipeline/scoring outputs (e.g. `Gravity_Final_Scores/NFL/NFL_Final_001.csv`), not raw scraper output.
- **Cache**: `Config.CACHE_DIR` for HTTP/scrape response cache.

---

## 5. Configuration Reference

### 5.1 Player Scrapers (Env Vars)

| Variable | Default | Description |
|----------|---------|-------------|
| **FIRECRAWL_API_KEY** | (required) | Firecrawl API key; required for player scrapers that use web scraping. |
| **OPENAI_API_KEY** | "" | OpenAI key for LLM parsing and sentiment; optional. |
| **PERPLEXITY_API_KEY** | "" | Perplexity key for AI fallback when data is missing. |
| **USE_LLM_PARSING** | "true" | Use LLM (OpenAI/Ollama) for parsing pages when needed. |
| **USE_LLM_SENTIMENT** | "true" | Use LLM for news sentiment. |
| **USE_LLM_PARSING_ROSTERS** | "false" | Use LLM for roster parsing; usually false for speed. |
| **MAX_CONCURRENT_PLAYERS** | 25 (100 if FAST_MODE) | Number of players collected in parallel. |
| **MAX_CONCURRENT_DATA_COLLECTORS** | 15 (30 if FAST_MODE) | Parallel collectors per player (Brand, Proof, etc.). |
| **REQUEST_DELAY** | 0.1 (0.02 if FAST_MODE) | Seconds between requests (rate limiting). |
| **PLAYER_TIMEOUT** | 300 (45 if FAST_MODE) | Seconds before a single player collection is abandoned. |
| **FIRECRAWL_TIMEOUT** | 60000 (30000 if FAST_MODE) | Firecrawl request timeout (ms). |
| **ROSTER_TIMEOUT** | 15000 (8000 if FAST_MODE) | Roster fetch timeout (ms). |
| **FAST_MODE** | "false" | When "true", uses faster defaults (more concurrency, lower delay, shorter TTL). |
| **USE_DIRECT_APIS** | "true" | Prefer direct ESPN/league APIs where available. |
| **SCRAPES_DIR** | "scrapes" | Base directory for scrape output. |
| **CACHE_DIR** | "cache" | Cache directory for responses. |
| **CACHE_TTL_HOURS** | 24 (48 if FAST_MODE) | Cache TTL in hours. |
| **MAX_NEWS_ARTICLES** | 25 (15 if FAST_MODE) | Cap on news articles per player. |
| **MAX_SOCIAL_POSTS** | 50 (30 if FAST_MODE) | Cap on social posts considered. |
| **INJURY_LOOKBACK_YEARS** | 3 (2 if FAST_MODE) | Years of injury history to consider. |
| **SKIP_OPERATIONS** | (see Config) | Comma-separated list of operations to skip (e.g. screenshot_capture). |
| **QUICK_MODE** | "false" | Skip non-essential ops; can be tied to FAST_MODE. |
| **USE_DATABASE** | "false" | Enable DB persistence (if implemented). |
| **DATABASE_PATH** | "nfl_players.db" | Path to SQLite DB when USE_DATABASE is true. |
| **YOUTUBE_API_KEY** | "" | Optional for YouTube stats in free collector. |

### 5.2 NIL Connectors

- **Rate limit**: Per-connector delay (e.g. 1.0s) and retry/backoff in base connector.
- **Orchestrator**: Max workers (e.g. 6), timeout per connector (e.g. 30s). No Firecrawl; connectors use their own HTTP and parsing.
- **DB**: PostgreSQL connection for normalization pipeline (see `gravity/db/` and NIL docs).

---

## 6. File and Module Reference

### 6.1 Player Scrapers

| Component | Path |
|-----------|------|
| Config, FirecrawlScraper, NFLPlayerCollector, SocialMediaCollector, StatsCollector, NewsAnalyzer, RiskAnalyzer, BusinessCollector, TrendsAnalyzer, collect_players_by_selection | `gravity/scrape` (or `gravity/scrape.py`) |
| NFL CLI and roster helpers | `gravity/nfl_scraper.py` |
| NBA collector and CLI | `gravity/nba_scraper.py` |
| NBA stats collector | `gravity/nba_stats_collector.py` |
| NBA data models | `gravity/nba_data_models.py` |
| Unified NFL+NBA CLI | `gravity/unified_scraper.py` |
| CFB collector | `gravity/cfb_scraper.py` |
| NCAAB (men’s) | `gravity/ncaab_scraper.py` |
| NCAAB (women’s) | `gravity/wncaab_scraper.py` |
| WNBA | `gravity/wnba_scraper.py` |
| Firecrawl SDK (social JSON) | `gravity/firecrawl_sdk.py` |
| Contract collector | `gravity/contract_collector.py` |
| Proximity collector | `gravity/proximity_collector.py` |
| News collector | `gravity/news_collector.py` |
| Endorsement collector | `gravity/endorsement_collector.py` |
| NIL deal collector (legacy) | `gravity/nil_collector.py` |
| Recruiting collector | `gravity/recruiting_collector.py` |
| Enhanced social collector | `gravity/enhanced_social_collector.py` |
| Free APIs (trends, Wikipedia, etc.) | `gravity/free_apis.py` |
| Perplexity fallback | `gravity/perplexity_fallback.py` |
| Output manager (Gravity_Final_Scores) | `gravity/output_manager.py` |

### 6.2 NIL Connector Scrapers

| Component | Path |
|-----------|------|
| Base connector | `gravity/nil/connectors/base.py` |
| On3 | `gravity/nil/connectors/on3_connector.py` |
| Opendorse | `gravity/nil/connectors/opendorse_connector.py` |
| INFLCR | `gravity/nil/connectors/inflcr_connector.py` |
| Teamworks | `gravity/nil/connectors/teamworks_connector.py` |
| 247Sports | `gravity/nil/connectors/sports247_connector.py` |
| Rivals | `gravity/nil/connectors/rivals_connector.py` |
| Orchestrator | `gravity/nil/connector_orchestrator.py` |
| Normalization | `gravity/nil/normalization.py` |
| Entity resolution | `gravity/nil/entity_resolution.py` |

### 6.3 Documentation Cross-References

| Doc | Content |
|-----|---------|
| [SCRAPER_ARCHITECTURE.md](./SCRAPER_ARCHITECTURE.md) | NIL connectors in depth: base class, each connector, orchestrator, normalization, DB, extending. |
| [SCRAPER_OVERVIEW.md](./SCRAPER_OVERVIEW.md) | NIL overview and quick start. |
| [SCRAPER_DATA_FLOW.md](./SCRAPER_DATA_FLOW.md) | NIL data flow and consensus. |
| [SCRAPER_QUICK_REFERENCE.md](./SCRAPER_QUICK_REFERENCE.md) | NIL cheat sheet and code snippets. |
| [OUTPUT_FOLDER_STRUCTURE.md](../OUTPUT_FOLDER_STRUCTURE.md) | Scrape and test output folder layout. |
| [README_SCRAPERS.md](../README_SCRAPERS.md) | High-level scraper separation (NFL vs NBA). |

---

## 7. Performance and Tuning

### 7.1 Player Scrapers

- **Throughput**: Dominated by `MAX_CONCURRENT_PLAYERS` and `MAX_CONCURRENT_DATA_COLLECTORS`. Higher values shorten wall-clock time but increase API usage and risk of rate limits.
- **Firecrawl**: Most variable cost; reduce calls by enabling `USE_DIRECT_APIS`, caching (CACHE_TTL_HOURS), and optional QUICK_MODE / SKIP_OPERATIONS.
- **LLM**: OPENAI_API_KEY and USE_LLM_PARSING increase quality and cost; disable for speed or cost savings where acceptable.
- **Typical runs**: NFL full league ~15–30 min (conservative settings) to ~1–3 hours (FAST_MODE); NBA ~10–20 min. Actual times depend on hardware, network, and API limits.

### 7.2 NIL

- **Parallelism**: 6 connectors by default; each has its own rate limit and retries.
- **Duration**: Full collection per athlete usually on the order of 5–10 seconds.

---

## 8. Troubleshooting and Operations

### 8.1 Player Scrapers

- **"Set FIRECRAWL_API_KEY"**: Export a valid Firecrawl key; without it, any collector that needs Firecrawl will fail.
- **Timeouts / hangs**: Increase `PLAYER_TIMEOUT` and `FIRECRAWL_TIMEOUT`; reduce `MAX_CONCURRENT_PLAYERS` to avoid overloading.
- **Rate limits (429)**: Increase `REQUEST_DELAY`, reduce `MAX_CONCURRENT_PLAYERS` and `MAX_CONCURRENT_DATA_COLLECTORS`.
- **Missing or thin data**: Enable `USE_LLM_PARSING` and/or `PERPLEXITY_API_KEY` for fallbacks; check logs for which collector failed.
- **Memory**: Lower concurrency (e.g. `MAX_CONCURRENT_PLAYERS=1`) if OOM on large runs.
- **Resume**: Re-run the same command; cached and previous-run data may be reused so progress is not lost.

### 8.2 NIL

- **No valuation / low quality**: Check `results['summary']['data_quality_score']` and `sources_successful`; ensure athlete name and school are correct; inspect `errors` in results.
- **Connector failures**: See SCRAPER_ARCHITECTURE for per-connector behavior and logging; enable DEBUG to see HTTP and parsing steps.

### 8.3 Logging

- **Player scrapers**: Python logging (e.g. INFO); set to DEBUG for per-request and per-collector detail.
- **NIL**: Same; orchestrator and connectors log success/failure and timing.

---

## 9. Extending the Scrapers

### 9.1 Adding a New Sport (Player Data)

1. **Roster**: Implement or reuse a roster fetcher (e.g. league or ESPN API) that returns list of `{name, team, position}`.
2. **Collector**: Create a `{Sport}PlayerCollector` that:
   - Uses `FirecrawlScraper` (or direct APIs) and any shared collectors (social, news, risk, etc.) where applicable.
   - Implements sport-specific Proof (stats) and optionally Identity if not from a shared API.
3. **CLI**: Add a `{sport}_scraper.py` that mirrors `nfl_scraper.py` / `nba_scraper.py` (modes: all, team, player, test, interactive) and calls the new collector.
4. **Output**: Reuse the same `scrapes/{sport}/{timestamp}/` pattern and CSV/JSON writing used for NFL/NBA.

### 9.2 Adding a New NIL Connector

1. **Class**: Subclass `BaseNILConnector`, implement `get_source_name()`, `get_source_reliability_weight()`, `fetch_raw()`, and `normalize()`.
2. **Register**: Add the connector instance to `ConnectorOrchestrator`’s connector dict.
3. **Schema**: Normalize to the canonical NIL schema (valuation, ranking, deals, social_metrics, etc.); see SCRAPER_ARCHITECTURE.

### 9.3 Adding a New Data Category (Player Scrapers)

1. **Collector**: Implement a collector that takes player identity (and any other context) and returns a dict of fields.
2. **Orchestrator**: In `NFLPlayerCollector.collect_player_data` (or equivalent), add a new parallel task (e.g. `future_new_category = executor.submit(self._collect_new_category, ...)`) and merge the result into the player record.
3. **Schema**: Ensure the new fields are included in the flattened output so the pipeline and Gravity Score calculator can consume them.

---

## Summary

- **Player scrapers**: Sport-specific entry points (NFL, NBA, CFB, NCAAB, WNBA) that resolve rosters, then run parallel per-player collection (Identity, Brand, Proof, Proximity, Velocity, Risk) using Firecrawl, direct APIs, and optional LLM/Perplexity. Output is CSV/JSON under `scrapes/{sport}/{timestamp}/`.
- **NIL scrapers**: Multi-source connectors (On3, Opendorse, INFLCR, Teamworks, 247, Rivals) run in parallel by `ConnectorOrchestrator`, aggregated and normalized into consensus valuations and deals, stored in PostgreSQL.
- **Config**: Driven by environment variables; FAST_MODE and USE_DIRECT_APIS significantly affect speed and cost for player scrapers.
- **Operations**: Cache and previous-run reuse reduce redundant work; concurrency and delays control rate limits and stability; logging and summary stats support troubleshooting.

For NIL-only depth, use **SCRAPER_ARCHITECTURE.md** and **SCRAPER_DATA_FLOW.md**; for high-level app and product context, use **APP_OVERVIEW.md** and **EXECUTIVE_TECH_BRIEF.md**.
