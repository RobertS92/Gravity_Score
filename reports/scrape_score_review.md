# Scrape & Score Review — Gap-Fill Run

**Last updated:** 2026-07-02 15:05 UTC  
**Full CFB run:** In progress (`LIMIT=6761`, `DISABLE_FIRECRAWL=1`) — log `/tmp/gap_fill_cfb_full.log`

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

**Tests:** 35 passed (stat_normalizer, raw_stats_sync, sports_reference_stats, commercial_viability, gap_fill_scrape)

---

## Smoke test (100 CFB, no Firecrawl)

| Metric | Result |
|--------|--------|
| Scraped | 100/100 |
| Scored | 100/100 |
| Failures | 0 |
| Runtime | ~23 min |

---

## Population metrics vs baseline (after smoke + prior 500 batch)

| Metric | Baseline | Current | Δ |
|--------|----------|---------|---|
| CFB GP% | 1.4% | 1.5% | +0.1pp |
| CFB stats≥3 | 5.6% | 6.2% | +0.6pp |
| CFB NIL observed | 0.2% | 1.6% | +1.4pp |
| SR sources | 0 | 0 | — (needs full run + SR reachability) |
| ASS≥3 not in raw | 204 | 453 | still high until full sync |
| Commercial viability (CFB) | 0% | 7.4% | +7.4pp |

**Training labels ingested:** 123 NIL valuation (observed), 11 deal labels, 917 quality labels

---

## Full CFB gap-fill (running)

```bash
tail -f /tmp/gap_fill_cfb_full.log
```

When complete:

```bash
export PYTHONPATH=.
export REPORT_NOTE="Post CFB full gap-fill (6761, HTTP-first)."
python3 scripts/generate_scrape_score_eda_report.py
python3 -m gravity_api.jobs.ingest_training_labels
```

---

## Still required (not code)

1. **Redeploy gravity-ml on Railway** — `/score/athlete/cfb` still 404; 69.7% CFB scores use `composite_fallback_v0`
2. **Verify CFBD_API_KEY** — `cfbd_api_stats_cfb` is free stats path when ESPN sparse
3. **Monitor SR httpx** — if blocked, CFBD becomes primary CFB stats source

---

## Commits in this workstream

- `fa59eac` — CFB stats/NIL pipeline fixes + EDA tooling
- `92bebc1` — Commercial viability JSON-string fix
- `d0374f4` — Durable serial gap-fill runner
- `5845c3c` — Post gap-fill EDA results
- `2d613f8` — HTTP-first scraping, ESPN multi-category, SR HTML parse, Firecrawl gating
