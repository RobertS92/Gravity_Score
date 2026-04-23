# Gravity — Roster Cap Intelligence & Data Integrity Design
**Feature Design Document**  
Covers: CapIQ (Roster Cap Intelligence), School Data Input & Verification, Scraper Architecture Overhaul

---

## Part 1: What We're Building

Three interconnected systems:

1. **Roster Cap Intelligence ("CapIQ")** — A financial planning module inside the NIL Intelligence Terminal for schools, athletic departments, and NIL collectives. Power 5 CFB and NCAAB/NCAAW only.

2. **School Data Input & Verification Layer** — Allows school users to input athlete data, correct scraped data, and have corrections flow through verification before affecting the canonical Gravity network score.

3. **Scraper Architecture Overhaul** — Rebuild the scraper pipeline modeled after a low-latency prop shop: event-driven, tick-aware, prioritized queues, delta detection, and circuit breakers.

---

## Part 2: Roster Cap Intelligence (CapIQ)

### 2.1 What It Does

Gives school-side users (ADs, NIL collective directors, coaches) a financial planning layer on top of their Gravity-powered roster. They can see cap utilization in real time, model roster scenarios with NIL deal structures, and see a 5-year forward financial projection — all anchored to Gravity Scores so the financial decisions are informed by athlete quality signals, not just dollar amounts.

### 2.2 Users & Permissions

| Role | Access |
|---|---|
| **Coach / Sport GM** | Their sport only. Can view roster financials, run scenarios, input player comp, flag data corrections. Cannot see other sports or set cap limits. |
| **AD / Collective Director (Admin)** | All sports. Sets cap limits and allocations. Promotes scenarios to official. Views multi-sport rollup. |

Sport scope is enforced at the API level via `org_id + sport` scoping on every query. There is no cross-sport data leakage between roles.

### 2.3 Database Schema — New Tables

Three new tables. Everything else builds on existing `athletes`, `gravity_scores`, and `rosters`.

```sql
-- Budget envelope per org per sport per year
CREATE TABLE nil_budgets (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id),
  sport           TEXT NOT NULL CHECK (sport IN ('CFB', 'NCAAB', 'NCAAW')),
  fiscal_year     INT NOT NULL,  -- e.g. 2025 = July 2025 - June 2026
  total_allocation BIGINT NOT NULL,  -- in cents
  notes           TEXT,
  set_by          UUID REFERENCES users(id),
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE (org_id, sport, fiscal_year)
);

-- Financial commitment per athlete per roster (official or scenario)
CREATE TABLE nil_roster_contracts (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                    UUID NOT NULL REFERENCES organizations(id),
  athlete_id                UUID NOT NULL REFERENCES athletes(id),
  sport                     TEXT NOT NULL,
  base_comp                 BIGINT NOT NULL,           -- cents, annual
  incentives                JSONB DEFAULT '[]',        -- [{desc, amount, likelihood_pct}]
  third_party_flag          BOOLEAN DEFAULT false,     -- does NOT count against cap
  payment_schedule          JSONB DEFAULT '{}',        -- monthly payment timing (July-June)
  fiscal_year_start         INT NOT NULL,
  eligibility_years_remaining INT,
  status                    TEXT DEFAULT 'active' CHECK (status IN ('active', 'expired', 'draft')),
  scenario_id               UUID REFERENCES nil_scenarios(id),  -- NULL = official roster
  created_by                UUID REFERENCES users(id),
  created_at                TIMESTAMPTZ DEFAULT now(),
  updated_at                TIMESTAMPTZ DEFAULT now()
);

-- Named what-if roster configurations
CREATE TABLE nil_scenarios (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                  UUID NOT NULL REFERENCES organizations(id),
  sport                   TEXT NOT NULL,
  name                    TEXT NOT NULL,
  base_roster_id          UUID,                        -- optional: duplicated from
  status                  TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'promoted')),
  aggregate_gravity_score FLOAT,                       -- cached from gravity-ml after compare
  total_committed         BIGINT,                      -- cached sum in cents
  total_risk_exposure     BIGINT,                      -- incentives at 100% likelihood
  created_by              UUID REFERENCES users(id),
  promoted_at             TIMESTAMPTZ,
  promoted_by             UUID REFERENCES users(id),
  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now()
);

-- Audit log (written to on every mutation — UI built later)
CREATE TABLE cap_audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL,
  user_id     UUID NOT NULL REFERENCES users(id),
  table_name  TEXT NOT NULL,
  record_id   UUID NOT NULL,
  action      TEXT NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
  old_values  JSONB,
  new_values  JSONB,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

**Key design decision:** `scenario_id IS NULL` = official roster record. `scenario_id IS NOT NULL` = scenario record. Promoting a scenario flips its contracts to `scenario_id = NULL` (after archiving displaced official records). Simple, no duplicated logic.

### 2.4 API Endpoints — New Routes in `gravity_api`

All under `/v1/cap/`, JWT-authenticated, org+sport scoped.

```
-- Budget
GET  /v1/cap/budget/{org_id}/{sport}              List budgets by fiscal year
POST /v1/cap/budget                               Create/update allocation (Admin only)

-- Utilization (computed, not stored)
GET  /v1/cap/utilization/{org_id}/{sport}/{year}  Committed vs available, incentive exposure

-- Contracts (official roster)
GET  /v1/cap/contracts/{org_id}/{sport}           All active official contracts
POST /v1/cap/contracts                            Add contract to official roster
PATCH /v1/cap/contracts/{id}                     Update contract
DELETE /v1/cap/contracts/{id}                    Soft-delete (sets status=expired)

-- Scenarios
GET  /v1/cap/scenarios/{org_id}/{sport}           List scenarios
POST /v1/cap/scenarios                            Create scenario
GET  /v1/cap/scenarios/{id}                       Scenario detail + contracts
POST /v1/cap/scenarios/{id}/contracts             Add/edit contract within scenario
DELETE /v1/cap/scenarios/{id}/contracts/{cid}    Remove player from scenario

-- The power endpoint
GET  /v1/cap/scenarios/{id}/compare               Scenario vs official:
                                                  - Financial delta (cost diff)
                                                  - Gravity Score delta (calls gravity-ml)
                                                  - Risk delta (R component avg)
                                                  - Returns both roster states side-by-side

POST /v1/cap/scenarios/{id}/promote               Promote to official (Admin only)

-- Projections
GET  /v1/cap/outlook/{org_id}/{sport}             5-year financial view:
                                                  - Committed spend by year
                                                  - Roster headcount by year
                                                  - Eligibility expirations
                                                  - Available cap by year

-- Multi-sport rollup (Admin only)
GET  /v1/cap/rollup/{org_id}                      All sports: utilization summary
```

### 2.5 The Compare Endpoint — Core Logic

This is what separates CapIQ from a spreadsheet. When a user compares a scenario to their official roster, the API:

1. Loads the official roster's athlete IDs + their current `gravity_scores` from DB (already computed, no ML call needed for official state)
2. Loads the scenario's athlete IDs — some overlap with official, some are adds/removes
3. For athletes in the scenario NOT in the existing scores table (e.g. portal targets the school is evaluating), calls `POST /score/athlete` on `gravity-ml` to get their scores
4. Computes aggregate Gravity Score for both rosters (weighted average, position-adjusted)
5. Returns:
```json
{
  "official": {
    "athletes": [...],
    "aggregate_gravity": 71.4,
    "total_committed_cents": 4200000,
    "avg_risk_score": 28.1
  },
  "scenario": {
    "athletes": [...],
    "aggregate_gravity": 74.8,
    "total_committed_cents": 5100000,
    "avg_risk_score": 31.6
  },
  "delta": {
    "gravity": +3.4,
    "cost_cents": +900000,
    "risk": +3.5,
    "gravity_per_dollar": "scenario costs $265K per gravity point vs $295K official"
  }
}
```

That last line — **gravity-per-dollar** — is the insight you can't get anywhere else.

### 2.6 Terminal UI — New Views

Two new primary views added to the terminal nav, scoped to authenticated school users:

**Cap Dashboard** (route: `/cap`)
- Utilization ring: Committed / Total allocation, color-coded (green < 80%, yellow 80-95%, red > 95%)
- Third-party tracker (separate ring — doesn't affect cap)
- Year selector → switches all figures to that fiscal year
- Alert banners: over cap, near cap (<5% remaining), underutilized (<50% deployed with >60 days left in cycle)
- Gravity-per-dollar leaderboard for current official roster — ranked list: who is delivering the most Gravity Score per dollar of commitment
- Risk-weighted exposure table: athletes with Risk > 65 and their committed dollars flagged

**Scenario Builder** (route: `/cap/scenarios`)
- List of existing scenarios with status badges
- Create/duplicate scenario
- Roster builder within scenario: search athletes (pulls from Gravity athlete DB), set comp fields, flag third-party
- Live preview panel: as you add/remove athletes, shows running cost total and estimated Gravity delta (uses cached scores for speed, triggers ML call on finalize)
- Compare view: side-by-side official vs scenario with the delta metrics from the compare endpoint
- Promote button (Admin only, requires confirmation modal)

**5-Year Outlook** (sub-view within Cap Dashboard)
- Table: rows = fiscal years (current + 4 forward), columns = committed, incentive exposure, headcount, available cap
- Color coding by cap pressure (green/yellow/red)
- Eligibility expiration markers per year (shows how many current commitments expire)
- Scenario overlay toggle: shows how a selected scenario would change the 5-year picture

---

## Part 3: School Data Input & Verification Layer

### 3.1 The Problem

Scrapers miss data. Athletes have incorrect social handles, stale follower counts, wrong transfer status, missing stats. A school using Gravity may have ground-truth data that the scraper doesn't. They need a way to input and correct it.

But there's a conflict of interest: a school has an incentive to inflate their own athletes' scores. User-submitted data cannot flow directly into the canonical Gravity Score used by the entire network.

### 3.2 Two-Profile Architecture

Every athlete in the system has two score contexts:

**Network Profile** — The canonical Gravity Score. Driven entirely by verified scraper data + platform-validated corrections. This is what everyone on the network sees. Trust level: high.

**Org Profile** — A school's private view of an athlete, enriched with their submitted data. Gravity Score is recomputed using org-submitted fields blended with network data at configurable weights. Only visible to that org. Trust level: org-controlled.

The key rule: **org-submitted data never pollutes the network profile automatically.** It can be promoted to the network profile only through verification.

### 3.3 Verification Pipeline

```
School submits correction/addition
           │
           ▼
  Lands in `athlete_data_submissions` (status = 'pending')
           │
           ├── Auto-verification layer runs:
           │     - Cross-reference ESPN API for identity fields
           │     - Cross-reference Sports Reference for stat fields
           │     - Cross-reference On3 for NIL fields
           │     - Social handle validation (check handle exists, follower count within 20% of scraped)
           │     - Flag fields that contradict verified sources
           │
           ├── If all fields pass auto-verification:
           │     status = 'auto_verified' → merged into network profile with conf boost
           │
           ├── If partial pass:
           │     status = 'partial' → auto-verified fields go to network, flagged fields queue for review
           │
           └── If critical contradiction detected:
                 status = 'flagged' → human review queue, school notified
```

### 3.4 Database Schema — Submissions & Verification

```sql
-- School-submitted athlete data
CREATE TABLE athlete_data_submissions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id      UUID NOT NULL REFERENCES athletes(id),
  org_id          UUID NOT NULL REFERENCES organizations(id),
  submitted_by    UUID NOT NULL REFERENCES users(id),
  fields          JSONB NOT NULL,  -- {field_name: submitted_value, ...}
  source_notes    TEXT,            -- school explains where data came from
  status          TEXT DEFAULT 'pending' 
                  CHECK (status IN ('pending','auto_verified','partial','flagged','rejected','promoted')),
  verification_results JSONB,      -- per-field: {field: {passed, source, delta_pct}}
  reviewed_by     UUID REFERENCES users(id),
  review_notes    TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Org-specific field overrides (the "org profile" layer)
-- These are the fields currently active for an org's private view of an athlete
CREATE TABLE athlete_org_overrides (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id      UUID NOT NULL REFERENCES athletes(id),
  org_id          UUID NOT NULL REFERENCES organizations(id),
  field_name      TEXT NOT NULL,
  network_value   JSONB,           -- what the network currently shows
  org_value       JSONB NOT NULL,  -- what this org sees
  submission_id   UUID REFERENCES athlete_data_submissions(id),
  confidence      FLOAT DEFAULT 0.6,
  is_promoted     BOOLEAN DEFAULT false,  -- true = also in network profile
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE (athlete_id, org_id, field_name)
);

-- Org-specific gravity score (recomputed with org overrides blended in)
CREATE TABLE athlete_org_gravity_scores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id      UUID NOT NULL REFERENCES athletes(id),
  org_id          UUID NOT NULL REFERENCES organizations(id),
  gravity_score   FLOAT NOT NULL,
  brand_score     FLOAT,
  proof_score     FLOAT,
  proximity_score FLOAT,
  velocity_score  FLOAT,
  risk_score      FLOAT,
  blend_config    JSONB,           -- which fields came from org vs network
  computed_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE (athlete_id, org_id)
);
```

### 3.5 Blended Scoring Logic

When an org has override fields for an athlete, the ML service needs to know how to blend them. The approach:

The `POST /score/athlete` endpoint in `gravity-ml` already accepts a raw field vector. For org-profile scoring, `gravity_api` constructs the input vector by:

1. Starting with the athlete's network raw fields from `raw_athlete_data`
2. Overlaying `athlete_org_overrides` fields for that org, weighted by their confidence score
3. Sending the blended vector to `gravity-ml` with a flag: `{"org_blend": true, "org_id": "..."}`
4. Storing the result in `athlete_org_gravity_scores`

The org-profile score is clearly labeled in the UI: **"Org-Enhanced Score"** with a breakdown showing which fields came from their submissions vs. the network.

### 3.6 What Schools Can Submit

| Field Category | Auto-Verifiable | Notes |
|---|---|---|
| Transfer portal status | Yes — ESPN transfer tracker | High confidence if matches |
| Injury status | Partial — ESPN injury reports | Flagged if contradicts ESPN |
| Social handles | Yes — direct platform lookup | Must resolve to real account |
| Social follower counts | Yes — within 20% threshold | Outside 20% → flagged |
| Stats corrections | Yes — Sports Reference cross-ref | Contradictions → human review |
| NIL deal values | No — not auto-verifiable | Always queued for review |
| Recruiting rank corrections | Yes — On3/247 cross-ref | |
| Eligibility years remaining | Partial — ESPN roster | |
| New athlete (not in system) | Partial identity check | Full submission required |

### 3.7 Adding a New Athlete (Not Found by Scrapers)

Schools can add athletes completely missing from the system. This is important for walk-ons, JUCO transfers, or athletes the scraper missed.

Flow:
1. School submits: name, position, sport, ESPN ID (optional), stats, social handles
2. Auto-verification attempts ESPN ID resolution
3. If ESPN ID resolves → athlete created in `athletes` table with `source = 'school_submitted'`, `is_verified = false`
4. Scraper is triggered to run enrichment on the new athlete on next cycle
5. Gravity Score computed using available data + confidence penalty (0.75 base confidence for unverified athletes)
6. Athlete is flagged `is_verified = false` in UI with a "Pending Verification" badge
7. Once scraper enriches and data matches submission within thresholds → `is_verified = true`, penalty removed

---

## Part 4: Scraper Architecture — Prop Shop Model

### 4.1 The Mental Model

A low-latency prop shop doesn't poll markets on a timer. It:
- Maintains **persistent connections** to data feeds
- Processes **events** (price changes, news, order flow) as they arrive
- Prioritizes signals by **alpha decay** — some signals go stale in seconds, others in hours
- Has **circuit breakers** that cut off bad feeds without taking down the system
- Tracks **position** (what it knows) and updates on **deltas** (only what changed)
- Has tiered processing: ultra-low latency path for critical signals, batch path for bulk enrichment

Gravity's scrapers should work the same way. Different data has different staleness tolerance:

| Signal Type | Staleness Tolerance | Prop Shop Equivalent |
|---|---|---|
| Transfer portal entries | Minutes to hours | Breaking news feed |
| Injury reports | Hours | Risk event |
| Social follower counts | 24-48 hours | Slow-moving price |
| Season stats | Weekly (in-season) | Fundamental data |
| Historical stats | Monthly | Static reference data |
| NIL valuations | Daily | Mark-to-market |
| Recruiting ranks | Weekly | Rating update |

### 4.2 Architecture: Event-Driven Pipeline

Replace the current cron-driven full scrape model with a four-tier architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│  TIER 1: FEED WATCHERS (Persistent / Near Real-Time)            │
│  - ESPN Transfer Portal watcher (poll every 5 min)             │
│  - ESPN Injury Report watcher (poll every 15 min)              │
│  - On3 NIL news watcher (poll every 30 min)                    │
│  Outputs: ChangeEvent → Priority Queue                          │
└─────────────────────────────────────────────────────────────────┘
                              │ (ChangeEvents)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 2: PRIORITY QUEUE (Redis Streams or equivalent)           │
│  Priority levels:                                               │
│    P0 — Transfer/injury events (process within 5 min)          │
│    P1 — NIL deal detected (process within 30 min)              │
│    P2 — Social delta > 10% (process within 2 hrs)              │
│    P3 — Scheduled enrichment (process within 24 hrs)           │
│    P4 — Full roster refresh (process weekly)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 3: WORKERS (Stateless, horizontally scalable)             │
│  - Each worker pulls from queue by priority                     │
│  - Executes only the affected collectors (not full scrape)      │
│  - Delta detection: compare new value to stored, skip if same  │
│  - Writes delta to raw_athlete_data                             │
│  - Triggers ML rescore only if delta exceeds threshold          │
│  Circuit breaker per source: 5 consecutive failures → open      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 4: ML RESCORE TRIGGER                                     │
│  - Only fires when field delta > configured threshold           │
│  - Thresholds: followers ±10%, stats ±5%, injury/transfer = any│
│  - Calls gravity-ml POST /score/athlete                         │
│  - Updates gravity_scores table                                 │
│  - Triggers Supabase Realtime notification to terminal          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Delta Detection — No Wasted Compute

Current scrapers re-scrape everything and overwrite. The new model stores a **field-level hash** alongside each raw value:

```sql
-- Add to raw_athlete_data
ALTER TABLE raw_athlete_data ADD COLUMN field_hashes JSONB DEFAULT '{}';
-- {field_name: md5(value)} — updated on every write
-- Worker checks: if md5(new_value) == stored_hash → skip write, skip rescore
```

This means a weekly full scrape only triggers ML rescores for athletes who actually changed. In a stable week, 80%+ of athletes won't have meaningful deltas. This is the core cost and latency win.

### 4.4 Circuit Breakers Per Source

Each data source (ESPN, Sports Reference, On3, Firecrawl, social APIs) has an independent circuit breaker:

```python
class SourceCircuitBreaker:
    def __init__(self, source: str, failure_threshold: int = 5, 
                 recovery_timeout: int = 300):
        self.source = source
        self.failure_count = 0
        self.state = "closed"  # closed=normal, open=failing, half-open=testing
        self.last_failure_time = None
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds

    def call(self, fn, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitOpenError(f"{self.source} circuit open")
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.critical(f"Circuit OPEN: {self.source} — {self.failure_count} consecutive failures")
```

When a circuit opens, that source is skipped for its timeout window. Workers continue processing using cached data + fallback sources. No cascading failure.

### 4.5 Collector Granularity — Targeted Rescapes

Current model: athlete event → re-collect all 5 dimensions (Brand, Proof, Proximity, Velocity, Risk).

New model: event type determines which collectors fire.

```python
COLLECTOR_MAP = {
    "transfer_portal": ["identity", "proximity", "risk"],
    "injury_report":   ["risk", "velocity"],
    "nil_deal":        ["proximity", "brand", "velocity"],
    "social_delta":    ["brand", "velocity"],
    "stat_update":     ["proof", "velocity"],
    "scheduled_full":  ["identity", "brand", "proof", "proximity", "velocity", "risk"],
}
```

A transfer portal event triggers 3 collectors. A social delta triggers 2. Only a scheduled full refresh runs everything. This is the prop shop equivalent of hedging only the legs that moved, not re-hedging the entire book.

### 4.6 Priority Queue Implementation

Use **Redis Streams** (already available if you're on Railway + Redis, or use Supabase's pg_notify as a simpler alternative):

```python
# Worker pull pattern
async def worker_loop(redis_client):
    while True:
        # Read from stream, prioritized
        for priority in ["P0", "P1", "P2", "P3", "P4"]:
            messages = await redis_client.xreadgroup(
                groupname="scraper-workers",
                consumername=f"worker-{socket.gethostname()}",
                streams={f"scraper:{priority}": ">"},
                count=1,
                block=100  # ms — non-blocking poll across priorities
            )
            if messages:
                await process_event(messages[0], priority)
                break  # always drain higher priority first
```

### 4.7 Scraper Service API Changes

Add these endpoints to the `gravity-scrapers` FastAPI service:

```
POST /jobs/athlete/{athlete_id}          Trigger targeted rescrape for one athlete
                                         Body: {"collectors": ["risk", "proximity"]}

POST /jobs/event                         Ingest an external event (transfer, injury)
                                         Body: {"event_type": "transfer_portal",
                                                "athlete_id": "...",
                                                "source": "espn",
                                                "payload": {...}}

GET  /jobs/queue/status                  Queue depth by priority level
GET  /jobs/circuits                      Circuit breaker states per source
POST /jobs/circuits/{source}/reset       Manually reset a circuit (admin)
GET  /jobs/delta-report/{date}           How many athletes changed vs prior day
```

### 4.8 Scheduling — Replacing Cron with Intelligent Scheduling

| Job | Old Approach | New Approach |
|---|---|---|
| Daily top athletes | GitHub Actions cron 2am | Feed watcher P0/P1 events replace this for high-priority athletes |
| Weekly full scrape | GitHub Actions cron Sunday 3am | Still runs as P4 batch, but delta detection means only real changes trigger rescore |
| Transfer portal | Not real-time | Feed watcher polls ESPN transfer tracker every 5 min, emits P0 events |
| Injury reports | Not real-time | Feed watcher polls ESPN injury reports every 15 min, emits P0 events |
| NIL deal detection | Batch | Feed watcher polls On3 news every 30 min, emits P1 events |
| School-submitted data | N/A (new) | Submission triggers P2 targeted scrape for verification cross-reference |

---

## Part 5: Integration — How It All Connects

### 5.1 School Data Input → Scraper → ML → Terminal

```
School submits athlete data correction via Terminal UI
        │
        ▼
gravity_api: POST /v1/data/submit
        │ stores in athlete_data_submissions (status=pending)
        │
        ▼
gravity_api: emits P2 scraper event
        │ {"event_type": "school_submission", "athlete_id": ..., "fields": [...]}
        │
        ▼
gravity-scrapers: targeted rescrape runs affected collectors
        │ cross-references submitted fields against live sources
        │
        ▼
gravity-scrapers: writes verification_results back to athlete_data_submissions
        │ status → auto_verified | partial | flagged
        │
        ├── if auto_verified:
        │     updates raw_athlete_data with new values + confidence
        │     triggers ML rescore via gravity-ml
        │
        └── if flagged:
              queues for human review
              notifies school user via alerts
        │
        ▼
gravity-ml: POST /score/athlete (if data changed)
        │ recomputes network gravity_score
        │ recomputes org_gravity_score (blended with org overrides)
        │
        ▼
Supabase Realtime: pushes score update to terminal
        │
        ▼
Terminal: athlete card updates live, "Score Updated" badge shown
```

### 5.2 CapIQ Scenario → ML → Compare

```
Coach builds scenario in Scenario Builder
        │ adds portal target athlete + comp terms
        │
        ▼
gravity_api: GET /v1/cap/scenarios/{id}/compare
        │
        ├── official roster: load gravity_scores from DB (cached, no ML call)
        │
        ├── scenario roster:
        │     for known athletes → load from gravity_scores
        │     for portal targets not in DB → POST /score/athlete to gravity-ml
        │
        ▼
gravity_api: computes aggregate scores + delta + gravity-per-dollar
        │
        ▼
Terminal: renders Compare panel with full delta breakdown
```

---

## Part 6: Build Sequence

### Phase 1 — Foundation (Weeks 1-3)
- Migrations for `nil_budgets`, `nil_roster_contracts`, `nil_scenarios`, `cap_audit_log`
- Migrations for `athlete_data_submissions`, `athlete_org_overrides`, `athlete_org_gravity_scores`
- `/v1/cap/budget` and `/v1/cap/contracts` endpoints (official roster only)
- `/v1/data/submit` endpoint (store submission, no verification yet)
- Basic Cap Dashboard UI: utilization view, official roster with comp fields
- Audit log writes on every mutation (no UI yet)

### Phase 2 — Scenario Engine (Weeks 4-6)
- `nil_scenarios` CRUD endpoints
- Scenario Builder UI
- Compare endpoint with gravity-ml integration
- Gravity-per-dollar and risk-weighted exposure views
- 5-year outlook computation + UI

### Phase 3 — Verification Layer (Weeks 7-9)
- Auto-verification pipeline: ESPN, Sports Reference, On3 cross-reference per field type
- Verification results written back to `athlete_data_submissions`
- `athlete_org_overrides` management + blended scoring via gravity-ml
- School submission UI in terminal: form per athlete, field-level status indicators
- New athlete submission flow with confidence penalty

### Phase 4 — Scraper Architecture Overhaul (Weeks 10-14)
- Redis Streams setup (or pg_notify fallback)
- Priority queue worker loop
- Circuit breakers per source
- Delta detection (field hashes)
- Feed watchers: ESPN transfer portal, ESPN injuries, On3 NIL news
- COLLECTOR_MAP event routing
- New scraper service endpoints
- Replace GitHub Actions cron with hybrid: feed watchers for P0/P1, keep cron for P4 weekly full

### Phase 5 — Multi-Sport Rollup & Alerts (Weeks 15-16)
- Admin rollup view (CFB + NCAAB side by side)
- Cap Alerts Center: over-cap, near-cap, underutilized, risk exposure
- Eligibility clock alerts (players with 1 year remaining, large commitments)

---

## Part 7: Open Questions to Resolve Before Building

1. **Organization identity**: How are `organizations` created and linked to users? Do schools self-register or does Gravity onboard them? This gates every cap feature.

2. **Cap budget source of truth**: Does the school tell Gravity their total NIL collective budget, or does Gravity infer it? Schools may not want to disclose this. Consider making the budget input optional — if not set, utilization shows as a raw dollar amount with no % calculation.

3. **Portal target athletes**: For scenario modeling, a coach needs to add athletes not on their roster (portal targets). These athletes need to exist in Gravity's DB. What's the flow if a target athlete isn't found? → School submission flow handles this, but needs to be designed as a search-first UX.

4. **Org profile score labeling**: When showing an "Org-Enhanced Score" vs. the "Network Score," the UI language needs to be precise. Schools need to understand that their submissions don't change what other schools see.

5. **Redis vs pg_notify for queue**: Redis Streams is the right call for a prop-shop model. pg_notify is simpler to operate on Railway + Supabase. Decision depends on volume — at Power 5 scale (CFB ~6,500 athletes, NCAAB ~5,000+), pg_notify may saturate. Recommend Redis from the start.

6. **Verification SLA**: How long can a school wait for a flagged submission to be reviewed? Need a defined SLA and escalation path or the feature becomes a black hole for school trust.
