# Gravity Partner API — Developer guide (Ecosystem OS)

This document is for **Ecosystem OS developers** who need to display **Gravity Scores** and **Impact Scores** for athletes on their sites or apps.

You read **precomputed scores** from Gravity’s API. You do **not** run scoring or need Gravity Terminal login.

### Score semantics

| Field | Display name | Meaning |
|-------|--------------|---------|
| `gravity_score` | **Gravity Score** | Commercial / market value |
| `impact_score` | **Impact Score** | Winning impact (on-field / on-court contribution) |
| `value_score` | *(deprecated alias)* | Same as `impact_score` — prefer `impact_score` for new integrations |

Optional companions: `impact_sport_percentile`, `impact_score_source` (and deprecated `value_*` mirrors).

---

## 1. What you need from Gravity (before you code)

Ask the Gravity platform team for:

| Item | Example | Notes |
|------|---------|--------|
| **API base URL** | `https://your-gravity-api.up.railway.app` | No trailing slash. Not the `/v1` terminal path. |
| **Partner API key** | `gsk_live_…` | Secret. **One per integration** or one shared for all Ecosystem OS backends. |
| **Confirmation** | Migration applied | Gravity runs DB migration `033_partner_api.sql` on production. |

You will **not** receive:

- `GRAVITY_INTERNAL_API_KEY` (Gravity staff only — creates keys)
- Terminal JWT / user login (for `gravityscore.ai` app only)

---

## 2. Security rules (read this first)

1. **Never put the partner API key in frontend code** (no React `VITE_*`, no browser `fetch` to Gravity with the key).
2. Store the key only on **your server** (env var, secrets manager).
3. Your **frontend** calls **your backend**; your backend calls Gravity.
4. Every public UI must show attribution: **“Powered by Gravity Score”** with a link to https://gravityscore.ai (the API also returns an `attribution` block — use it).

---

## 3. Environment variables (your backend)

Set on **each Ecosystem OS backend** that proxies Gravity:

```env
# Base URL of Gravity API (no trailing slash)
GRAVITY_API_URL=https://your-gravity-api.up.railway.app

# Partner key from Gravity team (secret — server only)
GRAVITY_PARTNER_API_KEY=gsk_live_your_key_here
```

Optional naming: any name works if your code reads the same vars.

---

## 4. Authentication

Every **protected** request:

```http
Authorization: Bearer gsk_live_your_key_here
```

Public (no key):

```http
GET {GRAVITY_API_URL}/v2/partner/health
```

---

## 5. Endpoints

Base path: `{GRAVITY_API_URL}/v2/partner`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Smoke test (no auth) |
| `GET` | `/sports` | **All sports** + codes + counts |
| `GET` | `/athletes` | Search + leaderboard |
| `GET` | `/athletes/resolve` | Match name → athlete |
| `GET` | `/athletes/{athlete_id}` | Profile + latest score |
| `GET` | `/scores/{athlete_id}` | Latest score only |
| `GET` | `/athletes/{athlete_id}/score-history` | Score trend |

Interactive docs (if exposed): `{GRAVITY_API_URL}/docs` → tag **partner**.

---

## 5b. All sports (call this first)

Gravity supports **all** platform sports (college + pro). List them and how to filter:

```http
GET /v2/partner/sports
Authorization: Bearer {GRAVITY_PARTNER_API_KEY}
```

Returns each sport’s `sport` (db slug), `code` (filter code), `display_name`, counts, plus a `codes` array for multi-sport filters.

**Supported filter codes:**

| Code | Sport |
|------|--------|
| `CFB` | College Football |
| `NCAAB` | Men's College Basketball |
| `NCAAW` | Women's College Basketball |
| `NCAA_BASEBALL` | College Baseball |
| `NCAA_VOLLEYBALL` | College Volleyball (W) |
| `NFL` | NFL |
| `NBA` | NBA |
| `WNBA` | WNBA |

You can also use **db slugs** directly: `cfb`, `ncaab_mens`, `nba`, `wnba`, etc.

**Examples:**

```http
GET /v2/partner/athletes?sport=nba&limit=25
GET /v2/partner/athletes?sports=NBA,WNBA,NFL&min_gravity=70
GET /v2/partner/athletes/resolve?name=LeBron&sport=NBA
```

---

### Flow A — You already have `athlete_id`

Use when your DB or URL already stores Gravity’s athlete UUID.

```http
GET /v2/partner/scores/{athlete_id}
Authorization: Bearer {GRAVITY_PARTNER_API_KEY}
```

**Example response:**

```json
{
  "athlete_id": "00000000-0000-4000-8000-000000000001",
  "gravity_score": 87.4,
  "gravity_sport_percentile": 96.0,
  "impact_score": 91.2,
  "impact_sport_percentile": 98.0,
  "impact_score_source": "ml_value_v1",
  "value_score": 91.2,
  "value_sport_percentile": 98.0,
  "value_score_source": "ml_value_v1",
  "components": {
    "brand": 82.1,
    "proof": 75.0,
    "proximity": 88.0,
    "velocity": 91.2,
    "risk": 75.0
  },
  "nil_estimate_usd": {
    "p10": 500000,
    "p50": 1200000,
    "p90": 2500000
  },
  "confidence": 0.78,
  "model_version": "athlete_v2",
  "score_tier": 1,
  "fallback_kind": null,
  "fallback_used": false,
  "quality": null,
  "gravity_source": "commercial_ml",
  "calculated_at": "2026-06-28T12:00:00Z",
  "attribution": {
    "text": "Powered by Gravity Score",
    "url": "https://gravityscore.ai",
    "profile_url": "https://gravityscore.ai/athletes/{athlete_id}"
  }
}
```

`gravity_score` is commercial/market value. `impact_score` is winning impact (primary public field; `value_score` is a deprecated alias for one release).

### Score quality (high / mid / low)

Partners should label Gravity Score confidence from scoring-stack metadata:

| Field | Meaning |
|-------|---------|
| `score_tier` | `1` = production model (**high**); `2` = mid fallback; `3+` = low |
| `fallback_kind` | e.g. `heuristic_gravity_v1`, `ml_composite` (**mid**); `commercial_viability`, `composite_fallback` (**low**) |
| `fallback_used` | `false` when model-scored |
| `quality` | Partner dollar-confidence quality (`low`, `moderate`, `beta_rank_only`, …) |
| `gravity_source` | e.g. `commercial_ml`, `commercial_viability`, `commercial_bpxvr` |
| `model_version` | Bundle / scorer version string |
| `confidence` | 0–1 numeric confidence (fallback when tier fields absent) |

`components.risk` is a **safety-style** score (higher = safer), not raw internal risk.

---

### Flow B — You know name (+ optional school)

**Step 1 — Resolve**

```http
GET /v2/partner/athletes/resolve?name=Arch Manning&school=Texas&sport=cfb
Authorization: Bearer {GRAVITY_PARTNER_API_KEY}
```

Pick `athlete_id` from `matches[]`.

**Step 2 — Score** (same as Flow A)

```http
GET /v2/partner/scores/{athlete_id}
```

---

### Flow C — Search / autocomplete / leaderboard

```http
GET /v2/partner/athletes?q=Manning&limit=10
GET /v2/partner/athletes?sport=cfb&min_gravity=80&sort_by=gravity_score&limit=50
Authorization: Bearer {GRAVITY_PARTNER_API_KEY}
```

**Query parameters (`/athletes`):**

| Param | Description |
|-------|-------------|
| `q` | Name search (substring) |
| `sport` | Single sport: db slug (`cfb`, `nba`) or code (`CFB`, `NBA`) |
| `sports` | Multi: `CFB,NCAAB,NBA,NFL,WNBA,NCAA_BASEBALL,NCAA_VOLLEYBALL` |
| `school` | School name (substring) |
| `conference` | Conference (substring) |
| `min_gravity` / `max_gravity` | Filter by score |
| `sort_by` | `gravity_score`, `brand_score`, `name`, … |
| `sort_dir` | `desc` or `asc` |
| `limit` | Max 100 (default 25) |
| `offset` | Pagination |

Response shape:

```json
{
  "athletes": [ { "athlete_id", "name", "school", "gravity_score", "impact_score", "components", ... } ],
  "total": 42,
  "returned": 10,
  "offset": 0,
  "limit": 10,
  "attribution": { "text", "url" }
}
```

---

### Flow D — Score history (charts)

```http
GET /v2/partner/athletes/{athlete_id}/score-history?weeks=12
Authorization: Bearer {GRAVITY_PARTNER_API_KEY}
```

---

## 7. Recommended architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│ Ecosystem OS    │     │ Your backend         │     │ Gravity API     │
│ (browser/app)   │────▶│ holds PARTNER_KEY    │────▶│ /v2/partner/... │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
   no Gravity key          server-side only              read-only scores
```

**Example — minimal proxy route (Node / Express):**

```javascript
const GRAVITY_BASE = process.env.GRAVITY_API_URL;
const PARTNER_KEY = process.env.GRAVITY_PARTNER_API_KEY;

async function gravityFetch(path) {
  const res = await fetch(`${GRAVITY_BASE}${path}`, {
    headers: { Authorization: `Bearer ${PARTNER_KEY}` },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.detail || res.statusText);
    err.status = res.status;
    throw err;
  }
  return body;
}

// Athlete page — you have athlete_id
app.get("/api/gravity/score/:athleteId", async (req, res) => {
  try {
    const data = await gravityFetch(`/v2/partner/scores/${req.params.athleteId}`);
    res.json(data);
  } catch (e) {
    res.status(e.status || 500).json({ error: e.message });
  }
});

// Search — name lookup
app.get("/api/gravity/search", async (req, res) => {
  const q = new URLSearchParams(req.query).toString();
  try {
    const data = await gravityFetch(`/v2/partner/athletes?${q}`);
    res.json(data);
  } catch (e) {
    res.status(e.status || 500).json({ error: e.message });
  }
});
```

**Frontend:**

```javascript
const score = await fetch(`/api/gravity/score/${athleteId}`).then((r) => r.json());
// Display score.gravity_score (commercial) and score.impact_score (winning impact)
// plus score.attribution
```

---

## 8. `curl` smoke tests

Replace `API` and `KEY`:

```bash
export API="https://your-gravity-api.up.railway.app"
export KEY="gsk_live_your_key_here"

# No auth
curl -s "$API/v2/partner/health" | jq .

# Search
curl -s -H "Authorization: Bearer $KEY" \
  "$API/v2/partner/athletes?q=Manning&limit=3" | jq .

# Resolve
curl -s -H "Authorization: Bearer $KEY" \
  "$API/v2/partner/athletes/resolve?name=Arch Manning&school=Texas" | jq .

# Score (replace ATHLETE_ID)
curl -s -H "Authorization: Bearer $KEY" \
  "$API/v2/partner/scores/ATHLETE_ID" | jq .
```

---

## 9. Errors

| HTTP | Meaning | What to do |
|------|---------|------------|
| `401` | Missing Bearer token | Add `Authorization` header |
| `403` | Invalid or revoked key | Ask Gravity for a new key |
| `404` | Athlete or score not found | Check `athlete_id`; athlete may have no score yet |
| `429` | Rate limit | Cache on your backend; retry after 60s |
| `503` | API not configured | Gravity team: keys / migration / deploy |

Error body is usually JSON: `{ "detail": "..." }`.

---

## 10. Rate limits

- Default: **120 requests/minute** per partner key (Gravity may set higher for Ecosystem OS).
- Limits are per key across all your servers sharing that key.
- **Cache** scores on your side (e.g. 5–15 minutes) for popular athlete pages.

---

## 11. Attribution (required)

When showing Gravity scores publicly:

- Show text: **Powered by Gravity Score**
- Link to: https://gravityscore.ai
- Optional: link `attribution.profile_url` to the athlete on Gravity
- Label **Gravity Score** for `gravity_score` and **Impact Score** for `impact_score`

---

## 12. What you should NOT call

| Do not use | Why |
|------------|-----|
| `/v1/athletes` without partner key | Terminal/product API; different auth and fuller payloads |
| `/v1/scores/v2/athletes/{id}` | Internal scoring trigger; requires `X-Gravity-Internal-Key` |
| `gravity-ml` `/score/athlete` | Runs ML inference; not for read-only display |
| Partner key in browser | Security risk |

---

## 13. Checklist for go-live

- [ ] Received `GRAVITY_API_URL` and `GRAVITY_PARTNER_API_KEY` from Gravity team
- [ ] Keys stored in server secrets only (not frontend env)
- [ ] Backend proxy routes implemented
- [ ] `curl` health + search + score succeed
- [ ] Attribution visible in UI
- [ ] 404 handled when athlete has no score
- [ ] Caching considered for high traffic pages

---

## 14. Support

- **API down / 503:** Gravity platform / DevOps
- **New key or higher rate limit:** Gravity platform team
- **Wrong or missing scores:** Gravity data team (scores are precomputed; you cannot force recalc via partner API)

---

## Quick reference

```text
Health:     GET  {API}/v2/partner/health
Sports:     GET  {API}/v2/partner/sports
Search:     GET  {API}/v2/partner/athletes?q=...&sport=nba  OR  &sports=NBA,WNBA
Resolve:    GET  {API}/v2/partner/athletes/resolve?name=...&school=...
Profile:    GET  {API}/v2/partner/athletes/{id}
Score:      GET  {API}/v2/partner/scores/{id}
History:    GET  {API}/v2/partner/athletes/{id}/score-history?weeks=12

Auth:       Authorization: Bearer {GRAVITY_PARTNER_API_KEY}
```
