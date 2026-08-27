# Spec Bible — Partner Honest Deal Pricing + Regional / Local Opportunities

**Status:** Active development bible  
**Owner:** Gravity platform (API + scoring governance)  
**Consumer:** Ecos OS (and other partners) via Partner API only  
**Date:** 2026-08-04  
**Related:** Ecos Sprint 2 brief (Honest Deal Pricing + Regional Gravity), milestones 01–06, migration `036_scoped_deal_pricing_governance.sql`

---

## 0. Product intent

Ship two partner-consumable capabilities without:

1. Letting Ecos invent scores, confidence tiers, or midpoints Gravity did not return.
2. Recomputing or “region-adjusting” national Gravity Score on the partner side.
3. Presenting uncalibrated prior guidance as empirically calibrated confidence.

| Feature | Partner job-to-be-done |
|---------|------------------------|
| **A. Honest scoped deal pricing** | Price brand activations / packages by commercial scope with governance fields intact |
| **B. Local & regional opportunities** | Find local and regional brand/deal opportunities for an athlete (and market-scoped athlete supply) |

---

## 1. Standing rules (non-negotiable)

1. **Gravity is the scoring authority.** Partners read precomputed / server-computed outputs. No partner-side rescore, blend, or regional multiplier on `gravity_score`.
2. **API keys server-side only.** Never `NEXT_PUBLIC_*` / client bundles.
3. **Never render a number the API did not return.** No interpolation, derived midpoints, or scope averaging by the client.
4. **Never invent governance.** `readiness`, `qualified_transactions`, and measured-error `confidence` display exactly as served or not at all.
5. **National vs regional scores stay distinct.** If a regional Gravity Score is ever shipped, it is a separate field with its own `model_version` — never a silent overwrite of `gravity_score`.
6. **Opportunities are not past deals.** `verified_deal_transactions` / `athlete_nil_deals` are outcomes or calibration evidence, not open RFPs.
7. **One reviewable diff per task** where practical; TypeScript/Python typed; no `any` in new partner client contracts.

---

## 2. Locked decisions (from product thread)

| ID | Decision | Lock |
|----|----------|------|
| D1 | “Regional Gravity” for this partner ask is **not** Ecos-side school→region leaderboard over national scores as the product. Commercial intent is **local/regional opportunity discovery**. | Locked |
| D1b | **Do not** ship a client-side or partner-side recomputed regional Gravity Score as a temporary hack. A true per-region Gravity Score is a future Gravity scoring project (holdout + case-study review). | Locked |
| D1c | v1 opportunities are **geo-scoped fit / opportunity matching**, labeled honestly (`inferred_regional_fit` until a live opportunity inventory exists). | Locked pending inventory answer (§11) |
| D2 | Deal scopes are exactly the five enum values in migration 036 / `deal_scope_pricing.DEAL_SCOPES`. | Locked |
| D3 | Partner deal pricing reuses `price_all_deal_scopes` + the same DB count/calibration queries as CSC — not full CSC reports. | Locked |
| D4 | `nil_estimate_usd` on scores remains the **annual NIL estimate band**, not activation deal guidance. Docs must say so. | Locked |

---

## 3. Feature A — Honest scoped deal pricing

### 3.1 Endpoint

```http
GET /v2/partner/athletes/{athlete_id}/deal-pricing
Authorization: Bearer {GRAVITY_PARTNER_API_KEY}
```

**Auth scope:** `pricing:read` (new). Keys with only `scores:read` do **not** get pricing.

Optional query:

| Param | Default | Notes |
|-------|---------|-------|
| `scope` | omitted | If set, must be one of the five scopes; response still includes full `deal_scopes` map so clients can disable missing scopes. Prefer always returning all scopes. |

### 3.2 Response contract (verbatim field names)

```json
{
  "athlete_id": "uuid",
  "annual_nil_benchmark": 1200000.0,
  "annual_nil_benchmark_unit": "annual_usd",
  "deal_scopes": {
    "standard_activation": {
      "scope": "standard_activation",
      "label": "Standard activation",
      "low": 1234.56,
      "mid": 2000.0,
      "high": 3500.0,
      "unit": "per_scope_usd",
      "model_version": "activation_prior_v2",
      "calibrated": false,
      "confidence": "Uncalibrated",
      "basis": "string",
      "qualified_transactions": 0,
      "validation_transactions": 0,
      "empirical_coverage": null,
      "target_coverage": null,
      "median_absolute_percentage_error": null,
      "evaluated_through": null,
      "readiness": "insufficient_data"
    }
  },
  "signals_used": {
    "brand_score": 82.0,
    "proof_score": 75.0,
    "exposure_score": 88.0,
    "velocity_score": 91.0,
    "risk_score": 25.0
  },
  "calculated_at": "ISO-8601 or null",
  "attribution": {
    "text": "Powered by Gravity Score",
    "url": "https://gravityscore.ai",
    "profile_url": "https://gravityscore.ai/athletes/{id}"
  }
}
```

### 3.3 Enums & nullability

| Field | Values / nullability |
|-------|----------------------|
| `scope` | `standard_activation` \| `season_partnership` \| `collective_package` \| `group_licensing` \| `revenue_sharing` |
| `readiness` | `insufficient_data` \| `pilot` \| `production` — **required on every scope object** when pricing succeeds |
| `confidence` | `High` \| `Moderate` \| `Low` \| `Uncalibrated` — measured-error tier; `Uncalibrated` when not calibrated |
| `low` / `mid` / `high` | `number \| null` — null when annual benchmark unavailable |
| `empirical_coverage`, `target_coverage`, `median_absolute_percentage_error`, `evaluated_through` | `number/string \| null` |
| `annual_nil_benchmark` | `number \| null` |

**No defaulting of missing readiness to a fake state.** If the pricing service cannot produce a complete scope object, the whole endpoint fails as `503`/`500` with a clear reason — do not return partial scopes with invented governance.

### 3.4 Readiness display rules (for partner UI docs)

| `readiness` | May show | Must not show |
|-------------|----------|---------------|
| `production` or `pilot` with `calibrated: true` | Range, evidence count, confidence as served | Any tier not returned |
| `insufficient_data` or `confidence: "Uncalibrated"` | Range labeled **prior guidance — not empirically calibrated** | Implying measured confidence |
| Endpoint error / missing athlete score | Unavailable reason | Stubbed tier or fabricated range |

### 3.5 Annual vs activation separation

- `annual_nil_benchmark` + unit `annual_usd`
- Per-scope `low/mid/high` + unit `per_scope_usd`
- Response must keep them as sibling fields, never nested so one brackets the other
- Partner guide must state they are **not comparable on one axis**

### 3.6 Implementation plan (Gravity)

1. `gravity_api/services/partner_deal_pricing.py` — load latest score row, compute exposure if needed (parity with CSC signals), fetch transaction counts + calibrations (tolerate missing 036 tables → counts empty, all `Uncalibrated`), call `price_all_deal_scopes`.
2. Route on `partner.py`.
3. Extend `DEFAULT_SCOPES` optionally; new keys may request `pricing:read`.
4. Tests: shape, uncalibrated path, missing athlete 404, unauthorized without scope, conference filter separately.
5. Update `PARTNER_API_ECOSYSTEM_DEV_GUIDE.md`.

### 3.7 Acceptance

- [ ] Live OpenAPI lists the new route *(pending deploy)*
- [x] Response includes all five scopes with governance fields
- [x] Uncalibrated scopes return `confidence: "Uncalibrated"` and `readiness: "insufficient_data"` when evidence gates fail
- [x] No selected-scope default forced on partners
- [x] Unit tests pass
- [x] Guide documents honesty rules for Ecos

---

## 4. Feature B — Local & regional opportunities

### 4.1 Product definition

Help partners find:

1. **Local opportunities** for an athlete (home market / school market).
2. **Regional opportunities** for an athlete (broader commercial region).
3. Optionally: athletes suitable for a brand targeting a region (invert of Brand Match) — phase 2.

This is **not** a regional Gravity Score. Ranking still uses national `gravity_score` plus geo/category fit metadata.

### 4.2 Endpoint (target)

```http
GET /v2/partner/athletes/{athlete_id}/opportunities
  ?market_scope=local|regional|national
  &limit=25
Authorization: Bearer …
Scope: opportunities:read
```

### 4.3 Response contract (target)

```json
{
  "athlete_id": "uuid",
  "athlete_markets": {
    "local": { "home_state": "TX", "school": "Texas", "dma_rank": 5 },
    "regional": ["southwest", "national"]
  },
  "opportunities": [
    {
      "opportunity_id": "uuid-or-stable-slug",
      "brand_name": "string",
      "category": "finance",
      "market_scope": "regional",
      "target_geos": ["southwest"],
      "budget_low_usd": 10000,
      "budget_high_usd": 40000,
      "fit_score": 78.5,
      "fit_breakdown": { "geo": 90, "category": 80, "brand": 70, "risk": 75 },
      "match_type": "inferred_regional_fit",
      "status": "catalog",
      "rationale": "string",
      "attribution": { "text": "Powered by Gravity Score", "url": "..." }
    }
  ],
  "unmapped_geo": false,
  "attribution": { "text": "Powered by Gravity Score", "url": "..." }
}
```

### 4.4 Honesty labels

| `match_type` | Meaning |
|--------------|---------|
| `live_opportunity` | Backed by a live opportunity row (`status=open`) |
| `inferred_regional_fit` | Catalog / taxonomy fit only — **not** a live RFP |
| `historical_deal_context` | Past deal context — must not be presented as an open opportunity |

UI must surface `match_type`. Shipping inferred rows as if they were live RFPs is a shipped misrepresentation.

### 4.5 Supporting partner search fixes (ship with B or earlier)

| Change | Why |
|--------|-----|
| Wire `conference` query param on `GET /v2/partner/athletes` | Documented already; search service supports it; router gap |
| Expose `home_state`, `hometown` on athlete detail | Needed for credible local matching |
| Optional `GET /v2/partner/regions` | Lists canonical region tokens partners may filter on |

### 4.6 Region taxonomy (v1)

Reuse Brand Match tokens (lowercase):

`northeast` | `southeast` | `midwest` | `west` | `national`

Mapping: athlete `conference` → `CONFERENCE_REGION_MAP` in `brand_match.py`. Unmapped conferences → `{national}` plus flag `unmapped_geo: true` when no conference/home_state.

**Commercial DMA taxonomy (DFW, Houston, Atlanta)** is **out of v1** unless product supplies a mapping table.

### 4.7 Data dependency (BLOCKING for live opportunities)

| Source | Can back opportunities? |
|--------|-------------------------|
| Brand Match engine | Brand→athlete only; geo via conference |
| `gravity_brands` | Thin catalog; not live RFPs |
| `verified_deal_transactions` | No — calibration outcomes |
| New `brand_opportunities` table | **Yes** — required for `live_opportunity` |

**v1 ship choice (needs product answer §11):**

- **B-lite:** inferred catalog fit only, `match_type=inferred_regional_fit`, seeded partner brand catalog  
- **B-full:** migration for `brand_opportunities` + admin ingest + `live_opportunity`

### 4.8 Acceptance

- [ ] Endpoint returns only labeled match types
- [ ] Grep: no arithmetic on `gravity_score` beyond sort comparison in opportunity modules
- [ ] Attribution present
- [ ] Unmapped geo visible, not dropped
- [ ] Partner guide documents local vs regional vs national

---

## 5. Explicitly out of scope (this update)

- Ecos UI (Deal Studio, KitData, screenshots) — Ecos repo
- Recomputed per-region Gravity Score / holdout redesign
- Stubbing confidence tiers when governance tables empty (show Uncalibrated honestly instead)
- Using CSC LLM narratives on partner pricing
- DMA-level commercial markets without an approved taxonomy table

---

## 6. Auth scopes matrix

| Scope | Endpoints |
|-------|-----------|
| `scores:read` | scores, athlete detail, history |
| `search:read` | athletes search, resolve, sports |
| `pricing:read` | deal-pricing |
| `opportunities:read` | opportunities |

Bootstrap env key (`GRAVITY_PARTNER_API_KEY`) should include the new scopes in dev, or tests override `PartnerContext.scopes`.

---

## 7. Migration / ops checklist

1. Confirm `036_scoped_deal_pricing_governance.sql` applied on the DB the production API uses.
2. If tables missing, pricing still returns priors with `Uncalibrated` / `insufficient_data` (backward compatible), never fake High confidence.
3. Issue Ecos a partner key with `pricing:read` (+ `opportunities:read` when B ships).
4. Smoke: `GET /v2/partner/health`, then deal-pricing for a known athlete.

---

## 8. Test plan

### 8.1 Automated

| Test | Expected |
|------|----------|
| `test_partner_deal_pricing_shape` | All five scopes; governance fields present |
| `test_partner_deal_pricing_uncalibrated_without_evidence` | `confidence == Uncalibrated`, `readiness == insufficient_data` |
| `test_partner_deal_pricing_requires_scope` | 403 without `pricing:read` |
| `test_partner_deal_pricing_unknown_athlete` | 404 |
| `test_partner_athletes_conference_filter` | Conference param passed through to search |
| Opportunities tests (when unblocked) | Labels, no score mutation, unmapped geo |

### 8.2 Failure policy (this engagement)

If the same test fails **more than three times** without the expected outcome → **pause and escalate to human** with failing assertion, last diff, and hypothesis.

### 8.3 Manual / live

- OpenAPI lists routes
- Curl deal-pricing with partner key
- Confirm no deal-pricing fields appear on `/scores/{id}` (avoid conflation)

---

## 9. Sequencing

```
Spec (this doc)
  → A1 partner_deal_pricing service
  → A2 partner route + auth
  → A3 tests green
  → A4 conference filter + guide update
  → STOP for §11 opportunity inventory answers
  → B1 opportunities service (lite or full)
  → B2 route + tests + guide
  → Spec checklist pass (circle back)
```

---

## 10. Spec completion checklist (circle-back)

### Feature A

- [x] Service exists and wraps `price_all_deal_scopes` only (`partner_deal_pricing.py`)
- [x] Route added: `GET /v2/partner/athletes/{id}/deal-pricing` (deploy to see in live OpenAPI)
- [x] Auth scope enforced (`pricing:read`)
- [x] Guide updated with honesty rules + annual vs activation
- [x] Tests in §8.1 green (`test_partner_deal_pricing.py` — 18 partner tests passed)
- [x] No selected-scope default in API payload

### Feature B

- [ ] Inventory decision recorded in §11 — **BLOCKED on product answers**
- [ ] Endpoint + labels match §4.3–4.4
- [x] Conference filter wired on partner `/athletes`; `home_state`/`hometown` on athlete detail
- [ ] Guide updated for opportunities endpoint
- [x] Guard: no regional rescore of `gravity_score` (not implemented; correctly deferred)

### Process

- [x] Feature A acceptance checked against code
- [x] Partner guide matches code field names for deal-pricing
- [ ] Open questions in §11 either answered or explicitly deferred

---

## 11. Open questions (STOP — need product answer before B)

1. **Opportunity inventory:** Ship **B-lite** (inferred catalog fit only) now, or wait for a **`brand_opportunities`** table / feed of real open briefs?
2. **Who supplies brand rows for v1?** Gravity-curated seed list, Ecos-provided list, or `gravity_brands` as-is?
3. **Local definition:** `home_state` + school state, or school DMA via `programs`, or both?
4. **Should Ecos’ partner key get `pricing:read` by default** on next key rotation, or opt-in only?

---

## 12. File touch list (expected)

| File | Change |
|------|--------|
| `docs/specs/PARTNER_HONEST_PRICING_AND_REGIONAL_OPPORTUNITIES.md` | This bible |
| `gravity_api/services/partner_deal_pricing.py` | New |
| `gravity_api/routers/partner.py` | Routes + conference param |
| `gravity_api/partner_types.py` | Scope constants |
| `gravity_api/services/partner_api.py` | Optional geo fields on detail |
| `gravity_api/tests/test_partner_deal_pricing.py` | New |
| `gravity_api/tests/test_partner_api.py` | Conference + scope tests |
| `docs/PARTNER_API_ECOSYSTEM_DEV_GUIDE.md` | Contract docs |

---

## 13. Change log

| Date | Note |
|------|------|
| 2026-08-04 | Initial bible from Ecos brief + Gravity recon + product clarification (opportunities, not regional rescore) |
| 2026-08-04 | Feature A implemented in repo: partner deal-pricing service/route/tests + conference filter + guide. Feature B paused on §11. |
