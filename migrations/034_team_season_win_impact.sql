-- Team season records and athlete-team-season participation for win-impact scoring.

CREATE TABLE IF NOT EXISTS team_season_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sport TEXT NOT NULL,
  team_id TEXT NOT NULL,
  team_name TEXT,
  season_year INT NOT NULL,
  wins INT NOT NULL DEFAULT 0,
  losses INT NOT NULL DEFAULT 0,
  ties INT NOT NULL DEFAULT 0,
  win_pct NUMERIC,
  conference_wins INT,
  conference_losses INT,
  source_key TEXT,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE (sport, team_id, season_year)
);

CREATE INDEX IF NOT EXISTS idx_team_season_stats_lookup
  ON team_season_stats (sport, season_year, team_id);

CREATE TABLE IF NOT EXISTS athlete_team_seasons (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  sport TEXT NOT NULL,
  team_id TEXT NOT NULL,
  team_name TEXT,
  season_year INT NOT NULL,
  games_played INT,
  games_started INT,
  source_key TEXT,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE (athlete_id, sport, season_year, team_id)
);

CREATE INDEX IF NOT EXISTS idx_athlete_team_seasons_athlete
  ON athlete_team_seasons (athlete_id, season_year DESC);
