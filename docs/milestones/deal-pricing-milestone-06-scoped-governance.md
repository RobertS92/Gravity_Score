# Milestone 06 — Scoped pricing, governed evidence, and current-roster gate

Date: 2026-07-20

## Outcome

Implemented the production code path for five distinct commercial scopes:

1. Standard activation
2. Season partnership
3. Collective package
4. Group licensing
5. Revenue sharing

Each scope has a separate versioned prior and commercial definition. The UI now
requires an explicit scope selection and displays the range, qualified evidence
count, readiness state, and measured-error confidence for that scope.

## Scientific safeguards

- Confidence is `Uncalibrated` until a scope has at least 100 qualified
  transactions and 20 later out-of-time validation outcomes.
- 100 transactions is a pilot gate; 300 is the preferred production gate.
- Calibrated intervals use empirical log residual quantiles.
- Confidence tiers use measured median absolute percentage error and measured
  interval coverage, not model confidence or comparable counts.
- Evaluation splits by `available_at`, rejects duplicate transaction IDs, and
  purges every test athlete from training.
- Verified labels require a valid HTTP(S) source URL, structured evidence,
  verification status, source tier/domain, verification timestamp, and verifier.
- Retracted records are excluded from training and readiness counts.
- Every athlete score write creates a timestamped immutable snapshot through a
  database trigger, allowing the deal label to bind to information available at
  that time.

## Current-athlete safeguard

Live search and report generation require:

- `is_active = true`
- roster status `active_on_roster` or `transferred`
- authoritative roster verification no older than 21 days

The weekly scraper now fails closed if it cannot apply the active-roster query;
it no longer falls back to scraping all historical athletes. Historical athletes
remain available in storage for audit and time-correct evaluation only.

## Data acquisition status

The schema, strict ingestion path, readiness report, split policy, and calibration
code are complete. The repository does **not** currently contain 100-300 qualified
transactions for every scope. Those outcomes must be licensed or collected from
primary documents / authoritative sources and independently verified. Synthetic,
annual-valuation, and media-rumor rows are not counted toward the gate.

This is an intentional production block: the application may show transparent
prior guidance, but it may not claim empirically calibrated confidence until the
required evidence exists.

## Verification

- Scoped pricing, roster gate, leakage, and calibration tests: 14 passed.
- Pricing/report/search regression suite: 74 passed.
- Terminal contract tests: 60 passed.
- Terminal TypeScript and production Vite build: passed.
- Python compilation and `git diff --check`: passed.
- Scraper scheduler test collection is environment-blocked because the local
  scraper virtual environment lacks its declared APScheduler/Supabase runtime
  packages. The Sunday 01:00 America/Chicago schedule remains covered by the
  existing repository test and was not changed in this milestone.

## Release gate

Do not push to `main` until the user reviews and approves this milestone. Apply
migration `036_scoped_deal_pricing_governance.sql` before enabling the scoped
evidence counts in production.
