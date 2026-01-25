# Scraper System Overview

## 🎯 Purpose

The Gravity NIL Pipeline scraper system collects NIL (Name, Image, Likeness) data from **6+ sources** for college football athletes, normalizes it into a canonical schema, and stores it in PostgreSQL for downstream analysis and underwriting.

## 🏗️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│              ConnectorOrchestrator                           │
│  • Parallel execution (6 connectors simultaneously)        │
│  • Result aggregation & consensus calculation                │
│  • Error handling & retry logic                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   On3        │ │  Opendorse   │ │   INFLCR     │
│  (0.95)      │ │   (0.90)     │ │   (0.85)     │
└──────────────┘ └──────────────┘ └──────────────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │ Normalization    │
            │ Pipeline         │
            └──────────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │ PostgreSQL       │
            │ Database         │
            └──────────────────┘
```

## 📊 Data Sources

### Tier 1: Primary NIL Platforms (90-95% reliability)

| Source | Reliability | What It Provides |
|--------|-------------|------------------|
| **On3** | 0.95 | Verified NIL valuations, rankings, deal announcements |
| **Opendorse** | 0.90 | Athlete profiles, marketplace listings, social metrics |

### Tier 2: Analytics Platforms (80-85% reliability)

| Source | Reliability | What It Provides |
|--------|-------------|------------------|
| **INFLCR** | 0.85 | Social analytics, engagement rates, content activity |
| **Teamworks** | 0.80 | Limited NIL deal mentions |

### Tier 3: News & Recruiting (70-75% reliability)

| Source | Reliability | What It Provides |
|--------|-------------|------------------|
| **247Sports** | 0.75 | Recruiting rankings, NIL news, transfer portal |
| **Rivals** | 0.70 | Recruiting profiles, NIL coverage |

## 🔄 How It Works

### 1. Collection Phase

```python
# User requests data for athlete
results = run_nil_collection("Shedeur Sanders", "Colorado", "football")

# Orchestrator runs all 6 connectors in parallel
# Each connector:
#   - Searches for athlete
#   - Fetches profile/data
#   - Extracts NIL information
#   - Normalizes to canonical schema
```

### 2. Aggregation Phase

```python
# Results from all sources are combined
# Consensus values calculated (weighted by reliability)
# Data quality score computed
# Deals deduplicated
```

### 3. Normalization Phase

```python
# Entity resolution (match to athlete_id)
# Extract valuations → NILValuation records
# Extract deals → NILDeal records
# Store in PostgreSQL
```

## 📋 Canonical Schema

All connectors normalize to this standard format:

```python
{
    'nil_valuation': float,      # Annual value in USD
    'nil_ranking': int,          # National ranking
    'nil_deals': [               # List of deals
        {
            'brand': str,
            'type': str,
            'value': float,
            'source': str
        }
    ],
    'social_metrics': {
        'instagram': int,
        'twitter': int,
        'total_followers': int
    },
    'recruiting_ranking': int,
    'recruiting_stars': int,
    'profile_url': str
}
```

## 🚀 Quick Start

### Basic Usage

```python
from gravity.nil.connector_orchestrator import run_nil_collection

# Collect NIL data
results = run_nil_collection(
    athlete_name="Arch Manning",
    school="Texas",
    sport="football"
)

# Access consensus valuation
valuation = results['aggregated']['consensus']['nil_valuation']
print(f"Consensus NIL Valuation: ${valuation:,.0f}")

# Check data quality
quality = results['summary']['data_quality_score']
print(f"Data Quality: {quality:.2f}")
```

### Individual Connector

```python
from gravity.nil.connectors import On3Connector

connector = On3Connector()
data = connector.collect("Shedeur Sanders", "Colorado", "football")

if data:
    print(f"On3 Valuation: ${data.get('nil_valuation', 0):,.0f}")
    print(f"On3 Ranking: #{data.get('nil_ranking', 'N/A')}")
```

## 🛠️ Key Components

### BaseNILConnector

Abstract base class providing:
- Rate limiting
- Retry logic
- HTTP client with timeouts
- Currency/ranking parsers
- HTML parsing utilities

### Individual Connectors

Each source has its own connector:
- `On3Connector` - Primary valuation source
- `OpendorseConnector` - Marketplace & profiles
- `INFLCRConnector` - Social analytics
- `TeamworksConnector` - Team platform
- `Sports247Connector` - Recruiting & news
- `RivalsConnector` - Recruiting & news

### ConnectorOrchestrator

Manages:
- Parallel execution
- Result aggregation
- Consensus calculation
- Error handling

### NormalizationPipeline

Handles:
- Entity resolution
- Schema mapping
- Database storage
- Event tracking

## 📈 Performance

- **Parallel Execution**: 6 connectors run simultaneously
- **Rate Limiting**: 1.0s delay between requests (per connector)
- **Timeout**: 30 seconds per connector
- **Retry Logic**: 3 attempts with exponential backoff
- **Typical Duration**: 5-10 seconds for full collection

## 🔍 Monitoring

### Key Metrics

```python
results = run_nil_collection(...)

# Success rate
success_rate = results['summary']['sources_successful'] / \
               results['summary']['sources_attempted']

# Data quality
quality = results['summary']['data_quality_score']

# Consensus variance
valuations = [v['value'] for v in results['aggregated']['nil_valuations']]
variance = max(valuations) - min(valuations) if valuations else 0
```

## 🐛 Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Raw Data

```python
results = run_nil_collection(...)

# Check specific source
on3_result = results['sources']['on3']
if on3_result['success']:
    raw_data = on3_result['data']
    print(raw_data.get('raw_html'))  # If stored
```

## 📚 Documentation

- **[Full Architecture](./SCRAPER_ARCHITECTURE.md)** - Detailed technical documentation
- **[Quick Reference](./SCRAPER_QUICK_REFERENCE.md)** - Cheat sheet for developers
- **[Data Flow](./SCRAPER_DATA_FLOW.md)** - Visual flow diagrams
- **[Implementation Summary](../IMPLEMENTATION_SUMMARY.md)** - System overview

## 🎯 Best Practices

1. ✅ **Always use orchestrator** - Don't call connectors directly
2. ✅ **Check data quality score** - Ensure sufficient sources succeeded
3. ✅ **Use consensus values** - More reliable than single source
4. ✅ **Handle missing data** - Not all sources have all fields
5. ✅ **Monitor error rates** - Track failed connectors
6. ✅ **Respect rate limits** - Don't modify connector delays unnecessarily

## 🔮 Future Enhancements

- [ ] API key support for authenticated sources
- [ ] Caching layer for profile URLs
- [ ] Real-time webhook updates
- [ ] ML-based extraction for better accuracy
- [ ] Additional sources (ESPN, Sports Illustrated, etc.)
- [ ] GraphQL API for flexible queries

---

**Last Updated**: 2026-01-23  
**Version**: 1.0.0  
**Maintainer**: Gravity NIL Pipeline Team
