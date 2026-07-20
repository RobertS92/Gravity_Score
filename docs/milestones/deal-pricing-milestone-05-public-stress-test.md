# Deal Pricing Scientific Fix — Milestone 05: 20-Athlete Public Stress Test

Date: 2026-07-20

## Outcome

Gravity's current season-partnership output does not represent the reported
collective/roster-package market. On a 20-athlete external panel containing eight
quarterbacks, baseline coverage was **0/20** and QB coverage was **0/8**.

This is a completed external stress test, not a contract-verified temporal holdout.
The public source explicitly warns that its figures are based on media reports and
may be inaccurate. Results must not be presented as verified predictive accuracy.

## External panel

The versioned fixture contains 20 distinct named athletes:

- 9 football athletes, including 8 QBs;
- 10 men's basketball athletes;
- 1 women's basketball athlete.

The source is a 2026 NIL financial-literacy brief prepared for the California State
Assembly. It publishes athlete, school, position, external annual NIL valuation,
and reported collective/package figures.

Source:

https://aart.assembly.ca.gov/system/files/2026-05/nil-legislative-brief.pdf

## Method

1. Use the external annual NIL valuation as the pricing input.
2. Do not pass the reported package as a comparable or model feature.
3. Generate Gravity's season-partnership low/high interval.
4. Count coverage only when the predicted and reported intervals overlap.
5. Calculate midpoint absolute percentage error and signed percentage error.
6. Repeat under a deliberately aggressive commercial-signal profile to test
   whether neutral score assumptions explain the result.

The baseline profile fixes brand/proof/exposure at 70, velocity at 65, risk at 20,
and model confidence at 0.60. The aggressive profile fixes all positive signals at
95, risk at 5, confidence at 0.85, and selects the aggressive market view.

## Results

| Metric | Baseline | Aggressive sensitivity |
|---|---:|---:|
| Overall coverage | 0/20 (0%) | 1/20 (5%) |
| QB coverage | 0/8 (0%) | 0/8 (0%) |
| Median midpoint APE | 77.3% | 71.3% |
| Mean midpoint APE | 76.9% | 70.8% |
| Median signed error | -77.3% | -71.3% |

The negative signed error means Gravity's midpoint is lower than the reported
package midpoint. The miss persists under the aggressive sensitivity profile,
showing that it is primarily a scope/model-structure problem rather than a small
commercial-signal tuning issue.

## Baseline athlete results

| Athlete | Position | External valuation | Reported package | Gravity season range | Overlap |
|---|---|---:|---:|---:|:---:|
| Carson Beck | QB | $4.30M | $3.00M–$4.00M | $352K–$1.11M | No |
| Jeremiah Smith | WR | $4.20M | $1.00M–$2.00M | $344K–$885K | No |
| Garrett Nussmeier | QB | $3.70M | ~$2.00M | $303K–$952K | No |
| LaNorris Sellers | QB | $3.70M | ~$2.00M | $303K–$952K | No |
| DJ Lagway | QB | $3.70M | ~$2.00M | $303K–$952K | No |
| Cade Klubnik | QB | $3.40M | ~$1.50M | $278K–$875K | No |
| Drew Allar | QB | $3.10M | ~$1.50M | $254K–$798K | No |
| Sam Leavitt | QB | $3.10M | ~$1.50M | $254K–$798K | No |
| Bryce Underwood | QB | $3.00M | ~$1.50M | $246K–$772K | No |
| AJ Dybantsa | F | $4.10M | ~$7.00M | $336K–$863K | No |
| JT Toppin | F | $2.80M | ~$4.00M | $229K–$590K | No |
| Yaxel Lendeborg | F | $2.30M | ~$3.00M | $188K–$484K | No |
| Boogie Fland | G | $2.10M | ~$2.00M | $172K–$442K | No |
| Donovan Dent | G | $2.00M | ~$3.00M | $164K–$421K | No |
| Jayden Quaintance | F | $1.90M | ~$2.00M | $156K–$400K | No |
| Cameron Boozer | F | $1.80M | ~$1.50M | $147K–$379K | No |
| Darryn Peterson | G | $1.60M | ~$1.00M | $131K–$337K | No |
| Braden Smith | G | $1.60M | ~$1.00M | $131K–$337K | No |
| Milos Uzan | G | $1.50M | ~$1.00M | $123K–$316K | No |
| Aaliyah Chavez | G | $755K | ~$1.50M | $62K–$159K | No |

## Scientific interpretation

The result does not invalidate the standard 4–6 week activation calculation. It
shows that a commercial season partnership and a roster/collective package are
different targets. Collective packages may price competitive roster scarcity,
transfer leverage, retention, revenue-sharing adjacency, and school-specific donor
demand. Those signals are not represented by multiplying annual commercial value by
the current 7%–22% season factors.

The product must expose separate outputs for:

1. standard commercial activation;
2. season-long commercial partnership;
3. roster/collective compensation package;
4. group licensing;
5. direct institutional revenue share.

Until a roster/collective model is implemented and contract-confirmed labels are
available, Gravity should not describe its existing season-partnership range as a
collective or transfer-market recommendation.

## Reproduction

```bash
python3 -m gravity_api.jobs.evaluate_public_deal_pricing --profile baseline
python3 -m gravity_api.jobs.evaluate_public_deal_pricing --profile aggressive
python3 -m pytest gravity_api/tests/test_deal_pricing_validation.py -q
```
