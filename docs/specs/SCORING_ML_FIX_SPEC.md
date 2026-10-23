# SCORING ML FIX SPEC — learn Impact and Gravity from real outcomes

**Status:** Ready for implementation · **Owner:** Rob · **Written:** 2026-10-22
**Repo:** `Gravity_Score` (canonical ML = `gravity_ml/`, imported in-process by `gravity_api`)
**Depends on:** `docs/specs/SCRAPER_FIX_SPEC.md` (WP1–WP7 for season history; WP10 for games/box scores/plays)

> **For agents:** This spec replaces *labels and evaluation*, not just models. A bigger network trained on the current labels will not help. Read §1–§3 before coding. Every model change must pass the gates in §4 before it can serve a public score. If a gate fails, the product shows the fallback with a "Planning estimate" confidence label (see `claude/CSC_REPORT_FIX_LIST.md` item 1) — never a silently-promoted model.

---

## 1. Two scores, two questions

| Score | Question it answers | Learned from |
|---|---|---|
| **Impact Score** (public `value_score`; retrospective `impact_score`) | How much does this athlete change his team's chance of winning? | Game results: point margins, play-level win-probability/expected-points changes |
| **Gravity Score** (commercial) | How strong is this athlete's commercial pull relative to peers? | Market outcomes: who signs NIL deals next, whose attention grows next, verified deal $ (when n is sufficient) |

Impact becomes an **input feature** to Gravity's Proof group. Gravity never feeds Impact.

## 2. Diagnosis (why the current models cannot be right)

All findings verified in code at `Gravity_Score@10472a4` and `gravity-ml@f502095`.

| ID | Location | Problem |
|---|---|---|
| M1 | `gravity-ml/ml/training_labels.py:77-202` | Gravity label = `raw_composite_score()`, a fixed weighted sum (nil 0.28, recruiting 0.22, social 0.20, news 0.12, trends 0.10, draft 0.08, + stats/wiki/"dynasty" bonus), min–max scaled. Its inputs are also network inputs (`ml/feature_engineer.py:256-283`). The net learns to copy the formula. |
| M2 | `gravity-ml/ml/training_labels.py:242-286` | B/P/X/V/R towers trained on `component_proxy_raw()` — also hand formulas. SHAP therefore explains the formula, not the market. |
| M3 | `gravity_ml/train/train_champion.py:120-157` | Champion trainer reads targets from `athlete_gravity_scores` — **the model's own previous outputs** (`dollar_p50_usd`, `proof_score`, fallback `gravity_score`) — and adds `gravity_score_prior`, `proof_score_prior`, and `proof_composite_pctile = proof_score` as features. Self-training loop with direct target leakage. |
| M4 | `gravity_api/services/win_impact.py:348-538` | Impact label `target_impact_score` = `compute_win_impact_score_v0()`: 0.72·proof + 0.14·availability + 0.08·starter + 0.06·team + hand floors (MVP ⇒ ≥93, NBA star ⇒ ≥86.5, …). No game outcome is ever used. Docstring at 537 admits it is a bootstrap. |
| M5 | `scripts/train_cfb_impact_v1.py:95-134` | Promotion gate `--min-spearman 0.50` against M4's formula. The formula's inputs remain features (only the label columns are excluded via `gravity_ml/inference/vectorizer.py:94-130`), so the gate passes by construction. |
| M6 | `gravity_ml/inference/predict.py:228-298` | Live components are constants: Brand from log reach + trends; Velocity = 18 + 2·news + 0.28·trends (no time deltas); Risk = 62 − 28·data_quality − 0.5·news (more news ⇒ lower risk). Dollar bands (`:291-298`) = gravity × 22,000 heuristics. This is what the terminal shows when no bundle loads. |
| M7 | Two ML codebases | Sibling `gravity-ml` (last commit 2026-05-21, torch `GravityAthleteNet`) and in-monorepo `gravity_ml/` (sklearn regressors, imported by `gravity_api/services/sport_pipeline/run.py:36`, Docker bundle). |
| M8 | Data | Per-season history is corrupted (scraper spec B1–B9), and no game-level data exists. Any outcome-based model is blocked until the scraper spec lands. |

**M7 resolution:** implement in `Gravity_Score/gravity_ml/`. Port `GravityAthleteNet` from the sibling repo only if it wins the §4 bake-off. Before deploy, confirm what `ML_SERVICE_URL` points to in Railway; freeze whichever stack is not deployed.

## 3. Shared foundations (build first — WP-F)

### F1. Point-in-time dataset builder
`gravity_ml/data/pit.py`
```python
def build_snapshot(conn, athlete_ids, as_of: datetime, feature_set: str) -> pd.DataFrame
```
- Every feature value must have `observed_at <= as_of` (stats via `athlete_season_stats.stats_as_of`, socials via `social_snapshots.scraped_at`, metrics via `athlete_metric_history.period_start`).
- Excludes rows with `validation_status = 'mismatch'`.
- Returns `feature_coverage` per row (fraction of features observed vs imputed).
- Test: building as-of 2025-12-01 never returns a stat line from the 2026 season or a follower count scraped after that date.

### F2. Label registry with lineage
`gravity_ml/labels/registry.py` — each label declares `name`, `source_tables`, `horizon`, `builder`.
- **Banned sources:** `athlete_gravity_scores`, any `*_score*` column written by our models, `raw_composite_score`, `component_proxy_raw`, `compute_win_impact_score_v0`. Test fails if a registered label lists a banned source.
- **Banned features for every objective:** `gravity_score_prior`, `brand_score_prior`, `proof_score_prior`, `quality_score_prior`, `dollar_p*_usd`, `win_impact_score*`, `target_*`, and any column derived from a model output. Enforce in `vectorizer.OBJECTIVE_EXCLUDE` **and** via an allow-list: features must come from `features/manifest.py` (raw observations + engineered transforms of raw observations).

### F3. Circularity test (CI)
`gravity_ml/tests/test_label_circularity.py`: for each objective, fit `HistGradientBoostingRegressor` from the objective's feature set to its label on a fixture/staging sample; **fail if holdout R² ≥ 0.95**. This would have caught M1, M3, M4.

### F4. Evaluation harness
`gravity_ml/eval/harness.py`
- Time-based splits only (train on as_of < T, test on as_of ≥ T). No random row splits.
- Paired bootstrap (1,000 resamples) confidence intervals for every metric difference vs baseline.
- Writes `metrics.json` + a markdown report per run to `gravity_ml/reports/<model_key>/<timestamp>.md`.

### F5. Promotion
Extend `config/model_promotion_policy.json`: each model key lists required metrics, baselines, and minimum test sizes from §4/§5. `promotion_policy.py` refuses to load a bundle whose `metrics.json` does not satisfy them. Remove the `min_spearman` gates that compare against formula labels.

## 4. Impact model (winning contribution) — WP-I

### I0. Data required (from scraper spec)
`games`, `game_player_box` (minutes / snaps / started), `athlete_season_stats` (correct per-season), `team_season_stats`, and for CFB `cfb_plays` / `cfb_play_players` (CFBD PPA + win probability).

### I1. Game-level Adjusted Plus-Minus (all sports) — the core estimator
For each completed game *g* (home H, away A):
- Target: `y_g = home_score − away_score`.
- Design row: for each player *p* who appeared, `x_{g,p} = +s_{g,p}` if on H, `−s_{g,p}` if on A, where `s` = participation share:
  - basketball: `minutes_p / (team_minutes / 5)` (handles OT; a full-game player ≈ 1.0)
  - football: `snaps_p / team_snaps` per unit when snaps exist; else `1` if appeared (flag `participation_observed=false`).
- Extra columns: home-court/field indicator (0 for neutral site), season fixed effects.
- Fit: ridge regression (`sklearn.linear_model.Ridge`, sparse matrix), λ chosen by **forward-chaining time CV**. Multi-season fit with exponential sample-weight decay; half-life tuned by CV (search 0.5–3 seasons).
- Output: `beta_p` = points of margin per full game of participation, plus approximate standard error from the ridge posterior `σ²(XᵀWX + λI)⁻¹`.
- Separate fits per league (`ncaab_mens`, `ncaab_womens`, `cfb`, and pro leagues only if in product scope).

### I2. Basketball stint RAPM (refinement, where available)
If ESPN play-by-play substitution data reconstructs lineups for ≥ 80% of possessions in a game, fit possession-level RAPM (target: points per 100 possessions margin per stint). Use as the observation for those athletes; I1 otherwise. Skip games with broken lineups rather than imputing.

### I3. Football play value (CFB)
- Use CFBD PPA (expected-points added) per play and CFBD win probability before/after each play.
- Credit: passer/rusher/target get play PPA per CFBD role; defenders credited on sacks, TFL, INT, PBU, forced fumbles (role from `cfb_play_players`). Aggregate per player-season: `ppa_total`, `ppa_per_play`, `wpa_total`.
- These are observations for skill positions and the defensive event-makers; OL/DL-without-events rely on I1 + I4.

### I4. Box-score prior (generalizes to low-sample players)
Regress I1/I2/I3 estimates on per-season box rates (per-40 for basketball, per-game/per-snap for football), position group, class year, height/weight:
- Model: ridge and `HistGradientBoostingRegressor`; pick by CV. Sample weight = participation volume. Train only on player-seasons with high participation (e.g. top half of minutes within league) so the target is reliable; apply to everyone.
- Output: `prior_mean_p`, `prior_sd` (CV residual SD within position group).

### I5. Fusion and units
- Posterior per player-season: precision-weighted `(prior/σp² + obs/σo²) / (1/σp² + 1/σo²)`. No hand floors, no award bonuses — awards may enter only as I4 features if CV shows they help.
- Replacement level: 20th percentile of posterior impact among players meeting the minimum-participation rule in the same league and position group (percentile is a tunable constant documented in the report).
- Points → wins: fit per league from `team_season_stats` (win% regressed on average margin). Do not hard-code.
- Outputs per player-season:
  - `impact_rate` (margin per full game) ± SE
  - `impact_wins_added` = (posterior − replacement) × games-equivalent participation × wins-per-point ± SE
  - `impact_score` (0–100) = percentile of `impact_wins_added` within (league, position_group, season) among players meeting min participation; below the threshold → `impact_score = NULL`, `impact_status = 'insufficient_sample'`.
  - `impact_confidence` = derived from posterior SE (replace the hand-built `conf` at `win_impact.py:299-313`).
- Career "accumulation": sum of `impact_wins_added` across seasons, and a recency-weighted version (same half-life as I1).

### I6. Gates (all must pass on the latest completed season held out)
| Gate | Test | Pass condition |
|---|---|---|
| G-I1 | Predict held-out game margins from pre-game rosters (sum of posterior impact × expected participation + home term) | RMSE lower than a team-only rating baseline (prior-games team margin-adjusted rating) with 95% bootstrap CI of the difference excluding 0 |
| G-I2 | Predict next-season team win % from returning-roster impact | Beats previous-season team win % baseline (same CI rule) |
| G-I3 | Year-over-year stability of `impact_rate` for players with ≥ min participation in both seasons | Positive correlation reported; must exceed the stability of raw PPG/yards (for basketball/football respectively) or the report must explain why |
| G-I4 | Circularity test F3 | Pass |
| G-I5 | v0 baseline | New model must beat `compute_win_impact_score_v0` on G-I1 and G-I2 |

### I7. Code changes
- New package `gravity_ml/impact/`: `apm.py` (I1), `rapm.py` (I2), `football_play_value.py` (I3), `box_prior.py` (I4), `fuse.py` (I5), `train_impact.py` (CLI), `tests/`.
- `gravity_api/services/win_impact.py`: keep `compute_win_impact_score_v0` **only** as the fallback + baseline; rename to make that explicit; delete `compute_target_impact_score` and remove `win_impact_score_v0`/`target_impact_score` from `IMPACT_FEATURE_KEYS` (`:86-117`).
- Delete `scripts/train_cfb_impact_v1.py`'s formula-label path; replace with `python -m gravity_ml.impact.train_impact --league ncaab_mens`.
- Persist to new table `athlete_impact_seasons(athlete_id, league, season_year, impact_rate, impact_rate_se, impact_wins_added, impact_wins_added_se, impact_score, impact_status, model_version, computed_at)`.
- `predict.py:357-363` reads `athlete_impact_seasons` for the athlete's latest season instead of an impact bundle.

### I8. Rollout order
1. **NCAAB men 2025-26** (smallest valid experiment; box scores only) → gates → shadow.
2. NCAAB women, then CFB (needs CFBD plays).
3. Live 2026-27 updates nightly once in-season games accumulate (impact for current season shown with its SE; early-season SE will be large — display it).

## 5. Gravity model (commercial) — WP-G

### G1. Labels (all from market outcomes; registered in F2)
| Label | Definition at snapshot date t | Source | Role |
|---|---|---|---|
| `L_deal_180` | 1 if athlete has a deal with `deal_date ∈ (t, t+180d]` | `athlete_nil_deals`, `verified_deal_transactions` | **Primary** (ranking) |
| `L_attention_90` | log(reach at t+90d / reach at t), reach = trusted social total; also news-volume and search-interest versions | `social_snapshots`, `athlete_metric_history` | Auxiliary |
| `L_dollars` | log1p(verified deal USD) | `verified_deal_transactions` only (not On3, not our own estimates) | Quantile head; **disabled until ≥ 500 verified deals** (existing decision) |
| `L_unavail_180` | 1 if transfer-portal entry, draft departure, season-ending injury, or loss of starting role occurs in (t, t+180d] | roster events, injury feed, `athlete_team_seasons` | Risk head = `availability_index` |

**Coverage rule for `L_deal_180`:** deals are observed only where our deal sources were scraped. Include an athlete-window in training only if deal sources were scraped for that athlete during the window (`coverage_ok`). Report positive rate per sport; if a sport has < 30 positives in the test window, that sport is not promoted.

Snapshot dates: monthly as-of dates across available history. One row per (athlete, as_of).

### G2. Features (point-in-time via F1)
- Brand group: trusted social reach by platform (levels + 30/90d deltas), news volume (7/30/90d), search interest, Wikipedia views, partnership history up to t.
- Proof group: **Impact model outputs** (`impact_rate`, `impact_wins_added`, career accumulation), per-season box stats (from history, decay-weighted), awards, recruiting rank/stars.
- Proximity group: school, conference, market size, program success (`team_season_stats`), collective budget estimates, position.
- Velocity group: deltas of all of the above (7/30/90d; season-over-season).
- Risk group: injury history, transfer history, eligibility remaining, roster depth.
- External estimates allowed as **features only**: On3 `nil_valuation` (must also be a baseline to beat).
- Banned: see F2.
- "Gravity accumulation": career features computed from per-season history with exponential decay; half-life tuned by CV.

### G3. Model
- Baseline A: `HistGradientBoostingClassifier` on `L_deal_180` (no new dependencies).
- Candidate B: the torch trunk from sibling `gravity-ml/ml/athlete_net.py` (FiLM sport-position conditioning) with heads: listwise/pairwise ranking on `L_deal_180` (main), regression on `L_attention_90` (aux), `L_unavail_180` classifier, optional dollar quantiles. Remove the five component towers trained on proxy labels.
- Pick by §G5 gates. Calibrate probabilities (isotonic) on a separate time slice.

### G4. Outputs
- `gravity_raw` = calibrated P(deal in next 180d).
- `gravity_score` (0–100) = percentile of `gravity_raw` within (sport, season) among active athletes.
- **B/P/X/V/R component scores** = grouped SHAP attribution of `gravity_raw` over the §G2 feature groups, converted to within-cohort percentiles. This keeps the five-component contract (unified spec §6) but the components now explain a model of real market behavior. Risk additionally exposes `availability_index` from the `L_unavail_180` head.
- `top_drivers`: top grouped SHAP contributions with feature names.
- Dollar bands: only from `L_dollars` head after its gate passes; otherwise the API returns no dollar band (delete `_dollar_bands` heuristic at `predict.py:291-298` from public output; keep internally as a baseline).

### G5. Gates
| Gate | Test | Pass condition |
|---|---|---|
| G-G1 | Held-out time window, `L_deal_180` | Average precision and precision@50 per sport beat the best of: current formula (`raw_composite_score`), log social reach, On3 `nil_valuation`, recruiting rank — 95% bootstrap CI of the AP difference excludes 0 |
| G-G2 | `L_attention_90` | Spearman beats "current reach" and "last-90d growth" baselines |
| G-G3 | Calibration | Expected calibration error ≤ 0.05 on the held-out window |
| G-G4 | Circularity F3 | Pass |
| G-G5 | `L_unavail_180` | AUC beats a transfer-history-only baseline |
| G-G6 | Dollars (when enabled) | Existing `production_gates` in `model_promotion_policy.json`, recomputed on verified-only labels |

### G6. Code changes
- New `gravity_ml/gravity/`: `labels.py` (G1 builders registered in F2), `features.py`, `train_gravity.py`, `explain.py` (grouped SHAP), `tests/`.
- `gravity_ml/train/train_champion.py:120-157`: delete targets read from `athlete_gravity_scores` and the `*_prior` features. `train_champion` may remain only as an orchestration wrapper calling the new trainers.
- `gravity_ml/inference/predict.py`: `_components_from_raw` (228-275) becomes the **fallback only**, used when no promoted bundle exists; response sets `model_version="heuristic-fallback"` and `confidence_tier="planning_estimate"`. Fix the Risk fallback so news volume does not lower risk.
- Sibling `gravity-ml/ml/training_labels.py`: if that service is the deployed one, retire `composite_labels_0_100` and `component_proxy_raw` as training targets (keep as baselines in the eval harness).

## 6. Implementation order (work packages)
1. **WP-F** (F1–F5) — no model changes; adds tests that currently fail on M1/M3/M4 (expected).
2. **Scraper spec WP1–WP7, WP10** (prerequisite data).
3. **WP-I** NCAAB men → gates → shadow → promote; then other leagues.
4. **WP-G** labels + baseline A → gates → shadow; then candidate B.
5. Terminal/API: show `impact_score` with SE/confidence, Gravity with components from grouped SHAP, fallback clearly labeled. Update `docs/GRAVITY_UNIFIED_SPEC.md` and the two source-of-truth docs.

**Shadow period:** new and old scores computed side by side for ≥ 2 weeks; report rank changes for the top 100 per sport; promotion requires gates + Rob's sign-off on the report.

## 7. Do NOT
- Do not train on any label computed from our own scores or from a formula over the feature set.
- Do not add hand floors, award bonuses, or name-specific adjustments to make rankings "look right". If a known star ranks low, investigate data (scraper validation status, participation) and report; do not patch outputs.
- Do not use random row splits or evaluate on seasons/dates seen in training.
- Do not expose dollar figures from heuristics as model outputs.
- Do not treat On3 valuation as ground truth (it is a third-party model estimate).
- Do not claim a model is better without the §4/§5 gate report attached to the PR.

## 8. Open questions for Rob (do not block WP-F)
1. Are pro leagues (NBA/NFL/WNBA) in product scope for Impact and Gravity, or only as college-to-pro labels?
2. Which ML service is live on Railway (`ML_SERVICE_URL`)?
3. CFBD plan tier/quota for bulk `/plays` + `/play/stats` pulls.
4. How many dated deals exist in `athlete_nil_deals` + `verified_deal_transactions` per sport (sets whether G-G1 is testable now)?
