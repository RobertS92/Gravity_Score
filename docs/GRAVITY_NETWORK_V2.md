# Gravity Network v2

Gravity Network v2 separates observable data, learned predictions, entity
relationships, and product-facing summaries. A larger neural network is not
treated as an improvement unless it beats a calibrated tabular baseline on a
chronological holdout.

## Outputs

| Entity | Primary outputs |
|---|---|
| Athlete | Gravity, B/P/X/V/R, NIL P10/P50/P90, 30/90/365-day growth, transfer probability |
| Team | Roster value, retention, NIL environment, market reach, performance |
| Brand | Audience demand, activation quality, conversion, renewal, brand safety |
| Relationship | Athlete↔team, athlete↔brand, and team↔brand fit |

Every prediction includes `model_version`, data quality, confidence,
out-of-distribution score, and `fallback_used`.

## Data architecture

Migration `025_gravity_network_v2.sql` adds:

- source registry and field-level observations;
- point-in-time feature snapshots with missingness and provenance;
- leakage-guarded supervised labels;
- model registry with champion/challenger stages;
- calibrated prediction records;
- canonical teams, brands, campaign outcomes, and entity edges.

Missing values are represented by an explicit mask. They are never interpreted
as observed zero values.

## Training order

1. Apply migrations and backfill observations/snapshots.
2. Populate verified outcomes in `gravity_training_labels` and
   `gravity_campaign_outcomes`.
3. Train `QuantileValueBaseline`; record chronological MAE and interval coverage.
4. Train athlete v2:

   ```bash
   PYTHONPATH=. python -m ml.trainer_v2 data/athlete_training.csv --out models
   ```

5. Train team and brand models:

   ```bash
   PYTHONPATH=. python -m ml.trainer_entity_v2 team data/team_training.csv --out models
   PYTHONPATH=. python -m ml.trainer_entity_v2 brand data/brand_training.csv --out models
   ```

6. Train relationship fit after time-correct entity embeddings exist:

   ```bash
   PYTHONPATH=. python -m ml.trainer_relationship_v2 data/fit_training.json --out models
   ```

7. Register artifacts as `candidate`, run them in `shadow`, and promote only
   after cohort metrics and calibration outperform the current champion.

## Evaluation gates

- Chronological split only; no random leakage across future outcomes.
- Athlete value: MAE, median absolute percentage error, P10–P90 coverage.
- Rankings: NDCG and Spearman correlation by sport/position.
- Binary outcomes: Brier score, AUROC, and reliability plots.
- Teams/brands: performance by sport, conference, category, and data-density cohort.
- Fit: campaign renewal/conversion lift over the current rules baseline.
- Production: fallback rate, confidence, OOD rate, drift, latency, and freshness.

## APIs

ML:

- `POST /score/athlete/v2`
- `POST /score/team`
- `POST /score/brand`
- `POST /score/fit`

Product API, protected by `X-Gravity-Internal-Key`:

- `POST /v1/scores/v2/athletes/{id}`
- `POST /v1/scores/v2/teams/{id}`
- `POST /v1/scores/v2/brands/{id}`
- `POST /v1/scores/v2/fit`
- `GET /v1/scores/v2/models`
- `POST /v1/scores/v2/models/promote`

The legacy athlete endpoint automatically uses v2 when `gravity_v2.pt` exists,
while retaining the old response fields consumed by the terminal.

## Deployment

The first deployment should run v2 in shadow mode. Do not promote a model merely
because an artifact exists. A production champion requires:

- applied migration 025;
- verified labels and point-in-time snapshots;
- acceptable interval coverage and calibration;
- no severe cohort regression;
- fallback and OOD rates below agreed thresholds;
- rollback artifact retained in the model registry.
