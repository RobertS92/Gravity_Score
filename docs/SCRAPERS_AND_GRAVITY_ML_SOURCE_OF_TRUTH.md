# gravity-scrapers & gravity-ml — source of truth

**Purpose:** Single reference for the **data plane** (gravity-scrapers) and **learned scoring plane** (gravity-ml): responsibilities, contracts between them, env vars, jobs, and how **Gravity_Score** (`gravity_api`) consumes the result.

**Audience:** Engineers and agents working in sibling repos, CI operators, and anyone debugging “empty scores,” “scrapers ran but nothing changed,” or ML inference failures.

**Companion:** [GRAVITY_PLATFORM_SOURCE_OF_TRUTH.md](./GRAVITY_PLATFORM_SOURCE_OF_TRUTH.md) (whole platform). Deep product/score math: [GRAVITY_UNIFIED_SPEC.md](./GRAVITY_UNIFIED_SPEC.md).

**Repos (siblings of this monorepo):**

| Repo | URL (canonical) |
|------|------------------|
| gravity-scrapers | `https://github.com/RobertS92/gravity-scrapers` |
| gravity-ml | `https://github.com/RobertS92/gravity-ml` |

Clone them **next to** `Gravity_Score` and open **`gravity-platform.code-workspace`** from this repo root.

---

## 1. Why two repos?

| Layer | Repo | Question it answers |
|-------|------|---------------------|
| **Ingestion & freshness** | **gravity-scrapers** | “What did we collect from ESPN, NIL, social, news, … and when?” |
| **Ranking & explainability** | **gravity-ml** | “Given a wide feature vector, what is **G** and the **B/P/X/V/R** breakdown + SHAP?” |

**Scrapers do not replace the NN:** they **feed** normalized raw payloads into storage; the ML service **reads** those (or equivalent rows) through its feature pipeline and writes scores back per that repo’s deploy contract (often via scraper-orchestrated POST, or via `gravity_api` sync routes).

---

## 2. gravity-scrapers (data plane)

### 2.1 Role

- **HTTP API** (FastAPI) deployed to **Railway** (typical): roster sync, scheduled **daily** / **weekly** jobs, optional NIL/social enrichment.
- **Persistence:** **Supabase Postgres** (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) — tables such as **`athletes`**, **`raw_athlete_data`**, **`scraper_jobs`**, score tables per migrations in the scrapers repo.
- **Jobs** return quickly: handlers often **`BackgroundTasks`** — GitHub Actions “success” only means **POST accepted**; real work appears in **Railway logs** and **Supabase** row counts.

### 2.2 Auth

- **`SCRAPER_API_KEY`** (you generate it, e.g. `openssl rand -hex 32`) must match everywhere:
  - Railway → gravity-scrapers service variables  
  - GitHub Actions secrets on **gravity-scrapers** repo (`SCRAPER_API_KEY`, `RAILWAY_SCRAPER_URL`)  
- Requests use **`Authorization: Bearer <token>`** (see scraper repo `app/auth.py` / README).

### 2.3 GitHub Actions → Railway

- Workflows call **`POST …/jobs/daily`** and **`POST …/jobs/weekly`** (no trailing slash on base URL).
- **`RAILWAY_SCRAPER_URL`**: HTTPS base only, e.g. `https://<service>.up.railway.app`
- Health checks: use **`/`** or **`/health`** on Railway — **`/health/ready`** may **503** until Supabase is wired (do not use as sole health gate if that breaks deploy).

### 2.4 Verifying jobs actually did work

| Signal | What to check |
|--------|----------------|
| **`scraper_jobs`** | `status`, `processed_count`, `failed_count`, timestamps |
| **`raw_athlete_data`** | `scraped_at` advancing |
| **`athletes`** | `last_scraped_at`, roster fields; **`is_active`** for departures |
| **Railway logs** | Tracebacks after POST; “Processed: N” |
| **HTTP** | `GET /jobs/status` with Bearer — aligns with DB job history |

**Gotcha:** If **`athletes`** is **empty**, daily/weekly can finish in seconds with **`processed_count = 0`**. Seed athletes or run **`POST /jobs/roster-sync`** (with Bearer) per scraper docs.

**Local script (in gravity-scrapers clone):** `python scripts/verify_scraper_jobs.py` with Supabase env set.

### 2.5 Contract with gravity-ml (schema lockstep)

1. **Raw JSON keys** must align with **`GRAVITY_ML_RAW_FIELD_NAMES`** in **gravity-ml** (`ml/schema.py`) and scraper-side mirrors (e.g. `scrapers/ml_fields.py` in gravity-scrapers).
2. **Missing / wrong keys** become zeros after NaN handling in feature engineering → **weak or misleading rankings**.
3. **Identity:** stable **`external_id`** + source (e.g. ESPN) for joins and roster sync.
4. **Roster correctness** before scoring: roster sync jobs + DB migrations (e.g. athlete roster identity SQL referenced in unified spec).
5. **Provenance:** Prefer **`collection_timestamp`**, **`collection_errors`**, **`data_quality_score`** on pulls so downstream knows freshness and quality.

### 2.6 What Gravity_Score passes to scrapers

From **Gravity_Score** `.env` / Railway (for `gravity_api` or jobs):

- **`SCRAPERS_SERVICE_URL`** — deployed scrapers API base  
- **`SCRAPERS_SERVICE_API_KEY`** — same secret the scraper app expects as Bearer  

`gravity_api/jobs/*` and **`railway-service` `ScraperService`** may still be **stubs** until wired to HTTP — see [SCRAPER_EXHAUSTIVE.md](./SCRAPER_EXHAUSTIVE.md).

---

## 3. gravity-ml (neural network & inference)

### 3.1 Role

- **Training + inference** for college athlete **Gravity** scoring using a **PyTorch** stack.
- **Feature engineering:** tabular vector (on the order of **~250 dimensions**) from raw fields + cohort/ratio features where **`cohort_v1.pkl`** is available.
- **Model:** **`GravityNet`** — deep MLP (e.g. 250 → 512 → 256 → 128 → 64 → 1, sigmoid × 100) — see that repo’s `ml/feature_engineer.py` and model definition for exact shapes.
- **Explainability:** **SHAP** (or equivalent) attributions are **routed** into the **five named components** (B, P, X, V, R) for terminal and PDF narratives — **do not break this mapping** without updating product contracts (unified spec §6).

### 3.2 Inference service

- **HTTP:** **`POST /score/athlete`** (typical), secured with **`ML_API_KEY`** on the service.
- **Artifacts on disk:** **`MODEL_BUNDLE_PATH`** — weights (`gravity_v1.pt` or successor), **`normalizer_v1.pkl`**, optional **`cohort_v1.pkl`** for meaningful ratio features.
- **Health:** `/health`; optional deeper **`/health/ready`** depending on that repo’s implementation.

### 3.3 What Gravity_Score passes to ML

- **`ML_SERVICE_URL`** (or `ML_API_URL` in some configs) — base URL of gravity-ml  
- **`ML_API_KEY`** / **`ML_SERVICE_API_KEY`** — Bearer for inference  

`gravity_api` may call ML on score sync routes when configured.

### 3.4 Formula vs NN (one paragraph)

The **linear blend** \(G \approx w_B B + w_P P + w_X X + w_V V - w_R R\) is the **conceptual** and **fallback** story. **Production ranking at scale** targets the **learned** composition in **gravity-ml** so interactions (e.g. risk dampening proximity) are not forced into a single subtractive term. Roadmap (encoder, component heads, velocity time-series) lives in **GRAVITY_UNIFIED_SPEC.md** §1–4.

### 3.5 Outputs consumed downstream

| Output | Typical consumer |
|--------|------------------|
| Scalar **G** (0–100) | Rankings, watchlist, alerts |
| **Component scores** (display) | Terminal charts, program deltas |
| **SHAP / top drivers** | Deal assessment, alert copy, profile drill-down |
| **`model_version`** | Auditing, compliance, A/B |

---

## 4. End-to-end pipeline (ASCII)

```text
  ESPN / NIL / social / news / …
           │
           ▼
  ┌─────────────────────┐
  │   gravity-scrapers   │  Bearer: SCRAPER_API_KEY
  │   jobs + collectors  │
  └──────────┬──────────┘
             │ write
             ▼
  ┌─────────────────────┐
  │ Supabase / Postgres  │  athletes, raw_athlete_data, scraper_jobs, …
  └──────────┬──────────┘
             │
             ├──────────────────┐
             ▼                  ▼
  ┌─────────────────┐  ┌─────────────────┐
  │   gravity-ml     │  │   gravity_api    │
  │ POST /score/…    │  │ reads scores,    │
  │ FE → GravityNet  │  │ sync-from-ml,    │
  │ → SHAP → B/P/X/V/R│  │ serves terminal │
  └─────────┬─────────┘  └─────────────────┘
            │ write scores (per deploy wiring)
            ▼
  ┌─────────────────────┐
  │ athlete_gravity_     │
  │ scores (etc.)        │
  └─────────────────────┘
```

Exact “who writes `athlete_gravity_scores`” depends on your deployed wiring (scraper callback vs `gravity_api` sync). **Source of wiring detail:** gravity-scrapers + gravity-ml READMEs and **SCRAPER_EXHAUSTIVE**.

---

## 5. Environment variable cheat sheet

| Variable | Where set | Purpose |
|----------|-----------|---------|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | gravity-scrapers (Railway) | DB read/write |
| `SCRAPER_API_KEY` | gravity-scrapers + GitHub Actions | Bearer auth |
| `RAILWAY_SCRAPER_URL` | GitHub Actions (scraper repo) | Target for workflow POSTs |
| `ML_API_URL`, `ML_API_KEY` | gravity-scrapers (if it calls ML) | Inference after scrape |
| `SCRAPERS_SERVICE_URL`, `SCRAPERS_SERVICE_API_KEY` | Gravity_Score (`gravity_api`) | Call scrapers from product API |
| `ML_SERVICE_URL`, `ML_API_KEY` | Gravity_Score (`gravity_api`) | Call ML from product API |
| `MODEL_BUNDLE_PATH`, `ML_API_KEY` | gravity-ml (Railway) | Load weights + auth |

Names may vary slightly by repo branch—**treat each repo’s `.env.example` as authoritative** for that service.

---

## 6. Common failure modes (quick triage)

| Symptom | Likely cause |
|---------|----------------|
| GitHub Action green, no new rows | Job returned immediately; **empty `athletes`**; or background task failed — check **Supabase** + **Railway logs** |
| 401 from scrapers | **`SCRAPER_API_KEY`** mismatch between GitHub/Railway/caller |
| Flat or nonsense rankings | **Sparse raw fields** vs ML schema; re-check **`GRAVITY_ML_RAW_FIELD_NAMES`** alignment |
| ML 401/403 | Wrong **`ML_API_KEY`** or URL |
| Stale rosters / wrong school | Roster sync not run or **`is_active`** not updated when players leave |

---

## 7. Related documents

| Document | Use for… |
|----------|----------|
| [SCRAPER_EXHAUSTIVE.md](./SCRAPER_EXHAUSTIVE.md) | Integration checklist, Actions secrets, empty-table debugging |
| [SCRAPER_OVERVIEW.md](./SCRAPER_OVERVIEW.md) | High-level scraper concepts |
| [SCRAPER_DATA_FLOW.md](./SCRAPER_DATA_FLOW.md) | Legacy in-monorepo NIL connector flow (orchestrator pattern); not identical to deployed gravity-scrapers but useful mentally |
| [PLATFORM_PRODUCTION_AND_ROSTER_OPS.md](./PLATFORM_PRODUCTION_AND_ROSTER_OPS.md) | Production checklist, three-repo deploy, roster/transfer ops |
| [GRAVITY_UNIFIED_SPEC.md](./GRAVITY_UNIFIED_SPEC.md) | ML architecture roadmap, Velocity time-series, data source table, SHAP contract |
| [ML_PIPELINE_GUIDE.md](../ML_PIPELINE_GUIDE.md) | Older monorepo ML pipeline notes (may overlap legacy `gravity/` / `api/` paths) |

---

**Maintenance:** When gravity-scrapers or gravity-ml changes **job paths**, **auth header names**, or **schema field lists**, update this file and **SCRAPER_EXHAUSTIVE** / the sibling repo README so operators have one path to the truth.
