# Deal Pricing Scientific Fix — Milestone 04: Holdout Readiness Audit

Date: 2026-07-20

## Objective

Run a genuinely out-of-sample evaluation on 20 historical athlete transactions,
including at least five quarterbacks, without allowing the target transaction or
post-deal information to enter model inputs.

## Required admission criteria

A transaction is admissible only when all of the following are available:

1. Athlete identity (or stable anonymous athlete identifier), sport, and position.
2. Exact compensation amount and the scope of the purchased rights/deliverables.
3. Contract or announcement date.
4. Traceable source URL and verification status.
5. Athlete/model inputs timestamped before the transaction date.
6. Comparable transactions dated before the target transaction and excluding the
   target athlete and target transaction.
7. A scope matching the model output under test. A season-long collective payment,
   aggregate annual earnings, valuation, or recruiting promise cannot be scored as
   a standard 4–6 week commercial activation.

## Internal database audit

Read-only production audit results:

- `verified_nil_deals`: 0 rows.
- `athlete_nil_deals`: 11 rows with positive amounts.
- Legacy `verified = true`: 5 rows.
- Structured `verification = VERIFIED/CONFIRMED`: 0 rows.
- Rows with a source URL: 0.
- Historical score table: absent.
- Current `gravity_scores`: 1 row, which cannot reconstruct pre-deal features.
- QB records: 5 rows across 4 unique athletes; only 3 unique QBs have the legacy
  verified flag.

The 11 rows are inadmissible because every row is marked `UNVERIFIED`, every source
URL is missing, historical pre-deal features do not exist, and several amounts have
generated-looking fractional-dollar precision. The legacy boolean does not override
these failures.

## Independent public-data audit

The Washington Post obtained about 22,000 itemized NIL payments through public
records requests, but athlete names were omitted from the released school datasets.
Only some schools supplied sport and vendor. The article identifies a handful of
high-value cases through contextual matching, but not a 20-athlete panel with five
known quarterbacks and complete pre-deal features.

Opendorse publishes useful verified aggregate and cohort statistics, but its public
reports anonymize individual transactions. These aggregates are appropriate for
priors and calibration targets, not athlete-level holdout outcomes.

Publicly reported recruiting promises, collective packages, annual earnings, and NIL
valuations were excluded because they do not measure the standard activation target.

Sources consulted:

- Washington Post, "How NIL money is paid to college athletes":
  https://www.washingtonpost.com/sports/interactive/2024/nil-money-deals-college-sports-athlete-pay/
- Opendorse, "NIL at Four: Monetizing the New Reality":
  https://biz.opendorse.com/wp-content/uploads/2025/07/NIL-at-Four-Monetizing-the-New-Reality_July2025.pdf
- NCAA NIL overview and disclosure guidance:
  https://www.ncaa.org/student-athletes/name-image-likeness/

## Result

Admissible athlete-level holdout cases: **0 of 20 required**.

The stronger accuracy test was therefore not run, because substituting synthetic,
rumored, post-deal, aggregate, or mismatched-scope values would create a misleading
accuracy claim. This is a failed data-readiness gate, not a passing model-validation
result.

## Data required to unblock validation

Obtain 20 signed or athlete/brand-confirmed transactions, including five QBs, with
the seven admission fields above. The preferred source is a licensed CSC/NIL Go,
Opendorse, school/collective, agency, or athlete-confirmed export. Athlete names may
be irreversibly anonymized as long as stable IDs, positions, dates, terms, and
pre-deal snapshots remain available.

When those records are available, the final report must include:

- empirical interval coverage;
- median absolute percentage error of the midpoint;
- median and maximum normalized interval width;
- median signed log error (overpricing versus underpricing);
- QB versus non-QB coverage and error;
- results segmented by activation scope and source tier;
- bootstrap 95% confidence intervals, with the warning that `n = 20` remains a
  small pilot sample.
