# Gravity NIL Intelligence Terminal

React (Vite + TypeScript) UI for **Gravity** buyer workflows: CSC deal assessment, agent watchlist/program comparison, brand matching, and score alerts. It talks to **`gravity_api`** (`VITE_API_URL`).

## Product spec

- **[docs/NIL_APPLICATIONS.md](../docs/NIL_APPLICATIONS.md)** — buyer workflows, outputs, commercial framing  
- **[docs/GRAVITY_UNIFIED_SPEC.md](../docs/GRAVITY_UNIFIED_SPEC.md)** — formula vs neural net, scrapers, Velocity/time-series, data sources, terminal architecture (single system reference)

## Environment

Copy `.env.example` to `.env`:

- `VITE_API_URL` — API host; `/v1` is appended automatically if the URL does not already end with `/v1`.
- `VITE_USE_MOCKS` — default `false` for production-like runs; set `true` for local fixture-only demos.
- `VITE_AGENT_USE_PROXY` — set `true` to call `POST /v1/agent/complete` (Anthropic key stays on the API via `ANTHROPIC_API_KEY`).
- `VITE_API_BEARER_TOKEN` — optional static Bearer; `localStorage` session token (`gravity_access_token`) wins when set after login.
- `VITE_TERMINAL_USER_ID` — optional fallback UUID when no JWT session exists (watchlist/alerts `?user_id=`).
- **Auth** — create a row in `user_accounts`, set `JWT_SECRET` on the API, `POST /v1/auth/login` with `{ "email": "..." }`, store `access_token` (e.g. via a small login UI or DevTools) as `gravity_access_token`.

## Run locally

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Views (main panel)

| View | Application |
|------|-------------|
| Home | Application overview |
| Deal assessment | CSC / NIL Go reports; category deal ceilings |
| Program comparison | Transfer / school NIL environment |
| Brand match | Campaign shortlists |
| Watchlist | Agent clients |
| Alerts | Score monitoring |
| Athlete profile | Detail + history + report CTA |
| Market scan | Table browse (`/v1/athletes`) |
