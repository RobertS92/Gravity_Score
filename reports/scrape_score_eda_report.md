# Scrape & Score EDA Report

**Generated:** 2026-07-02 02:29 UTC

> Interim report — full gap-fill in progress (500/sport).

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
| cfb | 6761 | 6761 | 1.4% | 5.7% | 0.2% | 0 | 0.0% |
| nfl | 2924 | 2924 | 1.3% | 50.4% | 0.0% | 0 | 0.0% |
| nba | 535 | 535 | 1.7% | 99.6% | 0.4% | 0 | 0.0% |
| ncaab_mens | 1042 | 1042 | 0.7% | 91.8% | 0.5% | 0 | 0.0% |
| ncaab_womens | 847 | 847 | 0.9% | 96.1% | 0.6% | 0 | 0.0% |
| wnba | 199 | 199 | 4.5% | 97.5% | 0.0% | 0 | 0.0% |

## Scoring by sport

| Sport | Scored | Avg | Std | Min | Max | Near 77 | Fallback | $ P50 |
|-------|--------|-----|-----|-----|-----|---------|----------|-------|
| cfb | 6717 | 61.45 | 11.87 | 43.08 | 90.64 | 0.6% | 68.0% | 68.0% |
| nfl | 2888 | 77.12 | 0.68 | 41.91 | 79.13 | 65.8% | 100.0% | 100.0% |
| nba | 535 | 77.15 | 0.52 | 74.62 | 84.76 | 84.1% | 100.0% | 100.0% |
| ncaab_mens | 1042 | 77.30 | 0.55 | 74.15 | 85.32 | 0.1% | 100.0% | 100.0% |
| ncaab_womens | 847 | 48.11 | 8.45 | 45.50 | 77.38 | 7.7% | 7.9% | 8.5% |
| wnba | 199 | 77.12 | 0.34 | 74.89 | 80.56 | 82.4% | 100.0% | 100.0% |

### Model version mix

- **cfb:** `composite_fallback_v0` (4565), `gravity_athlete_v2` (2150), `heuristic_cfb` (2)
- **nfl:** `composite_fallback_v0` (2887), `heuristic_nfl` (1)
- **nba:** `composite_fallback_v0` (535)
- **ncaab_mens:** `composite_fallback_v0` (1042)
- **ncaab_womens:** `gravity_athlete_v2` (780), `composite_fallback_v0` (67)
- **wnba:** `composite_fallback_v0` (199)

## CFB deep dive

- **athlete_season_stats ≥3 but raw <3:** 201 (of 477 with ASS≥3)

### By position (n≥30)

| Pos | N | GP% | Stats≥3 | NIL obs |
|-----|---|-----|---------|---------|
| OL | 1087 | 0.0% | 0.8% | 0.0% |
| WR | 881 | 0.1% | 7.0% | 0.2% |
| LB | 785 | 0.3% | 8.2% | 0.1% |
| DB | 694 | 0.3% | 6.5% | 0.1% |
| DL | 681 | 0.1% | 5.7% | 0.1% |
| RB | 455 | 0.4% | 8.6% | 0.0% |
| TE | 439 | 0.5% | 6.2% | 0.2% |
| QB | 324 | 0.3% | 6.8% | 1.2% |
| S | 307 | 0.0% | 4.2% | 0.0% |
| CB | 250 | 0.4% | 5.6% | 0.4% |
| PK | 193 | 0.5% | 5.7% | 0.0% |
| DE | 172 | 0.0% | 5.2% | 0.6% |
| LS | 149 | 0.7% | 4.7% | 0.7% |
| DT | 138 | 0.0% | 10.1% | 0.0% |
| P | 114 | 0.0% | 5.3% | 0.0% |

### NIL sources (CFB)

- `(none)`: 6717 total, 3 observed
- `synthesized`: 34 total, 0 observed
- `on3`: 8 total, 8 observed
- `existing_raw`: 2 total, 2 observed

## College commercial viability sample

_No commercial_viability_score fields yet — run gap-fill + college rescore._

## Recommendations

- CFB GP coverage still low — verify ESPN parser and SR fallback on next scrape batch.
- Zero Sports Reference sources — check Firecrawl + direct SR search URLs.
- Majority fallback scoring — redeploy gravity-ml with sport routes + CFB value bundle.
- NIL observed count low — gap-fill prioritization should target ranked athletes; confirm On3 scrapes.
- ASS→raw sync gap remains — confirm raw_stats_sync runs on orchestrator path.

## Delta vs baseline

| Sport | GP Δ | Stats≥3 Δ | NIL obs Δ | Comm. score Δ | Near 77 Δ |
|-------|------|-----------|-----------|---------------|-----------|
| cfb | +0.0pp | +0.0pp | +0.0pp | +0.0pp | +0.0pp |
| nfl | +0.0pp | +0.0pp | +0.0pp | +0.0pp | +0.8pp |
| nba | +0.0pp | +0.0pp | +0.0pp | +0.0pp | +0.0pp |
| ncaab_mens | +0.0pp | +0.0pp | +0.0pp | +0.0pp | +0.0pp |
| ncaab_womens | +0.0pp | +0.0pp | +0.0pp | +0.0pp | +0.0pp |
| wnba | +0.0pp | +0.0pp | +0.0pp | +0.0pp | +0.0pp |

---

_Report JSON snapshot: `reports/scrape_score_eda_report.json`_
