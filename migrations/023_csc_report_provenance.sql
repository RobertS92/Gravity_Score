-- CSC report provenance: deterministic report IDs per (date, athlete initials).
-- Sequence is incremented atomically; reads return the next id without race.

CREATE TABLE IF NOT EXISTS csc_report_sequence (
  report_date      DATE   NOT NULL,
  athlete_initials TEXT   NOT NULL,
  next_seq         INT    NOT NULL DEFAULT 1,
  PRIMARY KEY (report_date, athlete_initials)
);

CREATE INDEX IF NOT EXISTS idx_csc_report_sequence_date
  ON csc_report_sequence (report_date DESC);
