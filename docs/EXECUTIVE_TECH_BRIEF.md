# Gravity Score — Technical Brief for Executives

**Purpose:** Explain the technology, architecture, and tradeoffs behind Gravity Score for executive decision-makers (risk, scalability, cost, strategic fit).

---

## 1. What Problem the Technology Solves

- **Manual** athlete valuation is slow and inconsistent; **scattered** data (stats, social, contracts, risk) is hard to combine.
- **Gravity Score** automates: (1) collection of 150+ fields across multiple sports and sources, (2) cleaning and imputation of missing data, (3) a single weighted score (Brand, Proof, Proximity, Velocity, Risk) and (4) optional ML predictions (contract, draft, injury risk, etc.). The same pipeline supports NFL, NBA, CFB, NCAAB, WNBA so the approach is repeatable and auditable.

---

## 2. High-Level Architecture (One Slide)

```
[Data Sources: ESPN, PFR, BR, Firecrawl, NIL connectors, Crawlers]
                              |
                              v
[Scrapers / Collectors]  -->  Raw CSV/JSON  -->  [Pipeline: Flatten → Impute → Features]
                              |
                              v
[Component Scorers (B,P,X,V,R)]  -->  [Gravity Calculator]  -->  [ML Models / NN]
                              |
                              v
[Storage: CSV/JSON, optional DB]  <--  [API]  <--  [React Dashboard / External Clients]
```

- **Sources** feed into sport-specific scrapers and crawlers; output is timestamped CSV/JSON per run.
- **Pipeline** normalizes structure, fills gaps, and builds 100+ features; **scoring** turns features into component scores and final Gravity Score; **ML** adds predictions (imputation, contract, risk, etc.).
- **API** serves real-time scoring and predictions; **dashboard** and other clients consume the API or exported files.

---

## 3. Technology Behind Key Features

### 3.1 Data collection (scraping)

- **Mechanism:** Sport-specific modules (e.g. `nfl_scraper`, `nba_scraper`) using Firecrawl (and optional OpenAI) for discovery and parsing; parallel players and batched requests; rate limiting and retries.
- **Why it matters:** One command yields a single, wide CSV per league; no manual copy-paste. Quality depends on source stability and parsing logic.
- **Risk:** API limits, source changes, or ToS changes can affect freshness; design uses configurable concurrency and delays.

### 3.2 Pipeline (flatten, impute, features)

- **Mechanism:** **Flatten** converts nested JSON to flat rows (e.g. limited year-by-year); **imputation** uses rules (position defaults, medians) and/or trained ML models (XGBoost-style) for critical fields; **feature engineering** builds 100+ derived metrics (ratios, trends, position-specific).
- **Why it matters:** Consistent schema and fewer missing values improve scoring and model training; one code path for all sports with sport-specific logic where needed.
- **Risk:** Imputation can be wrong; we use confidence scores and optional human review for high-stakes fields.

### 3.3 Gravity Score (B, P, X, V, R)

- **Mechanism:** Each component (Brand, Proof, Proximity, Velocity, Risk) is scored 0–100 from features; weights combine them (e.g. B+P+X+V−R) with optional confidence weighting; output is 0–100 score, percentile, and tier.
- **Why it matters:** Single, explainable number for "market gravity" that stakeholders can tune (weights) and audit (component breakdowns).
- **Risk:** Weights and formulas are business choices; we keep them configurable and documented.

### 3.4 ML and neural networks

- **Mechanism:** **Classical ML** (e.g. XGBoost) for imputation and some predictors (draft, contract, trend, injury, market value); **PyTorch** neural nets in `ml/` for performance, market value, social, velocity, and risk; trained in `ml/train_all_models.py` (and related scripts) on historical scraped/pipeline data.
- **Why it matters:** Enables predictions (e.g. contract value, injury risk) and better imputation; NNs capture non-linear patterns.
- **Risk:** Model quality depends on data volume and labels; we version models and report metrics (e.g. MAE, MAPE) for transparency.

### 3.5 API and dashboard

- **Mechanism:** **FastAPI** backend loads models at startup; exposes REST endpoints for single/batch scoring and ML predictions; **React + Vite** dashboard calls API (or mocks) for market/player views.
- **Why it matters:** Real-time scoring for internal tools or partners; dashboard gives a single pane for market and player analytics.
- **Risk:** API and dashboard need deployment and access control in production; CORS and origins should be tightened.

### 3.6 Crawlers and NIL

- **Mechanism:** **Crawlers** (news, injury, social, trades, sentiment, etc.) run on a schedule; **NIL** connectors (On3, Opendorse, etc.) pull deals and entities; entity resolution and confidence scoring normalize NIL data for proximity/brand.
- **Why it matters:** Keeps Gravity Score current with news, injuries, and NIL activity; improves velocity and risk signals.
- **Risk:** Third-party NIL and news sources can change or disappear; we abstract connectors so they can be swapped.

---

## 4. Key Technical Choices and Tradeoffs

| Choice | Rationale | Tradeoff |
|--------|-----------|----------|
| Sport-specific scrapers | Clean separation; league-specific fields and sources. | More modules to maintain; shared patterns (e.g. Firecrawl) reduce duplication. |
| Single CSV per run | Simple to archive, share, and replay pipeline. | Large files for full leagues; can add DB for querying at scale. |
| Rule + ML imputation | Rules for obvious cases; ML where it adds value. | Two code paths; we prefer ML when we have enough data. |
| Weighted component formula | Transparent, tunable, auditable. | Requires periodic review of weights and definitions. |
| FastAPI + React | Fast to develop and deploy; familiar stack. | Not the only option; stack is replaceable if needed. |
| PyTorch NNs + classical ML | NNs for complex signals; classical for interpretability/speed. | More training and ops surface; we isolate training in `ml/` and `gravity/`. |

---

## 5. Scalability and Operations (Executive View)

- **Current design:** Single-machine scraping and pipeline; file-based output; API loads models in memory. Suitable for department/team use and periodic full-league runs.
- **Scaling up:** (1) **Data:** Move to a DB (PostgreSQL) for scores and features; keep raw scrapes as files or object storage. (2) **Compute:** Run scrapers and pipeline as batch jobs (e.g. cron, queue); optional worker pool for parallel runs. (3) **API:** Multiple API instances behind a load balancer; model cache shared or per-instance. (4) **Dashboard:** Static build on CDN; point to production API.
- **Security:** API keys (Firecrawl, OpenAI) in environment variables; no secrets in frontend. In production: secrets manager, restricted CORS, and auth for API and dashboard.
- **Observability:** Add logging, metrics (run duration, API latency, model load), and alerts so you can monitor cost, freshness, and errors.

---

## 6. Cost and Dependency Summary

- **APIs:** Firecrawl (and optionally OpenAI) drive most variable cost; usage scales with scrape frequency and player count.
- **Compute:** Training (ML/NN) is batch and can run on demand; API and dashboard are low cost at moderate traffic.
- **Storage:** CSV/JSON and optional DB; cost grows with history and number of sports/runs.
- **Dependencies:** Python (pandas, scikit-learn, XGBoost, PyTorch, FastAPI, etc.), Node/React for dashboard. We rely on widely used libraries to keep maintenance manageable.

---

## 7. How to Explain It in a Meeting

**One sentence:**  
"Gravity Score collects 150+ data points per athlete from multiple sports and sources, runs them through a standardized pipeline and component scoring (Brand, Proof, Proximity, Velocity, Risk), and exposes a single Gravity Score plus ML predictions via an API and dashboard so we can value and compare athletes consistently."

**Three bullets:**
- **Data:** Automated scraping and crawling (NFL, NBA, CFB, NCAAB, WNBA) plus NIL connectors; one wide CSV per run for reproducibility.
- **Score:** Transparent formula (B, P, X, V, R) with configurable weights; optional ML imputation and predictions (contract, risk, draft, etc.) for richer signals.
- **Delivery:** Pipeline and ML run in batch; API serves real-time scoring; React dashboard and exports support decision-making and partners.

**Risk mitigation:**  
"We use rule-based and ML imputation with confidence scores, version our models and weights, and keep raw data and pipeline outputs so we can audit and retune. Scrapers and NIL connectors are abstracted so we can adapt to source changes."

Use **APP_OVERVIEW.md** for product and user flows; use this document for the **technical and architectural** narrative with executives.
