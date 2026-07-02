# Scrape & Score Review — Gap-Fill Run

**Status:** ✅ Complete (2026-07-02 10:13 UTC, ~7.6 hours)  
**Log:** `/tmp/gap_fill_run.log`  
**Checkpoint:** [`reports/gap_fill_checkpoint.json`](gap_fill_checkpoint.json)

---

## Run summary

| Sport | Athletes | Scraped | Scored | Failures |
|-------|----------|---------|--------|----------|
| cfb | 500 | 500 | 500 | 0 |
| ncaab_mens | 500 | 500 | 500 | 0 |
| ncaab_womens | 500 | 500 | 500 | 0 |
| nfl | 500 | 500 | 500 | 0 |
| nba | 500 | 500 | 500 | 0 |
| wnba | 199 | 199 | 199 | 0 |
| **Total** | **2,699** | **2,699** | **2,699** | **0** |

**Root cause of earlier crashes:** `nohup` from Cursor's short-lived shell tool exits when the parent session ends (~7s). Fixed with `scripts/run_gap_fill_durable.py` (serial sports + checkpoint file) launched in a persistent background shell.

---

## Post-run vs baseline

### CFB (primary target)

| Metric | Baseline | Post gap-fill | Δ |
|--------|----------|---------------|---|
| GP coverage | 1.4% | 1.5% | +0.1pp ⚠️ |
| Stats ≥3 | 5.6% | 5.9% | +0.2pp ⚠️ |
| NIL observed | 0.2% (11) | **1.6% (~108)** | **+1.5pp ✅** |
| SR sources | 0 | 0 | no change ❌ |
| Commercial viability | 0% | **7.4%** | +7.4pp ✅ |
| ASS≥3 not in raw | 204 | 457 | worsened ⚠️ |

**NIL wins:** On3 observed 8→39; `existing_raw` verified 69; QB NIL obs 0.6%→6.8%. Ranked-athlete prioritization is working for NIL.

**Stats still broken:** GP and stats≥3 barely moved population-wide because gap-fill only touched 500/6761 CFB athletes and ESPN GP mapping + SR fallback still aren't landing in raw JSON at scale. SR fallback remains at **0 sources** — Firecrawl may not be reaching parseable SR pages.

### College commercial viability ✅

| Sport | Comm. score coverage | Dollar P50 on scores |
|-------|---------------------|----------------------|
| cfb | 7.4% (500 rescored) | 70.3% |
| ncaab_mens | 48.0% | 100% |
| ncaab_womens | 59.0% | 61.9% |

Top CFB athletes now have CV 99 + observed NIL dollar bands (e.g. Mark Davis $12.1M observed, Joe Cruz $9.7M observed).

### Scoring — still mostly fallback

| Sport | Avg | % fallback | Notes |
|-------|-----|------------|-------|
| NFL, NBA, WNBA | ~77.1 | **100%** | `composite_fallback_v0` — ML 404 on sport routes |
| NCAAB M | 77.2 | 99.8% | fallback |
| CFB | 62.4 | 69.7% fallback + 30% v2 | some spread, not value model |
| NCAAB W | 47.7 | 7.6% fallback | old collapsed `gravity_athlete_v2` dominates |

Production `gravity-ml` still 404s `/score/athlete/cfb` → falls back to generic endpoint. **Redeploy gravity-ml** to unlock real model scoring.

---

## Reports

| File | Description |
|------|-------------|
| [`scrape_score_eda_report_baseline.md`](scrape_score_eda_report_baseline.md) | Pre-run baseline |
| [`scrape_score_eda_report.md`](scrape_score_eda_report.md) | **Final post-run EDA with delta table** |
| [`scrape_score_eda_report.json`](scrape_score_eda_report.json) | Machine-readable snapshot |
| [`gap_fill_checkpoint.json`](gap_fill_checkpoint.json) | Per-sport run results |

---

## Remaining action items

1. **Fix CFB GP/stats at source** — ESPN parser + SR fallback still not populating raw; investigate Firecrawl SR search pages and ASS→raw sync direction (gap grew 204→457).
2. **Redeploy gravity-ml on Railway** — sport routes + `gravity_athlete_cfb_value_v1` bundle.
3. **Run full CFB gap-fill** (limit 6761 or nightly cron) — 500-athlete batch only moved population metrics ~0.2pp on stats.
4. **Ingest training labels** — NIL observed now ~108 CFB athletes: `python3 -m gravity_api.jobs.ingest_training_labels`
5. **Re-run gap-fill durably:** `bash scripts/run_gap_fill_and_report.sh` (uses checkpoint; skips completed sports)

---

## Commits in this workstream

- `fa59eac` — CFB stats/NIL pipeline fixes + EDA tooling
- `92bebc1` — Commercial viability JSON-string fix
- `b1ec3d5` — Persist CV + dollar bands to raw
- `d0374f4` — Durable serial gap-fill runner with checkpointing
