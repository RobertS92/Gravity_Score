# SMU demonstration cohort

Operator guide for a dependable SMU demo set (search, CSC, Brand Match, Gravity AI, CapIQ).

## Canonical data

- Fixture: [`data/demo/smu_demo_cohort.json`](../data/demo/smu_demo_cohort.json)
- ESPN team id: **2567** (CFB / MBB / WBB)
- Primary athlete: **Kevin Jennings** (QB, ESPN `5084084`)

## Seed / refresh

```bash
# Direct DB path (preferred when PG_DSN is available)
PG_DSN=... python scripts/seed_smu_demo_cohort.py
PG_DSN=... python scripts/seed_smu_demo_cohort.py --verify-only

# Or via API (requires GRAVITY_INTERNAL_API_KEY)
./scripts/trigger_smu_roster_sync.sh
```

After roster sync, run gap-fill + scoring for Brand Match / CSC quality.

## Demo login

`smu@gravity.local` / `demo1234` (non-production). Seed string `SMU` fills an empty watchlist from `athletes` where name/school ILIKE `%SMU%`.

## Smoke (summary)

| Flow | Action | Pass if |
|------|--------|---------|
| Search | Find Player `Jennings` + CFB | Kevin Jennings |
| CSC | Open Jennings report | QB / SMU / male pronouns |
| Brand Match | Apparel + National (or ACC/Texas-friendly geo) | ≥1 SMU skill athlete |
| Gravity AI | “Gravity vs Impact Score” with Jennings selected | Answer (not network error) |
| CapIQ | Linked org membership (not just profile label “SMU”) | Org linked; no fake $15M when unlinked |

WBB is a known gap (empty ESPN roster as of fixture date) — skip for demos.
