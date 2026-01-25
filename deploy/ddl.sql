CREATE TABLE IF NOT EXISTS athletes (
  athlete_id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  sport TEXT NOT NULL,
  league TEXT NOT NULL,
  team TEXT, conference TEXT, position TEXT, jersey_number TEXT,
  dob DATE, height_cm INT, weight_kg INT, class_year TEXT,
  urls JSONB, recruiting JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS season_stats (
  athlete_id TEXT REFERENCES athletes(athlete_id),
  season TEXT, league TEXT, team TEXT,
  stat_bucket TEXT,
  stats JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (athlete_id, season, stat_bucket)
);
CREATE TABLE IF NOT EXISTS game_stats (
  athlete_id TEXT REFERENCES athletes(athlete_id),
  league TEXT, season TEXT,
  game_id TEXT, date DATE,
  opponent TEXT, location TEXT, team TEXT,
  stats JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (athlete_id, game_id)
);
CREATE TABLE IF NOT EXISTS social_snapshots (
  id BIGSERIAL PRIMARY KEY,
  athlete_id TEXT REFERENCES athletes(athlete_id),
  platform TEXT, handle TEXT,
  profile_url TEXT,
  follower_count BIGINT, following_count BIGINT, posts_count BIGINT,
  verified BOOLEAN, bio TEXT, external_links JSONB,
  scraped_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS team_history (
  athlete_id TEXT REFERENCES athletes(athlete_id),
  league TEXT, season TEXT, team TEXT,
  start_date DATE, end_date DATE, depth_chart_slot TEXT,
  UNIQUE (athlete_id, season, team)
);
