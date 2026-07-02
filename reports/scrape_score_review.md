# Scrape & Score Review — Full All-Sports Gap-Fill

**Last updated:** 2026-07-02 15:56 UTC  
**Orchestrator:** Running (pid in `/tmp/gap_fill_orchestrator.pid`) — waiting for in-flight CFB jobs

---

## Pipeline status

| Phase | Status | Log |
|-------|--------|-----|
| **Pre-flight CFB gap-fill** | In progress (`LIMIT=6761`, old checkpoint) | `/tmp/gap_fill_cfb_full.log` |
| **Pre-flight CFB rescore** | In progress (`--skip-scrape`, heuristic) | `/tmp/cfb_rescore.log` |
| **Phase A — full gap-fill** | Queued (orchestrator waiting) | `/tmp/gap_fill_all_sports_full.log` |
| **Phase B — full rescore** | Pending | `/tmp/all_sports_rescore.log` |
| **Phase C — EDA + labels** | Pending | auto after Phase B |

**Checkpoint:** `reports/gap_fill_checkpoint_full_v2.json` (fresh; ignores prior 500-athlete batch)  
**Results:** `reports/gap_fill_full_v2_results.json`

### Launch / monitor

```bash
# Already running via:
python3 scripts/spawn_full_acceptance_gap_fill.py

# Monitor
tail -f /tmp/gap_fill_all_sports_full.log
cat /tmp/gap_fill_orchestrator.pid && ps -p $(cat /tmp/gap_fill_orchestrator.pid)
```

### Sport limits (Phase A + B)

| Sport | Active DB | Limit |
|-------|-----------|-------|
| cfb | 6,761 | 7,000 |
| nfl | 2,924 | 3,000 |
| ncaab_mens | 1,042 | 1,100 |
| ncaab_womens | 847 | 900 |
| nba | 535 | 5,000 |
| wnba | 199 | 250 |

**Env:** `DISABLE_FIRECRAWL=1`, `FALLBACK_SCORER=heuristic_gravity_v1`, `SCRAPE_CONCURRENCY=2`, `SCORE_CONCURRENCY=8`

---

## Prior 500-athlete batch (old checkpoint)

| Sport | scraped_ok | scored_ok | failures |
|-------|------------|-----------|----------|
| ncaab_mens | 500 | 500 | 0 |
| ncaab_womens | 500 | 500 | 0 |
| nfl | 500 | 500 | 0 |
| nba | 500 | 500 | 0 |
| wnba | 199 | 199 | 0 |

CFB full gap-fill (6761) still running separately.

---

## Baseline EDA (pre full v2 run)

| Sport | GP% | stats≥3 | NIL obs | heuristic | composite | ML |
|-------|-----|---------|---------|-----------|-----------|-----|
| cfb | 0.5% | 8.0% | 1.6% | 753 | 4,117 | 1,803 |
| nfl | 7.3% | 50.4% | — | 0 | 2,887 | 0 |
| ncaab_mens | 0.7% | 91.8% | 0.5% | 0 | 1,040 | 0 |
| ncaab_womens | 0.9% | 96.1% | 0.6% | 0 | 64 | 742 |
| nba | 1.9% | 99.6% | — | 0 | 535 | 0 |
| wnba | 4.5% | 97.5% | — | 0 | 199 | 0 |

**Training labels:** 123 nil_valuation_usd, 33 nil_deal_value_usd, 1,780 external_quality_score

---

## Code changes (commit `0293b90`)

| Area | Change |
|------|--------|
| **Orchestration** | `scripts/run_full_acceptance_gap_fill.py` — Phase A/B/C serial all-sports |
| **Detached spawn** | `scripts/spawn_full_acceptance_gap_fill.py` — survives agent exit |
| **Rescore-all** | `--rescore-all`, `--score-stale-days`, `--scrape-stale-days` on nightly_pipeline |
| **Checkpoint env** | `CHECKPOINT=reports/gap_fill_checkpoint_full_v2.json` in durable runner |

**Tests:** 4 passed (`test_scoring_stack.py`)

---

## Blockers / notes

1. **Railway ML 404** — `/score/athlete/cfb` returns 404; CFB rescore falls back to generic endpoint then heuristic tier. Redeploy gravity-ml needed for sport-specific CFB ML.
2. **CFB rescore in flight** — ~753/6761 already heuristic; rescore progressing (~1400 HTTP requests logged).
3. **Runtime ETA** — Phase A ~6–12h (CFB scrape-heavy), Phase B ~4–8h (all sports rescore), Phase C ~5 min.

---

## Commits in this workstream

- `fa59eac` — CFB stats/NIL pipeline fixes + EDA tooling
- `92bebc1` — Commercial viability JSON-string fix
- `d0374f4` — Durable serial gap-fill runner
- `5845c3c` — Post gap-fill EDA results
- `2d613f8` — HTTP-first scraping, ESPN multi-category, SR HTML parse, Firecrawl gating
- `0293b90` — Full acceptance gap-fill orchestration and rescore-all CLI
