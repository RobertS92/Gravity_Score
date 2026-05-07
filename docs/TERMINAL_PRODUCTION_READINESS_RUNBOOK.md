# Terminal Production Readiness Runbook

## Deployment verification

- Confirm Railway frontend service has `VITE_API_URL` pointing to the active API `/v1` host.
- Confirm active API service exposes `/health` and `/v1/auth/health`.
- Confirm deployed service repo root/subdir matches expected `gravity-terminal` and `gravity_api`.
- Confirm no stale service is still receiving production traffic.

## Security verification (proxy-only AI)

- Frontend runtime vars:
  - `VITE_AGENT_USE_PROXY=true`
  - `VITE_ANTHROPIC_API_KEY` unset
- Validate browser network calls hit only `/v1/agent/complete` or `/v1/agent/stream`.
- Validate no direct requests to Anthropic from browser in production.

## Onboarding verification

- Register new user.
- Complete onboarding as school or collective with org name.
- Verify `GET /v1/user/preferences` returns `onboarding_completed_at`.
- Verify `GET /v1/auth/me` includes `organization_id` when onboarding org is provided.

## Data integrity verification

- Spot-check athlete detail:
  - `gravity_delta_30d` tracks historical baseline, not prior row only.
  - Comparables table label shows `GS DELTA`.
  - NIL valuation panel does not show placeholder `30D: —`.
- Spot-check feed:
  - categories `TRANSFER`, `INJURY`, `RECRUITING`, `SCORE`, `ROSTER`, `SOCIAL`, `RANKING` render tags.
- Spot-check school index favorites:
  - missing `team_id` shows disabled star with tooltip.
- Spot-check BPXVR panel:
  - when SHAP is missing, UI shows `Attribution unavailable`.

## Reliability verification

- Trigger a forced render error in a child panel and confirm UI contains it via error boundary.
- Fill localStorage with many athlete bundle entries and confirm oldest bundles are evicted.
- Validate Gravity AI conversation cache never persists more than 20 threads.
- Run score sync and verify `score_alerts` rows are created for watched athletes when thresholds hit.
