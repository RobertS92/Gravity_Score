# Scrapers & collectors

## Local layout (three repos)

Clone next to each other so paths match **`gravity-platform.code-workspace`** in this repo:

```text
parent/
  Gravity_Score/          # this repo — open gravity-platform.code-workspace from here
  gravity-scrapers/       # git@github.com:RobertS92/gravity-scrapers.git
  gravity-ml/             # git@github.com:RobertS92/gravity-ml.git
```

**Where is the file?** At the **root of this repo**: `gravity-platform.code-workspace` (same level as `README.md` and `requirements.txt`).

**Open it in Cursor:** `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux) → type **Open Workspace from File** → pick `gravity-platform.code-workspace`.  
Or **File → Open Workspace from File…** (wording can vary slightly).

If you **don’t see the file** in the sidebar, you may have opened a subfolder (e.g. only `gravity-terminal/`). Use **File → Open Folder…** on the full `Gravity_Score` repo root, or open the `.code-workspace` via the command palette as above. After a fresh `git clone`, run `git pull` so you have the latest commit that includes this file.

If a sibling folder is missing, the workspace still opens; clone `gravity-scrapers` / `gravity-ml` next to this repo, or remove that folder entry from the JSON.

---

**This repository no longer ships scraper implementations or ML training code.** They live in sibling GitHub repositories:

| Repo | URL | Role |
|------|-----|------|
| **gravity-scrapers** | [github.com/RobertS92/gravity-scrapers](https://github.com/RobertS92/gravity-scrapers) | Rosters, NIL, social, Firecrawl-style collection; expose an HTTP API this monorepo calls |
| **gravity-ml** | [github.com/RobertS92/gravity-ml](https://github.com/RobertS92/gravity-ml) | Model training, checkpoints, inference service (if you deploy one) |

## Environment (wire from Gravity_Score)

Set in `.env` / Railway / hosting (names are suggestions—match whatever those services document):

- `SCRAPERS_SERVICE_URL` — base URL of the deployed **gravity-scrapers** API
- `SCRAPERS_SERVICE_API_KEY` — optional shared secret for scraper calls
- `ML_SERVICE_URL` — optional base URL if **gravity-ml** exposes HTTP inference

Use these in `railway-service` (`ScraperService`) and `gravity_api/jobs/*` when you replace in-process stubs with HTTP clients.

## GitHub Actions (`gravity-scrapers` repo)

Scheduled workflows (**Daily Scrape**, **Weekly Full Scrape**, monitors) call your **deployed** scraper API on Railway (or elsewhere). If **`Weekly Full Scrape`** fails with *RAILWAY_SCRAPER_URL* / exit code 1, configure the **gravity-scrapers** repository on GitHub:

1. **Settings → Secrets and variables → Actions**
2. Add **Repository secret** (or **Variable**) **`RAILWAY_SCRAPER_URL`**  
   - Value: public HTTPS base URL only, e.g. `https://your-service.up.railway.app`  
   - **No trailing slash**, no `/jobs` suffix (workflows append `/jobs/weekly`, `/jobs/daily`, etc.).
3. Add **Repository secret** **`SCRAPER_API_KEY`**  
   - Same bearer token your FastAPI app checks (`Authorization: Bearer …` — see `gravity-scrapers` `app/auth.py` / `README.md`).

After deploy, confirm in a browser or with `curl` that `https://…/docs` or a health route responds. Manual **Run workflow** will fail fast if secrets are missing until you set them; scheduled runs skip quietly so the Actions tab is not full of red noise.

### Verify daily / weekly actually did work (not just “8 seconds on GitHub”)

**Why GitHub finishes in seconds:** The Actions workflow only sends `POST …/jobs/daily` or `POST …/jobs/weekly`. The FastAPI handlers **enqueue** work with `BackgroundTasks` and immediately return `{"status":"started",…}`. The real scrape runs **on Railway** after the HTTP response.

**Fast “success” with no data usually means one of:**

1. **`athletes` is empty** — Weekly selects all rows; Daily builds a batch from `gravity_scores` / `athletes` / events. **Zero athletes → job completes in seconds** with `processed_count = 0` (still “success”).
2. **Background task errors** — Check **Railway → gravity-scrapers → Logs** for tracebacks after the POST time.
3. **Supabase env wrong on Railway** — `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` missing or wrong → `_create_job` or queries fail (see logs).

**Where to check (in order):**

| Where | What to look for |
|--------|------------------|
| **Supabase → Table `scraper_jobs`** | Latest rows: `job_type` = `daily_vip_update` or `weekly_full_scrape`, `status` = `completed` / `failed`, **`processed_count`**, **`failed_count`**, `started_at` / `completed_at`. |
| **Supabase → `raw_athlete_data`** | New rows after the job window; `scraped_at` moving forward. |
| **Supabase → `athletes`** | `last_scraped_at` updating for rows that were scraped. |
| **Railway logs** | Lines like `Starting daily job`, `Scraping <name>`, `Daily job done. Processed: …`. |
| **HTTP** | `GET <RAILWAY_URL>/jobs/status` with header `Authorization: Bearer <SCRAPER_API_KEY>` — same data as the table (see `gravity-scrapers` `app/routers/jobs.py`). |

**Local check script** (clone **gravity-scrapers**, set `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in `.env`, then):

```bash
cd gravity-scrapers && python scripts/verify_scraper_jobs.py
```

Prints the last few `scraper_jobs` rows so you can see `processed_count` without opening SQL.

## What remains in this repo

- **`gravity/`** — rule-based **data pipeline**, **scoring**, **valuation** helpers, **NIL stubs**, DB models, packs.
- **`gravity_api/`** — FastAPI app, agents, routers, DB access; **jobs** under `gravity_api/jobs/` are placeholders until they call **gravity-scrapers** (and optionally **gravity-ml**).
- **`railway-service/`** — Deployable API; **CrawlerService** is a stub; **ScraperService** uses the in-package **NIL stub** (`gravity.nil.ConnectorOrchestrator`) until wired to **gravity-scrapers** over HTTP.

## Integrating

1. Run collection in **gravity-scrapers** and write results to Postgres (or object storage) using the same schema as `migrations/001_gravity_nil_terminal.sql`, **or**
2. Implement HTTP clients in `gravity_api/jobs/*.py` and Railway `ScraperService` against **gravity-scrapers**’ API contract.
3. For learned scores or imputation, consume **gravity-ml** artifacts or its inference API as documented in that repo.

Historical markdown files in the repo root may still mention removed paths (`gravity/ml_imputer.py`, `nfl_gravity/`, etc.); treat them as archive only.
