# Scoring pipeline (terminal data)

## Real data vs terminal “mocks”

- **Real data** comes from **gravity-scrapers** (rosters, social, collectors → your Postgres / Supabase) and **gravity-ml** (`POST /score/athlete`, etc.), which your jobs or `gravity_api` persist into `athlete_gravity_scores` / `gravity_scores`. That is the production path.
- **`VITE_USE_MOCKS=true`** in the terminal is **optional**: it only swaps API calls for in-browser fixture handlers so the UI runs **without** a live API or database (useful for isolated frontend work). **Default in `.env.example` is `false`**, so the terminal talks to your real **`VITE_API_URL`** and sees scraper/ML-backed data. There is no requirement to use mocks for a real deployment.

## Apply database migrations (read this if you use Supabase SQL Editor)

- **`apply_all.sh` files are Bash scripts**, not SQL. **Do not paste them into the Supabase SQL editor** — you will get `ERROR: 42601: syntax error at or near "#!/"` because Postgres tries to parse `#!/usr/bin/env bash` as SQL.
- **In the SQL editor:** open and run the contents of each **`*.sql`** file only, in numeric order (`001`, `002`, …).
- **From your laptop/CI:** set `PG_DSN` and run `./migrations/apply_all.sh` or `./supabase/apply_all.sh` in a terminal (requires `psql`).

---

1. **Ingest athletes** — `gravity-scrapers` (or your ETL) upserts `athletes` and related tables.
2. **Score** — `gravity-ml` HTTP `POST /score/athlete` returns `gravity_score`, BPXVR components, **`brand_gravity_score`** (brand–velocity–proof composite), **dollar P10/P50/P90** (from the v2 dollar head when present, else gravity-derived bands), and **`dollar_confidence`**. Persist those columns on `athlete_gravity_scores` (see `migrations/001` + idempotent `002`, or `./migrations/apply_all.sh`).
3. **Company (program) gravity** — `gravity_api` can append a full score row via `POST /v1/scores/athletes/{id}/sync-from-ml` (header `X-Gravity-Internal-Key` + `GRAVITY_INTERNAL_API_KEY`, plus `ML_SERVICE_URL` / `ML_API_KEY`). That call scores the athlete and, when a matching `programs` row exists, calls `POST /score/team` and stores **`company_gravity_score`**. Supabase `gravity_scores` upserts from scrapers forward the same ML fields when present.
4. **Comparables** — After scores exist, run:
   - `python -m gravity_api.jobs.rebuild_comparables` (from repo root with `PYTHONPATH=.`), or
   - `gravity_api.jobs.weekly_refresh.run_weekly_refresh()` which calls `rebuild_comparables_index`.
5. **Terminal** — `gravity-terminal` uses `VITE_API_URL` (with `/v1` auto-appended), `VITE_USE_MOCKS=false`, and optional `VITE_AGENT_USE_PROXY=true` so the agent runs in `gravity_api` with `ANTHROPIC_API_KEY` server-side.

Without scoring + comparables, athlete detail still loads but comparables and score-driven feeds may be sparse.

## Apply database migrations

**Gravity API / terminal (Postgres):** from repo root, `export PG_DSN=...` then run `Gravity_Score/migrations/apply_all.sh` (runs `001` then `002`).

**gravity-scrapers (Supabase or any Postgres):** `export PG_DSN=...` then run `gravity-scrapers/supabase/apply_all.sh` (runs `001`–`006` in order). Or paste each file in the Supabase SQL editor in that order.
