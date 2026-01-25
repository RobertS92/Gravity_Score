# Quick Start Guide - Async Scraper Enhancements

## 🚀 Installation

```bash
# Install new dependencies
pip install httpx>=0.27.0
pip install openai>=1.0.0  # Optional, for AI fallback
```

## ⚡ Usage Examples

### Basic Async Collection (Recommended)

```python
import asyncio
from gravity.nil.connector_orchestrator import ConnectorOrchestrator

async def collect_athlete_data():
    orchestrator = ConnectorOrchestrator()
    
    results = await orchestrator.collect_all_async(
        athlete_name="Shedeur Sanders",
        school="Colorado",
        sport="football"
    )
    
    print(f"Sources: {len(results['sources'])}/6")
    print(f"NIL Deals: {len(results['aggregated']['nil_deals'])}")
    print(f"Valuation: ${results['aggregated']['consensus'].get('nil_valuation', 0):,.0f}")
    
    return results

# Run it
results = asyncio.run(collect_athlete_data())
```

### Parallel Multi-Athlete Collection

```python
import asyncio
from gravity.nil.connector_orchestrator import ConnectorOrchestrator

async def collect_multiple_athletes():
    orchestrator = ConnectorOrchestrator()
    
    athletes = [
        {'name': 'Shedeur Sanders', 'school': 'Colorado'},
        {'name': 'Arch Manning', 'school': 'Texas'},
        {'name': 'Travis Hunter', 'school': 'Colorado'}
    ]
    
    # Collect all in parallel
    tasks = [
        orchestrator.collect_all_async(
            athlete['name'],
            athlete['school'],
            'football'
        )
        for athlete in athletes
    ]
    
    all_results = await asyncio.gather(*tasks)
    
    print(f"Collected data for {len(all_results)} athletes")
    return all_results

# Run it
results = asyncio.run(collect_multiple_athletes())
```

### Backward Compatible Sync Usage

```python
from gravity.nil.connector_orchestrator import ConnectorOrchestrator

# Still works! (but slower)
orchestrator = ConnectorOrchestrator()
results = orchestrator.collect_all(
    athlete_name="Shedeur Sanders",
    school="Colorado",
    sport="football"
)
```

### Using AI Extraction Directly

```python
import os
from gravity.ai.extractor import AIExtractor

# Set API key
os.environ['OPENAI_API_KEY'] = 'your-key-here'

extractor = AIExtractor()

# Extract deals
deals = extractor.extract(
    text="""Shedeur Sanders has NIL deals with Nike ($500K), 
            Gatorade ($250K), and local car dealership ($50K).""",
    extraction_type='nil_deals',
    context={'athlete_name': 'Shedeur Sanders'}
)

print(f"Found {len(deals)} deals")
for deal in deals:
    print(f"- {deal['brand']}: ${deal.get('value', 'Unknown')}")
```

### Individual Connector Async Usage

```python
import asyncio
from gravity.nil.connectors import On3Connector

async def fetch_on3_data():
    connector = On3Connector()
    
    raw_data = await connector.fetch_raw_async(
        athlete_name="Shedeur Sanders",
        school="Colorado",
        sport="football"
    )
    
    if raw_data:
        normalized = connector.normalize(raw_data)
        print(f"Valuation: ${normalized.get('nil_valuation', 0):,.0f}")
        print(f"Deals: {len(normalized.get('nil_deals', []))}")
    
    # Important: Close async client when done
    await connector.close_async_client()

asyncio.run(fetch_on3_data())
```

## 🧪 Testing

```bash
# Run performance tests
python tests/test_async_performance.py

# With AI extraction testing (requires OpenAI key)
export OPENAI_API_KEY=your-key-here
python tests/test_async_performance.py
```

## 📊 Performance Comparison

### Before (Sequential):
```python
# ~30-40 seconds per athlete
results = orchestrator.collect_all("Shedeur Sanders", "Colorado", "football")
```

### After (Async):
```python
# ~8-10 seconds per athlete
results = await orchestrator.collect_all_async("Shedeur Sanders", "Colorado", "football")
```

**Speedup: ~70-75% faster** ⚡

## 🔑 Key Features

### 1. Automatic AI Fallback
- Triggers when regex finds <2 deals
- No code changes needed
- Set `OPENAI_API_KEY` to enable

### 2. Enhanced Pattern Matching
Automatically handles:
- "$1.2M NIL valuation"
- "(NIL: $1.2M)"
- "estimated at $1.2M"
- "$1M-$1.5M" (averages to $1.25M)

### 3. Optimized Rate Limiting
- On3, Opendorse: 0.5s delay
- Others: 1.0s delay
- Prevents rate limit errors

## ⚙️ Configuration

### Disable AI Fallback (save costs)
```python
# In connector code
result = connector.extract_with_ai_fallback(
    text=text,
    extraction_type='nil_deals',
    athlete_name=name,
    use_ai=False  # Disable AI
)
```

### Custom Rate Limiting
```python
from gravity.nil.connectors import On3Connector

connector = On3Connector()
connector.rate_limit_delay = 0.3  # Faster (be careful!)
```

### AI Model Selection
```python
from gravity.ai.extractor import AIExtractor

# Use a different model
extractor = AIExtractor(model="gpt-4o")  # More expensive but better
```

## 📋 Common Patterns

### Pattern 1: Collect with error handling
```python
async def safe_collect(athlete_name, school):
    orchestrator = ConnectorOrchestrator()
    
    try:
        results = await orchestrator.collect_all_async(
            athlete_name, school, 'football'
        )
        
        if results['errors']:
            print(f"Warnings: {len(results['errors'])} sources failed")
        
        return results
    except Exception as e:
        print(f"Collection failed: {e}")
        return None
```

### Pattern 2: Batch processing
```python
async def batch_collect(athlete_list):
    orchestrator = ConnectorOrchestrator()
    
    # Process in batches of 10
    batch_size = 10
    all_results = []
    
    for i in range(0, len(athlete_list), batch_size):
        batch = athlete_list[i:i+batch_size]
        
        tasks = [
            orchestrator.collect_all_async(a['name'], a['school'], 'football')
            for a in batch
        ]
        
        batch_results = await asyncio.gather(*tasks)
        all_results.extend(batch_results)
        
        # Brief pause between batches
        await asyncio.sleep(2)
    
    return all_results
```

## 🎯 Best Practices

1. **Use async methods for best performance**
   ```python
   # Good
   results = await orchestrator.collect_all_async(...)
   
   # Okay (slower)
   results = orchestrator.collect_all(...)
   ```

2. **Clean up async clients**
   ```python
   await connector.close_async_client()
   ```

3. **Enable AI fallback selectively**
   - Development: Disable to save costs
   - Production: Enable for better accuracy

4. **Monitor rate limits**
   - Start conservative (1.0s)
   - Tune down (0.5s) for stable sources
   - Monitor for 429 errors

## 📈 Expected Results

✅ **Speed**: 8-10s per athlete (vs 30-40s)
✅ **Accuracy**: ~85% deal extraction (vs ~70%)
✅ **Reliability**: Handles ranges, estimates, variations
✅ **Scalability**: Process multiple athletes efficiently

## 🆘 Troubleshooting

### Issue: "RuntimeError: asyncio.run() cannot be called from a running event loop"
**Solution**: Use `await` instead of `asyncio.run()`
```python
# In async context
results = await orchestrator.collect_all_async(...)

# In sync context
results = asyncio.run(orchestrator.collect_all_async(...))
```

### Issue: AI extraction not working
**Check**:
1. `OPENAI_API_KEY` environment variable set?
2. `openai` package installed?
3. Check logs for error messages

### Issue: Slow performance
**Check**:
1. Using async methods? (`collect_all_async`)
2. Rate limits too conservative?
3. Network connection stable?

## 📚 Additional Resources

- Full implementation details: `ASYNC_ENHANCEMENTS_SUMMARY.md`
- Test suite: `tests/test_async_performance.py`
- Original plan: See attached plan file
