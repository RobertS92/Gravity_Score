# Deal Pricing Scientific Fix — Milestone 01: Diagnosis

Date: 2026-07-20

## Problem observed

The CSC report was showing a "recommended deal range" that could climb toward the athlete's total annual NIL benchmark. For elite athletes, that produced ranges such as a six-figure lower bound and a multi-million-dollar upper bound. The number is visually dramatic, but it is not an actionable brand deal price.

## Root cause

The current report builder used `total_benchmark`, `dollar_p10_usd`, `dollar_p90_usd`, peer cohort percentiles, and a hard invariant that forced the displayed range to contain the benchmark. That made sense when the range was interpreted as valuation uncertainty, but it is scientifically wrong when the UI labels the field as a "recommended deal range."

Annual NIL value and activation deal price are different targets:

- Annual NIL benchmark estimates total market earning potential or media/commercial value over a year.
- Deal price estimates a transaction for a specific activation, duration, exclusivity package, and deliverables.

## Scientific acceptance criteria

1. The report must separate annual NIL benchmark from activation deal guidance.
2. Recommended campaign deal guidance must no longer be required to bracket the annual benchmark.
3. Deal guidance must use a log-dollar, cohort-shrunk activation model with explicit uncertainty.
4. Elite outliers must receive plausible activation ranges rather than fantasy ranges anchored to annual NIL value.
5. Tests must verify at least 20 athletes, including at least 5 QBs.
6. The report metadata must expose the deal-pricing method and calibration diagnostics for audit.

## Implementation plan

Add a deterministic deal-pricing engine that computes:

- activation deal low / mid / high
- season partnership low / high
- confidence and uncertainty level
- pricing basis and methodology metadata

Then update the API report payload and UI language so the annual benchmark remains visible, but the recommended deal range becomes activation-specific.
