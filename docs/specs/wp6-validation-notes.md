# WP6 — Second-source season validation notes

**Branch:** `cursor/season-history-backfill-e76b` (PR #17)  
**Module:** `gravity_api/services/stat_validation.py`  
**Tests:** `gravity_api/tests/test_wp6_stat_validation.py`, `test_arch_manning_sr_zero_tolerance.py`

## What landed

- `ValidationResult` with status `matched | mismatch | no_second_source | unvalidated`
- `validate_completed_season(line, *, second_source_stats=None, position=None, on=None)`
- `validate_career_counting_stat` for SUM(season) vs second-source career
- `collection_errors_from_validation` / `log_validation_result` — mismatch logs both values
- Primary-stat tables per SCRAPER_FIX_SPEC §4.4 (basketball; football QB / skill / defense)
- Zero tolerance on counting stats; ±0.1 on decimal primaries (`sacks`, `tfl`)
- `fetch_second_source_stats`: **CFBD** for `cfb`, **Sports-Reference** (`fetch_sports_ref_stats`) for other leagues
- In-progress / future seasons → `unvalidated` (no second source required)
- Backfill (`backfill_season_stats`) fetches second source when available and logs mismatches

## CI strategy

Live CFBD / Sports-Reference fetches are not required in CI. Most WP0 athletes inject second-source dicts equal to the ESPN fixture parse (parser self-check). **Arch Manning** additionally locks a real Sports-Reference snapshot fixture and asserts **mismatch** + `collection_errors` (see below).

When a live second source is unavailable at runtime, status `no_second_source` is correct. A `mismatch` caused by our parser must be fixed in the parser — not accepted by loosening tolerances. A `mismatch` caused by incomplete ESPN capture vs a fuller second source is **documented and flagged**, not rewritten toward SR (§7 Do NOT).

## WP0 athlete results (fixture second source)

| Athlete | League | Completed season tested | Status | Notes |
|---|---|---|---|---|
| LeBron James | nba | 2026 (`statistics_2026_2`) | **matched** | gp 60, pts 1256, reb 364, ast 432, min 1989 |
| Kevin Durant | nba | 2023 (`statistics_2023_2`, trade year) | **matched** | TOT line; gp 47, pts 1366 |
| Patrick Mahomes | nfl | 2025 | **matched** | QB package |
| Will Anderson Jr. | nfl | 2025 | **matched** | Defense package; sacks 12.0 |
| Arch Manning | cfb | 2025 | **matched** (parser twin) / **mismatch** (locked SR) | Twin CI check uses ESPN 2942; SR fixture 3163 → mismatch + collection_errors |
| Colin Simmons | cfb | 2025 | **matched** | Defense; sacks 11 / tfl 11 |
| AJ Dybantsa | ncaab_mens | 2026 (BYU) | **matched** | College completed season |
| AJ Dybantsa | nba | — | **unvalidated** | Only 2026-27 in progress; core stats 404 in WP0 |
| Sarah Strong | ncaab_womens | 2026 | **matched** | gp=8 in ESPN fixture (short/partial season line — not a parser mismatch vs injected SR twin) |

## Documented mismatches

### Arch Manning — ESPN ~5206 vs SR ~4994 (zero tolerance)

**Fixture:** `gravity_api/tests/fixtures/sports_reference/cfb/arch_manning.json`  
**Tests:** `test_arch_manning_sr_zero_tolerance.py`

| Source | pass_yards | Notes |
|---|---|---|
| ESPN v3 season-sum (fixture) | **5206** | 2023:30 + 2024:939 + 2025:2942 + 2026:1295 |
| ESPN career aggregate (unscoped) | 5427 | Prior career-as-season hallucination — not used as truth |
| Sports-Reference locked snapshot | **4994** | Career through 30 GP (StatMuse/SR-aligned snapshot) |
| SR 2025 season (locked) | 3163 | vs ESPN WP0 `statistics_2025_2` **2942** |

**Root cause:** ESPN WP0/v3 **2025** line is incomplete vs full SR 2025 (2942/370 ATT/12 GP vs 3163/404 ATT/13 GP). Career cross-check therefore mismatches. Live SR later moved to career 5427 as more 2025/2026 games accrued — do **not** retarget ESPN values toward SR; store ESPN season rows, set `validation_status=mismatch`, append `collection_errors` with both values.

**collection_errors shape:**  
`validation_mismatch:Arch Manning:cfb:…:pass_yards:ours=5206.0:theirs=4994.0`

### Watch items (not CI failures)

1. **Sarah Strong 2026 GP=8** — ESPN completed-season fixture reports only 8 games. If a live Sports-Reference page for the same season shows a full-season GP, investigate whether the fixture capture was mid-window or the athlete’s season was truncated; do **not** adjust our values toward SR without a parser root-cause.
2. **Sports-Reference historical seasons** — `fetch_sports_ref_stats` returns the latest HTML table row (typically current season). Validating a past `season_year` against a live SR page may yield `mismatch` or stale-year data; prefer season-scoped SR HTML or injected dicts (Arch fixture is the pattern).
3. **CFBD quota** — when `cfbd_is_rate_limited()`, fetch returns `None` → `no_second_source` (acceptable under §4.4).

## Acceptance mapping

| Spec acceptance | Evidence |
|---|---|
| Fixture comparisons for 8 WP0 athletes → `matched` or documented mismatch | Parametrized test + Arch SR mismatch tests + this notes file |
| Parser bugs causing mismatch fixed, not accepted | Arch mismatch is incomplete ESPN capture vs SR, not a category-alias parser bug |
| In-progress OK without second source | `test_dybantsa_nba_in_progress_is_unvalidated` |
| Mismatch → collection_errors with both values | `collection_errors_from_validation` + Arch tests |
