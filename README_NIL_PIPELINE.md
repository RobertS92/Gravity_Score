# Gravity NIL Data Pipeline & Underwriting System

**Production-grade NIL valuation and deal decisioning system**

## Overview

This system implements a comprehensive NIL (Name, Image, Likeness) data pipeline and underwriting engine for college football athletes. It provides:

1. **NIL Data Pipeline**: Reliable, accurate, event-driven data collection from 6+ sources
2. **Annual NIL Negotiation Pack**: Underwriting-grade valuation memos
3. **Underwriting Engine**: Gravity-driven valuation and deal decisioning

All outputs are auditable, confidence-scored, and produce deterministic structured JSON that can be rendered to web and PDF.

## Architecture

```
Ingestion → Normalization → Entity Resolution → Data Quality → Feature Store → Scoring → Valuation → Pack Generation
```

### Key Components

1. **Ingestion Layer** (`gravity/nil/connectors/`)
   - On3 Connector (Tier 1: 0.95 reliability)
   - Opendorse Connector (Tier 1: 0.90 reliability)
   - INFLCR Connector (Tier 2: 0.85 reliability)
   - Teamworks Connector (Tier 2: 0.80 reliability)
   - 247Sports Connector (Tier 3: 0.75 reliability)
   - Rivals Connector (Tier 3: 0.75 reliability)

2. **Normalization & Storage** (`gravity/nil/normalization.py`)
   - Stores raw payloads for audit
   - Normalizes into canonical schema
   - PostgreSQL for structured data

3. **Entity Resolution** (`gravity/nil/entity_resolution.py`)
   - Deterministic matching (verified handles, roster match)
   - Probabilistic matching (name similarity + attributes)
   - Confidence threshold: 0.85

4. **Data Quality & Confidence Scoring** (`gravity/nil/confidence_scorer.py`)
   - Source reliability weighting
   - Recency decay (90-day half-life)
   - Cross-source agreement
   - Anomaly detection (Z-score > 3)

5. **Feature Store** (`gravity/nil/feature_calculator.py`)
   - Raw metrics (followers, deals, valuations)
   - Derived metrics (growth rates, trends)
   - Fraud-adjusted metrics

6. **Gravity Scoring** (`gravity/scoring/`)
   - Brand (B): Social presence, recognition
   - Proof (P): Performance, achievements
   - Proximity (X): Commercial readiness, deals
   - Velocity (V): Momentum, growth
   - Risk (R): Risk factors

7. **Valuation Engine** (`gravity/valuation/`)
   - IACV (Intrinsic Annual Commercial Value)
   - Deal underwriting (DSUV, RADV)
   - Negotiation terms generation

8. **Pack Generator** (`gravity/packs/`)
   - JSON export with full provenance
   - PDF generation with WeasyPrint
   - Deterministic, auditable outputs

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis (for async jobs)

### Setup

1. **Clone and install dependencies**:
```bash
cd gravity
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.nil.example .env.nil
# Edit .env.nil with your database and API credentials
```

3. **Initialize database**:
```bash
python -c "from gravity.storage import get_storage_manager; get_storage_manager().init_database()"
```

4. **Run migrations** (if using Alembic):
```bash
cd gravity/db/migrations
alembic upgrade head
```

## Usage

### 1. Collect NIL Data

```python
from gravity.nil import run_nil_collection

# Collect data from all sources
results = run_nil_collection(
    athlete_name="Travis Hunter",
    school="Colorado",
    sport="football"
)

print(f"Collected from {results['summary']['sources_successful']} sources")
print(f"NIL Valuation: ${results['aggregated']['consensus']['nil_valuation']:,.0f}")
```

### 2. Calculate Gravity Score

```python
from gravity.scoring import calculate_gravity_score
from datetime import date

gravity_score = calculate_gravity_score(
    athlete_id=athlete_uuid,
    season_id="2024-25",
    as_of_date=date.today()
)

print(f"Gravity Score: {gravity_score['gravity_conf']:.2f}/100")
print(f"Components: B={gravity_score['components']['brand']:.1f}, "
      f"P={gravity_score['components']['proof']:.1f}, "
      f"X={gravity_score['components']['proximity']:.1f}")
```

### 3. Calculate Valuation

```python
from gravity.valuation import calculate_iacv

valuation = calculate_iacv(
    athlete_id=athlete_uuid,
    season_id="2024-25"
)

print(f"IACV (P50): ${valuation['iacv_p50']:,.0f}")
print(f"Range: ${valuation['iacv_p25']:,.0f} - ${valuation['iacv_p75']:,.0f}")
```

### 4. Underwrite a Deal

```python
from gravity.valuation import underwrite_deal

deal_proposal = {
    'price': 100_000,
    'term_months': 12,
    'structure_type': 'fixed',
    'is_exclusive': True,
    'territory': 'national'
}

underwriting = underwrite_deal(
    athlete_id=athlete_uuid,
    season_id="2024-25",
    deal_proposal=deal_proposal
)

print(f"Decision: {underwriting['decision']}")
print(f"RADV: ${underwriting['radv']:,.0f}")
print(f"Rationale: {underwriting['decision_rationale']}")
```

### 5. Generate Negotiation Pack

```python
from gravity.packs import aggregate_pack_data, generate_pack_pdf

# Aggregate all data
pack_data = aggregate_pack_data(
    athlete_id=athlete_uuid,
    season_id="2024-25",
    deal_proposal=deal_proposal
)

# Generate PDF
pdf_path = generate_pack_pdf(pack_data, "pack.pdf")
print(f"Pack generated: {pdf_path}")
```

## API Usage

### Start API server:
```bash
cd gravity
uvicorn api.nil_api:app --reload --port 8000
```

### API Endpoints:

**Calculate Valuation**:
```bash
curl -X POST "http://localhost:8000/api/v1/athletes/{athlete_id}/valuation" \
  -H "Content-Type: application/json" \
  -d '{
    "athlete_id": "...",
    "season_id": "2024-25"
  }'
```

**Underwrite Deal**:
```bash
curl -X POST "http://localhost:8000/api/v1/athletes/{athlete_id}/underwrite" \
  -H "Content-Type: application/json" \
  -d '{
    "athlete_id": "...",
    "season_id": "2024-25",
    "deal_proposal": {
      "price": 100000,
      "term_months": 12,
      "structure_type": "fixed"
    }
  }'
```

**Request Negotiation Pack**:
```bash
curl -X POST "http://localhost:8000/api/v1/athletes/{athlete_id}/negotiation-pack" \
  -H "Content-Type: application/json" \
  -d '{
    "athlete_id": "...",
    "season_id": "2024-25"
  }'
```

## Async Job Processing

### Start Celery worker:
```bash
celery -A gravity.jobs.pack_worker worker --loglevel=info
```

### Start Redis (if not running):
```bash
redis-server
```

## CFB Scraper Integration

To integrate with the existing CFB scraper:

```python
# In gravity/cfb_scraper.py
from gravity.integrations.cfb_integration import integrate_nil_pipeline

# After collecting player data:
nil_result = integrate_nil_pipeline(
    player_name=player_name,
    team=team,
    sport='football'
)

if nil_result['success']:
    print(f"Gravity Score: {nil_result['gravity_score']['gravity_conf']:.2f}")
    print(f"IACV: ${nil_result['valuation']['iacv_p50']:,.0f}")
```

## Data Flow

1. **Collection**: 6 connectors run in parallel (ThreadPoolExecutor)
2. **Storage**: Raw payloads saved to filesystem/S3, metadata to PostgreSQL
3. **Normalization**: Parse and validate into canonical schema
4. **Entity Resolution**: Match to canonical athlete_id (deterministic + probabilistic)
5. **Quality Scoring**: Calculate confidence for every field
6. **Feature Calculation**: Compute raw, derived, and fraud-adjusted metrics
7. **Gravity Scoring**: Calculate B, P, X, V, R components → G_conf
8. **Valuation**: Calculate IACV with confidence intervals
9. **Underwriting**: Evaluate deal → approve/counter/no-go
10. **Pack Generation**: JSON + PDF with full provenance

## Formulas

### Gravity Score
```
G_raw = 0.25*B + 0.25*P + 0.20*X + 0.15*V - 0.15*R

G_conf = (wB*cB*B + wP*cP*P + wX*cX*X + wV*cV*V - wR*cR*R) /
         (wB*cB + wP*cP + wX*cX + wV*cV + wR*cR)
```

### IACV (Intrinsic Annual Commercial Value)
```
IACV_base = M_sport_level * f(G_conf) * Adj_market * Adj_role

Where f(g) = exp(k * (g - 0.5))

Variance: σ = σ₀ + λ*(1-avg_conf) + μ*volatility + ν*R/100

P25 = IACV_base * (1 - σ)
P50 = IACV_base
P75 = IACV_base * (1 + σ)
```

### Deal Underwriting
```
DSUV = IACV_base * Eff_structure * Mult_rights * Prob_exec
RADV = DSUV * (1 - LossRate(R))

Decision:
- RADV ≥ Price * 1.2 → approve
- RADV ≥ Price * 0.8 → counter
- RADV < Price * 0.8 → no-go
```

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/nil/test_connectors.py

# Run with coverage
pytest --cov=gravity tests/
```

## Production Deployment

1. **Database**: PostgreSQL 13+ with proper indexes
2. **Redis**: For Celery job queue
3. **API**: Deploy with Gunicorn + Nginx
4. **Workers**: Multiple Celery workers for pack generation
5. **Monitoring**: Log aggregation and error tracking
6. **Backups**: Automated PostgreSQL backups

## License

Proprietary - Gravity Score

## Contact

For questions or support, contact the Gravity engineering team.
