-- Team-to-conference mapping with effective dates to handle conference realignment.
-- Power-4 CFB (SEC, Big Ten, Big 12, ACC) and Power-5/6 NCAAB (those plus Big East).
-- team_id is the canonical school name (case/whitespace normalized at lookup time).

CREATE TABLE IF NOT EXISTS team_conferences (
  team_id         TEXT NOT NULL,
  sport           TEXT NOT NULL CHECK (sport IN ('cfb', 'ncaab')),
  conference      TEXT NOT NULL,
  conference_tier TEXT NOT NULL CHECK (conference_tier IN ('power_5', 'group_of_5', 'fcs', 'mid_major', 'other')),
  effective_from  DATE NOT NULL,
  effective_to    DATE,
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (team_id, sport, effective_from),
  CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_team_conferences_lookup
  ON team_conferences (team_id, sport, effective_from, effective_to);

CREATE INDEX IF NOT EXISTS idx_team_conferences_conf
  ON team_conferences (sport, conference);

-- ============================================================================
-- CFB Power 4 seed (post-2024 realignment; effective_from reflects move date).
-- All teams use effective_from = 2024-08-01 for the current alignment unless
-- the team moved into the conference on a different date.
-- ============================================================================

INSERT INTO team_conferences (team_id, sport, conference, conference_tier, effective_from, notes)
VALUES
  -- SEC (16)
  ('Alabama',          'cfb', 'SEC', 'power_5', DATE '1992-07-01', 'Founding modern SEC'),
  ('Arkansas',         'cfb', 'SEC', 'power_5', DATE '1991-07-01', NULL),
  ('Auburn',           'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Florida',          'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Georgia',          'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Kentucky',         'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('LSU',              'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Mississippi State','cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Missouri',         'cfb', 'SEC', 'power_5', DATE '2012-07-01', NULL),
  ('Oklahoma',         'cfb', 'SEC', 'power_5', DATE '2024-07-01', 'Moved from Big 12 in 2024'),
  ('Ole Miss',         'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('South Carolina',   'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Tennessee',        'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Texas',            'cfb', 'SEC', 'power_5', DATE '2024-07-01', 'Moved from Big 12 in 2024'),
  ('Texas A&M',        'cfb', 'SEC', 'power_5', DATE '2012-07-01', NULL),
  ('Vanderbilt',       'cfb', 'SEC', 'power_5', DATE '1992-07-01', NULL),

  -- Big Ten (18)
  ('Illinois',         'cfb', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Indiana',          'cfb', 'Big Ten', 'power_5', DATE '1899-01-01', NULL),
  ('Iowa',             'cfb', 'Big Ten', 'power_5', DATE '1899-01-01', NULL),
  ('Maryland',         'cfb', 'Big Ten', 'power_5', DATE '2014-07-01', NULL),
  ('Michigan',         'cfb', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Michigan State',   'cfb', 'Big Ten', 'power_5', DATE '1953-07-01', NULL),
  ('Minnesota',        'cfb', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Nebraska',         'cfb', 'Big Ten', 'power_5', DATE '2011-07-01', NULL),
  ('Northwestern',     'cfb', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Ohio State',       'cfb', 'Big Ten', 'power_5', DATE '1913-07-01', NULL),
  ('Oregon',           'cfb', 'Big Ten', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Penn State',       'cfb', 'Big Ten', 'power_5', DATE '1993-07-01', NULL),
  ('Purdue',           'cfb', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Rutgers',          'cfb', 'Big Ten', 'power_5', DATE '2014-07-01', NULL),
  ('UCLA',             'cfb', 'Big Ten', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('USC',              'cfb', 'Big Ten', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Washington',       'cfb', 'Big Ten', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Wisconsin',        'cfb', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),

  -- Big 12 (16)
  ('Arizona',          'cfb', 'Big 12', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Arizona State',    'cfb', 'Big 12', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Baylor',           'cfb', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('BYU',              'cfb', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Cincinnati',       'cfb', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Colorado',         'cfb', 'Big 12', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Houston',          'cfb', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Iowa State',       'cfb', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('Kansas',           'cfb', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('Kansas State',     'cfb', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('Oklahoma State',   'cfb', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('TCU',              'cfb', 'Big 12', 'power_5', DATE '2012-07-01', NULL),
  ('Texas Tech',       'cfb', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('UCF',              'cfb', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Utah',             'cfb', 'Big 12', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('West Virginia',    'cfb', 'Big 12', 'power_5', DATE '2012-07-01', NULL),

  -- ACC (17 CFB members, including football-only members)
  ('Boston College',   'cfb', 'ACC', 'power_5', DATE '2005-07-01', NULL),
  ('California',       'cfb', 'ACC', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Clemson',          'cfb', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Duke',             'cfb', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Florida State',    'cfb', 'ACC', 'power_5', DATE '1992-07-01', NULL),
  ('Georgia Tech',     'cfb', 'ACC', 'power_5', DATE '1979-07-01', NULL),
  ('Louisville',       'cfb', 'ACC', 'power_5', DATE '2014-07-01', NULL),
  ('Miami',            'cfb', 'ACC', 'power_5', DATE '2004-07-01', NULL),
  ('NC State',         'cfb', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('North Carolina',   'cfb', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Pittsburgh',       'cfb', 'ACC', 'power_5', DATE '2013-07-01', NULL),
  ('SMU',              'cfb', 'ACC', 'power_5', DATE '2024-08-02', 'Joined from AAC in 2024'),
  ('Stanford',         'cfb', 'ACC', 'power_5', DATE '2024-08-02', 'Moved from Pac-12 in 2024'),
  ('Syracuse',         'cfb', 'ACC', 'power_5', DATE '2013-07-01', NULL),
  ('Virginia',         'cfb', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Virginia Tech',    'cfb', 'ACC', 'power_5', DATE '2004-07-01', NULL),
  ('Wake Forest',      'cfb', 'ACC', 'power_5', DATE '1953-07-01', NULL)
ON CONFLICT (team_id, sport, effective_from) DO NOTHING;

-- ============================================================================
-- NCAAB Power 5+1 seed (SEC + Big Ten + Big 12 + ACC + Big East).
-- ============================================================================

INSERT INTO team_conferences (team_id, sport, conference, conference_tier, effective_from, notes)
VALUES
  -- SEC (16)
  ('Alabama',          'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Arkansas',         'ncaab', 'SEC', 'power_5', DATE '1991-07-01', NULL),
  ('Auburn',           'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Florida',          'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Georgia',          'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Kentucky',         'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('LSU',              'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Mississippi State','ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Missouri',         'ncaab', 'SEC', 'power_5', DATE '2012-07-01', NULL),
  ('Oklahoma',         'ncaab', 'SEC', 'power_5', DATE '2024-07-01', 'Moved from Big 12 in 2024'),
  ('Ole Miss',         'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('South Carolina',   'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Tennessee',        'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),
  ('Texas',            'ncaab', 'SEC', 'power_5', DATE '2024-07-01', 'Moved from Big 12 in 2024'),
  ('Texas A&M',        'ncaab', 'SEC', 'power_5', DATE '2012-07-01', NULL),
  ('Vanderbilt',       'ncaab', 'SEC', 'power_5', DATE '1992-07-01', NULL),

  -- Big Ten (18)
  ('Illinois',         'ncaab', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Indiana',          'ncaab', 'Big Ten', 'power_5', DATE '1899-01-01', NULL),
  ('Iowa',             'ncaab', 'Big Ten', 'power_5', DATE '1899-01-01', NULL),
  ('Maryland',         'ncaab', 'Big Ten', 'power_5', DATE '2014-07-01', NULL),
  ('Michigan',         'ncaab', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Michigan State',   'ncaab', 'Big Ten', 'power_5', DATE '1953-07-01', NULL),
  ('Minnesota',        'ncaab', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Nebraska',         'ncaab', 'Big Ten', 'power_5', DATE '2011-07-01', NULL),
  ('Northwestern',     'ncaab', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Ohio State',       'ncaab', 'Big Ten', 'power_5', DATE '1913-07-01', NULL),
  ('Oregon',           'ncaab', 'Big Ten', 'power_5', DATE '2024-08-02', NULL),
  ('Penn State',       'ncaab', 'Big Ten', 'power_5', DATE '1993-07-01', NULL),
  ('Purdue',           'ncaab', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),
  ('Rutgers',          'ncaab', 'Big Ten', 'power_5', DATE '2014-07-01', NULL),
  ('UCLA',             'ncaab', 'Big Ten', 'power_5', DATE '2024-08-02', NULL),
  ('USC',              'ncaab', 'Big Ten', 'power_5', DATE '2024-08-02', NULL),
  ('Washington',       'ncaab', 'Big Ten', 'power_5', DATE '2024-08-02', NULL),
  ('Wisconsin',        'ncaab', 'Big Ten', 'power_5', DATE '1896-01-01', NULL),

  -- Big 12 (16)
  ('Arizona',          'ncaab', 'Big 12', 'power_5', DATE '2024-08-02', NULL),
  ('Arizona State',    'ncaab', 'Big 12', 'power_5', DATE '2024-08-02', NULL),
  ('Baylor',           'ncaab', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('BYU',              'ncaab', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Cincinnati',       'ncaab', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Colorado',         'ncaab', 'Big 12', 'power_5', DATE '2024-08-02', NULL),
  ('Houston',          'ncaab', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Iowa State',       'ncaab', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('Kansas',           'ncaab', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('Kansas State',     'ncaab', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('Oklahoma State',   'ncaab', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('TCU',              'ncaab', 'Big 12', 'power_5', DATE '2012-07-01', NULL),
  ('Texas Tech',       'ncaab', 'Big 12', 'power_5', DATE '1996-07-01', NULL),
  ('UCF',              'ncaab', 'Big 12', 'power_5', DATE '2023-07-01', NULL),
  ('Utah',             'ncaab', 'Big 12', 'power_5', DATE '2024-08-02', NULL),
  ('West Virginia',    'ncaab', 'Big 12', 'power_5', DATE '2012-07-01', NULL),

  -- ACC (18 NCAAB)
  ('Boston College',   'ncaab', 'ACC', 'power_5', DATE '2005-07-01', NULL),
  ('California',       'ncaab', 'ACC', 'power_5', DATE '2024-08-02', NULL),
  ('Clemson',          'ncaab', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Duke',             'ncaab', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Florida State',    'ncaab', 'ACC', 'power_5', DATE '1991-07-01', NULL),
  ('Georgia Tech',     'ncaab', 'ACC', 'power_5', DATE '1979-07-01', NULL),
  ('Louisville',       'ncaab', 'ACC', 'power_5', DATE '2014-07-01', NULL),
  ('Miami',            'ncaab', 'ACC', 'power_5', DATE '2004-07-01', NULL),
  ('NC State',         'ncaab', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('North Carolina',   'ncaab', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Notre Dame',       'ncaab', 'ACC', 'power_5', DATE '2013-07-01', NULL),
  ('Pittsburgh',       'ncaab', 'ACC', 'power_5', DATE '2013-07-01', NULL),
  ('SMU',              'ncaab', 'ACC', 'power_5', DATE '2024-08-02', NULL),
  ('Stanford',         'ncaab', 'ACC', 'power_5', DATE '2024-08-02', NULL),
  ('Syracuse',         'ncaab', 'ACC', 'power_5', DATE '2013-07-01', NULL),
  ('Virginia',         'ncaab', 'ACC', 'power_5', DATE '1953-07-01', NULL),
  ('Virginia Tech',    'ncaab', 'ACC', 'power_5', DATE '2004-07-01', NULL),
  ('Wake Forest',      'ncaab', 'ACC', 'power_5', DATE '1953-07-01', NULL),

  -- Big East NCAAB (11) — basketball-focused conference
  ('Butler',           'ncaab', 'Big East', 'power_5', DATE '2013-07-01', NULL),
  ('Connecticut',      'ncaab', 'Big East', 'power_5', DATE '2020-07-01', NULL),
  ('Creighton',        'ncaab', 'Big East', 'power_5', DATE '2013-07-01', NULL),
  ('DePaul',           'ncaab', 'Big East', 'power_5', DATE '2005-07-01', NULL),
  ('Georgetown',       'ncaab', 'Big East', 'power_5', DATE '1979-07-01', NULL),
  ('Marquette',        'ncaab', 'Big East', 'power_5', DATE '2005-07-01', NULL),
  ('Providence',       'ncaab', 'Big East', 'power_5', DATE '1979-07-01', NULL),
  ('Seton Hall',       'ncaab', 'Big East', 'power_5', DATE '1979-07-01', NULL),
  ('St. John''s',      'ncaab', 'Big East', 'power_5', DATE '1979-07-01', NULL),
  ('Villanova',        'ncaab', 'Big East', 'power_5', DATE '1980-07-01', NULL),
  ('Xavier',           'ncaab', 'Big East', 'power_5', DATE '2013-07-01', NULL)
ON CONFLICT (team_id, sport, effective_from) DO NOTHING;
