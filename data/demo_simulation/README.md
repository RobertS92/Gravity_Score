# Running the Gravity NIL Pipeline Simulation

## Quick Demo (No Dependencies)

The demo simulation runs without any database or external dependencies. It simulates the entire NIL pipeline with realistic data.

```bash
cd /Users/robcseals/Gravity_Score
python3 gravity/demo_simulation.py
```

**What it demonstrates:**
- NIL data collection from multiple sources
- 5-factor Gravity scoring (Brand, Proof, Proximity, Velocity, Risk)
- IACV valuation with confidence intervals
- Deal underwriting with risk adjustment
- Negotiation strategy generation

**Output:**
- Console output with detailed results
- `data/demo_simulation/demo_results.json` - structured data
- `data/demo_simulation/DEMO_SUMMARY.md` - detailed analysis

**Test Athletes:**
1. Shedeur Sanders - Colorado QB
2. Arch Manning - Texas QB
3. Travis Hunter - Colorado WR/CB

---

## Full Pipeline (Requires Setup)

The full implementation requires PostgreSQL, Python dependencies, and optional services.

### Prerequisites

1. **Python 3.9+**
2. **PostgreSQL 14+**
3. **Redis** (optional, for async jobs)

### Installation

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Setup PostgreSQL database
createdb gravity_nil

# 3. Set environment variable
export DATABASE_URL="postgresql://user:password@localhost:5432/gravity_nil"

# 4. Run database migrations
cd /Users/robcseals/Gravity_Score
alembic upgrade head

# 5. (Optional) Start Redis for async jobs
redis-server
```

### Running the Full Pipeline

#### Option 1: Full Test Simulation
```bash
PYTHONPATH=/Users/robcseals/Gravity_Score python3 gravity/test_simulation.py
```

This runs the complete pipeline with real scrapers and database storage.

#### Option 2: API Server
```bash
uvicorn gravity.api.nil_api:app --reload --host 0.0.0.0 --port 8000
```

Then access the API:
- GET `/api/nil/athletes/{athlete_id}` - Get athlete profile
- POST `/api/nil/collect` - Trigger NIL data collection
- POST `/api/nil/calculate-gravity` - Calculate Gravity score
- POST `/api/nil/generate-pack` - Generate negotiation pack

#### Option 3: Celery Workers (Async)
```bash
# Terminal 1: Start Celery worker
celery -A gravity.jobs.pack_worker worker --loglevel=info

# Terminal 2: Trigger async job
python -c "from gravity.jobs.pack_worker import generate_pack_async; generate_pack_async.delay(athlete_id, season_id, deal_proposal)"
```

### Manual Data Collection

Collect NIL data for a specific athlete:

```python
from gravity.nil.connector_orchestrator import NILConnectorOrchestrator

orchestrator = NILConnectorOrchestrator()
data = orchestrator.collect_all_nil_data(
    player_name="Shedeur Sanders",
    college="Colorado"
)
```

### Generate Negotiation Pack

```python
from gravity.packs import aggregate_pack_data, export_pack_json, generate_pack_pdf

# Aggregate data
pack_data = aggregate_pack_data(
    athlete_id=athlete_uuid,
    season_id="2025-26",
    deal_proposal={
        'price': 100000,
        'term_months': 12,
        'rights': ['social_media', 'appearances']
    }
)

# Export
export_pack_json(pack_data, 'output/pack.json')
generate_pack_pdf(pack_data, 'output/pack.pdf')
```

---

## Architecture

```
gravity/
├── db/                      # Database models & migrations
│   ├── schema.sql          # PostgreSQL schema
│   ├── models.py           # SQLAlchemy ORM models
│   └── migrations/         # Alembic migrations
│
├── storage/                 # Data persistence layer
│   └── storage_manager.py  # Database operations
│
├── nil/                     # NIL data pipeline
│   ├── connectors/         # Source-specific scrapers
│   │   ├── on3_connector.py
│   │   ├── opendorse_connector.py
│   │   └── ...
│   ├── connector_orchestrator.py  # Parallel collection
│   ├── entity_resolution.py       # Athlete matching
│   ├── normalization.py           # Data normalization
│   ├── confidence_scorer.py       # Confidence scoring
│   └── feature_calculator.py      # Feature engineering
│
├── scoring/                 # Gravity scoring system
│   ├── component_scorers.py      # B, P, X, V, R scorers
│   └── gravity_calculator.py     # Weighted G score
│
├── valuation/              # Underwriting engine
│   ├── iacv_calculator.py        # Intrinsic value
│   ├── deal_underwriter.py       # DSUV/RADV calculation
│   └── negotiation_terms.py      # Deal strategy
│
├── packs/                  # Output generation
│   ├── pack_aggregator.py        # Data aggregation
│   ├── json_exporter.py          # JSON output
│   └── pdf_generator.py          # PDF generation
│
├── api/                    # REST API endpoints
│   └── nil_api.py          # FastAPI routes
│
└── jobs/                   # Async job processing
    └── pack_worker.py      # Celery tasks
```

---

## Key Concepts

### Gravity Score (G)
5-factor weighted score (0-100):
- **Brand (25%)**: Social reach, media presence
- **Proof (25%)**: Performance metrics, accolades
- **Proximity (20%)**: Market access, school reputation
- **Velocity (15%)**: Growth trajectory, momentum
- **Risk (15%)**: Controversy, injuries, reliability

### IACV (Intrinsic Annual Commercial Value)
Annual NIL value based on:
```
IACV = M_base × f(G) × M_adj × R_adj
```
- Base market multiplier
- Gravity-based scaling
- Market adjustments (conference, school, location)
- Role adjustments (position premium)

### Deal Underwriting
Risk-adjusted deal evaluation:
1. **DSUV**: Deal Structural Underwritten Value
2. **RADV**: Risk-Adjusted Deal Value  
3. **Decision**: Approve / Counter / No-Go

### Negotiation Pack
Production-grade PDF including:
- Athlete profile & Gravity breakdown
- Valuation with confidence intervals
- Deal analysis & recommendation
- Negotiation strategy
- Contract clause recommendations
- Provenance & confidence tracking

---

## Troubleshooting

### Demo Won't Run
```bash
# Ensure Python 3.9+
python3 --version

# Run from correct directory
cd /Users/robcseals/Gravity_Score
python3 gravity/demo_simulation.py
```

### Full Pipeline Import Errors
```bash
# Set PYTHONPATH
export PYTHONPATH=/Users/robcseals/Gravity_Score:$PYTHONPATH

# Or install in dev mode
pip install -e .
```

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_isready

# Verify DATABASE_URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Missing Dependencies
```bash
# Install all requirements
pip install sqlalchemy alembic psycopg2-binary fastapi uvicorn celery redis requests beautifulsoup4 numpy pandas

# For PDF generation
pip install weasyprint
```

---

## Results Location

- **Demo**: `data/demo_simulation/`
- **Full Pipeline**: `data/test_simulation/`
- **Logs**: `*.log` files in project root
- **Database**: PostgreSQL `gravity_nil` database

---

**Last Updated**: 2026-01-23  
**Version**: 1.0.0
