-- CSC v2 config tables: season windows + exposure formula versions.

CREATE TABLE IF NOT EXISTS season_states (
  id                 SERIAL PRIMARY KEY,
  sport              TEXT NOT NULL,
  state              TEXT NOT NULL,
  start_date         DATE NOT NULL,
  end_date           DATE NOT NULL,
  cohort_window_days INTEGER NOT NULL,
  notes              TEXT,
  effective_year     INTEGER NOT NULL,
  created_at         TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (sport, state, effective_year, start_date, end_date),
  CHECK (end_date >= start_date),
  CHECK (cohort_window_days > 0)
);

CREATE INDEX IF NOT EXISTS idx_season_states_lookup
  ON season_states (sport, start_date, end_date);

CREATE TABLE IF NOT EXISTS exposure_formulas (
  version            TEXT PRIMARY KEY,
  proximity_weight   NUMERIC NOT NULL,
  velocity_weight    NUMERIC NOT NULL,
  calibration_method TEXT,
  calibrated_at      TIMESTAMPTZ,
  is_active          BOOLEAN DEFAULT FALSE,
  CHECK (ROUND((proximity_weight + velocity_weight)::numeric, 6) = 1.0),
  CHECK (proximity_weight >= 0 AND velocity_weight >= 0)
);

-- Exactly one active row may exist at a time.
CREATE UNIQUE INDEX IF NOT EXISTS uq_exposure_formulas_active_true
  ON exposure_formulas ((is_active))
  WHERE is_active = TRUE;

-- 2026 seed coverage (no date gaps per sport).
INSERT INTO season_states (sport, state, start_date, end_date, cohort_window_days, notes, effective_year)
VALUES
  ('CFB', 'offseason', DATE '2026-01-01', DATE '2026-08-15', 90, 'Offseason window', 2026),
  ('CFB', 'in_season', DATE '2026-08-16', DATE '2026-12-31', 21, 'In-season window', 2026),
  ('NCAAB', 'in_season', DATE '2026-01-01', DATE '2026-04-15', 21, 'Tournament/in-season window', 2026),
  ('NCAAB', 'offseason', DATE '2026-04-16', DATE '2026-10-31', 90, 'Offseason window', 2026),
  ('NCAAB', 'preseason', DATE '2026-11-01', DATE '2026-12-31', 45, 'Preseason ramp', 2026),
  ('NCAAWB', 'in_season', DATE '2026-01-01', DATE '2026-04-15', 21, 'Tournament/in-season window', 2026),
  ('NCAAWB', 'offseason', DATE '2026-04-16', DATE '2026-10-31', 90, 'Offseason window', 2026),
  ('NCAAWB', 'preseason', DATE '2026-11-01', DATE '2026-12-31', 45, 'Preseason ramp', 2026)
ON CONFLICT DO NOTHING;

INSERT INTO exposure_formulas (
  version,
  proximity_weight,
  velocity_weight,
  calibration_method,
  calibrated_at,
  is_active
)
VALUES (
  'exposure_formula_v1',
  0.6,
  0.4,
  'phase_a_default',
  NOW(),
  TRUE
)
ON CONFLICT (version) DO UPDATE SET
  proximity_weight = EXCLUDED.proximity_weight,
  velocity_weight = EXCLUDED.velocity_weight,
  calibration_method = EXCLUDED.calibration_method,
  calibrated_at = EXCLUDED.calibrated_at,
  is_active = EXCLUDED.is_active;
