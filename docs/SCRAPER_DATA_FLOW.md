# Scraper Data Flow Diagram

## Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER REQUEST                                     │
│  run_nil_collection("Shedeur Sanders", "Colorado", "football")          │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ConnectorOrchestrator                                 │
│  • Initialize 6 connectors                                              │
│  • Create ThreadPoolExecutor (6 workers)                                │
│  • Submit parallel tasks                                                 │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ On3Connector │    │OpendorseConn │    │ INFLCRConn   │
│              │    │              │    │              │
│ 1. fetch_raw │    │ 1. fetch_raw │    │ 1. fetch_raw │
│    ├─ Search │    │    ├─ Search │    │    ├─ School │
│    ├─ Profile│    │    ├─ Profile│    │    └─ Extract │
│    └─ Extract│    │    └─ Extract│    │              │
│              │    │              │    │              │
│ 2. normalize│    │ 2. normalize │    │ 2. normalize │
│    ├─ Valuat │    │    ├─ Valuat │    │    ├─ Social │
│    ├─ Rank   │    │    ├─ Social │    │    └─ Engage │
│    └─ Deals  │    │    └─ Deals  │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Result Aggregation                                  │
│  • Combine all source results                                            │
│  • Deduplicate deals (by brand)                                         │
│  • Calculate consensus values (weighted by reliability)                  │
│  • Compute data quality score                                            │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Aggregated Results                                    │
│  {                                                                       │
│    'sources': {                                                          │
│      'on3': {success: True, data: {...}, reliability: 0.95},           │
│      'opendorse': {success: True, data: {...}, reliability: 0.90},     │
│      ...                                                                 │
│    },                                                                    │
│    'aggregated': {                                                       │
│      'nil_valuations': [...],                                            │
│      'nil_deals': [...],                                                 │
│      'consensus': {                                                      │
│        'nil_valuation': 1175000,  # Weighted average                    │
│        'nil_valuation_min': 1150000,                                    │
│        'nil_valuation_max': 1200000                                     │
│      }                                                                   │
│    },                                                                    │
│    'summary': {                                                          │
│      'sources_successful': 5,                                            │
│      'data_quality_score': 0.87                                         │
│    }                                                                     │
│  }                                                                       │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  NormalizationPipeline                                    │
│  normalize_collection_results(results, athlete_id=None)                  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Entity Resolution                                      │
│  • Try deterministic match (external IDs)                                 │
│  • Fall back to probabilistic match (name similarity)                    │
│  • Create new athlete if no match                                        │
│  • Return athlete_id + confidence                                        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Data Extraction                                        │
│  • Extract valuations → NILValuation records                            │
│  • Extract deals → NILDeal records                                      │
│  • Deduplicate by (brand, source)                                        │
│  • Validate data types and ranges                                        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    StorageManager                                        │
│  • Save NILValuation to database                                        │
│  • Save NILDeal to database                                              │
│  • Store raw payloads (for audit)                                       │
│  • Create AthleteEvent records                                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                                    │
│  • athletes table                                                        │
│  • nil_valuations table                                                  │
│  • nil_deals table                                                       │
│  • raw_data table (audit trail)                                         │
│  • athlete_events table                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## Individual Connector Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BaseNILConnector.collect()                            │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Rate Limiting                                         │
│  • Check last_request_time                                               │
│  • Sleep if needed (default: 1.0s)                                      │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    fetch_raw() [Abstract]                                 │
│  • Build search URL                                                      │
│  • fetch_url() with retry logic                                          │
│  • Parse HTML with BeautifulSoup                                         │
│  • Extract raw data                                                      │
│  • Return dict or None                                                   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    normalize() [Abstract]                                 │
│  • Extract nil_valuation                                                │
│  • Extract nil_ranking                                                   │
│  • Extract nil_deals                                                     │
│  • Extract social_metrics                                                │
│  • Return canonical schema                                               │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Add Metadata                                           │
│  {                                                                       │
│    ...normalized_data...,                                                │
│    '_metadata': {                                                        │
│      'source': 'on3',                                                    │
│      'source_reliability': 0.95,                                        │
│      'fetched_at': '2026-01-23T...',                                     │
│      'athlete_name': 'Shedeur Sanders',                                 │
│      'school': 'Colorado'                                                │
│    }                                                                     │
│  }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Consensus Calculation Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Multiple Source Valuations                            │
│  [                                                                       │
│    {source: 'on3', value: 1200000, reliability: 0.95},                 │
│    {source: 'opendorse', value: 1150000, reliability: 0.90},           │
│    {source: '247sports', value: 1100000, reliability: 0.75}              │
│  ]                                                                       │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Weighted Average                                      │
│  total_weight = 0.95 + 0.90 + 0.75 = 2.60                              │
│  weighted_sum = (1200000 × 0.95) + (1150000 × 0.90) + (1100000 × 0.75)│
│              = 1140000 + 1035000 + 825000 = 3000000                     │
│  consensus = 3000000 / 2.60 = 1,153,846                                 │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Range Calculation                                     │
│  values = [1100000, 1150000, 1200000]                                   │
│  min = 1100000                                                           │
│  max = 1200000                                                           │
│  median = 1150000                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Connector Execution                                   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
        ┌──────────────┐          ┌──────────────┐
        │   Success    │          │    Error     │
        └──────┬───────┘          └──────┬───────┘
               │                         │
               │                         ▼
               │                  ┌──────────────┐
               │                  │ Log Error    │
               │                  │ Add to errors│
               │                  └──────┬───────┘
               │                         │
               ▼                         │
        ┌──────────────┐                │
        │ Add to       │                │
        │ sources dict │                │
        └──────┬───────┘                │
               │                        │
               └────────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Continue with other  │
                │ connectors           │
                └───────────────────────┘
```

## Data Quality Score Calculation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Quality Score Components                             │
│                                                                         │
│  1. Source Success (weighted by reliability)                            │
│     • On3 success: 0.95 points                                          │
│     • Opendorse success: 0.90 points                                   │
│     • INFLCR success: 0.85 points                                      │
│     • ...                                                               │
│                                                                         │
│  2. Key Data Presence                                                   │
│     • Has valuation: +0.5 points                                       │
│     • Has ranking: +0.3 points                                         │
│     • Has deals: +0.2 points                                           │
│                                                                         │
│  3. Calculate Score                                                     │
│     score = (source_points + data_points) / max_possible                │
│     max_possible = sum(all_reliabilities) + 1.0                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

**Visual Legend**:
- `┌─┐` = Process/Component
- `│` = Data flow
- `▼` = Downward flow
- `├─` = Branching
- `{ }` = Data structure
