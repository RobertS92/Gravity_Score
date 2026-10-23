# ESPN payload notes (WP0)

**Captured:** 2026-10-23 via `scripts/capture_espn_fixtures.py`  
**Fixtures:** `gravity_api/tests/fixtures/espn/<league>/<espn_id>/`  
**Index:** `gravity_api/tests/fixtures/espn/INDEX.json`

WP2–WP4 must code against these paths. Do not invent fields.

---

## League path map

| Sport key | Core (`sports.core.api.espn.com/v2/sports/…`) | Site v3 (`site.web.api.espn.com/apis/common/v3/sports/…`) |
|-----------|-----------------------------------------------|-----------------------------------------------------------|
| `nba` | `basketball/leagues/nba` | `basketball/nba` |
| `nfl` | `football/leagues/nfl` | `football/nfl` |
| `cfb` | `football/leagues/college-football` | `football/college-football` |
| `ncaab_mens` | `basketball/leagues/mens-college-basketball` | `basketball/mens-college-basketball` |
| `ncaab_womens` | `basketball/leagues/womens-college-basketball` | `basketball/womens-college-basketball` |

---

## 1. `statisticslog` — season index

```
GET …/athletes/{id}/statisticslog
```

| Path | Meaning |
|------|---------|
| `entries[]` | One entry per ESPN season year the athlete has stats for |
| `entries[].season.$ref` | `…/seasons/{season_year}` — **year is in the URL path** |
| `entries[].statistics[]` | Blocks with `type` ∈ `{total, team}` |
| `entries[].statistics[].statistics.$ref` | Season-scoped stats URL containing `/seasons/{y}/types/{t}/…` |
| `entries[].statistics[].team.$ref` | Present on `type=team` blocks (mid-season / multi-team) |

**Season type:** not a top-level field on the log entry. Parse `/types/{t}/` from the stats `$ref`:
- `t=2` → `regular`
- `t=3` → `postseason`

**Verified counts:** LeBron 24 entries (2004→2027); Will Anderson 4; Colin Simmons 3; Dybantsa college 1; Dybantsa NBA log **404/empty** (no pack yet).

**Mid-season trades:** log may omit regular-season team splits (Durant 2023). Prefer v3 `/stats` for BKN/PHX/TOT discovery; follow core `$ref`s for counting stats.

---

## 2. Season-scoped statistics

```
GET …/seasons/{y}/types/{t}/athletes/{id}/statistics
GET …/seasons/{y}/types/{t}/athletes/{id}/statistics/0   # often required
```

| Path | Meaning |
|------|---------|
| `season.$ref` / nested year | ESPN season year |
| `seasonType` | Object with `type` / `id` (2 or 3) |
| `athlete.$ref` | Athlete |
| `splits.categories[]` | **Category blocks** — keep namespace |
| `splits.categories[].name` | Category id: `passing`, `rushing`, `receiving`, `defensive`, `defensiveInterceptions`, `general`, `offensive`, `scoring`, … |
| `splits.categories[].stats[]` | `{name, displayName, value, …}` |

**Category collisions (B3) — confirmed live:**

| Athlete | Category.stat | Value |
|---------|---------------|-------|
| Will Anderson 2026 | `defensive.sacks` | **7.5** |
| Will Anderson 2026 | `passing.sacks` | **0.0** (must NOT win) |
| Will Anderson 2026 | `defensive.tacklesForLoss` | **11.5** |
| Colin Simmons 2026 | `defensive.sacks` | **10.5** |
| Colin Simmons 2026 | `defensive.tacklesForLoss` | **15.5** |
| Colin Simmons 2026 | `defensive.stuffs` | **16.5** |
| Mahomes (passing) | `passing.sacks` | times-sacked → canonical `pass_sacks` |
| Mahomes | `defensive.sacks` | absent / 0 — QB has no defensive sacks |

Map with **(category, name)** pairs only. Never flatten by `name` alone.

**Absent vs zero:** if a stat is missing from its category's `stats[]`, leave it absent (`NULL`). Keep literal `0.0` only when ESPN returns it in that category.

---

## 3. Season-scoped athlete (team for that season)

```
GET …/seasons/{y}/athletes/{id}
```

Typed `…/types/2/athletes/{id}` → **404** (all leagues probed earlier). Use the untyped path.

| Path | Meaning |
|------|---------|
| `team.$ref` | `…/seasons/{y}/teams/{team_id}` — **team id is in the URL** |
| Resolve `$ref` | `abbreviation`, `displayName`, `id` |

**LeBron 2027:** `team.$ref` → `…/teams/20` (PHI).  
**Dybantsa NBA 2027:** athlete record **200** with team; stats pack still missing.

---

## 4. common/v3 `/stats` — cross-check + trade splits

```
GET https://site.web.api.espn.com/apis/common/v3/sports/{site}/athletes/{id}/stats
```

| Path | Meaning |
|------|---------|
| `categories[]` | e.g. Regular Season Averages / Totals / Misc |
| `categories[].statistics[]` | Per-season rows |
| `statistics[].season.year` | ESPN integer year (NBA 2022-23 → **2023**) |
| `statistics[].season.displayName` | Human label `"2022-23"` |
| `statistics[].teamId` | Team id string, or `null` for totals |
| `statistics[].teamSlug` | e.g. `brooklyn-nets` or `2022-23 Totals` |
| `teams` | Map for abbreviations / names |
| `filters` | Exposes `seasontype` 2 / 3 |

**Durant 2023 (verified):** three regular-season rows — `teamId=17` (BKN), `teamId=21` (PHX), `teamId=null` / slug `2022-23 Totals` → map to `team_id='TOT'`, `is_total=TRUE`.

Prefer **Totals** category for counting stats; averages are rates.

---

## 5. League `seasons/{year}` — calendar

```
GET …/seasons/{year}
```

| Path | Meaning |
|------|---------|
| `year` | ESPN season year |
| `displayName` | `"2026-27"` (NBA) or calendar label |
| `startDate` / `endDate` | ISO timestamps (season window) |
| `type` | Current/default type object with its own `startDate`/`endDate` |
| `types.$ref` | Enumeration of season types |

**NBA 2027 (verified):** `displayName=2026-27`, `startDate=2026-09-30T07:00Z`, `endDate=2027-06-26T06:59Z`. Use these for `season_status` and completed-season `stats_as_of` (= `endDate`), not hard-coded months alone.

---

## 6. Unscoped `athletes/{id}/statistics` — career only

Returns a multi-season / career aggregate (`splits.categories`). **Never** use as a per-season row (B1). Store only for career cross-check (§4.4).

LeBron unscoped `gamesPlayed` ≈ career total (smoke previously showed 1623 in a season field).

---

## 7. `stats_as_of` provenance

| Season status | Value |
|---------------|-------|
| `complete` | League `seasons/{y}.endDate` (or type endDate) |
| `in_progress` | HTTP `Date` / `Last-Modified` from the stats response, else fetch UTC time |

Never store a season label string in `stats_as_of` (B8). Capture meta in fixtures under `_capture.date` / `_capture.last-modified`.

---

## 8. Fixture inventory

| Athlete | Path |
|---------|------|
| LeBron James | `espn/nba/1966/` |
| Kevin Durant | `espn/nba/3202/` |
| Patrick Mahomes | `espn/nfl/3139477/` |
| Will Anderson Jr. | `espn/nfl/4685724/` |
| Arch Manning | `espn/cfb/4870906/` |
| Colin Simmons | `espn/cfb/5079689/` |
| AJ Dybantsa (college) | `espn/ncaab_mens/5142718/` |
| AJ Dybantsa (nba) | `espn/nba/5142718/` |
| Sarah Strong | `espn/ncaab_womens/5239592/` |

Each directory (when available): `statisticslog.json`, `v3_stats.json`, `athlete_season_{y}.json`, `statistics_{y}_2.json`, `seasons_{y}.json`, `statistics_career_unscoped.json`.
