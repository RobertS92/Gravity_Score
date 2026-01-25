# Score Recalculation System

## Overview

The score recalculation system automatically updates Gravity scores when crawler events occur. This ensures scores are always up-to-date with the latest information.

## How It Works

1. **Crawler creates event** → Stored in `athlete_events` table
2. **Event processor detects event** → Determines affected component scores
3. **Features recalculated** → Updated feature snapshot
4. **Component scores recalculated** → Updated component scores
5. **Gravity score recalculated** → Updated final Gravity score

## Event-to-Score Mapping

Each event type triggers recalculation of specific component scores:

| Event Type | Components Affected |
|------------|---------------------|
| `news_contract_extension` | Proof |
| `news_trade` | Proximity, Risk |
| `social_brand_mention` | Brand |
| `social_engagement_spike` | Brand, Velocity |
| `transfer_portal_entry` | Risk, Proximity |
| `injury` | Risk, Proof |
| `trade_completed` | Proximity, Risk, Proof |
| `game_stats` | Proof, Velocity |

## Manual Recalculation

Scores can be manually recalculated:

```python
from gravity.crawlers.score_recalculator import ScoreRecalculator

recalculator = ScoreRecalculator()

# Recalculate all components
result = await recalculator.recalculate_scores(athlete_id)

# Recalculate specific components
result = await recalculator.recalculate_scores(
    athlete_id,
    components=['brand', 'proof']
)
```

## Recalculation History

All recalculations are tracked in the `score_recalculations` table:

- `trigger_event_id` - Event that triggered recalculation
- `trigger_event_type` - Type of triggering event
- `components_recalculated` - Components that were recalculated
- `old_gravity_score` - Previous Gravity score
- `new_gravity_score` - New Gravity score
- `score_delta` - Change in Gravity score

## Performance Considerations

- Recalculations run asynchronously to avoid blocking crawler execution
- Only affected components are recalculated (not all components)
- Feature recalculation is optimized to only update changed features
- Batch recalculation available for multiple athletes

## Monitoring

Monitor recalculation activity:

```python
from gravity.crawlers.crawler_monitor import CrawlerMonitor

monitor = CrawlerMonitor()
metrics = monitor.get_score_recalculation_metrics(days=7)

# Returns:
# - total_recalculations
# - recalculations_by_event_type
# - avg_score_delta
# - components_recalculated
```
