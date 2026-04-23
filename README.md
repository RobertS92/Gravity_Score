# Gravity Score / Gravity NIL Terminal

College-focused NIL intelligence: PostgreSQL schema, **FastAPI** (`gravity_api/`), rule-based **scoring pipeline** (`gravity/data_pipeline.py`), and the **gravity-terminal** React UI.

## Sibling repositories

| | GitHub |
|---|--------|
| **Scrapers** (rosters, NIL, social, collection APIs) | [RobertS92/gravity-scrapers](https://github.com/RobertS92/gravity-scrapers) |
| **ML** (training, models, optional inference service) | [RobertS92/gravity-ml](https://github.com/RobertS92/gravity-ml) |

This monorepo consumes data those services produce (e.g. Postgres or HTTP). See **`docs/SCRAPER_EXHAUSTIVE.md`** for wiring notes and suggested env vars (`SCRAPERS_SERVICE_URL`, `ML_SERVICE_URL`, etc.).

**One Cursor/VS Code window (multi-root):** Clone `gravity-scrapers` and `gravity-ml` as **sibling folders** next to this repo. Open the file **`gravity-platform.code-workspace`** at the **repo root** (next to `README.md`): Command Palette → **Open Workspace from File** → select it. Don’t open only a subfolder like `gravity-terminal/`, or you won’t see that file in the tree.

## Quick start

### API
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-gravity-api.txt
export PG_DSN="postgresql://user:pass@host:5432/db"
.venv/bin/python -m uvicorn gravity_api.main:app --reload --port 8000
```

Apply SQL in `migrations/001_gravity_nil_terminal.sql` before using the API.

### Terminal UI
```bash
cd gravity-terminal && npm install && npm run dev
```

Set `VITE_API_URL` (see `.env.example`) if the API is not on `http://localhost:8000`.

### Deploy terminal (cloud)

The UI is a static Vite build. Point **`VITE_API_URL`** at your deployed **`gravity_api`** origin **including `/v1`** (example: `https://gravity-api.up.railway.app/v1`). Enable **CORS** on the API for your frontend origin (`CORS_ORIGINS` in `.env.example`).

**Railway (Docker)**  
1. New service → same Git repo → set **Root Directory** to `gravity-terminal` (see [Deploying a monorepo](https://docs.railway.com/guides/deploying-a-monorepo)).  
2. Ensure **`Dockerfile`** is used (repo includes `gravity-terminal/railway.toml` with `builder = "DOCKERFILE"`).  
3. Under **Variables**, add **`VITE_API_URL`** (same name as the `ARG` in the Dockerfile). Railway exposes service variables during the Docker build; declare matching `ARG` lines in each build stage that needs them ([Dockerfiles](https://docs.railway.com/builds/dockerfiles)). Prefer a [reference variable](https://docs.railway.com/variables#referencing-another-services-variable) to your API service’s public URL.  
4. Deploy. The image runs **`serve -s`** on **`$PORT`** ([frontend env vars](https://docs.railway.com/guides/frontend-environment-variables)).  
5. If client-side routes 404 on refresh, enable SPA fallback for this service ([SPA routing](https://docs.railway.com/guides/spa-routing-configuration)).

**Local image check**

```bash
cd gravity-terminal
docker build --build-arg VITE_API_URL=https://your-api.example.com/v1 -t gravity-terminal:prod .
docker run --rm -p 8080:8080 -e PORT=8080 gravity-terminal:prod
```

**Vercel**  
Import the repo, set project **Root Directory** to `gravity-terminal`, add env **`VITE_API_URL`** (with `/v1`), and deploy. `vercel.json` adds SPA fallback rewrites.

### Scoring CSVs (local pipeline)
```bash
python run_pipeline.py input.csv output.csv
python score_all_sports.py
```

### Environment
```bash
export ANTHROPIC_API_KEY="sk-ant-…"   # agentic `/v1/query` in gravity_api
```

Copy `.env.example` to `.env` and fill values for Postgres, scrapers/ML URLs when deployed.

## Layout

| Path | Role |
|------|------|
| `gravity_api/` | FastAPI: athletes, scores, query agent, watchlist, jobs (wire to gravity-scrapers) |
| `gravity-terminal/` | Vite + React terminal |
| `gravity/` | Data pipeline, scoring, valuation, NIL stubs, packs, DB helpers |
| `migrations/` | Postgres schema |
| `railway-service/` | Deployable service; stub crawlers; ScraperService → wire to gravity-scrapers |
| `api/` | Legacy Gravity Score API (rule-based `api/model_cache.py`) |

## Docs

- **`docs/GRAVITY_PLATFORM_SOURCE_OF_TRUTH.md`** — team & agent onboarding: Gravity vs terminal vs scrapers vs NN, repos, stack, architecture (start here).
- **`docs/SCRAPERS_AND_GRAVITY_ML_SOURCE_OF_TRUTH.md`** — sibling repos only: scraper jobs, Supabase, ML inference, env matrix, failure triage.
- `docs/SCRAPER_EXHAUSTIVE.md` — links to **gravity-scrapers** / **gravity-ml** and integration checklist.

## License & credits

See repository history for authors and dependencies.
