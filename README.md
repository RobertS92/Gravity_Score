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

The UI is a static Vite build. Point **`VITE_API_URL`** at your deployed **`gravity_api`** base URL. The app appends **`/v1`** if it is missing ([`getApiBaseUrl`](gravity-terminal/src/api/client.ts)). On the API, set **`CORS_ORIGINS`** to include your terminal’s public origin (see `.env.example`).

#### Railway (recommended for this repo)

Use a **second service** in the same Railway project as `gravity_api` so you can [reference variables](https://docs.railway.com/variables#referencing-another-services-variable) and one-click HTTPS on the generated `*.up.railway.app` domain (or attach a custom domain later).

1. **Create the service:** New → **GitHub repo** → pick **Gravity_Score** → **Add variables** (you can skip for a moment) → **Deploy** (or finish wizard).  
2. **Monorepo root:** Service → **Settings** → set **Root Directory** to `gravity-terminal` ([monorepo guide](https://docs.railway.com/guides/deploying-a-monorepo)).  
3. **Build:** Confirm **Dockerfile** deploys (`gravity-terminal/railway.toml` sets `builder = "DOCKERFILE"`).  
4. **`VITE_API_URL` (required):** Variables → add **`VITE_API_URL`**. Same name as **`ARG VITE_API_URL`** in the Dockerfile so Railway passes it into the **build** ([Dockerfiles](https://docs.railway.com/builds/dockerfiles#using-variables-at-build-time), [frontend env vars](https://docs.railway.com/guides/frontend-environment-variables)).  
   - **Reference your API service** (replace `API_SERVICE_NAME` with the exact service name on the Railway canvas, e.g. `Gravity_Score`):  
     `https://${{API_SERVICE_NAME.RAILWAY_PUBLIC_DOMAIN}}/v1`  
   - **Before references work:** the API service must have a **generated Railway public URL** (Networking). If `RAILWAY_PUBLIC_DOMAIN` is empty at build time, the value becomes **`https:///v1`** and the Docker build will fail with a hostname error. Until the API has a domain, paste the **full** API HTTPS URL (copy from the API service → Networking).  
   - Or paste the full public API URL if you prefer. **Redeploy** after changing this value so Vite rebakes the bundle.  
5. **Networking:** Service → **Settings** → **Networking** → generate **Public URL** for the terminal. HTTPS is automatic on Railway’s domain.  
6. **CORS:** On **`gravity_api`**, add the terminal’s public origin to **`CORS_ORIGINS`** (comma-separated), e.g. `https://your-terminal.up.railway.app`, then redeploy the API.  
7. **GoDaddy custom domain (optional):** Use **DNS records** only (avoid GoDaddy “forwarding” for the app URL).  
   1. Railway → **Gravity Frontend** (or your UI service) → **Settings** → **Networking** → **Custom Domain** → enter e.g. `app.yourdomain.com` or `www.yourdomain.com`.  
   2. Railway shows the **CNAME** (or **A**) targets to create.  
   3. GoDaddy → **My Products** → your domain → **DNS** → **Add** the exact **host** (often `app` or `www`) and **points to** value Railway gave you.  
   4. Wait for Railway to verify (can take a few minutes). HTTPS certificates are issued by Railway after verification.  
   5. Add the **final https://…** UI origin to **`CORS_ORIGINS`** on the API and redeploy the API.  
8. **SPA routing:** This image uses **`serve -s`**, which serves `index.html` for unknown paths—no extra Railway SPA config required for client-side routes.

**Find your API base URL (not stored in Git):** Log in, then **link** this folder to your Railway project, then run the helper. If **`railway login`** fails in a terminal without a working browser (e.g. Cursor, SSH), use **`railway login --browserless`**: the CLI prints a **URL and pairing code**; open the URL on **any** device, enter the code, then return to the terminal.

Run **one line at a time** (do not paste whole blocks with `#` comment lines if your zsh has **interactivecomments** off, or you will see `command not found: #`).

```bash
cd /path/to/Gravity_Score
railway login --browserless
railway link
bash scripts/railway-print-api-base.sh
```

Optional (replace with your real API service name from the Railway canvas):

```bash
bash scripts/railway-print-api-base.sh my-api-service-name
```

If the script exits with **“Not linked to a project”**, `railway link` did not finish or was never run in this directory.

Then set **`VITE_API_URL`** on the **terminal** service to `https://<that-host>/v1` (or without `/v1`; the app normalizes it).

**Local Docker check**

```bash
cd gravity-terminal
docker build --build-arg VITE_API_URL=https://your-api.example.com/v1 -t gravity-terminal:prod .
docker run --rm -p 8080:8080 -e PORT=8080 gravity-terminal:prod
```

#### Vercel (alternative)

Import the repo, set project **Root Directory** to `gravity-terminal`, add env **`VITE_API_URL`**, and deploy. `vercel.json` adds SPA fallback rewrites.

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
