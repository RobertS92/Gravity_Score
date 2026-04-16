# Deploying `railway-service` on Railway

## Shared variables vs this service

Railway **Project → Shared Variables** are a good place for values **used by more than one service** (e.g. `CORS_ORIGINS`, `OPENAI_API_KEY`, `SUPABASE_URL`). Each service still needs **its own** secrets where names differ (e.g. this app uses `API_KEY`; **gravity-scrapers** uses `SCRAPER_API_KEY`).

**Your current shared set** (`CORS_ORIGINS`, `FIRECRAWL_API_KEY`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`) is fine for optional features. **`railway-service` must have `API_KEY`** or Pydantic fails at import. **`SUPABASE_*` is optional**: omit both (or leave empty) if this deploy is not wired to Supabase — `/health` works; DB-backed routes return **503** or empty job lists until you add them (or promote **`SUPABASE_URL`** / **`SUPABASE_SERVICE_KEY`** to shared if both scrapers API and this service use the same Supabase project).

| Variable | Use as shared? | `railway-service` needs it? |
|----------|----------------|------------------------------|
| `SUPABASE_URL` | Yes, if all backends share one DB | **For DB features** — omit if not using Supabase |
| `SUPABASE_SERVICE_KEY` | Yes (same note) | **For DB features** — omit if not using Supabase |
| `API_KEY` | Usually **no** — different services use different header secrets | **Yes** (this service only) |
| `CORS_ORIGINS` | Yes | Optional (has default in code) |
| `FIRECRAWL_API_KEY` / `OPENAI_API_KEY` / `PERPLEXITY_API_KEY` | Yes | Optional |

**gravity-scrapers** (if deployed separately) typically needs: `SCRAPER_API_KEY`, `SUPABASE_*`, `ML_API_URL`, `ML_API_KEY`, optional `CORS_ORIGINS` — not the same as `API_KEY` here.

**gravity-ml** typically needs: `ML_API_KEY`, `MODEL_BUNDLE_PATH`, etc. — do **not** reuse `API_KEY` unless you intentionally unify.

## Healthcheck

Railway is configured (see repo root `railway.toml`) to probe **`GET /health`**. The process must bind to **`0.0.0.0:$PORT`** (`$PORT` is injected by Railway).

## Required variables

Set these in **Railway → Service → Variables**. If **`API_KEY`** is missing, **Pydantic fails at import** and the container never listens — healthchecks show **503 / service unavailable**.

| Variable | Required | Notes |
|----------|----------|--------|
| `API_KEY` | **Yes** | Long random string; clients send `X-API-Key` or equivalent per your routes |
| `SUPABASE_URL` | No* | `https://xxx.supabase.co` — omit or empty if not using a database |
| `SUPABASE_SERVICE_KEY` | No* | Service role key (server only) — pair with `SUPABASE_URL` when you enable DB |
| `PORT` | Auto | Set by Railway; do not override unless you know what you’re doing |
| `CORS_ORIGINS` | No | JSON array string, e.g. `["https://your-app.lovable.app"]` |

\* **Both** `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` must be non-empty for athlete refresh, job triggers, and job persistence. If either is missing, `GET /health/detailed` reports `database: not_configured`.

Optional API keys (scrapers / LLM) can stay empty unless you use those code paths.

## Where to get each value (I can’t do this step for you)

Railway and Supabase require **your** login. Copy values from the sources below; never commit them to git.

| Variable | Where it comes from |
|----------|---------------------|
| **`SUPABASE_URL`** | [Supabase Dashboard](https://supabase.com/dashboard) → your project → **Project Settings** (gear) → **API** → **Project URL** (looks like `https://abcdefgh.supabase.co`). |
| **`SUPABASE_SERVICE_KEY`** | Same **API** page → **`service_role`** key (under “Project API keys”). **Server-only** — bypasses Row Level Security; do not put in frontend or public repos. Prefer **shared** Railway variable if scrapers + this API share one Supabase project. |
| **`API_KEY`** | **You generate it** — any long random secret the API will check (e.g. `openssl rand -hex 32` on your Mac). Store in Railway; configure Lovable / GitHub Actions / Postman to send the same value as your app expects (`X-API-Key` or whatever the route uses). |
| **`CORS_ORIGINS`** | Not from a vendor — a **JSON array string** of allowed browser origins, e.g. `["https://your-app.lovable.app","http://localhost:5173"]`. Must be valid JSON (double quotes). Wrong format falls back to defaults in code (see `config.py`). |
| **`OPENAI_API_KEY`** | [OpenAI API keys](https://platform.openai.com/api-keys). |
| **`PERPLEXITY_API_KEY`** | Perplexity account / API dashboard (product-specific). |
| **`FIRECRAWL_API_KEY`** | [Firecrawl](https://firecrawl.dev) (or your Firecrawl dashboard) if you use that integration. |

If you don’t have a Supabase project yet: **Supabase → New project** → wait for provisioning → then use **API** page for URL + `service_role` key.

## How to set them in Railway

1. Open [Railway](https://railway.app) → your **project** → select the **Gravity_Score / railway-service** deployment service.
2. **Variables** tab → **New Variable** (or **Raw Editor**).
3. Add **`API_KEY`** (required). Add **`SUPABASE_URL`** and **`SUPABASE_SERVICE_KEY`** only when connecting to Supabase (both must be set together; exact names, case-sensitive, match `config.py`).
4. For values used by **multiple** services: **Project** (not service) → **Variables** → create **Shared** variables; then in each service, **Reference** or ensure the service inherits shared vars (per Railway UI: “shared variable” / graph you mentioned).
5. **Redeploy** (or push a commit) so the new env is picked up.
6. Confirm **Deploy logs** show the app starting without `ValidationError` for missing fields.

## If deploy still fails

1. **Deploy logs** — look for `ValidationError` (missing env) or `ModuleNotFoundError: gravity`.
2. **PYTHONPATH** — Dockerfile sets `PYTHONPATH=/app` so `gravity/` is importable.
3. **Scheduler** — If Supabase or scheduler init fails, the app **still starts** and `/health` returns 200; check logs for `Failed to construct or start scheduler`.
4. **Workers** — Deploy uses **one** uvicorn worker so startup is faster and the healthcheck passes sooner.

## “Unexposed service”

That only means no public **Railway URL** is attached. Healthchecks still run against the running process. Generate a domain or enable public networking if you need external access.
