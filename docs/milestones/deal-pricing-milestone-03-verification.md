# Deal Pricing Scientific Fix — Milestone 03: Verification

Date: 2026-07-20

## Verification panel

The new unit test `gravity_api/tests/test_deal_pricing.py` validates a 20-athlete panel with at least 5 quarterbacks.

Panel coverage:

- 5 CFB QBs
- 8 additional CFB positions
- 6 men's/women's basketball roles
- 1 developing low-benchmark athlete

## Scientific checks performed

1. Activation range is strictly below annual NIL benchmark.
2. Elite QB case no longer permits the annual benchmark to become the recommended activation high.
3. Activation intervals maintain ordered low / mid / high outputs.
4. The 20-athlete panel requires at least 16 of 20 synthetic observed deals to land inside the predicted interval.
5. Interval widths are capped so the range is useful rather than theatrically wide.
6. Brand Match budget filtering now uses activation midpoint, not annual NIL benchmark.

## Test results

- Backend focused pricing/report/brand/contract suite: `47 passed`
- Backend targeted pricing/report/brand suite: `33 passed`
- Terminal build and tests: `60 passed`
- Static checks: `git diff --check` passed
- Python syntax checks: `py_compile` passed for changed backend services

## Full API suite note

The full API suite was attempted in a fresh temporary environment. It reached `117 passed` before being stopped after 8 minutes 44 seconds. The remaining observed failures were:

- `test_fetch_ncaa_baseball_power_entries`
- `test_fetch_ncaa_volleyball_power_entries`

Both failed because sandboxed test execution could not reach ESPN endpoints (`nodename nor servname provided, or not known`). These are external-network/environment failures, not deal-pricing regressions.

One contract expectation was updated to allow the new `range_quality="estimate"` state, then the focused contract suite passed.
