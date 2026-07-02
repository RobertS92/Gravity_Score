# Scrape & Score EDA Report

**Generated:** 2026-07-02 15:01 UTC

> Post smoke test (100 CFB, HTTP-first, no Firecrawl).

## Executive summary

This report summarizes post–gap-fill data quality (stats, NIL, SR fallback) and scoring
distribution across acceptance sports. Key health signals:

- **GP / stats3** — season stat coverage in raw JSON
- **nil_observed** — verified NIL only (imputed excluded from training signal)
- **sr_source** — Sports Reference fallback hits
- **near_77 / fallback_model** — composite fallback scoring (production ML may need redeploy)
- **commercial_viability_score** — college 1–99 percentile commercial index

## Scrape coverage by sport

| Sport | Active | Scraped | GP% | Stats≥3 | NIL obs | SR | Comm. score |
|-------|--------|---------|-----|---------|---------|-----|-------------|
| cfb | 6761 | 6761 | 1.5% | 6.2% | 1.6% | 0 | 7.4% |
| nfl | 2924 | 2924 | 8.1% | 50.4% | 0.0% | 0 | 0.0% |
| nba | 535 | 535 | 1.9% | 99.6% | 0.4% | 0 | 0.0% |
| ncaab_mens | 1042 | 1042 | 0.7% | 91.8% | 0.5% | 0 | 48.0% |
| ncaab_womens | 847 | 847 | 0.9% | 96.1% | 0.6% | 0 | 59.0% |
| wnba | 199 | 199 | 4.5% | 97.5% | 0.0% | 0 | 0.0% |

## Scoring by sport

| Sport | Scored | Avg | Std | Min | Max | Near 77 | Fallback | $ P50 |
|-------|--------|-----|-----|-----|-----|---------|----------|-------|
| cfb | 6717 | 62.42 | 12.40 | 41.05 | 90.64 | 0.9% | 69.7% | 70.3% |
| nfl | 2888 | 77.13 | 0.69 | 41.91 | 81.26 | 65.5% | 100.0% | 100.0% |
| nba | 535 | 77.14 | 0.56 | 72.32 | 84.76 | 83.9% | 100.0% | 100.0% |
| ncaab_mens | 1042 | 77.23 | 1.67 | 41.37 | 85.32 | 0.1% | 99.8% | 100.0% |
| ncaab_womens | 847 | 47.71 | 8.46 | 39.51 | 77.38 | 7.3% | 7.6% | 61.9% |
| wnba | 199 | 77.12 | 0.34 | 74.89 | 80.56 | 82.4% | 100.0% | 100.0% |

### Model version mix

- **cfb:** `composite_fallback_v0` (4680), `gravity_athlete_v2` (1993), `heuristic_cfb` (44)
- **nfl:** `composite_fallback_v0` (2887), `heuristic_nfl` (1)
- **nba:** `composite_fallback_v0` (535)
- **ncaab_mens:** `composite_fallback_v0` (1040), `heuristic_ncaab_mens` (2)
- **ncaab_womens:** `gravity_athlete_v2` (742), `composite_fallback_v0` (64), `heuristic_ncaab_womens` (41)
- **wnba:** `composite_fallback_v0` (199)

## CFB deep dive

- **athlete_season_stats ≥3 but raw <3:** 453 (of 765 with ASS≥3)

### By position (n≥30)

| Pos | N | GP% | Stats≥3 | NIL obs |
|-----|---|-----|---------|---------|
| OL | 1087 | 0.0% | 1.3% | 1.3% |
| WR | 881 | 0.2% | 7.5% | 1.4% |
| LB | 785 | 0.5% | 8.5% | 1.0% |
| DB | 694 | 0.4% | 6.8% | 1.2% |
| DL | 681 | 0.3% | 6.9% | 1.6% |
| RB | 455 | 0.4% | 9.5% | 1.5% |
| TE | 439 | 0.5% | 6.6% | 1.4% |
| QB | 324 | 0.3% | 7.7% | 6.8% |
| S | 307 | 0.0% | 4.2% | 1.3% |
| CB | 250 | 0.8% | 6.0% | 2.0% |
| PK | 193 | 0.5% | 5.7% | 0.0% |
| DE | 172 | 0.6% | 7.0% | 4.1% |
| LS | 149 | 0.7% | 4.7% | 0.7% |
| DT | 138 | 0.0% | 10.1% | 2.2% |
| P | 114 | 0.0% | 6.1% | 0.9% |

### NIL sources (CFB)

- `(none)`: 6644 total, 3 observed
- `existing_raw`: 69 total, 69 observed
- `on3`: 39 total, 39 observed
- `synthesized`: 9 total, 0 observed

## College commercial viability sample

| Athlete | Sport | CV 1-99 | NIL P50 | Signal | Gravity | Model |
|---------|-------|---------|---------|--------|---------|-------|
| Maria Anais Rodriguez | ncaab_womens | 99 | $1,189,222 | estimated | 45.6 | `gravity_athlete_v2` |
| Evan Johnson | cfb | 99 | $2,353,335 | estimated | 79.5 | `composite_fallback_v0` |
| Joe Cruz | cfb | 99 | $9,724,000 | observed | 85.5 | `composite_fallback_v0` |
| Eidan Buchanan | cfb | 99 | $8,000,000 | observed | 85.7 | `composite_fallback_v0` |
| Jeremiah Wilkinson | ncaab_mens | 99 | $1,226,522 | estimated | 77.3 | `composite_fallback_v0` |
| Mark Mitchell | ncaab_mens | 99 | $1,226,522 | estimated | 77.3 | `composite_fallback_v0` |
| Jamonta Waller | cfb | 99 | $2,852,280 | estimated | 78.2 | `composite_fallback_v0` |
| Rex Van Wyhe | cfb | 99 | $2,815,117 | estimated | 78.0 | `composite_fallback_v0` |
| Sav'ell Smalls | cfb | 99 | $2,321,970 | estimated | 78.1 | `composite_fallback_v0` |
| Gideon Davidson | cfb | 99 | $9,504,000 | observed | 87.3 | `composite_fallback_v0` |
| Eliza Maupin | ncaab_womens | 99 | $1,189,222 | estimated | 45.7 | `gravity_athlete_v2` |
| Mark Davis | cfb | 99 | $12,122,000 | observed | 86.5 | `composite_fallback_v0` |
| Quinn Merritt | cfb | 99 | $2,514,599 | estimated | 79.2 | `composite_fallback_v0` |
| Joey Schlaffer | cfb | 99 | $2,406,958 | estimated | 44.7 | `heuristic_cfb` |
| Christopher Burgess Jr. | cfb | 99 | $8,712,000 | observed | 86.2 | `composite_fallback_v0` |

## Recommendations

- CFB GP coverage still low — verify ESPN parser and SR fallback on next scrape batch.
- Zero Sports Reference sources — check Firecrawl + direct SR search URLs.
- Majority fallback scoring — redeploy gravity-ml with sport routes + CFB value bundle.
- ASS→raw sync gap remains — confirm raw_stats_sync runs on orchestrator path.

## Delta vs baseline

| Sport | GP Δ | Stats≥3 Δ | NIL obs Δ | Comm. score Δ | Near 77 Δ |
|-------|------|-----------|-----------|---------------|-----------|
| cfb | +0.1pp | +0.6pp | +1.5pp | +7.4pp | +0.3pp |
| nfl | +6.9pp | +0.0pp | +0.0pp | +0.0pp | +0.6pp |
| nba | +0.2pp | +0.0pp | +0.0pp | +0.0pp | -0.2pp |
| ncaab_mens | +0.0pp | +0.0pp | +0.0pp | +48.0pp | +0.0pp |
| ncaab_womens | +0.0pp | +0.0pp | +0.0pp | +59.0pp | -0.4pp |
| wnba | +0.0pp | +0.0pp | +0.0pp | +0.0pp | +0.0pp |

---

_Report JSON snapshot: `reports/scrape_score_eda_report.json`_
