-- Additional gravity_data_sources for micro-scrapers

INSERT INTO gravity_data_sources (source_key, display_name, source_type, default_confidence)
VALUES
  ('firecrawl', 'Firecrawl', 'scrape', 0.75),
  ('instagram', 'Instagram', 'scrape', 0.8),
  ('tiktok', 'TikTok', 'scrape', 0.78),
  ('twitter', 'X / Twitter', 'scrape', 0.78),
  ('on3', 'On3', 'scrape', 0.95),
  ('opendorse', 'Opendorse', 'scrape', 0.9),
  ('inflcr', 'INFLCR', 'licensed', 0.85),
  ('247sports', '247Sports', 'scrape', 0.75),
  ('rivals', 'Rivals', 'scrape', 0.7),
  ('sports_reference', 'Sports Reference', 'scrape', 0.85),
  ('wikipedia', 'Wikipedia', 'public_api', 0.72),
  ('google_trends', 'Google Trends', 'public_api', 0.65),
  ('ncaa', 'NCAA Official', 'official', 0.95),
  ('spotrac', 'Spotrac', 'scrape', 0.88),
  ('forbes', 'Forbes', 'scrape', 0.85),
  ('cfbd', 'CollegeFootballData', 'public_api', 0.93),
  ('perfect_game', 'Perfect Game', 'scrape', 0.88),
  ('d1baseball', 'D1Baseball', 'scrape', 0.82),
  ('avca', 'AVCA', 'scrape', 0.88),
  ('perplexity', 'Perplexity Gap Fill', 'licensed', 0.4)
ON CONFLICT (source_key) DO NOTHING;

-- Pro college experience scraper keys (predictive modeling)
INSERT INTO scraper_registry (
  scraper_key, display_name, sport, league_tier, dimension, source, source_type,
  description, feature_keys, status, terminal_visible, required_for_scoring,
  sla_days, default_confidence, priority
) VALUES (
  'college_experience_pro',
  'Pro athlete college career (ESPN)',
  '*',
  'pro',
  'proof',
  'espn',
  'public_api',
  'Scrape college ESPN stats/awards for NFL/NBA/WNBA athletes for predictive modeling.',
  '["college_career_found","college_espn_id","college_stats_json","college_achievements_json"]'::jsonb,
  'active',
  false,
  true,
  30,
  0.9,
  2
) ON CONFLICT (scraper_key) DO NOTHING;
