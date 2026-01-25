# Gravity NIL Pipeline - Demo Simulation Results

## Overview
This demonstration simulates the complete Gravity NIL Pipeline with 3 elite CFB athletes from the 2025-2026 season.

## Test Athletes

### 1. **Shedeur Sanders** - Colorado Buffaloes (QB, Senior)
- **Gravity Score**: 59.95/100
  - Brand (B): 83.0 - High social media presence and name recognition
  - Proof (P): 66.0 - Solid on-field performance
  - Proximity (X): 70.0 - Strong NIL deal ecosystem
  - Velocity (V): 76.0 - Growing momentum
  - Risk (R): 18.0 - Low risk profile

- **Valuation (IACV)**:
  - Conservative (P25): $82,260
  - Expected (P50): **$106,142**
  - Optimistic (P75): $130,024

- **Deal Underwriting**:
  - Proposed Price: $106,142/year
  - Risk-Adjusted Value (RADV): $105,558
  - **Decision**: COUNTER at $95,002
  
- **Negotiation Strategy**:
  - Anchor: $132,678
  - Target: $105,558
  - Walk-Away: $79,169

### 2. **Arch Manning** - Texas Longhorns (QB, Sophomore)
- **Gravity Score**: 57.20/100
  - Brand (B): 67.0 - Legacy name (Manning family)
  - Proof (P): 81.0 - Elite pedigree, emerging talent
  - Proximity (X): 65.0 - Strong market (SEC, Austin metro)
  - Velocity (V): 70.0 - High trajectory
  - Risk (R): 22.0 - Moderate risk (less experience)

- **Valuation (IACV)**:
  - Conservative (P25): $100,995
  - Expected (P50): **$130,316**
  - Optimistic (P75): $159,637

- **Deal Underwriting**:
  - Proposed Price: $130,316/year
  - Risk-Adjusted Value (RADV): $129,599
  - **Decision**: COUNTER at $116,639
  
- **Negotiation Strategy**:
  - Anchor: $162,895
  - Target: $129,599
  - Walk-Away: $97,199

### 3. **Travis Hunter** - Colorado Buffaloes (WR/CB, Junior)
- **Gravity Score**: 60.45/100
  - Brand (B): 80.0 - Unique two-way player story
  - Proof (P): 80.0 - Elite performance on both sides
  - Proximity (X): 70.0 - High-profile program exposure
  - Velocity (V): 69.0 - Consistent growth
  - Risk (R): 26.0 - Injury risk (plays both ways)

- **Valuation (IACV)**:
  - Conservative (P25): $65,610
  - Expected (P50): **$84,658**
  - Optimistic (P75): $103,706

- **Deal Underwriting**:
  - Proposed Price: $84,658/year
  - Risk-Adjusted Value (RADV): $84,192
  - **Decision**: COUNTER at $75,773
  
- **Negotiation Strategy**:
  - Anchor: $105,822
  - Target: $84,192
  - Walk-Away: $63,144

## Pipeline Stages Demonstrated

### 1. 📊 NIL Data Collection
- Simulated scraping from 5+ sources:
  - On3.com (NIL valuations & rankings)
  - Opendorse.com (deals & partnerships)
  - INFLCR.com (content tracking)
  - 247Sports.com (recruiting profiles)
  - Rivals.com (athlete profiles)
- Data quality scoring: 0.85-0.95
- Deal discovery: 5-6 deals per athlete
- External valuations captured

### 2. ⭐ Gravity Score Calculation
The 5-factor model weighs:
- **Brand (25%)**: Social following, media mentions, name recognition
- **Proof (25%)**: On-field stats, accolades, performance
- **Proximity (20%)**: Market access, school reputation, geography
- **Velocity (15%)**: Trend direction, momentum, growth
- **Risk (15%)**: Controversy, injury history, reliability

### 3. 💰 IACV Valuation
Intrinsic Annual Commercial Value formula:
```
IACV = M_base × f(G) × M_adj × R_adj
```
Where:
- `M_base`: Base market multiplier ($45K-$50K)
- `f(G)`: Scaling function based on Gravity score
- `M_adj`: Market adjustment (school, conference, location)
- `R_adj`: Role adjustment (position premium)

Outputs include P25/P50/P75 confidence intervals.

### 4. 📋 Deal Underwriting
For each proposed deal:
1. Calculate DSUV (Deal Structural Underwritten Value)
   - Accounts for structure efficiency, rights multiplier, execution probability
2. Calculate RADV (Risk-Adjusted Deal Value)
   - Applies loss rate based on risk factors
3. Make decision:
   - **APPROVE**: RADV ≥ 120% of price
   - **COUNTER**: RADV 80-120% of price
   - **NO-GO**: RADV < 80% of price

### 5. 💼 Negotiation Strategy
For counter scenarios, provide:
- **Anchor Price**: Opening offer (IACV × 1.25)
- **Target Price**: Desired outcome (RADV)
- **Walk-Away Price**: Minimum acceptable (RADV × 0.75)

## Key Insights from Demo

### Athlete Comparison
| Athlete | Position | Gravity | IACV (P50) | Decision |
|---------|----------|---------|------------|----------|
| Shedeur Sanders | QB | 59.95 | $106,142 | Counter |
| Arch Manning | QB | 57.20 | $130,316 | Counter |
| Travis Hunter | WR/CB | 60.45 | $84,658 | Counter |

### Observations
1. **QB Premium**: QBs command 20-40% higher valuations
2. **Conference Effect**: SEC athletes (Manning) receive higher base multipliers
3. **Brand Power**: High brand scores (Sanders 83, Hunter 80) drive valuations
4. **Risk Adjustment**: Two-way player (Hunter) carries higher risk score
5. **Market Efficiency**: All deals resulted in counter-offers, suggesting fair initial pricing

## Full Implementation Features

This demo simulates the core pipeline. The **production implementation** includes:

### Database Layer
- ✅ PostgreSQL schema for normalized data storage
- ✅ SQLAlchemy ORM models
- ✅ Alembic migrations
- ✅ Field-level provenance tracking
- ✅ Confidence scoring at every layer

### Data Ingestion
- ✅ Real web scrapers for 6+ NIL sources
- ✅ Parallel data collection (ThreadPoolExecutor)
- ✅ Entity resolution with deterministic + probabilistic matching
- ✅ Raw payload storage for auditability
- ✅ Data quality + anomaly detection

### Scoring & Valuation
- ✅ Feature store with 30+ computed metrics
- ✅ Component scorers for B, P, X, V, R
- ✅ Weighted Gravity score calculation
- ✅ IACV calculator with market adjustments
- ✅ Deal underwriter with DSUV/RADV formulas

### Output & Integration
- ✅ Negotiation Pack aggregator
- ✅ JSON export (structured data)
- ✅ PDF generation with WeasyPrint
- ✅ FastAPI REST endpoints
- ✅ Celery async job processing
- ✅ Redis message broker

### Compliance & Auditability
- ✅ Source reliability weighting
- ✅ Recency decay functions
- ✅ Cross-source agreement tracking
- ✅ Match explanation logging
- ✅ Decision rationale capture

## Next Steps

To run the **full pipeline** with real data:

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup PostgreSQL**:
   ```bash
   createdb gravity_nil
   export DATABASE_URL="postgresql://user:password@localhost:5432/gravity_nil"
   alembic upgrade head
   ```

3. **Run NIL Collection**:
   ```bash
   python -m gravity.nil.connector_orchestrator --athlete "Player Name" --school "School"
   ```

4. **Generate Pack**:
   ```bash
   python -m gravity.packs.pack_aggregator --athlete-id <uuid> --deal-proposal deal.json
   ```

5. **Start API Server**:
   ```bash
   uvicorn gravity.api.nil_api:app --reload
   ```

## Contact & Support

For questions about the Gravity NIL Pipeline:
- Review `README_NIL_PIPELINE.md` for architecture details
- Check `IMPLEMENTATION_SUMMARY.md` for component specifications
- See code documentation in `gravity/` modules

---

**Generated**: 2026-01-23  
**Version**: 1.0.0  
**Pipeline**: Gravity NIL Underwriting System
