# Scraper Quick Reference Guide

## 🚀 Quick Start

### Run Collection for Single Athlete

```python
from gravity.nil.connector_orchestrator import run_nil_collection

results = run_nil_collection(
    athlete_name="Shedeur Sanders",
    school="Colorado",
    sport="football"
)

# Access results
print(f"Valuation: ${results['aggregated']['consensus']['nil_valuation']:,.0f}")
print(f"Deals Found: {results['summary']['total_deals_found']}")
print(f"Quality Score: {results['summary']['data_quality_score']:.2f}")
```

### Use Individual Connector

```python
from gravity.nil.connectors import On3Connector

connector = On3Connector()
data = connector.collect(
    athlete_name="Arch Manning",
    school="Texas",
    sport="football"
)

if data:
    print(f"Valuation: ${data.get('nil_valuation', 0):,.0f}")
    print(f"Ranking: #{data.get('nil_ranking', 'N/A')}")
```

---

## 📊 Data Sources Cheat Sheet

| Source | Reliability | Key Fields | URL Pattern |
|--------|-------------|------------|-------------|
| **On3** | 0.95 | `nil_valuation`, `nil_ranking`, `nil_deals` | `on3.com/db/search/?q={name}` |
| **Opendorse** | 0.90 | `nil_valuation`, `social_metrics`, `marketplace_listing` | `opendorse.com/athletes?q={name}` |
| **INFLCR** | 0.85 | `social_metrics`, `engagement_rate` | `inflcr.com/athletes/{school}` |
| **Teamworks** | 0.80 | `nil_deals` (limited) | `teamworks.com/news?s={query}` |
| **247Sports** | 0.75 | `recruiting_ranking`, `nil_valuation` | `247sports.com/Search?searchterm={name}` |
| **Rivals** | 0.70 | `recruiting_ranking`, `nil_deals` | `rivals.com/search?q={name}` |

---

## 🔧 Common Operations

### Extract Valuation from Text

```python
from gravity.nil.connectors.base import BaseNILConnector

connector = BaseNILConnector()

# Parse currency strings
value = connector.parse_currency_value("$1.2M")  # Returns 1200000.0
value = connector.parse_currency_value("$850K")   # Returns 850000.0
value = connector.parse_currency_value("$1,200") # Returns 1200.0
```

### Extract Ranking from Text

```python
ranking = connector.extract_ranking("#42")        # Returns 42
ranking = connector.extract_ranking("Ranked 15th") # Returns 15
```

### Clean Athlete Name

```python
name = connector.clean_athlete_name("John Smith Jr.")  # "John Smith"
name = connector.clean_athlete_name("  Bob   Jones  ") # "Bob Jones"
```

---

## 📝 Canonical Schema

### Standard Output Format

```python
{
    # Core NIL Data
    'nil_valuation': float,      # Annual value in USD
    'nil_ranking': int,          # National ranking (1-10000)
    
    # Deals
    'nil_deals': [
        {
            'brand': str,        # Brand name
            'type': str,         # Deal type
            'value': float,      # Optional deal value
            'source': str,       # Source connector
            'is_team_deal': bool # Local vs national
        }
    ],
    
    # Social Metrics
    'social_metrics': {
        'instagram': int,
        'twitter': int,
        'tiktok': int,
        'total_followers': int
    },
    
    # Recruiting Data
    'recruiting_ranking': int,  # National rank
    'recruiting_stars': int,    # 3-5 stars
    
    # URLs
    'profile_url': str,
    
    # Metadata (auto-added)
    '_metadata': {
        'source': str,
        'source_reliability': float,
        'fetched_at': str
    }
}
```

---

## 🛠️ Adding New Connector

### Template

```python
from gravity.nil.connectors.base import BaseNILConnector
from typing import Dict, Any, Optional

class MyConnector(BaseNILConnector):
    BASE_URL = "https://example.com"
    
    def get_source_name(self) -> str:
        return "example"
    
    def get_source_reliability_weight(self) -> float:
        return 0.80  # Tier 2
    
    def fetch_raw(self, athlete_name, school=None, sport=None, **filters):
        url = f"{self.BASE_URL}/search?q={athlete_name}"
        response = self.fetch_url(url)
        if not response:
            return None
        
        soup = self.parse_html(response.text)
        return {'text': soup.get_text()}
    
    def normalize(self, raw_data):
        return {
            'nil_valuation': self._extract_valuation(raw_data['text']),
            'nil_deals': []
        }
    
    def _extract_valuation(self, text):
        import re
        match = re.search(r'\$\s*([\d,.]+)\s*([KMB])?', text)
        if match:
            return self.parse_currency_value(f"${match.group(1)}{match.group(2) or ''}")
        return None
```

### Register in Orchestrator

```python
# gravity/nil/connector_orchestrator.py
from gravity.nil.connectors.my_connector import MyConnector

self.connectors = {
    ...
    'example': MyConnector()
}
```

---

## 🐛 Debugging Tips

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Raw Data

```python
results = run_nil_collection("Player Name", "School")

# Check raw HTML from specific source
on3_data = results['sources']['on3']['data']
raw_html = on3_data.get('raw_html')  # If stored
```

### Test Extraction Methods

```python
connector = On3Connector()
test_text = "Player has $1.2M NIL valuation, ranked #42"
valuation = connector._extract_valuation(test_text)
assert valuation == 1200000.0
```

---

## ⚡ Performance Tips

### Rate Limiting

- Default: 1.0s delay between requests
- Adjust per connector: `connector.rate_limit_delay = 2.0`
- Handles 429 responses automatically

### Parallel Execution

- Default: 6 workers
- Adjust: `ConnectorOrchestrator(max_workers=10)`
- Timeout: 30s per connector

### Caching (Future)

```python
# Cache profile URLs to avoid re-searching
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_profile_url(athlete_name, school):
    # Search logic here
    pass
```

---

## 📈 Monitoring Metrics

### Key Metrics

```python
results = run_nil_collection(...)

# Success rate
success_rate = results['summary']['sources_successful'] / results['summary']['sources_attempted']

# Data quality
quality = results['summary']['data_quality_score']

# Consensus variance
valuations = [v['value'] for v in results['aggregated']['nil_valuations']]
variance = max(valuations) - min(valuations) if valuations else 0
```

---

## 🔍 Common Regex Patterns

### Extract Valuation

```python
patterns = [
    r'nil.*?\$\s*([\d,.]+)\s*([KMB])?',
    r'\$\s*([\d,.]+)\s*([KMB])?\s*nil',
    r'valuation.*?\$\s*([\d,.]+)\s*([KMB])?'
]
```

### Extract Ranking

```python
patterns = [
    r'#(\d+).*?nil.*?rank',
    r'nil.*?rank.*?#?(\d+)',
    r'ranked?\s+#?(\d+).*?nil'
]
```

### Extract Deals

```python
patterns = [
    r'signs?\s+(?:nil\s+)?deal\s+with\s+([\w\s&]+)',
    r'partnership\s+with\s+([\w\s&]+)',
    r'([\w\s&]+)\s+endorsement'
]
```

---

## 📚 File Locations

| Component | File Path |
|-----------|-----------|
| Base Connector | `gravity/nil/connectors/base.py` |
| On3 Connector | `gravity/nil/connectors/on3_connector.py` |
| Opendorse Connector | `gravity/nil/connectors/opendorse_connector.py` |
| INFLCR Connector | `gravity/nil/connectors/inflcr_connector.py` |
| 247Sports Connector | `gravity/nil/connectors/sports247_connector.py` |
| Rivals Connector | `gravity/nil/connectors/rivals_connector.py` |
| Orchestrator | `gravity/nil/connector_orchestrator.py` |
| Normalization | `gravity/nil/normalization.py` |

---

## 🎯 Best Practices

1. ✅ **Always use `fetch_url()`** - Handles retries and rate limiting
2. ✅ **Return `None` on failure** - Don't raise exceptions
3. ✅ **Log errors** - Use `logger.error()` for failures
4. ✅ **Normalize to schema** - Always return canonical format
5. ✅ **Set realistic reliability** - Based on data quality
6. ✅ **Test with real names** - Before deploying
7. ✅ **Handle missing data** - Use `Optional` types
8. ✅ **Document extraction patterns** - In docstrings

---

## 🚨 Common Issues

### Issue: Rate Limited (429)

**Solution**: Connector automatically handles with exponential backoff

### Issue: No Data Found

**Check**:
- Athlete name spelling
- School name format
- Source availability

### Issue: Extraction Failing

**Debug**:
- Enable DEBUG logging
- Inspect raw HTML/text
- Test regex patterns separately

### Issue: Normalization Errors

**Check**:
- Schema compliance
- Data type validation
- Required fields present

---

**Quick Links**:
- [Full Architecture Docs](./SCRAPER_ARCHITECTURE.md)
- [API Documentation](../README_NIL_PIPELINE.md)
- [Implementation Summary](../IMPLEMENTATION_SUMMARY.md)
