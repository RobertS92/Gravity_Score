# SCRAPER FIX SPEC — season-correct, history-complete athlete stats

**Status:** Ready for implementation · **Owner:** Rob · **Written:** 2026-10-22
**Repo:** `Gravity_Score` (canonical scrapers = `gravity_api/scrapers/`)
**Companion:** `docs/specs/SCORING_ML_FIX_SPEC.md` (consumes everything this spec produces)

> **For agents:** Read §1–§3 fully before writing code. Work packages (§5) are ordered; do not start a WP until its predecessor's acceptance tests pass. Every bug in §3 cites file and line as of commit `10472a4` — re-verify line numbers before editing. When ESPN payload shape is uncertain, capture a real fixture first (WP0) and code against the fixture, never against assumptions.

---

## 1. Goal

For every athlete in `athletes`, store **every season they have a stat record for, through the current in-progress season**, as separate, correctly-labeled rows — one per *(season, season type, team)* — plus a derived career line. Data must be accurate (cross-checked against a second source for completed seasons) and must say how fresh it is.

Worked example: **LeBron James** in Oct 2026 → 23 completed NBA regular seasons (2003-04 → 2025-26; CLE, MIA, CLE, LAL) + 1 in-progress season (2026-27, PHI). **AJ Dybantsa** → 1 completed `ncaab_mens` season (BYU 2025-26) + 1 in-progress `nba` season (WAS 2026-27), college row marked inactive for the college roster.

Why: the Impact model (winning contribution) and Gravity's Velocity/accumulation features need per-season history. Today the pipeline stores blended, mislabeled numbers that silently corrupt both models.

## 2. Non-negotiable rules

1. **Never fabricate.** No invented `games_played`, no copying one season's stats into another season's row, no `stats_as_of` that is not a real timestamp. Missing is `NULL`, not `0` and not `1`.
2. **Career is derived, never scraped as truth.** Career totals = SUM of per-season rows. ESPN career totals are stored only as a cross-check.
3. **Rate stats are recomputed from counts** (PPG = PTS/GP, completion % = CMP/ATT, passer rating from components). Never average rates across seasons.
4. **Regular season and postseason are separate rows.** Never summed together.
5. **Season year has one convention** (§4.1) applied everywhere through one module.
6. **Completed seasons are written once** and only re-scraped via explicit `--refresh-season`. Only the current season is re-scraped on schedule.
7. **Stat identity includes its category.** A defensive sack and a times-sacked are different stats even though ESPN names both `sacks`.
8. **Every row carries provenance:** `source_key`, `source_url`, `stats_as_of` (timestamptz), `collected_at`.

## 3. Verified bugs (root causes)

| ID | Location | Bug | Observed symptom |
|---|---|---|---|
| B1 | `gravity_api/scrapers/clients/espn.py:319-321` `_get_season_stats_core` | Calls core-v2 `athletes/{id}/statistics` with **no season scope**, which returns an aggregate (career/multi-season) document. | Smoke CSV: LeBron `games_played_season=1623`, Mahomes `131` (career totals in a season field). |
| B2 | `gravity_api/scrapers/parsers/espn_stats.py:246-269` `build_stats_bundle` | `current = _merge_stat_dicts(stats_from_espn_payload(data), latest_history)` — `_merge_stat_dicts` (lines 11-22) is **first-non-empty-wins**, so aggregate payload values override the latest real season. | Season fields hold career/multi-season values. |
| B3 | `espn_stats.py:53-60` `_stats_from_category_block` + `stats_from_espn_payload` | All ESPN categories (passing, rushing, defensive, …) are flattened into one dict by stat name with first-wins. Same-named stats in different categories collide (`sacks`, `interceptions`, `YDS`, `TD`, `Avg`, `Long`). A `0` from an earlier category shadows the real value. | Will Anderson Jr. `sacks=0.0`; Colin Simmons `tfl=0.0` while Texas Athletics lists 29.5 career TFL across 2024–2025. |
| B4 | `gravity_api/scrapers/parsers/stat_normalizer.py:46-206` `_alias_table` | Ambiguous aliases map one ESPN label to several canonical keys (`Avg` → pass YPA / YPC / Y/R; `INT` → `pass_int` and `interceptions`; `sacks` → `pass_sacks` and `sacks`). `_build_reverse_lookup` (212-220) keeps whichever is inserted last. | Category-dependent stats silently mis-assigned. |
| B5 | `stat_normalizer.py:288-293` `merge_stat_layers` | `if gp is None and normalized_current: ... gp = 1` — **invents one game played.** | Fake GP values feed participation and impact features. |
| B6 | `gravity_api/services/sport_pipeline/season_stats.py:110-127` | Writes the latest **completed** season's stats into the `season_year = current_year` row ("scoring anchor"). | Every athlete's prior season is stored twice (e.g. 2025 data also labeled 2026); real in-progress season is never stored. |
| B7 | `season_stats.py:142-144` `_current_season_year` + `espn_stats.py:110-112` `_season_label_to_key` + `season_stats.py:132-139` `_parse_season_year` | Three different season-year conventions. `"2003-04"` → 2003 via regex, but ESPN core uses the **end** year (2004) for NBA/NCAAB. `_current_season_year()` returns 2026 in Oct 2026, but ESPN's NBA 2026-27 season is `2027`. Regex `20\d{2}` cannot parse pre-2000 seasons. | Seasons shifted by one year; duplicates; collisions between history and anchor rows. |
| B8 | `espn_stats.py:256-262` | `stats_as_of = data.get("season")` — a season label, not a timestamp; often `None`. | Smoke CSV `stats_as_of` empty for all 10 athletes. |
| B9 | `migrations/029_feature_engineering_tables.sql:34-47` `athlete_season_stats` | `UNIQUE (athlete_id, sport, season_year, stat_key)` — no `team_id`, no `season_type`. History keyed only by year (`espn_stats.py:149`). | Mid-season trades and transfers collapse into one row (first team wins); postseason can merge into regular season. |
| B10 | `gravity_api/scraper_smoke/athletes.py` | Fixture `team_hint` values are hard-coded and stale (e.g. LeBron "Lakers"; he signed with PHI for 2026-27). | Smoke "PASS" while identity is wrong; no departure detection is tested. |
| B11 | Two scraper codebases | `gravity_api/scrapers/` (last change 2026-10-21) and sibling repo `gravity-scrapers` (last change 2026-07-20) both implement ESPN collection. | Fixes may land in the code that is not deployed. |

**B11 resolution for this spec:** implement all changes in `Gravity_Score/gravity_api/scrapers/`. Before WP6, confirm which service the Railway cron hits (`RAILWAY_SCRAPER_URL` / `SCRAPERS_SERVICE_URL`). If production still calls `gravity-scrapers`, open a separate ticket to point it at `gravity_api` jobs and freeze the sibling repo. Do not port fixes into both.

## 4. Target design

### 4.1 Season calendar (single source of truth)

New module `gravity_api/scrapers/season_calendar.py`. Everything that touches a season year imports from here; delete `_current_season_year`, `_parse_season_year`, `_season_label_to_key`.

| League | `season_year` stored (= ESPN core `seasons/{year}`) | `season_label` | Example |
|---|---|---|---|
| `nba`, `wnba`*, `ncaab_mens`, `ncaab_womens` | year the season **ends** | `"2026-27"` | 2026-27 → `2027` |
| `nfl`, `cfb` | year the season **starts** | `"2026"` | 2026 season → `2026` |
| `ncaa_baseball`, `ncaa_volleyball` | calendar year played | `"2026"` | |

\*WNBA plays within one calendar year; `season_year` = that year. **Verify each league against a live ESPN core `seasons/{year}` call (WP0) and encode the result in a test**, do not trust this table blindly.

Functions (all pure, fully unit-tested):
```python
def current_season_year(league: str, on: date) -> int
def season_label(league: str, season_year: int) -> str
def parse_season_label(league: str, label: str) -> int        # "2003-04" -> 2004 for nba
def season_status(league: str, season_year: int, on: date) -> Literal["complete","in_progress","future"]
```
Season start/end dates come from ESPN core `seasons/{year}` (`startDate`, `endDate`) cached per league-year, not hard-coded months.

### 4.2 Data model (migration `038_athlete_season_stats_v2.sql`)

Keep the existing EAV shape of `athlete_season_stats` (one row per stat) because cohort code reads it, but make the grain correct:

```sql
ALTER TABLE athlete_season_stats
  ADD COLUMN IF NOT EXISTS season_label  TEXT,
  ADD COLUMN IF NOT EXISTS season_type   TEXT NOT NULL DEFAULT 'regular'
       CHECK (season_type IN ('regular','postseason')),
  ADD COLUMN IF NOT EXISTS team_id       TEXT NOT NULL DEFAULT 'TOT',
  ADD COLUMN IF NOT EXISTS team_name     TEXT,
  ADD COLUMN IF NOT EXISTS is_total      BOOLEAN NOT NULL DEFAULT TRUE,   -- TRUE on the per-season TOT row
  ADD COLUMN IF NOT EXISTS is_complete   BOOLEAN,
  ADD COLUMN IF NOT EXISTS stats_as_of   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS source_url    TEXT,
  ADD COLUMN IF NOT EXISTS validation_status TEXT
       CHECK (validation_status IN ('unvalidated','matched','mismatch','no_second_source'));

ALTER TABLE athlete_season_stats DROP CONSTRAINT IF EXISTS athlete_season_stats_athlete_id_sport_season_year_stat_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ass_grain
  ON athlete_season_stats (athlete_id, sport, season_year, season_type, team_id, stat_key);
```

Row rules:
- Every (athlete, season, season_type) has exactly **one `team_id='TOT'` row set** (`is_total=TRUE`). Single-team seasons: TOT = that team's numbers. Multi-team seasons: one row set per team (`is_total=FALSE`) **plus** TOT.
- Existing readers must add `AND team_id = 'TOT' AND season_type = 'regular'` to preserve one-row-per-season semantics: `services/sport_pipeline/cohort_context.py:67-130`, `services/sport_pipeline/raw_payload.py:~94`, `services/sport_pipeline/raw_stats_sync.py:77-110`, `jobs/rebuild_cohort_baselines.py:55,96`. Grep for `athlete_season_stats` and fix every reader; a test must fail if any reader query lacks the filter.
- `athlete_team_seasons` (migration 034) is populated from the same pass: one row per (athlete, season, team) with `games_played`, `games_started` (NULL if not observed — never inferred here; inference belongs in feature engineering with an `_observed` flag).

Derived view (migration 038):
```sql
CREATE OR REPLACE VIEW athlete_career_stats AS
SELECT athlete_id, sport, season_type, stat_key,
       SUM(stat_value) AS career_value,
       COUNT(DISTINCT season_year) AS seasons
FROM athlete_season_stats
WHERE team_id = 'TOT' AND stat_key = ANY (/* counting stats only, from stat_catalog */)
GROUP BY athlete_id, sport, season_type, stat_key;
```
Rate stats are computed from this view in Python (`stat_catalog.derive_rates(sport, totals)`), never stored as summed values. Add `is_counting: bool` to every key in `scrapers/parsers/stat_catalog.py`.

**Existing data is not repaired; it is rebuilt.** B6/B7 have corrupted existing rows. After WP6 passes, the backfill job (WP7) deletes and rebuilds `athlete_season_stats` per athlete inside a transaction.

### 4.3 Source strategy (ESPN, verified by fixtures in WP0)

| Need | Primary | Fallback / cross-check |
|---|---|---|
| Season list per athlete | core-v2 `…/athletes/{id}/statisticslog` (one entry per season with `$ref`s to season-scoped statistics; documented by third-party wrappers, **verify**) | site common/v3 `…/athletes/{id}/stats` (`categories[].statistics[]` rows with `season.year`) |
| Stats for one season + type | core-v2 `…/seasons/{y}/types/{t}/athletes/{id}/statistics` (t: 2=regular, 3=postseason) | common/v3 per-season row |
| Team for that season | core-v2 `…/seasons/{y}/athletes/{id}` (season-scoped athlete record carries that season's team) | v3 row team fields if present |
| Mid-season trade split | v3 per-team rows if present; else game logs `…/athletes/{id}/gamelog?season={y}` aggregated by team | Sports-Reference |
| College football second source | CFBD (`scrapers/clients/cfbd.py`, `CFBD_API_KEY`) | Sports-Reference CFB |
| Basketball / NFL second source | Sports-Reference family (`scrapers/parsers/sports_reference_stats.py`) — respect their published rate limit | — |

**Never** call un-scoped `athletes/{id}/statistics` for per-season data (B1). It may be used only to fetch ESPN's career line for the cross-check in §4.4.

### 4.4 Validation (accuracy gate)

For each **completed** season row: compare `games_played` + the sport's primary counting stats (table below) against the second source. **Zero tolerance** on counts (allow ±0.1 on decimal stats like sacks). Result → `validation_status`. A `mismatch` row is still stored but excluded from model training sets (the ML spec enforces this) and logged to `scraper_jobs`/`collection_errors` with both values.

| Sport | Primary stats checked |
|---|---|
| nba/wnba/ncaab | gp, pts, reb, ast, min |
| nfl/cfb QB | gp, pass_yards, pass_td, pass_int, pass_attempts |
| nfl/cfb RB/WR/TE | gp, rush_yards, rush_td, receptions, rec_yards |
| nfl/cfb defense | gp, tackles, sacks, tfl, interceptions |

Career cross-check: SUM(TOT regular rows) vs ESPN career line; mismatch → flag athlete, do not overwrite.

In-progress seasons: no second-source requirement, but `stats_as_of` must be within **48 h** during the season window (§4.1 `season_status == in_progress`); otherwise flag `stale`.

## 5. Work packages (in order)

### WP0 — Capture fixtures (no production code)
- Script `scripts/capture_espn_fixtures.py` saves raw JSON for: LeBron James (nba 1966), Kevin Durant (nba 3202), Patrick Mahomes (nfl 3139477), Will Anderson Jr. (nfl 4685724), Arch Manning (cfb 4870906), Colin Simmons (cfb 5079689), AJ Dybantsa (ncaab_mens 5142718 + his nba id), Sarah Strong (ncaab_womens 5239592). For each: `statisticslog`, 2 season-scoped `statistics` docs (one completed, one current), season-scoped athlete record, v3 `/stats`, and `seasons/{y}` for each league.
- Store under `gravity_api/tests/fixtures/espn/<league>/<espn_id>/…json`.
- Write `docs/specs/ESPN_PAYLOAD_NOTES.md`: the actual JSON paths for season year, season type, team id, category name, stat name/value. **WP2–WP4 must code against these notes.**
- Acceptance: fixtures committed; notes doc answers "where is team, season type, and category in each payload".

### WP1 — Season calendar
- Implement §4.1 module + tests: LeBron 2003-04 → 2004 ↔ "2003-04"; NBA on 2026-10-22 → current 2027; CFB on 2026-10-22 → 2026; NBA on 2026-07-15 → 2026 complete / 2027 future.
- Replace all three old helpers (B7). `grep -rn "_current_season_year\|_parse_season_year\|_season_label_to_key"` must return nothing.

### WP2 — Category-aware parsing (fixes B2, B3, B4)
- Rewrite `parsers/espn_stats.py` to return a list of `SeasonStatLine` (new dataclass in `scrapers/types.py`):
  ```python
  @dataclass(frozen=True)
  class SeasonStatLine:
      league: str; season_year: int; season_type: str   # 'regular'|'postseason'
      team_id: str; team_name: str | None; is_total: bool
      stats: dict[str, float]          # keys namespaced "category.stat", e.g. "defensive.sacks"
      source_key: str; source_url: str; stats_as_of: datetime
  ```
- Keep category namespace through parsing. `stat_normalizer` maps **`(category, stat)` pairs** to canonical keys, e.g. `("defensive","sacks") → "sacks"`, `("passing","sacks") → "pass_sacks"`, `("defensive","interceptions") → "interceptions"`, `("passing","interceptions") → "pass_int"`. Remove every alias that is ambiguous without category (`Avg`, `INT`, `TD`, `YDS`, `Long`, `Rating`); a unit test asserts no alias string maps to two canonical keys within one category scope.
- Value semantics: a stat absent from the payload is absent (not 0). A literal `0` is kept only when ESPN returns it in the stat's own category.
- Delete `_merge_stat_dicts` first-wins behavior across categories; within one category duplicates raise `ParseConflict` (logged), never silently pick one.
- Acceptance (fixture tests): Will Anderson Jr. completed season `sacks > 0` and equals the defensive category value; Colin Simmons every completed season `tfl >= sacks`; Mahomes completed season `pass_sacks` populated and `sacks` absent.

### WP3 — Season-scoped client (fixes B1, B8)
- `EspnClient.list_stat_seasons(athlete_id, league) -> list[(season_year, season_type, stats_ref)]` from `statisticslog`.
- `EspnClient.get_season_stat_lines(athlete_id, league, season_year, season_type) -> list[SeasonStatLine]` using season-scoped endpoints; resolves team per season; produces per-team + TOT lines for multi-team seasons.
- `stats_as_of` = HTTP `Date`/`Last-Modified` or fetch time for in-progress seasons; for completed seasons = season `endDate`. Never a season label.
- Remove `get_season_stats`' fallback that returns un-scoped aggregates as `season_stats`.
- Acceptance: LeBron fixture yields regular-season lines for all seasons in `statisticslog`; Durant 2022-23 yields BKN + PHX + TOT; no line has `stats_as_of IS NULL`.

### WP4 — Remove fabrication (fixes B5, B6)
- Delete `gp = 1` block (`stat_normalizer.py:288-293`). If GP is unknown, it is NULL.
- Delete the "scoring anchor" (`season_stats.py:110-127`). The current-season row is written only from current-season data. Scoring code that needs "latest completed season" queries for it explicitly (`WHERE is_complete`), it does not get a relabeled copy.
- Acceptance: test feeds an athlete with only 2025 data on 2026-10-22 (CFB) → exactly one 2025 row set, zero 2026 rows.

### WP5 — Migration 038 + writer
- Apply §4.2 migration. Rewrite `upsert_season_stats_from_raw` → `upsert_season_stat_lines(conn, athlete_id, lines: list[SeasonStatLine])`, one transaction per athlete, also upserting `athlete_team_seasons`.
- Fix every reader query (list in §4.2). Add test `test_ass_readers_filter_grain.py` that greps SQL strings in the repo for `athlete_season_stats` and fails if `team_id` filter is missing.
- Acceptance: migration applies cleanly on a copy of prod schema (`migrations/apply_all.sh`); cohort baseline job output unchanged in row count for single-team, regular-season data on a fixture DB.

### WP6 — Second-source validation (§4.4)
- `gravity_api/services/stat_validation.py`: `validate_completed_season(line) -> ValidationResult`. CFBD for cfb; Sports-Reference for others.
- Acceptance: fixture comparisons for the 8 WP0 athletes produce `matched` on all completed seasons, or a documented, investigated `mismatch` (with both values) in the PR description. A mismatch caused by our parser is a bug to fix, not a row to accept.

### WP7 — Backfill + scheduled refresh
- Rewrite `jobs/backfill_career_stats.py`: for each athlete with an ESPN id (active **and** inactive — history matters for departed players too), enumerate seasons, fetch, validate, rebuild rows in one transaction. Idempotent; resumable via a checkpoint table or `scraper_jobs` cursor; obeys existing ESPN/CFBD rate limits (`clients/cfbd.py` limits already exist).
- Completed seasons with `validation_status='matched'` are skipped on later runs unless `--refresh-season YEAR`.
- Nightly job refreshes only `season_status == in_progress` lines.
- Acceptance: after backfill on staging, LeBron has 24 regular-season TOT rows (2004…2027 by `season_year`), team sequence CLE→MIA→CLE→LAL→PHI, and `SUM(pts)` over the 23 completed seasons equals the second source exactly.

### WP8 — Identity, rosters, departures
- Nightly order: roster sync → `roster_hygiene` (`left_for_draft`, transfers) → stats. College athletes drafted into a pro league get `is_active=false` on the college record and a linked pro athlete record (crosswalk by ESPN ids; if ESPN uses different ids per league, store both in an id crosswalk table — the data-infra decision already calls for one).
- Replace stale `team_hint` checks in `scraper_smoke/athletes.py`: smoke asserts the scraped team **equals the live ESPN roster team**, and separately asserts expected lifecycle facts (e.g. Dybantsa: college `is_active=false`, pro record exists).

### WP9 — Smoke + export
- Smoke CSV/JSON columns: `season_year, season_label, season_type, team_id, is_total, is_complete, stats_as_of, validation_status, n_seasons, career_<key>`. Remove `games_played_season` from any career context.
- `stats_scope` must be one of `season|career` and match the row.

### WP10 — Games and box scores (needed by the Impact model; can run in parallel after WP1)
New tables (migration `039_games.sql`):
- `games(game_id PK, league, season_year, season_type, start_time, home_team_id, away_team_id, home_score, away_score, neutral_site, status, source_url, collected_at)`
- `game_player_box(game_id, athlete_id, espn_athlete_id, team_id, started BOOL NULL, minutes NUMERIC NULL, snaps INT NULL, stats JSONB, PRIMARY KEY (game_id, espn_athlete_id))`
- `cfb_plays(game_id, play_id, …, ppa NUMERIC, home_wp_before, home_wp_after)` and `cfb_play_players(play_id, athlete_id, role)` from CFBD `/plays`, `/play/stats`, `/metrics/wp`, `/ppa/players/season` (endpoints listed in CFBD's API catalog; verify request params and plan quota before bulk pulls).
- Basketball/NFL box scores from ESPN game summary for every completed game of each season in scope (start: NCAAB 2023-24 → current, CFB 2023 → current; pro leagues optional).
- Acceptance: for one full NCAAB season, every completed game has both teams' box rows; `SUM(player pts)` per team equals `games.home_score/away_score` for ≥ 99.5% of games (remaining discrepancies listed).

## 6. Definition of done
- [ ] All WP acceptance tests pass in CI (`pytest gravity_api/tests -q`).
- [ ] Smoke run on the 8 fixture athletes shows correct current teams, per-season rows, `stats_as_of` everywhere, zero fabricated values.
- [ ] `athlete_career_stats` view matches second source for completed seasons of fixture athletes.
- [ ] `docs/SCRAPERS_AND_GRAVITY_ML_SOURCE_OF_TRUTH.md` updated: canonical scraper location, season convention, table grain.

## 7. Do NOT
- Do not "fix" mismatches by adjusting values toward the second source; fix the parser.
- Do not add a substring/fuzzy alias match (removed for good reason; see comment at `stat_normalizer.py:229-237`).
- Do not infer `games_started` in the scraper layer.
- Do not use LLM gap-fill (`jobs/llm_gap_fill.py`) for any stat field. LLM-filled values may never enter `athlete_season_stats`.
- Do not change public score outputs in this spec; scoring changes are owned by `SCORING_ML_FIX_SPEC.md`.
