-- WP10: games, player box scores, and CFB play-level tables for Impact model.
-- Box scores: ESPN game summary. CFB plays: CFBD /plays, /play/stats, /metrics/wp.

CREATE TABLE IF NOT EXISTS games (
  game_id TEXT PRIMARY KEY,
  league TEXT NOT NULL,
  season_year INT NOT NULL,
  season_type TEXT NOT NULL DEFAULT 'regular'
    CHECK (season_type IN ('regular', 'postseason')),
  start_time TIMESTAMPTZ,
  home_team_id TEXT,
  away_team_id TEXT,
  home_score INT,
  away_score INT,
  neutral_site BOOLEAN,
  status TEXT,
  source_url TEXT,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_games_league_season
  ON games (league, season_year, season_type);

CREATE INDEX IF NOT EXISTS idx_games_start_time
  ON games (start_time DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS game_player_box (
  game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
  athlete_id UUID REFERENCES athletes(id) ON DELETE SET NULL,
  espn_athlete_id TEXT NOT NULL,
  team_id TEXT,
  started BOOLEAN NULL,
  minutes NUMERIC NULL,
  snaps INT NULL,
  stats JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (game_id, espn_athlete_id)
);

CREATE INDEX IF NOT EXISTS idx_game_player_box_athlete
  ON game_player_box (athlete_id)
  WHERE athlete_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_game_player_box_team
  ON game_player_box (game_id, team_id);

-- CFBD play-by-play + PPA / win-probability enrichment.
CREATE TABLE IF NOT EXISTS cfb_plays (
  play_id TEXT PRIMARY KEY,
  game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
  drive_id TEXT,
  play_number INT,
  period INT,
  clock TEXT,
  offense_team_id TEXT,
  defense_team_id TEXT,
  home_team_id TEXT,
  away_team_id TEXT,
  down INT,
  distance INT,
  yards_to_goal INT,
  yards_gained INT,
  play_type TEXT,
  play_text TEXT,
  scoring BOOLEAN,
  home_score INT,
  away_score INT,
  ppa NUMERIC,
  home_wp_before NUMERIC,
  home_wp_after NUMERIC,
  source_url TEXT,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cfb_plays_game
  ON cfb_plays (game_id, play_number NULLS LAST);

-- Per-play player roles (passer, rusher, receiverTarget, sack, etc.).
CREATE TABLE IF NOT EXISTS cfb_play_players (
  play_id TEXT NOT NULL REFERENCES cfb_plays(play_id) ON DELETE CASCADE,
  athlete_id UUID REFERENCES athletes(id) ON DELETE SET NULL,
  cfbd_player_id TEXT NOT NULL,
  role TEXT NOT NULL,
  team_id TEXT,
  PRIMARY KEY (play_id, cfbd_player_id, role)
);

CREATE INDEX IF NOT EXISTS idx_cfb_play_players_athlete
  ON cfb_play_players (athlete_id)
  WHERE athlete_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cfb_play_players_role
  ON cfb_play_players (role, play_id);
