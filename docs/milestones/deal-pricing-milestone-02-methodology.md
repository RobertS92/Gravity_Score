# Deal Pricing Scientific Fix — Milestone 02: Methodology

Date: 2026-07-20

## What changed

The CSC report now treats the annual NIL value benchmark and brand activation deal guidance as separate outputs.

## Model logic

The new activation engine prices a standard 4-6 week brand activation using:

1. Annual NIL benchmark as an anchor, not a direct deal price.
2. Sport and position-specific inventory share.
3. Commercial signal multiplier from brand, proof, exposure, velocity, and risk.
4. Bayesian shrinkage toward observed comparable deal values when available.
5. Cohort prior when direct verified deal values are sparse.
6. Explicit uncertainty width based on model confidence, comparable depth, verified deals, cohort size, and cohort fit.

## Outputs added to CSC reports

- `annual_nil_benchmark`
- `activation_deal_low`
- `activation_deal_mid`
- `activation_deal_high`
- `season_partnership_low`
- `season_partnership_high`
- `deal_confidence`
- `deal_uncertainty`
- `deal_pricing_method`
- `deal_pricing_basis`

For backward compatibility, `range_low` and `range_high` now mirror the standard activation deal range.

## Scientific guardrail

The recommended activation range is no longer required to contain the annual NIL benchmark. For elite athletes, this prevents a public annual valuation from becoming a fantasy upper bound for one brand campaign.
