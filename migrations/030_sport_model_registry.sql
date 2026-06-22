-- Per-sport champion model registry entries (college + pro pipelines).

INSERT INTO gravity_model_registry (
  model_key, model_version, entity_type, stage,
  feature_schema_version, target_schema_version, config
) VALUES
  ('gravity_athlete_cfb_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"cfb","league":"ncaa","endpoint":"/score/athlete/cfb"}'::jsonb),
  ('gravity_athlete_ncaab_mens_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"ncaab_mens","league":"ncaa","endpoint":"/score/athlete/ncaab_mens"}'::jsonb),
  ('gravity_athlete_ncaab_womens_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"ncaab_womens","league":"ncaa","endpoint":"/score/athlete/ncaab_womens"}'::jsonb),
  ('gravity_athlete_ncaa_baseball_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"ncaa_baseball","league":"ncaa","endpoint":"/score/athlete/ncaa_baseball"}'::jsonb),
  ('gravity_athlete_ncaa_volleyball_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"ncaa_volleyball","league":"ncaa","endpoint":"/score/athlete/ncaa_volleyball"}'::jsonb),
  ('gravity_athlete_nfl_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"nfl","league":"nfl","endpoint":"/score/athlete/nfl"}'::jsonb),
  ('gravity_athlete_nba_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"nba","league":"nba","endpoint":"/score/athlete/nba"}'::jsonb),
  ('gravity_athlete_wnba_v1', '1.0.0', 'athlete', 'champion', 'gravity_features_bpxvr_v1', 'gravity_score_v1',
   '{"sport":"wnba","league":"wnba","endpoint":"/score/athlete/wnba"}'::jsonb)
ON CONFLICT (model_key, model_version) DO UPDATE SET
  stage = EXCLUDED.stage,
  feature_schema_version = EXCLUDED.feature_schema_version,
  config = EXCLUDED.config;
