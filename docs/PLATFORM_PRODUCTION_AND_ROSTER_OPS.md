# Gravity platform: production readiness, NCAA data + ML, and roster / transfer operations

This document is the **single operator runbook** for the three-repo Gravity stack: how to ship it safely, how scrapers must feed the neural net, and how to keep **rosters accurate** and **transfers** under control. Update this file when deploy topology or schemas change.

For the **unified product + ML + terminal architecture** (formula vs NN, Velocity time-series roadmap, data sources, NIL apps), see **[GRAVITY_UNIFIED_SPEC.md](./GRAVITY_UNIFIED_SPEC.md)**.

**Repos**

| Repository       | Purpose |
|------------------|---------|
| `gravity-scrapers` | FastAPI, Supabase persistence, `/jobs/daily` & `/jobs/weekly`, calls ML after scrape |
| `gravity-ml`       | `POST /score/athlete`, PyTorch bundle + optional `cohort_v1.pkl` |
| `Gravity_Score`    | NIL / Gravity API (`gravity_api`), legacy/alternate APIs, `railway-service` |

---

## Part A — What “production” means

Production-ready means **each service you actually deploy** has env vars set, secrets configured, callers wired end-to-end — **not** that every stub inside `Gravity_Score` is complete.

### A.1 Three deployable backends

| Piece | Repo | Role |
|--------|------|------|
| Scraping + scheduled jobs | **gravity-scrapers** | HTTP API, Supabase, `POST /jobs/daily`, `POST /jobs/weekly` (Bearer auth) |
| ML scoring | **gravity-ml** | `POST /score/athlete`, model files on disk (`MODEL_BUNDLE_PATH`) |
| NIL / Gravity API + older Railway bundle | **Gravity_Score** | `gravity_api`, `api/gravity_api.py`, `railway-service/` |

Pick which surfaces are **customer-facing** vs internal; document that choice in your deploy dashboard (Railway, etc.).

### A.2 Cross-service wiring (most common blocker)

**gravity-scrapers (Railway)**

- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- `SCRAPER_API_KEY` — required on mutating routes (`Authorization: Bearer <key>`)
- If ML is enabled: `ML_API_URL`, `ML_API_KEY` — must match the **gravity-ml** service

**GitHub Actions (gravity-scrapers repo)**

- `RAILWAY_SCRAPER_URL` — repository **secret** or **variable** (public URL is fine as a variable), e.g. `https://<service>.up.railway.app` (no trailing slash)
- `SCRAPER_API_KEY` — same value as the scraper service

**gravity-ml (Railway)**

- `ML_API_KEY` — Bearer token for `POST /score/athlete`
- `MODEL_BUNDLE_PATH` — directory containing trained artifacts (`gravity_v1.pt`, `normalizer_v1.pkl`, optional `cohort_v1.pkl`)
- Use `/health` for liveness; `/health/ready` if you want deeper checks (Supabase / config on scrapers; ML service may expose its own ready probe)

**Gravity_Score**

- **NIL / main API:** `PG_DSN`, `ENVIRONMENT`, `CORS_ORIGINS`, and settings in `gravity_api/config.py` as applicable
- **railway-service** uses a **different** env contract (`API_KEY`, Supabase keys, etc. in `railway-service/app/config.py`). Treat it as a **separate** service; root `.env.example` does not fully describe Railway service vars

Until URLs and keys form a consistent graph, components will “work in isolation” but fail in production chains (empty scores, 401s, missing rows).

### A.3 Security and posture (quick wins)

| Area | Risk | Mitigation |
|------|------|------------|
| `GET /jobs/status` (gravity-scrapers) | Job history readable without auth | Protect with Bearer (same as other routes), private network, or API gateway; do not expose publicly unauthenticated |
| Bearer validation | Timing side channels; weak keys | Use a long random `SCRAPER_API_KEY`; use **constant-time** comparison (`secrets.compare_digest`) for token checks |
| CORS `allow_origins=["*"]` | Over-permissive if browsers call API directly | Restrict to known front-end origins via env (e.g. comma-separated list) |

### A.4 Gravity_Score product / code completeness (expect stubs)

- `gravity_api` auth and comparables may be partial; NIL may log/delegate
- `gravity_api/jobs/daily_incremental.py` and `weekly_refresh.py` may be no-ops if **GitHub Actions → gravity-scrapers** is the real schedule — either implement them or document that operators must use scraper jobs only
- Multiple FastAPI apps exist (`gravity_api/main`, `api/gravity_api.py`, `gravity/api/nil_api.py`) — for production, **designate one primary HTTP surface** per hostname or document which host serves which

### A.5 Testing, CI, dependency hygiene

- **Gravity_Score:** If root `tests/` were removed, add **targeted** tests or contract tests for APIs you ship; `railway-service/.github/workflows` may be the only CI for that subtree
- **feature_testing_mcp:** If deployed, ensure all imports (`mcp`, `typer`, etc.) are pinned in the appropriate `requirements*.txt`

### A.6 Documentation hygiene

- Older markdown may reference deleted scripts; prefer this runbook + small scoped docs
- When adding env vars or routes, update **this file** and the relevant `.env.example`

### A.7 Minimal “done” checklist

You are in good shape when:

1. **gravity-scrapers** passes `/health/ready`, GitHub secrets/vars are set, and a manual `workflow_dispatch` on daily/weekly workflows succeeds.
2. **gravity-ml** serves real weights; scrapers complete an end-to-end score write to `gravity_scores`.
3. **Gravity_Score** endpoints you expose have explicit deploy config and **one** clear API story (no silent stubs on critical user paths).
4. Sensitive or informative endpoints are authenticated or network-restricted as intended.

---

## Part B — NCAA scrapers and the Gravity neural net

### B.1 Current state in code

**NCAA scrapers in `gravity-scrapers` are stubs.** `CFBScraper.collect` and `NCAAScraper.collect` return only `sport`, `player_name`, `team`, and `position`. The **scheduler** already persists `raw_data` to Supabase and POSTs to **gravity-ml**; the missing piece is a **real collector** that populates ML-aligned fields.

**ML contract:** keys must align with `gravity-ml/ml/schema.py` — `GRAVITY_ML_RAW_FIELD_NAMES`. `ml/feature_engineer.py` builds a **250-dimensional** vector; missing values become **0** after NaN handling, which **collapses ranking signal**.

Reference flow:

- Scrapers: `gravity-scrapers/scrapers/cfb_scraper.py`, `ncaab_scraper.py`
- Orchestration: `gravity-scrapers/app/services/scheduler.py` → `raw_athlete_data` → `_request_ml_score`
- Features: `gravity-ml/ml/feature_engineer.py` (`engineer_row`)
- Inference: `gravity-ml/ml/inference.py` (`GravityInference`, optional `cohort_v1.pkl`)

### B.2 High-impact raw fields (implement first)

`engineer_row` is the source of truth. Prioritize filling these (exact key names from schema):

| Theme | Example fields |
|--------|----------------|
| Identity & context | `college`, `conference`, `class_year`, `height`, `weight`, `jersey_number`, `hometown` |
| Recruiting | `recruiting_stars`, `recruiting_rank_national`, `recruiting_rank_position` |
| Social | `instagram_followers`, `twitter_followers`, `instagram_handle`, `twitter_handle` |
| Engagement | `news_count_30d`, `google_trends_score` |
| NIL | `nil_valuation`, `nil_deals`, `nil_ranking` |
| Hoops | `ppg`, `rpg`, `apg`, `fg_pct`, `three_pt_pct`, `ft_pct`, `career_points`, `career_rebounds`, `career_assists`, `current_season_stats`, `career_stats` |
| Football | `heisman_votes`, `all_american_count` |
| Risk / trajectory | `injury_history`, `current_injury_status`, `transfer_portal_status`, `previous_schools`, `eligibility_years_remaining` |
| MBB awards | `wooden_award_finalist`, `naismith_finalist` |
| Draft | `nba_draft_projection`, `wnba_draft_projection` |

**Metadata (schema-allowed):** `collection_timestamp`, `collection_errors`, `data_quality_score` (e.g. 0–1 completeness). During development, use `validate_row_keys` from `feature_engineer` to catch invalid keys.

### B.3 Modern players: identity and freshness

- **Stable external IDs:** Store ESPN (or NCAA stats, vendor) ids on `athletes`; pass into `collect()` to avoid ambiguous names.
- **Resolve then scrape:** Match canonical profile first; update `team` / `position` from source when Supabase is stale.
- **Season config:** Centralize current season (e.g. 2025–26) so stats are not silently last year’s.

### B.4 Layered ETL (recommended)

1. Official rosters / bios (structure: height, weight, class, hometown)
2. Stats APIs / structured JSON (ESPN-style where permitted)
3. NIL / recruiting (only with license/compliance)
4. News / trends (rate-limited)
5. HTML / Firecrawl fallback with caching

Merge with **source priority**; avoid ad hoc keys outside `GRAVITY_ML_RAW_FIELD_NAMES` unless you extend schema and ML jointly.

### B.5 Neural net operations after scraper quality improves

- Regenerate **`cohort_v1.pkl`** from a representative corpus so ratio features (e.g. follower vs team mean) are meaningful.
- If distributions shift materially, **retrain** (`gravity-ml/ml/trainer.py`) to limit covariate shift.
- Redeploy bundle + normalizer together.

### B.6 Suggested implementation order (data layer)

1. Replace stub `collect()` with multi-source builders keyed to `GRAVITY_ML_RAW_FIELD_NAMES`.
2. Add external ids + resolution in `gravity-scrapers` and Supabase (see Part C).
3. Emit `data_quality_score` and structured `collection_errors`.
4. Rebuild cohort; retrain if needed.

---

## Part C — Plan: transfers, roster drift, and continuous correction

Goal: **one canonical athlete row per real person**, correct **team / conference / eligibility** as the NCAA calendar moves, and explicit handling of **portal and transfers** without duplicate UUIDs or stale scores.

### C.1 Principles

1. **Source of truth is time-stamped:** Roster data is always `(data, observed_at, source)`. The database holds **current best** plus optional **history** if you add tables later.
2. **External id beats name matching:** Prefer `espn_athlete_id` (or equivalent) for joins; names + school are fallback.
3. **Separate “identity” from “employment”:** Transfer = same `athlete_id`, new `team` / `conference`; do not mint a new id unless duplicate resolution merges rows (see C.6).
4. **Scores are invalid until rescrape:** When team/conference changes, treat gravity score as **stale** until a new raw payload and ML run complete (optional flag or `last_scraped_at` / version check in product).

### C.2 Recommended schema extensions (Supabase / migrations)

Extend `athletes` beyond the minimal DDL in `gravity-scrapers/supabase/001_scraper_ml_tables.sql`:

| Column | Type | Purpose |
|--------|------|---------|
| `external_id` | `TEXT` | Primary vendor id (e.g. ESPN) |
| `external_id_source` | `TEXT` | `espn`, `ncaa`, etc. |
| `team_slug` | `TEXT` | Stable team key for roster APIs |
| `roster_season` | `TEXT` | e.g. `2025` or `2025-26` |
| `roster_verified_at` | `TIMESTAMPTZ` | Last time team matched official roster |
| `eligibility_remaining` | `INTEGER` | Optional cache (still scrape into `raw_data`) |
| `is_transfer` | `BOOLEAN` | Portal or inter-school move detected |
| `previous_team` | `TEXT` | Optional denormalized hint |
| `display_name` | `TEXT` | If legal vs common name differs |

**Optional later:** `athlete_team_history` (athlete_id, team, start_date, end_date, source) for audit and analytics.

Add **unique** constraint on `(external_id_source, external_id)` where `external_id` is not null to prevent duplicates.

### C.3 Roster ingestion architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│ Roster provider     │     │ Roster sync job       │     │ athletes table  │
│ (per league/sport)  │────▶│ diff + upsert merge   │────▶│ + raw_data      │
└─────────────────────┘     └──────────────────────┘     └─────────────────┘
                                      │
                                      ▼
                             gravity-scrapers VIP /
                             weekly full scrape
```

**Jobs**

| Job | Frequency | Action |
|-----|-----------|--------|
| **Roster sweep** | Daily or every 12h during peak (portal windows) | For each tracked `team_slug`, fetch official roster; upsert athletes; mark `roster_verified_at` |
| **Transfer detector** | Same or daily | Compare previous snapshot to new roster; set `is_transfer`, `previous_team`, `transfer_portal_status` in `raw_data` / columns |
| **VIP athlete refresh** | Existing daily job in scraper | Prioritize high `gravity_score`; full `collect()` + ML |
| **Weekly full scrape** | Existing weekly job | Backfill stale `last_scraped_at` |

Implement roster sync either **inside gravity-scrapers** (new module + optional cron route protected by `SCRAPER_API_KEY`) or as a **separate worker** writing to the same Supabase — the important part is **one writer** and clear ownership.

### C.4 Matching algorithm (new roster row → existing athlete)

1. If `external_id` present on roster row → **match** `athletes.external_id`.
2. Else match `(normalized_name, team_slug, sport)`.
3. Else fuzzy name within team + position family (Levenshtein / threshold); **queue for human review** if ambiguous.
4. On confident transfer (same person, new school): **update** `athletes.team`, `conference`, `roster_verified_at`; optionally append to team history table.

**Normalization:** lowercase, strip suffix (Jr., III), fold unicode; store raw display name separately.

### C.5 When a player transfers

1. Roster sync sets new `team` / `conference` on `athletes`.
2. Set `is_transfer = true` (or rely on `raw_data.transfer_portal_status`).
3. **Invalidate downstream:** Either null out latest `gravity_scores` row confidence, enqueue immediate `scrape_single_athlete`, or flag UI “updating.”
4. After successful scrape + ML, clear `is_transfer` or set `transfer_resolved_at` if you need UX state.

### C.6 Duplicate UUIDs (same human, two rows)

Prevention: unique `(external_io_source, external_id)`.  

**Detection:** Periodic query for same normalized name + overlapping seasons on different ids → **merge script**: pick canonical id, repoint FKs (`raw_athlete_data`, `gravity_scores`), delete duplicate (with backup).

### C.7 Season boundaries and “continuous” correction

- **Config:** `CURRENT_ROSTER_SEASON`, `CURRENT_STATS_SEASON` in env or `app.config`.
- At season rollover: bump config; roster job pulls new roster ids; old team slugs may change — prefer **team id** not display string.
- **Conference realignment:** Maintain `conference` from provider mapping table, not hardcoded strings in scrapers.

### C.8 Observability

- Log roster job: teams processed, rows added/updated/retired.
- Alert on spike in “unmatched roster players” or drop in roster size for a team.
- Dashboard: count athletes with `roster_verified_at` older than N days.

### C.9 Compliance and rate limits

- Respect robots/terms for each provider; use official APIs when available.
- Cache roster responses (Redis or DB) to avoid hammering sources during daily VIP loops.

---

## Part D — Single-threaded execution roadmap

| Phase | Outcome |
|-------|---------|
| **D1** | Lock prod topology: which APIs are public; document Railway URLs and GitHub secrets |
| **D2** | Harden auth: constant-time Bearer, protect `/jobs/status`, tighten CORS via env |
| **D3** | Schema migration: external ids + roster columns + unique constraint |
| **D4** | Roster sync job + transfer detection + VIP rescrape on team change |
| **D5** | Replace NCAA stub scrapers with ML-complete payloads + `data_quality_score` |
| **D6** | Rebuild `cohort_v1.pkl`; retrain if needed; verify end-to-end scores |

---

## Part E — What is wired in code (reference)

- **gravity-scrapers**
  - Bearer auth with constant-time compare: `app/auth.py`; `GET /jobs/status` requires the same token as mutating routes (`app/routers/jobs.py`).
  - CORS: set `CORS_ORIGINS` (comma-separated) in production; `*` is used only when `ENVIRONMENT` is `development` / `local` / `dev` and `CORS_ORIGINS` is unset (`app/main.py`). If both are unset in prod, browser cross-origin calls get no permissive CORS (API-to-API unaffected).
  - Roster / transfers: `supabase/002_athlete_roster_identity.sql`; ESPN roster pull `app/services/roster_sync.py`; `POST /jobs/roster-sync` (Bearer). Optional env: `ROSTER_SYNC_DEFAULT_SPORT`, `ROSTER_SYNC_DEFAULT_TEAM_IDS`, `CURRENT_STATS_SEASON`.
  - NCAA payloads: `scrapers/cfb_scraper.py`, `scrapers/ncaab_scraper.py`, field list `scrapers/ml_fields.py`; enrich via ESPN when `external_id_source=espn`.
- **gravity-ml** — Rebuild cohort: `scripts/rebuild_cohort_from_jsonl.py` (documented in README).
- **Gravity_Score** — Root `.env.example` includes a **railway-service** variable block; `gravity_api/jobs/*` placeholders log pointers to this runbook.
- **CI** — `gravity-scrapers/.github/workflows/ci.yml` runs pytest.

### API map (Gravity_Score monorepo — multiple apps)

| App | Typical entry | Notes |
|-----|----------------|--------|
| NIL / main API | `uvicorn gravity_api.main:app` | Postgres `PG_DSN`, product API surface |
| Legacy Gravity Score | `uvicorn api.gravity_api:app` | Rule-based / alternate pipeline |
| NIL API module | `uvicorn gravity.api.nil_api:app` | Separate FastAPI app in package |
| Railway scrapers bundle | `Gravity_Score/railway-service` | Env from `railway-service/app/config.py`, not root `.env.example` alone |

Designate one hostname per customer-facing API in deployment.

---

## Revision history

- **2026-04-01** — Initial consolidated runbook (production + NCAA/ML + roster/transfer plan).
- **2026-04-02** — Part E: implementation pointers (auth, roster sync, ML cohort script, CI, API map).
