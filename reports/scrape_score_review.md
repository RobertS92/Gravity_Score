# Scrape & Score Review — Gap-Fill Run

**Status:** Full gap-fill running in background (~6–8 hours for 500 athletes × 6 sports)  
**Log:** `/tmp/gap_fill_run.log`  
**Commits:** `fa59eac` (pipeline fixes), `92bebc1` (commercial viability scoring fix)

---

## What was done

1. **Committed** CFB stats/NIL pipeline fixes (GP mapping, SR fallback, ASS↔raw sync, ranked-athlete NIL priority, commercial viability 1–99 + dollar bands).
2. **Fixed scoring blocker** — commercial viability cohort percentile was crashing on JSON-string `raw_data`; rescore now succeeds.
3. **Smoke test** — CFB 3-athlete gap-fill: 3 scraped, 3 scored, 0 failures.
4. **Full gap-fill started** — all 6 acceptance sports, 500 athletes each, scrape + rescore.
5. **EDA reports generated** — baseline captured before run; interim report includes delta vs baseline.

---

## Reports to review

| File | Description |
|------|-------------|
| [`reports/scrape_score_eda_report_baseline.md`](scrape_score_eda_report_baseline.md) | Pre-run snapshot (2026-07-02) |
| [`reports/scrape_score_eda_report.md`](scrape_score_eda_report.md) | Latest metrics (updates when you re-run the generator) |
| [`reports/scrape_score_eda_report.json`](scrape_score_eda_report.json) | Machine-readable snapshot for dashboards |
| [`reports/scrape_score_eda_report_baseline.json`](scrape_score_eda_report_baseline.json) | Baseline JSON for diffing |

Re-generate after gap-fill completes:

```bash
export PYTHONPATH=.
export REPORT_NOTE="Post gap-fill final."
python3 scripts/generate_scrape_score_eda_report.py
```

---

## Baseline findings (before gap-fill)

### Data quality — CFB was broken on stats

| Metric | CFB | Basketball (control) |
|--------|-----|------------------------|
| GP coverage | **1.4%** | 91–99% stats≥3 |
| Stats ≥3 | **5.6%** | — |
| NIL observed | **0.2%** (11 athletes) | — |
| SR fallback sources | **0** | — |
| ASS≥3 not in raw | **204 athletes** | — |

Root causes addressed in code: ESPN `gp` not promoted, SR fallback not persisting, ASS→raw sync missing, On3 scraping random roster slots, imputed NIL treated as observed.

### Scoring — mostly fallback, not real models

| Sport | Avg score | % near 77 | % fallback model |
|-------|-----------|-----------|------------------|
| NFL, NBA, NCAAB M, WNBA | ~77.1 | 65–84% | **100%** |
| CFB | 61.5 | 0.6% | 68% fallback + 32% old v2 |
| NCAAB W | 48.1 | 7.7% | 92% old collapsed v2 |

Production `gravity-ml` returns **404** on `/score/athlete/cfb` → all pro sports use `composite_fallback_v0` (~77 flat). CFB has partial `gravity_athlete_v2` but needs redeploy with `gravity_athlete_cfb_value_v1` bundle.

---

## What to expect post gap-fill

| Signal | Target |
|--------|--------|
| CFB GP% | Should rise materially (GP finalize + SR fallback + ASS sync) |
| SR sources | >0 rows with `stats_source = sports_reference` |
| ASS→raw gap | `ass3_not_in_raw` should drop toward 0 |
| NIL observed | More On3 hits on ranked athletes (stars, nil_rank, social) |
| Commercial viability | College athletes get `commercial_viability_score` 1–99 + dollar P10/P50/P90 |
| Imputed NIL | No longer skips On3 scrape; not counted as training signal |

Scoring distribution will **still cluster near 77** for pro sports until `gravity-ml` is redeployed from current repo.

---

## Action items

1. **Wait for gap-fill** — monitor `tail -f /tmp/gap_fill_run.log`
2. **Re-run EDA report** when complete (command above)
3. **Redeploy gravity-ml on Railway** — enables sport routes + CFB value bundle (blocks real model scoring)
4. **Run training label ingest** after NIL observed count rises: `python3 -m gravity_api.jobs.ingest_training_labels`

---

## Scoring architecture (college commercial viability)

For CFB / NCAAB, each rescore now computes:

- **Commercial viability index** (0–100): social reach + recruiting + proof stats + observed NIL
- **Commercial viability score** (1–99): percentile vs sport cohort, capped at 99
- **NIL dollar bands** (P10/P50/P90): from observed On3 NIL when available, else estimated from index
- **nil_signal_source**: `observed` vs `estimated` — training labels only use `observed`

These persist on raw JSON and backfill `dollar_p10/p50/p90` on `athlete_gravity_scores` when ML omits them.
