-- Widen sport codes to support ncaab_womens, ncaa_volleyball, etc.

ALTER TABLE athletes DROP CONSTRAINT IF EXISTS athletes_sport_check;
ALTER TABLE athletes ALTER COLUMN sport TYPE VARCHAR(32);

ALTER TABLE athlete_performance_snapshots ALTER COLUMN sport TYPE VARCHAR(32);

ALTER TABLE programs ALTER COLUMN sport TYPE VARCHAR(32);
