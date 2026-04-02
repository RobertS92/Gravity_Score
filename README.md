# Gravity Score / Gravity NIL Terminal

College-focused NIL intelligence: **CFB**, **MCBB**, PostgreSQL schema, **FastAPI** (`gravity_api/`), and the **gravity-terminal** React UI.

## Quick start

### API
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-gravity-api.txt
export PG_DSN="postgresql://user:pass@host:5432/db"
.venv/bin/python -m uvicorn gravity_api.main:app --reload --port 8000
```

Apply SQL in `migrations/001_gravity_nil_terminal.sql` to your database before using the API.

### Terminal UI
```bash
cd gravity-terminal && npm install && npm run dev
```

Set `VITE_API_URL` (see `.env.example`) if the API is not on `http://localhost:8000`.

### College scrapers (legacy Python pipelines)
- **CFB**: `gravity/cfb_scraper.py`
- **Men’s college basketball**: `gravity/ncaab_scraper.py`
- **WNBA** (optional): `gravity/wnba_scraper.py`

**Removed:** `gravity/nfl_scraper.py`, `gravity/nba_scraper.py`, `gravity/unified_scraper.py` — use college pipelines and `gravity_api` above.

### Environment
```bash
export FIRECRAWL_API_KEY="fc-…"   # scraping / enrichment
export ANTHROPIC_API_KEY="sk-ant-…"  # agentic `/v1/query`
```

Optional: `OPENAI_API_KEY`, tuning vars (`MAX_CONCURRENT_PLAYERS`, etc.) as needed for `gravity/` collectors.

## Layout

| Path | Role |
|------|------|
| `gravity_api/` | FastAPI: athletes, scores, query agent, watchlist stubs, jobs |
| `gravity-terminal/` | Vite + React terminal |
| `gravity/` | Scrapers, NIL connectors, data pipeline, scoring helpers |
| `migrations/` | Postgres schema for NIL terminal |
| `railway-service/` | Deployed scrapers/crawlers service (college + NIL orchestrator) |
| `nfl_gravity/` | Separate NFL-focused package (tests still reference it) |

## Docs

- `docs/SCRAPER_EXHAUSTIVE.md` — scraper inventory (note: NFL/NBA CLI files listed there are removed; prefer CFB/MCBB and `gravity_api`).
- Other `*.md` files in the repo may be historical; trust `README.md`, `migrations/`, and `gravity_api/` for the current NIL-terminal path.

## License & credits

See repository history for authors and dependencies (Firecrawl, Anthropic, etc.).
