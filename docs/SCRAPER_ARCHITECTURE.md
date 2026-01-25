# Gravity NIL Pipeline - Scraper Architecture & Data Sources

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Base Connector Framework](#base-connector-framework)
3. [Data Sources & Reliability Tiers](#data-sources--reliability-tiers)
4. [Individual Scrapers](#individual-scrapers)
5. [Connector Orchestrator](#connector-orchestrator)
6. [Data Flow & Normalization](#data-flow--normalization)
7. [Extending the System](#extending-the-system)

---

## Architecture Overview

### Design Pattern: Strategy + Orchestrator

The scraper system uses a **Strategy Pattern** with a centralized **Orchestrator**:

```
┌─────────────────────────────────────────────────────────────┐
│                  ConnectorOrchestrator                        │
│  • Parallel execution (ThreadPoolExecutor)                  │
│  • Rate limiting & retry logic                              │
│  • Result aggregation & consensus calculation               │
│  • Error handling & logging                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ On3Connector │ │OpendorseConn │ │ INFLCRConn   │
│              │ │              │ │              │
│ • fetch_raw()│ │ • fetch_raw()│ │ • fetch_raw()│
│ • normalize()│ │ • normalize()│ │ • normalize()│
└──────────────┘ └──────────────┘ └──────────────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │ Normalization    │
            │ Pipeline         │
            │ • Entity resolve │
            │ • Schema mapping │
            │ • Store in DB    │
            └──────────────────┘
```

### Key Components

1. **BaseNILConnector** - Abstract base class defining connector interface
2. **Individual Connectors** - Source-specific implementations (On3, Opendorse, etc.)
3. **ConnectorOrchestrator** - Manages parallel execution and aggregation
4. **NormalizationPipeline** - Transforms raw data into canonical schema
5. **StorageManager** - Persists data to PostgreSQL

---

## Base Connector Framework

### BaseNILConnector Class

All scrapers inherit from `BaseNILConnector`, which provides:

#### Core Abstract Methods (Must Implement)

```python
@abstractmethod
def fetch_raw(athlete_name, school, sport, **filters) -> Optional[Dict]
    """Fetch raw data from source"""

@abstractmethod
def normalize(raw_data: Dict) -> Dict
    """Normalize raw data into canonical schema"""

@abstractmethod
def get_source_name() -> str
    """Return source identifier"""

@abstractmethod
def get_source_reliability_weight() -> float
    """Return reliability weight (0-1)"""
```

#### Built-in Utilities

**Rate Limiting**
- Automatic delay between requests (`rate_limit_delay = 1.0s`)
- Tracks `last_request_time` to prevent throttling

**HTTP Client**
- `fetch_url()` - Retry logic (3 attempts)
- Handles 429 (rate limit) with exponential backoff
- Timeout handling (15s default)
- User-Agent headers for browser-like requests

**Data Parsing**
- `parse_html()` - BeautifulSoup wrapper
- `extract_json_from_response()` - Safe JSON parsing
- `parse_currency_value()` - Converts "$1.2M" → 1,200,000
- `extract_ranking()` - Extracts "#42" → 42
- `clean_athlete_name()` - Normalizes names

**High-Level Collection**
- `collect()` - Combines `fetch_raw()` + `normalize()` + metadata

### Example Connector Structure

```python
class MyConnector(BaseNILConnector):
    BASE_URL = "https://example.com"
    
    def get_source_name(self) -> str:
        return "example"
    
    def get_source_reliability_weight(self) -> float:
        return 0.80  # Tier 2 reliability
    
    def fetch_raw(self, athlete_name, school=None, sport=None, **filters):
        # 1. Build search URL
        url = f"{self.BASE_URL}/search?q={athlete_name}"
        
        # 2. Fetch with retry logic
        response = self.fetch_url(url)
        if not response:
            return None
        
        # 3. Parse HTML
        soup = self.parse_html(response.text)
        
        # 4. Extract raw data
        return {
            'html': response.text,
            'text': soup.get_text(),
            'profile_url': self._find_profile(soup)
        }
    
    def normalize(self, raw_data):
        # Transform to canonical schema
        return {
            'nil_valuation': self._extract_valuation(raw_data['text']),
            'nil_deals': self._extract_deals(raw_data['text']),
            'profile_url': raw_data.get('profile_url')
        }
```

---

## Data Sources & Reliability Tiers

### Tier 1: Primary NIL Platforms (Reliability: 0.90-0.95)

**On3.com** (Reliability: 0.95)
- **What it provides**: Verified NIL valuations, national rankings, deal announcements
- **Data quality**: Highest - official NIL valuations
- **Update frequency**: Daily
- **Coverage**: ~5,000+ CFB athletes
- **Key fields**: `nil_valuation`, `nil_ranking`, `nil_deals`

**Opendorse.com** (Reliability: 0.90)
- **What it provides**: Athlete profiles, marketplace listings, social metrics
- **Data quality**: High - verified athlete profiles
- **Update frequency**: Real-time (athlete-managed)
- **Coverage**: ~10,000+ athletes across all sports
- **Key fields**: `nil_valuation`, `nil_deals`, `social_metrics`, `marketplace_listing`

### Tier 2: Social & Analytics Platforms (Reliability: 0.80-0.85)

**INFLCR.com** (Reliability: 0.85)
- **What it provides**: Social media analytics, content engagement, deal activity
- **Data quality**: Good - B2B platform for schools
- **Update frequency**: Daily
- **Coverage**: ~500+ schools, ~50,000+ athletes
- **Key fields**: `social_metrics`, `engagement_rate`, `content_activity`, `nil_deals`

**Teamworks.com** (Reliability: 0.80)
- **What it provides**: Team management platform, occasional NIL mentions
- **Data quality**: Moderate - limited public data
- **Update frequency**: Weekly
- **Coverage**: ~300+ schools
- **Key fields**: `nil_deals` (limited)

### Tier 3: Recruiting & News Platforms (Reliability: 0.70-0.75)

**247Sports.com** (Reliability: 0.75)
- **What it provides**: Recruiting rankings, NIL news coverage, transfer portal
- **Data quality**: Moderate - journalistic coverage
- **Update frequency**: Daily
- **Coverage**: ~20,000+ recruits/athletes
- **Key fields**: `recruiting_ranking`, `recruiting_stars`, `nil_valuation`, `nil_deals`, `transfer_portal_status`

**Rivals.com** (Reliability: 0.70)
- **What it provides**: Recruiting profiles, NIL news, athlete rankings
- **Data quality**: Moderate - journalistic coverage
- **Update frequency**: Daily
- **Coverage**: ~15,000+ recruits/athletes
- **Key fields**: `recruiting_ranking`, `recruiting_stars`, `nil_deals`

### Reliability Weight Usage

Reliability weights are used for:
1. **Consensus calculations** - Weighted averages across sources
2. **Confidence scoring** - Higher reliability → higher confidence
3. **Data quality metrics** - Contributes to overall quality score
4. **Conflict resolution** - Higher reliability wins in conflicts

---

## Individual Scrapers

### 1. On3Connector

**Source**: `gravity/nil/connectors/on3_connector.py`

**Purpose**: Primary NIL valuation and ranking source

**Data Collected**:
- NIL valuations (e.g., "$1.2M")
- National NIL rankings (e.g., "#42")
- Deal announcements (brand partnerships)
- Profile URLs

**Implementation Details**:

```python
# Search flow
1. Search: https://www.on3.com/db/search/?q={athlete_name}
2. Find profile link in search results
3. Fetch profile page if found
4. Extract valuation, ranking, deals from text

# Extraction patterns
- Valuation: r'nil.*?\$\s*([\d,.]+)\s*([KMB])?'
- Ranking: r'nil.*?rank.*?#?(\d+)'
- Deals: Brand mentions near deal keywords
```

**Normalized Output**:
```json
{
  "nil_valuation": 1200000.0,
  "nil_ranking": 42,
  "nil_deals": [
    {
      "brand": "Nike",
      "type": "Apparel",
      "source": "on3"
    }
  ],
  "profile_url": "https://www.on3.com/nil/player/..."
}
```

**Reliability**: 0.95 (Tier 1)

---

### 2. OpendorseConnector

**Source**: `gravity/nil/connectors/opendorse_connector.py`

**Purpose**: NIL marketplace and athlete profiles

**Data Collected**:
- Athlete profiles
- NIL valuations
- Marketplace listings (active deals, rates)
- Social media metrics
- Brand partnerships

**Implementation Details**:

```python
# Search flow
1. Search: https://opendorse.com/athletes?q={athlete_name}&school={school}
2. Find athlete profile link (/athletes/{slug})
3. Fetch profile page
4. Extract valuation, social metrics, marketplace info

# Extraction patterns
- Valuation: r'estimated value.*?\$\s*([\d,.]+)\s*([KMB])?'
- Social: r'instagram.*?(\d+(?:,\d+)*)\s*followers'
- Marketplace rate: r'starting at.*?\$\s*([\d,.]+)'
- Deals: r'(?:partnership|deal)\s+with\s+([\w\s&]+)'
```

**Normalized Output**:
```json
{
  "nil_valuation": 850000.0,
  "nil_deals": [...],
  "social_metrics": {
    "instagram": 125000,
    "twitter": 45000
  },
  "marketplace_listing": {
    "active": true,
    "rate": 5000.0,
    "categories": ["Social Media", "Appearances"]
  }
}
```

**Reliability**: 0.90 (Tier 1)

---

### 3. INFLCRConnector

**Source**: `gravity/nil/connectors/inflcr_connector.py`

**Purpose**: Social analytics and content engagement

**Data Collected**:
- Social media follower counts
- Engagement rates
- Content posting activity
- Brand partnerships (limited)

**Implementation Details**:

```python
# Search flow
1. Requires school name (B2B platform)
2. Try: https://inflcr.com/athletes/{school-slug}
3. Or: https://inflcr.com/schools/{school-slug}/athletes
4. Extract social metrics from school page

# Extraction patterns
- Followers: r'(\d+(?:,\d+)*)\s*total\s*followers'
- Engagement: r'engagement.*?(\d+(?:\.\d+)?)\s*%'
- Posts: r'(\d+)\s*posts?\s*per\s*week'
```

**Normalized Output**:
```json
{
  "social_metrics": {
    "total_followers": 250000,
    "instagram_followers": 180000,
    "twitter_followers": 70000
  },
  "engagement_rate": 4.2,
  "content_activity": {
    "posts_per_week": 5,
    "total_posts": 120
  },
  "nil_deals": [...]
}
```

**Reliability**: 0.85 (Tier 2)

---

### 4. TeamworksConnector

**Source**: `gravity/nil/connectors/teamworks_connector.py`

**Purpose**: Team management platform (limited public NIL data)

**Data Collected**:
- NIL deal mentions (from news/articles)
- School/team context

**Implementation Details**:

```python
# Search flow
1. Search news/blog: https://www.teamworks.com/news?s={query}
2. Find articles mentioning athlete + NIL
3. Extract deal mentions from article text

# Extraction patterns
- Deals: r'signed a NIL deal with ([\w\s&]+)'
```

**Normalized Output**:
```json
{
  "nil_deals": [
    {
      "brand": "Local Restaurant",
      "type": "Endorsement",
      "source": "teamworks"
    }
  ]
}
```

**Reliability**: 0.80 (Tier 2)

---

### 5. Sports247Connector

**Source**: `gravity/nil/connectors/sports247_connector.py`

**Purpose**: Recruiting rankings and NIL news coverage

**Data Collected**:
- Recruiting rankings (national)
- Star ratings (3-5 stars)
- NIL valuations (from news)
- NIL deal announcements
- Transfer portal status

**Implementation Details**:

```python
# Search flow
1. Search: https://247sports.com/Search?searchterm={athlete_name}
2. Find player profile link (/player/ or /recruit/)
3. Fetch profile page
4. Try NIL news tab: {profile_url}/nil
5. Extract recruiting + NIL data

# Extraction patterns
- Recruiting rank: r'#(\d+)\s+national\s+recruit'
- Stars: r'(\d)\s*-?\s*star\s+recruit'
- NIL valuation: r'nil\s+value.*?\$\s*([\d,.]+)\s*([KMB])?'
- Deals: r'signs?\s+(?:nil\s+)?deal\s+with\s+([\w\s&]+)'
```

**Normalized Output**:
```json
{
  "recruiting_ranking": 15,
  "recruiting_stars": 5,
  "nil_valuation": 750000.0,
  "nil_deals": [...],
  "transfer_portal_status": null
}
```

**Reliability**: 0.75 (Tier 3)

---

### 6. RivalsConnector

**Source**: `gravity/nil/connectors/rivals_connector.py`

**Purpose**: Recruiting profiles and NIL news

**Data Collected**:
- Recruiting rankings
- Star ratings
- NIL deal mentions (from news)

**Implementation Details**:

```python
# Similar to 247Sports
# Search → Profile → Extract recruiting + NIL data
```

**Reliability**: 0.70 (Tier 3)

---

## Connector Orchestrator

### Purpose

The `ConnectorOrchestrator` manages parallel execution of all connectors, aggregates results, and calculates consensus values.

**Source**: `gravity/nil/connector_orchestrator.py`

### Key Features

1. **Parallel Execution**
   - Uses `ThreadPoolExecutor` (default: 6 workers)
   - All connectors run simultaneously
   - Timeout: 30 seconds per connector

2. **Result Aggregation**
   - Combines data from all sources
   - Deduplicates deals (by brand name)
   - Calculates weighted consensus values

3. **Consensus Calculation**
   - **NIL Valuation**: Weighted average by reliability
   - **NIL Ranking**: Weighted average
   - **Deal Count**: Unique brands across sources

4. **Error Handling**
   - Individual connector failures don't stop others
   - Errors logged and included in results
   - Retry logic handled by base connector

5. **Raw Payload Storage**
   - Optionally saves raw responses for auditability
   - Stored in `raw_data` table

### Usage Example

```python
from gravity.nil.connector_orchestrator import ConnectorOrchestrator

orchestrator = ConnectorOrchestrator()

results = orchestrator.collect_all(
    athlete_name="Shedeur Sanders",
    school="Colorado",
    sport="football",
    athlete_id=some_uuid,  # Optional
    save_raw=True
)

# Results structure:
{
    'athlete_name': 'Shedeur Sanders',
    'school': 'Colorado',
    'sport': 'football',
    'collection_timestamp': '2026-01-23T...',
    'sources': {
        'on3': {
            'success': True,
            'data': {...},
            'reliability': 0.95,
            'duration_seconds': 2.3
        },
        'opendorse': {...},
        ...
    },
    'aggregated': {
        'nil_valuations': [
            {'source': 'on3', 'value': 1200000, 'reliability': 0.95},
            {'source': 'opendorse', 'value': 1150000, 'reliability': 0.90}
        ],
        'nil_deals': [...],
        'consensus': {
            'nil_valuation': 1175000,  # Weighted average
            'nil_valuation_min': 1150000,
            'nil_valuation_max': 1200000,
            'nil_valuation_median': 1175000,
            'unique_deals_count': 8
        }
    },
    'summary': {
        'sources_attempted': 6,
        'sources_successful': 5,
        'sources_failed': 1,
        'total_deals_found': 12,
        'has_valuation': True,
        'has_ranking': True,
        'data_quality_score': 0.87
    },
    'errors': [...]
}
```

### Consensus Calculation Logic

**NIL Valuation Consensus**:
```python
# Weighted average by reliability
total_weight = sum(v['reliability'] for v in valuations)
weighted_sum = sum(v['value'] * v['reliability'] for v in valuations)
consensus_valuation = weighted_sum / total_weight

# Also calculate min/max/median for range
```

**Data Quality Score**:
```python
# Based on:
# 1. Successful sources (weighted by tier)
# 2. Presence of key data (valuation, ranking, deals)
# Score range: 0.0 - 1.0
```

---

## Data Flow & Normalization

### Complete Pipeline Flow

```
1. ConnectorOrchestrator.collect_all()
   ├── Parallel execution of all connectors
   ├── Each connector: fetch_raw() → normalize()
   └── Aggregate results

2. NormalizationPipeline.normalize_collection_results()
   ├── Entity resolution (create/resolve athlete)
   ├── Extract valuations → NILValuation records
   ├── Extract deals → NILDeal records
   └── Create tracking events

3. StorageManager
   ├── Save to PostgreSQL tables
   ├── Store raw payloads (audit trail)
   └── Update athlete profiles
```

### Canonical Schema

All connectors normalize to this schema:

```python
{
    # NIL Valuation
    'nil_valuation': float,  # Annual value in USD
    
    # NIL Ranking
    'nil_ranking': int,  # National ranking (1-10000)
    
    # NIL Deals
    'nil_deals': [
        {
            'brand': str,  # Brand name
            'type': str,   # Deal type (Apparel, Endorsement, etc.)
            'value': float,  # Optional deal value
            'source': str,   # Source connector name
            'is_team_deal': bool  # Local vs national
        }
    ],
    
    # Social Metrics
    'social_metrics': {
        'instagram': int,  # Followers
        'twitter': int,
        'tiktok': int,
        'total_followers': int
    },
    
    # Recruiting Data
    'recruiting_ranking': int,  # National rank
    'recruiting_stars': int,    # 3-5 stars
    
    # Profile URLs
    'profile_url': str,
    
    # Metadata (added by base connector)
    '_metadata': {
        'source': str,
        'source_reliability': float,
        'fetched_at': str,  # ISO timestamp
        'athlete_name': str,
        'school': str,
        'sport': str
    }
}
```

### Normalization Pipeline

**Source**: `gravity/nil/normalization.py`

**Steps**:

1. **Entity Resolution**
   - Resolve athlete to `athlete_id` (or create new)
   - Uses deterministic matching (external IDs)
   - Falls back to probabilistic matching (name similarity)

2. **Valuation Extraction**
   - Extract from all sources
   - Create `NILValuation` records
   - Store source, confidence, ranking

3. **Deal Extraction**
   - Deduplicate by (brand, source)
   - Create `NILDeal` records
   - Categorize deal types

4. **Event Tracking**
   - Create `AthleteEvent` records
   - Track collection metadata
   - Store data quality scores

### Database Tables

**NILValuation**:
- `athlete_id`, `valuation_amount`, `source`, `ranking`, `confidence_score`

**NILDeal**:
- `athlete_id`, `brand`, `deal_type`, `deal_value`, `source`, `confidence_score`

**RawData**:
- `source`, `data` (JSONB), `ingested_at`, `status`

---

## Extending the System

### Adding a New Connector

**Step 1**: Create connector file

```python
# gravity/nil/connectors/my_source_connector.py

from gravity.nil.connectors.base import BaseNILConnector

class MySourceConnector(BaseNILConnector):
    BASE_URL = "https://mysource.com"
    
    def get_source_name(self) -> str:
        return "mysource"
    
    def get_source_reliability_weight(self) -> float:
        return 0.85  # Tier 2
    
    def fetch_raw(self, athlete_name, school=None, sport=None, **filters):
        # Implement fetching logic
        url = f"{self.BASE_URL}/search?q={athlete_name}"
        response = self.fetch_url(url)
        if not response:
            return None
        
        soup = self.parse_html(response.text)
        return {
            'html': response.text,
            'text': soup.get_text()
        }
    
    def normalize(self, raw_data):
        # Normalize to canonical schema
        return {
            'nil_valuation': self._extract_valuation(raw_data['text']),
            'nil_deals': self._extract_deals(raw_data['text'])
        }
```

**Step 2**: Register in orchestrator

```python
# gravity/nil/connector_orchestrator.py

from gravity.nil.connectors.my_source_connector import MySourceConnector

class ConnectorOrchestrator:
    def __init__(self, max_workers: int = 6):
        self.connectors = {
            'on3': On3Connector(),
            'opendorse': OpendorseConnector(),
            'mysource': MySourceConnector(),  # Add here
            ...
        }
```

**Step 3**: Export in package

```python
# gravity/nil/connectors/__init__.py

from gravity.nil.connectors.my_source_connector import MySourceConnector

__all__ = [
    ...,
    'MySourceConnector'
]
```

### Best Practices

1. **Rate Limiting**: Always use `self.rate_limit()` before requests
2. **Error Handling**: Return `None` on failure, don't raise exceptions
3. **Logging**: Use `logger.debug()` for details, `logger.error()` for failures
4. **Normalization**: Always return canonical schema, even if fields are `None`
5. **Testing**: Test with real athlete names before deploying
6. **Reliability**: Set realistic reliability weights based on data quality

### Common Patterns

**Search → Profile → Extract**:
```python
# 1. Search
search_url = f"{BASE_URL}/search?q={athlete_name}"
response = self.fetch_url(search_url)

# 2. Find profile
profile_url = self._find_profile_link(soup, athlete_name)

# 3. Fetch profile
if profile_url:
    profile_response = self.fetch_url(profile_url)
    profile_soup = self.parse_html(profile_response.text)
    text = profile_soup.get_text()

# 4. Extract
valuation = self._extract_valuation(text)
```

**Regex Extraction**:
```python
def _extract_valuation(self, text: str) -> Optional[float]:
    patterns = [
        r'nil.*?\$\s*([\d,.]+)\s*([KMB])?',
        r'\$\s*([\d,.]+)\s*([KMB])?\s*nil'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value_str = f"${match.group(1)}{match.group(2) or ''}"
            return self.parse_currency_value(value_str)
    
    return None
```

---

## Performance Considerations

### Rate Limiting

- **Default delay**: 1.0 second between requests
- **Per-connector**: Each connector tracks its own rate limit
- **429 handling**: Exponential backoff (up to 30s)

### Parallel Execution

- **Max workers**: 6 (configurable)
- **Timeout**: 30 seconds per connector
- **Failure isolation**: One connector failure doesn't affect others

### Caching (Future)

Consider caching:
- Profile URLs (avoid re-searching)
- Static data (school names, etc.)
- Recent results (TTL: 1 hour)

---

## Monitoring & Debugging

### Logging Levels

- **INFO**: Collection start/end, summary stats
- **DEBUG**: Detailed extraction steps, URL fetches
- **ERROR**: Failures, exceptions

### Metrics to Track

1. **Collection Success Rate**: `sources_successful / sources_attempted`
2. **Data Quality Score**: Overall quality (0-1)
3. **Average Duration**: Time per connector
4. **Error Rate**: Failed connectors per collection
5. **Consensus Variance**: Spread of valuations across sources

### Debugging Tips

1. **Enable DEBUG logging**: `logging.getLogger().setLevel(logging.DEBUG)`
2. **Inspect raw HTML**: Check `raw_data['html']` in connector
3. **Test extraction**: Unit test `_extract_*` methods with sample text
4. **Check rate limits**: Monitor for 429 responses
5. **Validate schema**: Ensure normalized data matches canonical schema

---

## Summary

### Architecture Highlights

✅ **Modular Design**: Each connector is independent  
✅ **Parallel Execution**: Fast collection across sources  
✅ **Reliability Weighting**: Consensus based on source quality  
✅ **Error Resilience**: Failures don't stop entire collection  
✅ **Audit Trail**: Raw payloads stored for debugging  
✅ **Extensible**: Easy to add new sources  

### Data Sources Summary

| Source | Tier | Reliability | Key Data |
|--------|------|-------------|----------|
| On3 | 1 | 0.95 | Valuations, Rankings |
| Opendorse | 1 | 0.90 | Profiles, Marketplace |
| INFLCR | 2 | 0.85 | Social Metrics |
| Teamworks | 2 | 0.80 | Limited Deals |
| 247Sports | 3 | 0.75 | Recruiting, News |
| Rivals | 3 | 0.70 | Recruiting, News |

### Next Steps

1. **Add API Keys**: Some sources may require authentication
2. **Implement Caching**: Reduce redundant requests
3. **Add More Sources**: ESPN, Sports Illustrated, etc.
4. **Enhance Extraction**: ML-based parsing for better accuracy
5. **Real-time Updates**: Webhook support for live data

---

**Last Updated**: 2026-01-23  
**Version**: 1.0.0  
**Maintainer**: Gravity NIL Pipeline Team
