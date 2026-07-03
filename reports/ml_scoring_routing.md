# ML scoring routing (2026-07-03)

## Champion bundles (`models/bundles/index.json`)

| Sport | Value model | Scorer |
|-------|-------------|--------|
| cfb | `gravity_athlete_cfb_value_v1` **1.1.0-beta** (361 observed NIL labels) | ML beta rank-only |
| nfl, nba, ncaab_*, wnba, ncaa_baseball, ncaa_volleyball | none in index | `heuristic_gravity_v1` |

Synthetic bootstrap bundles (identical `model.pkl` MD5 across sports) were removed from the champion index. `bundle_loader` rejects bundles without `training_source: observed_nil_valuation` or with `row_count=200` bootstrap signature.

## Training

- CFB value: `PYTHONPATH=. python3 scripts/train_cfb_value_v1.py --version 1.1.0-beta`
- CFB impact: `scripts/train_cfb_impact_v1.py` (needs more impact labels)
- Other sports: no value training until observed NIL/contract labels exist

## Rescore

- `run_fast_ml_rescore.py --mode ml`: CFB only (champion bundle required)
- `run_fast_ml_rescore.py --mode heuristic`: all sports
- `sport_pipeline/score.py`: skips ML HTTP when no local champion bundle
