# Scrape & Score Review — Gap-Fill Run

**Last updated:** 2026-07-02 23:40 UTC  
**Full CFB gap-fill:** Complete (user-confirmed; cohort **6761** active/scored in EDA). Durable log `/tmp/gap_fill_cfb_full.log` shows **6755** gap-fill IDs at start; `reports/gap_fill_checkpoint.json` is from the earlier multi-sport durable run (no separate CFB checkpoint row).

---

## Latest code changes (commit `2d613f8`)

| Area | Change |
|------|--------|
| **ESPN CFB** | Merge passing/rushing/receiving categories in `espn_stats.py` |
| **Sports Reference** | httpx search → player page → HTML table parse (no Firecrawl) |
| **HttpFetchClient** | Free HTTP fetch with per-athlete cache |
| **Firecrawl gating** | `DISABLE_FIRECRAWL=1`, optional `FIRECRAWL_ALLOW=suffix,...` |
| **On3 NIL** | Direct httpx to `on3.com/nil/{slug}/` first |
| **ASS→raw** | Full ASS merge when raw has &lt;3 stats; never downgrade GP |
| **Orchestrator** | `finalize_stat_fields` after ASS enrichment |
| **Scoring stack** | `FALLBACK_SCORER=heuristic_gravity_v1` (Tier 2) on ML miss |

**Tests:** 35 passed (stat_normalizer, raw_stats_sync, sports_reference_stats, commercial_viability, gap_fill_scrape)

---

## Post gap-fill rescore (skip-scrape)

```bash
export PYTHONPATH=.
export FALLBACK_SCORER=heuristic_gravity_v1
python3 -m gravity_api.jobs.nightly_pipeline --sport cfb --limit 6761 --skip-scrape
```

| Metric | Result |
|--------|--------|
| Stale cohort | 5709 (50 scored in prior smoke run) |
| Scored OK | **5704** |
| Scored fail | **5** (Postgres `statement timeout`) |
| Cohort baselines | 44 |
| Log | `/tmp/cfb_rescore.log` |

**Model mix (CFB, post-rescore):** `heuristic_gravity_v1` 5757, `composite_fallback_v0` 960, `heuristic_cfb` 42, `gravity_athlete_v2` 2 — fallback share **14.2%** (was ~69.7% composite-only pre-heuristic tier).

---

## Population metrics vs baseline (EDA `reports/scrape_score_eda_report.md`)

| Metric | Baseline | Current | Δ |
|--------|----------|---------|---|
| CFB GP% | 1.4% | **1.9%** | +0.5pp |
| CFB stats≥3 | 5.6% | **8.2%** | +2.5pp |
| CFB NIL observed | 0.2% | **3.7%** | +3.6pp |
| CFB commercial viability | 0% | **92.5%** | +92.5pp |
| CFB near-77 / fallback scoring | — | 0.7% / **14.2%** | heuristic tier dominant |
| SR sources (CFB) | 0 | 0 | — |
| ASS≥3 not in raw (CFB) | 204 | **1453** (of 1998 ASS≥3) | sync gap persists |

**Training labels ingested:** 264 NIL valuation (observed), 11 deal labels, 915 quality labels, 5 impact labels

---

## Artifacts refreshed

- `reports/scrape_score_eda_report.md` / `.json` — note: *Post CFB full gap-fill + heuristic rescore.*
- `reports/scrape_score_review.md` (this file)

---

## Still required (not code)

1. **Redeploy gravity-ml on Railway** — `/score/athlete/cfb` still **404**; generic `/score/athlete` succeeds but sport endpoint needed for production CFB ML.
2. **Verify CFBD_API_KEY** — `cfbd_api_stats_cfb` remains primary when ESPN sparse; SR httpx still **0** hits in EDA.
3. **Re-score 5 timeout athletes** — IDs in `/tmp/cfb_rescore.log` (`501bebf6`, `0959ad68`, `881f1a4a`, `549702d2`, `e9a87ef8` prefixes).

---

## Commits in this workstream

- `fa59eac` — CFB stats/NIL pipeline fixes + EDA tooling
- `92bebc1` — Commercial viability JSON-string fix
- `d0374f4` — Durable serial gap-fill runner
- `5845c3c` — Post gap-fill EDA results
- `2d613f8` — HTTP-first scraping, ESPN multi-category, SR HTML parse, Firecrawl gating
