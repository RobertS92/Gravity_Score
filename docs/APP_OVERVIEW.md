# Gravity Score — Application Overview

## What It Is

**Gravity Score** is a sports player data and analytics system. It collects rich data on athletes (NFL, NBA, CFB, NCAAB, WNBA), runs it through a pipeline (flatten, impute, feature-engineering), and produces a **Gravity Score** and related predictions. The score combines brand, proof (performance), proximity (market/context), velocity (momentum), and risk into a single market-value signal.

---

## Main Features

### 1. Data Collection (Scraping)

- **Sports:** NFL, NBA, CFB, NCAAB (men's/women's), WNBA.
- **Per player (~150+ fields):** Identity (name, age, college, draft, height, weight), career and current-season stats, social media (Instagram, Twitter, TikTok, YouTube — followers, engagement), contract (value, status, earnings), awards (Pro Bowls, All-Pro, championships), risk (injury, controversy, age), brand (endorsements, media).
- **Sources:** ESPN, Pro Football Reference, Basketball Reference, NBA.com, Wikipedia, Firecrawl, optional OpenAI for parsing.
- **Output:** One CSV (and JSON) per run, e.g. `scrapes/NFL/{timestamp}/nfl_players_{timestamp}.csv`, with all players and fields.
- **Modes:** All players, by team, single player, test (e.g. one per team), interactive.

### 2. Data Pipeline (ETL)

- **Flatten:** Nested JSON → flat table (e.g. year-by-year stats limited to last N years).
- **Impute:** Missing values via rules (position-based height/weight, median social, etc.) and/or ML imputation (XGBoost-style models per critical field).
- **Features:** 100+ derived features (interactions, ratios, time-series, position-specific, career stage).
- **Gravity Score:** Weighted combination of component scores (Brand, Proof, Proximity, Velocity, Risk) into a 0–100 score with confidence and tier (e.g. Developing → Superstar).

### 3. Component Scoring (B, P, X, V, R)

- **Brand (B):** Social presence, followers, engagement, recognition.
- **Proof (P):** On-field/court performance, awards, championships.
- **Proximity (X):** Market context, contract, NIL, endorsements.
- **Velocity (V):** Growth, trends, momentum (performance and social).
- **Risk (R):** Injury, controversy, age; used as a subtraction in the final formula.

Formula (conceptually):  
`G = wB*B + wP*P + wX*X + wV*V - wR*R` (with optional confidence weighting).

### 4. ML Models

- **Imputation:** Fill missing values for key fields (age, contract, social, stats) with confidence.
- **Predictions:** Draft position, contract value, performance trend, injury risk, market value (from `gravity/ml_models.py` and `ml/train_all_models.py`).
- **Neural networks (ml/):** Specialized nets for performance, market value, social, velocity, risk; trained in `ml/train_all_models.py`.

### 5. API (Real-Time Scoring)

- **FastAPI** app (`api/gravity_api.py`): Health, model status, single/batch player scoring, ML predictions.
- **Input:** Player data (or batch); **output:** Gravity Score, component scores, ML predictions (e.g. contract value, injury risk).
- **Startup:** Loads trained models from disk (cache); serves scores and predictions at request time.

### 6. React Market Dashboard

- **React + Vite** app in `react-market-dashboard/`: Market view, player overview, financial overview, data analysis, market intelligence.
- **Uses:** Mock or API-sourced market/player data for visualization and analysis.

### 7. Crawlers & Automation

- **Crawlers** (e.g. news, injury, social, trades, transfer portal, sentiment): Keep data fresh and feed into risk/velocity/brand.
- **Scheduler/orchestrator:** Run crawlers and scrapers on a schedule; events can trigger score recalculations.

### 8. NIL Pipeline

- **NIL (Name, Image, Likeness):** Connectors (e.g. On3, Opendorse, Inflcr, Teamworks, 247, Rivals), entity resolution, normalization, confidence scoring, anomaly detection. Feeds into proximity and brand.

### 9. Packs & Export

- **Packs:** Aggregated outputs (e.g. JSON export, PDF reports) for players or cohorts.
- **Output layout:** `scrapes/{sport}/{timestamp}/` with CSV + JSON per run; test outputs under `test_results/`.

---

## User Flows

### Flow 1: Collect Raw Player Data

1. Set `FIRECRAWL_API_KEY` (and optionally `OPENAI_API_KEY`).
2. Run e.g. `python collect_all_nfl_players.py` or `python collect_all_nba_players.py`.
3. Get one CSV (and JSON) in `scrapes/NFL/` or `scrapes/NBA/` with ~1,700 NFL or ~450 NBA players and 150+ fields.

### Flow 2: Run Pipeline → Gravity Score

1. Run pipeline on a CSV (e.g. `run_pipeline.py` or equivalent) with flatten → impute → features → Gravity Score.
2. Output: enriched CSV/JSON with component scores and final Gravity Score (and optionally tier/percentile).

### Flow 3: Train ML Models

1. Point training at data: e.g. `python ml/train_all_models.py` (or `train_models.py` for non-NN models) with paths to scraped/pipeline CSVs.
2. Train imputation, feature engineering, and prediction/neural models; save to `models/` (or equivalent).
3. API loads these at startup to serve real-time scores and predictions.

### Flow 4: Use the API

1. Start API: `uvicorn api.gravity_api:app --reload --port 8000`.
2. Send player payload(s); receive Gravity Score, components, and ML predictions (contract, risk, etc.).

### Flow 5: Use the Dashboard

1. Run React app (`react-market-dashboard`); connect to API or mocks.
2. View market overview, players, financials, and analytics.

---

## Where Data Lives

| Purpose | Location / Form |
|--------|------------------|
| Raw scraped output | `scrapes/{NFL,NBA,CFB,...}/{timestamp}/*.csv`, `*.json` |
| Test runs | `test_results/{sport}/{timestamp}/` |
| Trained models | `models/` (e.g. imputation, prediction, NN checkpoints) |
| Pipeline output | Configurable; often CSV/JSON next to inputs or in a dedicated output dir |
| DB (if used) | `gravity/db/` (schema, migrations); stores scores, features, athletes where enabled |

---

## Summary

- **Input:** Live scraping (NFL, NBA, etc.) or existing CSV/JSON of players.
- **Processing:** Flatten → impute → feature engineering → component scores (B, P, X, V, R) → Gravity Score; optional ML predictions and neural nets.
- **Output:** One comprehensive CSV/JSON per run, Gravity Scores, component breakdowns, ML predictions; API for real-time scoring; React dashboard for market view; crawlers and NIL for ongoing data and context.

For the **technology and architecture** narrative for executives, see **EXECUTIVE_TECH_BRIEF.md**.
