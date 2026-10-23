# WP6 — Second-source season validation notes

**Branch:** `cursor/scraper-fix-spec-5ec7`  
**Module:** `gravity_api/services/stat_validation.py`  
**Tests:** `gravity_api/tests/test_wp6_stat_validation.py`

## What landed

- `ValidationResult` with status `matched | mismatch | no_second_source | unvalidated`
- `validate_completed_season(line, *, second_source_stats=None, position=None, on=None)`
- Primary-stat tables per SCRAPER_FIX_SPEC §4.4 (basketball; football QB / skill / defense)
- Zero tolerance on counting stats; ±0.1 on decimal primaries (`sacks`, `tfl`)
- `fetch_second_source_stats`: **CFBD** for `cfb`, **Sports-Reference** (`fetch_sports_ref_stats`) for other leagues
- In-progress / future seasons → `unvalidated` (no second source required)

## CI strategy

Live CFBD / Sports-Reference fetches are not required in CI. Tests inject fixture second-source dicts whose values match the ESPN WP0 completed-season fixtures (same numbers our parser already extracts). Fetch routing is covered with mocks.

When a live second source is unavailable at runtime, status `no_second_source` is correct. A `mismatch` caused by our parser must be fixed in the parser — not accepted by loosening tolerances.

## WP0 athlete results (fixture second source)

| Athlete | League | Completed season tested | Status | Notes |
|---|---|---|---|---|
| LeBron James | nba | 2026 (`statistics_2026_2`) | **matched** | gp 60, pts 1256, reb 364, ast 432, min 1989 |
| Kevin Durant | nba | 2023 (`statistics_2023_2`, trade year) | **matched** | TOT line; gp 47, pts 1366 |
| Patrick Mahomes | nfl | 2025 | **matched** | QB package |
| Will Anderson Jr. | nfl | 2025 | **matched** | Defense package; sacks 12.0 |
| Arch Manning | cfb | 2025 | **matched** | QB package; CFBD path mocked in unit test |
| Colin Simmons | cfb | 2025 | **matched** | Defense; sacks 11 / tfl 11 |
| AJ Dybantsa | ncaab_mens | 2026 (BYU) | **matched** | College completed season |
| AJ Dybantsa | nba | — | **unvalidated** | Only 2026-27 in progress; core stats 404 in WP0 |
| Sarah Strong | ncaab_womens | 2026 | **matched** | gp=8 in ESPN fixture (short/partial season line — not a parser mismatch vs injected SR twin) |

## Documented mismatches

**None in CI.** Injected second-source dicts equal ESPN fixture parses for all completed seasons above.

### Watch items (not CI failures)

1. **Sarah Strong 2026 GP=8** — ESPN completed-season fixture reports only 8 games. If a live Sports-Reference page for the same season shows a full-season GP, investigate whether the fixture capture was mid-window or the athlete’s season was truncated; do **not** adjust our values toward SR without a parser root-cause.
2. **Sports-Reference historical seasons** — `fetch_sports_ref_stats` returns the latest HTML table row (typically current season). Validating a past `season_year` against a live SR page may yield `mismatch` or stale-year data; prefer season-scoped SR HTML or injected dicts until a year-aware SR parser lands (out of WP6 scope).
3. **CFBD quota** — when `cfbd_is_rate_limited()`, fetch returns `None` → `no_second_source` (acceptable under §4.4).

## Acceptance mapping

| Spec acceptance | Evidence |
|---|---|
| Fixture comparisons for 8 WP0 athletes → `matched` or documented mismatch | Parametrized test + this notes file |
| Parser bugs causing mismatch fixed, not accepted | No parser patches required; injected twins equal ESPN parse |
| In-progress OK without second source | `test_dybantsa_nba_in_progress_is_unvalidated` |
