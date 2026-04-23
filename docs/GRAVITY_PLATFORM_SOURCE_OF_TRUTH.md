# Gravity platform — source of truth (team & agents)

**Purpose:** One document so engineers, operators, and AI agents share the same mental model: what Gravity is, which repos and services exist, how the **NIL Intelligence Terminal**, **API**, **scrapers**, and **neural network** relate, and where to read more.

**Audience:** Onboarding, architecture reviews, support, and automated tooling that must not confuse similarly named components.

**Maintenance:** When you add a deployable service, a major API surface, or change the primary product API, update this file and the “Related docs” links at the bottom.

---

## 1. What “Gravity” is (product)

**Gravity** (often called **Gravity Score** in older docs) is a **college-focused NIL intelligence** system. It quantifies athlete “market gravity” using five interpretable components:

| Component | Symbol | Meaning (short) |
|-----------|--------|------------------|
| Brand | B | Audience, social reach, buzz, NIL surface area |
| Proof | P | On-field / résumé / performance signal |
| Proximity | X | Market, conference, program, NIL context |
| Velocity | V | Momentum (growth, trends, deltas over time) |
| Risk | R | Injury, transfer, controversy, eligibility downside |

A **scalar Gravity score** (typically 0–100) is derived from these signals—via a **learned model** at scale (see §6) and/or **formula / pipeline** fallbacks in legacy paths.

**NIL Intelligence Terminal** is the **buyer-facing product UI** in this monorepo: deal assessment, program comparison, brand match, watchlist, alerts, market scan, roster builder, and athlete profiles. It is **not** the same as the legacy “React market dashboard” described in older `APP_OVERVIEW.md` paths (`react-market-dashboard/`) unless you explicitly wire that stack.

---

## 2. Repository map (four moving parts)

Gravity is implemented across **three GitHub repos** plus this monorepo:

| Repo / place | Role |
|--------------|------|
| **Gravity_Score** (this monorepo) | **Product API** (`gravity_api/`), **terminal** (`gravity-terminal/`), Postgres **migrations**, legacy **`gravity/`** pipeline & **`api/`** FastAPI, optional **`railway-service/`** bundle |
| **gravity-scrapers** (sibling) | Scheduled **collection**: rosters, raw athlete payloads, jobs (`/jobs/daily`, `/jobs/weekly`, etc.), persistence to **Supabase/Postgres**, optional callout to ML after scrape |
| **gravity-ml** (sibling) | **Inference + training**: PyTorch **`GravityNet`**, feature engineering (~**250-d** vector), SHAP mapped to B/P/X/V/R, **`POST /score/athlete`** HTTP service |
| **Supabase** (hosted) | Common **Postgres + APIs** target for scrapers; **Gravity_Score** `gravity_api` uses **`PG_DSN`** (often a Supabase connection string) |

**Cursor / IDE:** Use **`gravity-platform.code-workspace`** at the repo root to open **Gravity_Score**, **gravity-scrapers**, and **gravity-ml** together (see root `README.md`).

---

## 3. Gravity_Score monorepo layout

| Path | Role |
|------|------|
| **`gravity_api/`** | **Primary NIL API** for the terminal: FastApp `gravity_api.main:app`, routes under **`/v1/*`**, `/health`. Postgres via **asyncpg**. Auth, athletes, scores, watchlist, roster, market, agent, operations, etc. |
| **`gravity-terminal/`** | **Vite + React + TypeScript** SPA. Build-time **`VITE_API_URL`** points at `gravity_api`. |
| **`migrations/`** | SQL for **athletes**, scores, rosters, events, `is_active` / roster verification columns, etc. |
| **`gravity/`** | **Legacy / research** Python: data pipeline, component scorers, collectors, packs—useful for batch CSV workflows and historical **formula** scoring; not the same process as **`gravity-ml`** production inference unless explicitly integrated. |
| **`api/`** | **Legacy** FastAPI (`api/gravity_api.py`) and model cache—**do not assume** this is what the terminal calls; the terminal targets **`gravity_api`**. |
| **`railway-service/`** | **Separate** FastAPI app (`app.main:app`) with its own Dockerfile and **Railway**-oriented config. May proxy scrapers or expose alternate endpoints. **Not** interchangeable with `gravity_api` without code and env changes. |

**Rule for agents:** If the user says “the API,” default to **`gravity_api`** for terminal + NIL features. If they say “Railway Dockerfile at repo root,” that **`railway.toml`** currently builds **`railway-service`**, not `gravity_api`—confirm which service is deployed.

---

## 4. NIL Intelligence Terminal (product UI)

**Location:** `gravity-terminal/`

**Stack:** React 18, TypeScript, Vite, Zustand (and similar) for client state; calls **`gravity_api`** over HTTPS.

**Configuration (high level):**

- **`VITE_API_URL`** — Base URL for the API (client appends `/v1` when needed).
- **`VITE_USE_MOCKS`** — `false` in production (real data).
- **`VITE_AGENT_USE_PROXY`** — Prefer server-side Anthropic proxy (`POST /v1/agent/complete`) so keys stay on the API.
- Optional **Supabase Realtime** keys for live updates (`VITE_SUPABASE_*`).

**Representative views (not exhaustive):**

| Area | Typical API areas |
|------|-------------------|
| Athlete search / profiles | `/v1/athletes`, detail bundles |
| Market scan | `/v1/market/scan`, schools |
| Watchlist & alerts | `/v1/watchlist`, `/v1/alerts` |
| Roster builder | `/v1/roster` |
| AI / command | `/v1/agent`, `/v1/query` |
| Auth | `/v1/auth` |

**Detail:** `gravity-terminal/README.md`, `docs/NIL_APPLICATIONS.md`.

---

## 5. gravity_api (product backend in this repo)

**Entry:** `uvicorn gravity_api.main:app`

**Responsibilities:**

- **Read/write** athlete and score data in **Postgres** (`PG_DSN`).
- **Enforce** CORS (`CORS_ORIGINS`), JWT / dev user patterns (`JWT_SECRET`, `GRAVITY_ALLOW_QUERY_USER_ID`).
- **Proxy or call** optional sibling services: **scrapers** (`SCRAPERS_SERVICE_URL`, `SCRAPERS_SERVICE_API_KEY`), **ML** (`ML_SERVICE_URL`, `ML_API_KEY`), **Anthropic** for agent routes.

**Config reference:** `gravity_api/config.py`, root `.env.example`.

**Important:** Roster and athlete eligibility use DB flags such as **`is_active`** (departed / transfer / draft) when migrations are applied—scrapers and jobs must keep these accurate for trustworthy rosters and search.

---

## 6. gravity-scrapers (sibling repo — data plane)

**Role:** **Ingestion and freshness**—ESPN-aligned roster sync, collectors for CFB/MBB (and roadmap sports), enrichment, scheduled jobs. Writes **structured raw rows** and metadata to the database the stack agrees on (typically **Supabase Postgres**).

**Contract with ML:** Raw field keys should align with **`GRAVITY_ML_RAW_FIELD_NAMES`** in **gravity-ml** (`ml/schema.py`) and mirrored conventions in scrapers. Sparse or mis-keyed fields become zeros in the 250-d vector and **hurt ranking signal**.

**Auth:** Mutating routes use **Bearer** (`SCRAPER_API_KEY` or equivalent—see scraper repo and `docs/PLATFORM_PRODUCTION_AND_ROSTER_OPS.md`).

**Truth on stubs:** Parts of NCAA collection in scrapers may still be **stubby**; the **scheduler + DB + ML POST** path may exist before every field is populated. Treat **PLATFORM_PRODUCTION** and scraper READMEs as the live status.

---

## 7. gravity-ml (sibling repo — neural network & inference)

**Role:** **Production-style scoring** for college athletes using a **deep MLP** (e.g. 250 → … → 1, scaled to 0–100) on engineered features, plus **SHAP** (or equivalent) attribution **mapped to the five named components** for the terminal and reports.

**Service:** HTTP **`POST /score/athlete`** (protected by **`ML_API_KEY`** in typical deploys).

**Artifacts:** Weights, normalizer, optional **`cohort_v1.pkl`** for ratio features—loaded from **`MODEL_BUNDLE_PATH`** on the ML host.

**Roadmap (spec, not always implemented):** Encoder + component heads + non-linear fusion; **Velocity** as explicit **time-series / deltas** (7d/30d/90d). See **`docs/GRAVITY_UNIFIED_SPEC.md`** §1–4.

**Relationship to formula:** The **weighted linear blend** \(G \approx w_B B + w_P P + w_X X + w_V V - w_R R\) remains the **conceptual** and **fallback** explanation; the NN is the **primary ranking engine at scale** when the bundle is deployed and fed quality raw data.

---

## 8. End-to-end data flow (happy path)

```text
  [Sources: ESPN, news, social, NIL, …]
              │
              ▼
  [gravity-scrapers] ──write──► [Postgres / Supabase: athletes, raw_athlete_data, scores, …]
              │
              ├──► [gravity-ml POST /score/athlete] ──► [athlete_gravity_scores, model_version, SHAP fields]
              │
              ▼
  [gravity_api reads DB] ◄──HTTPS── [gravity-terminal]
```

**gravity_api** may also **trigger** or **poll** scrapers/ML depending on routes and env; not every chain is mandatory in dev.

---

## 9. Deploy & operations (summary)

| Concern | Typical choice in this stack |
|---------|------------------------------|
| Database | **Supabase Postgres** (or any Postgres) — `PG_DSN` |
| API + workers | **Railway** (or similar) — multiple **services** possible: `railway-service` vs **`gravity_api`** are separate images/configs |
| Frontend | **Static host** (Vercel, Netlify, Cloudflare Pages) or Railway static — **`VITE_API_URL`** must match public API URL |
| CORS | **`CORS_ORIGINS`** on `gravity_api` must list the **exact** browser origin of the terminal |

**Operator runbook:** `docs/PLATFORM_PRODUCTION_AND_ROSTER_OPS.md`

---

## 10. Glossary (disambiguation)

| Term | Meaning |
|------|---------|
| **Gravity / Gravity Score** | Product + score family (B, P, X, V, R). |
| **NIL Intelligence Terminal** | `gravity-terminal` SPA. |
| **gravity_api** | FastAPI app in **`Gravity_Score`** serving `/v1` to the terminal. |
| **railway-service** | Different FastAPI app in **`Gravity_Score`**, own Dockerfile; do not conflate with `gravity_api`. |
| **gravity-scrapers** | Sibling repo; ingestion and jobs. |
| **gravity-ml** | Sibling repo; NN inference + training. |
| **gravity/** (folder) | Legacy monolith Python (pipeline, packs, scrapers-in-tree); not the HTTP ML service. |

---

## 11. Related documents (deeper dives)

| Document | Use when you need… |
|----------|-------------------|
| [SCRAPERS_AND_GRAVITY_ML_SOURCE_OF_TRUTH.md](./SCRAPERS_AND_GRAVITY_ML_SOURCE_OF_TRUTH.md) | **gravity-scrapers** + **gravity-ml** only: jobs, auth, schema contract, env matrix, triage |
| [GRAVITY_UNIFIED_SPEC.md](./GRAVITY_UNIFIED_SPEC.md) | Formula vs NN, Velocity roadmap, scraper↔ML schema, SHAP contract, data sources table |
| [PLATFORM_PRODUCTION_AND_ROSTER_OPS.md](./PLATFORM_PRODUCTION_AND_ROSTER_OPS.md) | Env vars, Railway/Supabase wiring, roster/transfer ops, production checklist |
| [NIL_APPLICATIONS.md](./NIL_APPLICATIONS.md) | Buyer workflows and terminal surfaces (commercial framing) |
| [SCRAPER_EXHAUSTIVE.md](./SCRAPER_EXHAUSTIVE.md) | Scraper integration checklist, env naming |
| [EXECUTIVE_TECH_BRIEF.md](./EXECUTIVE_TECH_BRIEF.md) | Executive-level technical narrative (broader than NCAA-only terminal) |
| [APP_OVERVIEW.md](./APP_OVERVIEW.md) | Legacy “full league CSV + dashboard” story—may overlap conceptually but paths differ from `gravity-terminal` |
| Root [README.md](../README.md) | Clone layout, quick start commands |

---

**Version note:** This file was authored to consolidate overlapping READMEs and specs. If something conflicts, prefer **this file for “where things live”** and **GRAVITY_UNIFIED_SPEC** for **ML/scoring math and roadmap**, and **PLATFORM_PRODUCTION** for **deploy env names and runbooks**.
