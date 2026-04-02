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

## What remains in this repo

- **`gravity/`** — rule-based **data pipeline**, **scoring**, **valuation** helpers, **NIL stubs**, DB models, packs.
- **`gravity_api/`** — FastAPI app, agents, routers, DB access; **jobs** under `gravity_api/jobs/` are placeholders until they call **gravity-scrapers** (and optionally **gravity-ml**).
- **`railway-service/`** — Deployable API; **CrawlerService** is a stub; **ScraperService** uses the in-package **NIL stub** (`gravity.nil.ConnectorOrchestrator`) until wired to **gravity-scrapers** over HTTP.

## Integrating

1. Run collection in **gravity-scrapers** and write results to Postgres (or object storage) using the same schema as `migrations/001_gravity_nil_terminal.sql`, **or**
2. Implement HTTP clients in `gravity_api/jobs/*.py` and Railway `ScraperService` against **gravity-scrapers**’ API contract.
3. For learned scores or imputation, consume **gravity-ml** artifacts or its inference API as documented in that repo.

Historical markdown files in the repo root may still mention removed paths (`gravity/ml_imputer.py`, `nfl_gravity/`, etc.); treat them as archive only.
