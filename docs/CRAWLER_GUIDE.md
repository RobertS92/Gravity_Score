# Crawler User Guide

## Overview

The Gravity crawler system consists of 8 automated crawlers that discover and update sports information across all sports. These crawlers automatically trigger score recalculation when new events are detected.

## Available Crawlers

1. **News Article Crawler** - Discovers sports news (contracts, trades, draft, performance, NIL deals)
2. **Social Media Crawler** - Tracks athlete social engagement and brand mentions
3. **Transfer Portal Crawler** - Monitors CFB transfer portal entries
4. **Sentiment Crawler** - Gauges public sentiment from Reddit/forums
5. **Injury Report Crawler** - Aggregates injury reports from multiple sources
6. **Brand Partnership Crawler** - Builds database of brand-athlete partnerships
7. **Game Stats Crawler** - Updates game-by-game performance statistics
8. **Trade Crawler** - Tracks athlete trades across professional sports

## Usage

### Manual Triggering via API

```python
import requests

# Run a specific crawler for an athlete
response = requests.post(
    "http://localhost:8000/crawlers/news_article/run",
    json={
        "athlete_id": "123e4567-e89b-12d3-a456-426614174000",
        "sport": "nfl"
    }
)

# Run all crawlers for an athlete
response = requests.post(
    "http://localhost:8000/crawlers/run_all",
    json={
        "athlete_id": "123e4567-e89b-12d3-a456-426614174000"
    }
)
```

### Programmatic Usage

```python
from gravity.crawlers.crawler_orchestrator import CrawlerOrchestrator
import uuid

orchestrator = CrawlerOrchestrator()

# Run all crawlers for an athlete
athlete_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
results = await orchestrator.run_all_crawlers(athlete_id)

# Run a specific crawler
result = await orchestrator.run_crawler(
    "news_article",
    athlete_id=athlete_id
)
```

## Scheduling

Crawlers can be scheduled to run automatically:

```python
from gravity.crawlers.crawler_scheduler import CrawlerScheduler

scheduler = CrawlerScheduler()

# Schedule daily at 2 AM
scheduler.schedule_crawler('news_article', interval='daily', time='02:00')

# Schedule every 6 hours
scheduler.schedule_crawler('injury_report', interval='6h')

# Schedule hourly
scheduler.schedule_crawler('transfer_portal', interval='1h')
```

## Monitoring

Check crawler health and performance:

```python
from gravity.crawlers.crawler_monitor import CrawlerMonitor

monitor = CrawlerMonitor()

# Get health status
health = monitor.check_crawler_health()

# Get performance metrics
metrics = monitor.get_crawler_metrics('news_article', days=7)
```

## Event-Driven Score Recalculation

When crawlers create events, scores are automatically recalculated:

- **News events** → Brand, Proof scores
- **Social events** → Brand, Velocity scores
- **Trade events** → Proximity, Risk, Proof scores
- **Injury events** → Risk, Proof scores
- **Game stats** → Proof, Velocity scores

## Configuration

Crawler configuration can be updated via API:

```python
# Update crawler config
requests.put(
    "http://localhost:8000/crawlers/news_article/config",
    json={
        "is_enabled": True,
        "schedule_interval": "daily",
        "schedule_time": "02:00"
    }
)
```
