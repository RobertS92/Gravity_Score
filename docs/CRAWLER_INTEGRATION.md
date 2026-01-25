# Crawler Integration Guide

## Architecture Overview

The crawler system integrates seamlessly with the existing Gravity pipeline:

```
Crawler → Event Storage → Event Processor → Score Recalculator → Gravity Scores
```

## Integration Points

### 1. Event Storage

Crawlers store events in the `athlete_events` table:

```python
from gravity.crawlers.base_crawler import BaseCrawler

class MyCrawler(BaseCrawler):
    async def crawl(self, athlete_id, **kwargs):
        # Store event
        event_id = await self.store_event(
            athlete_id=athlete_id,
            event_type='my_event',
            event_data={'key': 'value'},
            source='my_crawler'
        )
        
        # Trigger score recalculation
        await self.trigger_score_recalculation(athlete_id, 'my_event')
```

### 2. Event Processor

The event processor maps event types to component scores:

```python
from gravity.crawlers.event_processor import EventProcessor

processor = EventProcessor()

# Process new event
await processor.process_new_event(event_id)

# Get affected components
components = processor.get_affected_components('trade_completed')
# Returns: ['proximity', 'risk', 'proof']
```

### 3. Score Recalculation

Scores are automatically recalculated when events occur:

```python
from gravity.crawlers.score_recalculator import ScoreRecalculator

recalculator = ScoreRecalculator()

# Recalculate scores
result = await recalculator.recalculate_scores(
    athlete_id=athlete_id,
    components=['brand', 'proof']
)
```

### 4. Feature Calculator Integration

The score recalculator uses the existing feature calculator:

```python
from gravity.nil.feature_calculator import FeatureCalculator

feature_calc = FeatureCalculator()
features = feature_calc.calculate_all_features(
    athlete_id,
    season_id,
    as_of_date
)
```

### 5. Component Scorers Integration

Component scores are recalculated using existing scorers:

```python
from gravity.scoring.component_scorers import get_component_scorers

scorers = get_component_scorers()
scorer = scorers['brand']
score, confidence, explanation = scorer.score(
    athlete_id,
    features,
    as_of_date
)
```

## Event Types

### News Events
- `news_contract_extension` → Proof
- `news_trade` → Proximity, Risk
- `news_draft` → Proof
- `news_performance` → Proof
- `news_nil_deal` → Brand, Proof

### Social Events
- `social_brand_mention` → Brand
- `social_nil_partnership` → Brand, Proof
- `social_engagement_spike` → Brand, Velocity

### Transfer Portal Events
- `transfer_portal_entry` → Risk, Proximity
- `transfer_commitment` → Proximity
- `transfer_withdrawal` → Risk

### Injury Events
- `injury` → Risk, Proof
- `injury_recovery` → Risk
- `injury_status_change` → Risk

### Trade Events
- `trade_completed` → Proximity, Risk, Proof
- `trade_announced` → Proximity, Risk, Proof

### Game Stats Events
- `game_stats` → Proof, Velocity
- `performance_milestone` → Proof
- `record_achievement` → Proof

## Database Schema

### New Tables

- `crawler_executions` - Tracks crawler execution history
- `crawler_configs` - Crawler configuration and scheduling
- `score_recalculations` - Tracks score recalculation history

### Enhanced Tables

- `athlete_events` - Added `crawler_name` column

## API Endpoints

See `gravity/api/crawler_api.py` for complete API documentation.

Key endpoints:
- `POST /crawlers/{crawler_name}/run` - Run specific crawler
- `POST /crawlers/run_all` - Run all crawlers
- `GET /crawlers/status` - Get crawler status
- `POST /scores/recalculate/{athlete_id}` - Manual score recalculation
