# Gravity Scrapers & Crawlers API

FastAPI service for automated athlete data collection, deployed on Railway. This service orchestrates scrapers and crawlers for NIL, NFL, and NBA data, storing results in Supabase.

## Architecture

```
GitHub Actions (Schedule) → Railway API → Scrapers/Crawlers → Supabase → Lovable Frontend
```

## Features

- **Automated Scheduling**: Daily VIP updates (top 100 athletes) and weekly full scrapes
- **On-Demand Refresh**: API endpoint for real-time athlete data updates
- **8 Specialized Crawlers**: News, social media, transfers, sentiment, injuries, partnerships, stats, trades
- **Multiple Scrapers**: NIL (CFB), NFL, NBA data collection
- **Job Tracking**: Monitor scraper execution and status
- **Test Tracking**: Automated test execution logging
- **RESTful API**: Comprehensive endpoints with OpenAPI docs

## Quick Start

### Prerequisites

- Python 3.11+
- Supabase account with service role key
- API keys for:
  - Perplexity AI
  - OpenAI
  - Anthropic
  - Firecrawl
  - Reddit

### Local Development

1. **Clone and setup**

```bash
cd railway-service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**

Create `.env` file:

```env
API_KEY=your_secure_api_key_here
PORT=8000
CORS_ORIGINS=["http://localhost:5173"]

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key

PERPLEXITY_API_KEY=your_key
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
FIRECRAWL_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
```

3. **Run database migrations**

In Supabase SQL Editor, run:

```bash
cat ../gravity/db/migrations/add_scraper_jobs.sql
```

Copy and execute the SQL in Supabase.

4. **Start the server**

```bash
uvicorn app.main:app --reload
```

Access API docs at `http://localhost:8000/docs`

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=gravity --cov-report=html

# Run specific test types
pytest -m unit
pytest -m integration

# Skip test tracking
SKIP_TEST_TRACKING=1 pytest
```

## Railway Deployment

### 1. Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Create new project: "gravity-scrapers-service"
3. Connect your GitHub repository
4. Set root directory: `railway-service`

### 2. Configure Environment Variables

In Railway project settings, add:

```
SUPABASE_URL=https://[your-project].supabase.co
SUPABASE_SERVICE_KEY=[service_role_key]
API_KEY=[generate_secure_random_key]
PERPLEXITY_API_KEY=[your_key]
OPENAI_API_KEY=[your_key]
ANTHROPIC_API_KEY=[your_key]
FIRECRAWL_API_KEY=[your_key]
REDDIT_CLIENT_ID=[your_id]
REDDIT_CLIENT_SECRET=[your_secret]
CORS_ORIGINS=["https://your-app.lovable.app","http://localhost:5173"]
```

**Generate secure API key:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Deploy

Railway will automatically:
- Detect `Dockerfile`
- Build the container
- Deploy the service
- Provide a public URL: `https://[your-app].up.railway.app`

### 4. Verify Deployment

```bash
# Check health
curl https://[your-app].up.railway.app/health

# View API docs
open https://[your-app].up.railway.app/docs
```

## GitHub Actions Setup

### Add Repository Secrets

In your GitHub repository → Settings → Secrets:

- `RAILWAY_API_URL`: `https://[your-app].up.railway.app`
- `SCRAPER_API_KEY`: Same API_KEY from Railway
- `SUPABASE_URL`: Your Supabase URL
- `SUPABASE_SERVICE_KEY`: For test workflows

### Workflows

Three workflows are configured:

1. **Daily VIP Scrape** (`.github/workflows/daily-scrape.yml`)
   - Runs at 2 AM UTC daily
   - Processes top 100 athletes by Gravity score
   - Manual trigger available

2. **Weekly Full Scrape** (`.github/workflows/weekly-scrape.yml`)
   - Runs at 3 AM UTC Sunday
   - Processes all active athletes
   - May take several hours

3. **Test Suite** (`.github/workflows/test.yml`)
   - Runs on push/PR to main branch
   - Runs daily at 6 AM UTC
   - Tracks test results to database

### Manual Trigger

```bash
# From GitHub UI: Actions → [Workflow] → Run workflow

# Or via API
curl -X POST \
  https://api.github.com/repos/[owner]/[repo]/actions/workflows/daily-scrape.yml/dispatches \
  -H "Authorization: Bearer [GITHUB_TOKEN]" \
  -d '{"ref":"main"}'
```

## API Documentation

### Authentication

All protected endpoints require Bearer token authentication:

```bash
curl -X POST https://[your-app].up.railway.app/api/v1/athletes/[id]/refresh \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Endpoints

#### Health Check

```
GET /health
```

Returns service health status.

#### Athlete Refresh (Protected)

```
POST /api/v1/athletes/{athlete_id}/refresh
Authorization: Bearer {API_KEY}
```

Trigger on-demand data refresh for specific athlete.

**Response:**
```json
{
  "status": "started",
  "athlete_id": "uuid",
  "message": "Refresh started. Updates will appear in 30-60 seconds."
}
```

#### Get Athlete Status

```
GET /api/v1/athletes/{athlete_id}/status
```

Get current data status for athlete.

**Response:**
```json
{
  "athlete_id": "uuid",
  "name": "Athlete Name",
  "sport": "cfb",
  "is_active": true,
  "last_scraped": "2026-01-23T12:00:00Z",
  "last_source": "nil_scraper"
}
```

#### Trigger Daily Job (Protected)

```
POST /api/v1/jobs/daily
Authorization: Bearer {API_KEY}
```

Manually trigger daily VIP job.

#### Trigger Weekly Job (Protected)

```
POST /api/v1/jobs/weekly
Authorization: Bearer {API_KEY}
```

Manually trigger weekly full scrape.

#### Get Jobs Status

```
GET /api/v1/jobs/status?limit=20
```

Get recent job statuses (public).

**Response:**
```json
[
  {
    "id": "uuid",
    "job_type": "daily_vip",
    "status": "completed",
    "athletes_total": 100,
    "athletes_processed": 98,
    "athletes_failed": 2,
    "started_at": "2026-01-23T02:00:00Z",
    "completed_at": "2026-01-23T02:15:00Z"
  }
]
```

#### Run Crawler (Protected)

```
POST /api/v1/crawlers/{crawler_name}/run?athlete_id={uuid}
Authorization: Bearer {API_KEY}
```

Run specific crawler for athlete.

Available crawlers:
- `news_article`
- `social_media`
- `transfer_portal`
- `sentiment`
- `injury_report`
- `brand_partnership`
- `game_stats`
- `trade`

#### Run All Crawlers (Protected)

```
POST /api/v1/crawlers/run-all?athlete_id={uuid}&sport=cfb
Authorization: Bearer {API_KEY}
```

Run all crawlers for athlete.

#### Get Crawler Status

```
GET /api/v1/crawlers/status
```

Get status of crawler orchestrator.

### Interactive API Docs

Visit `https://[your-app].up.railway.app/docs` for:
- Interactive API testing
- Complete endpoint documentation
- Request/response schemas
- Try-it-now functionality

## Integration with Lovable Frontend

### Environment Variables

Add to Lovable project settings:

```
VITE_SCRAPER_API_URL=https://[your-app].up.railway.app
VITE_SCRAPER_API_KEY=[your_api_key]
```

### Example: Refresh Button

```typescript
// In React component
const refreshAthleteData = async (athleteId: string) => {
  try {
    const response = await fetch(
      `${import.meta.env.VITE_SCRAPER_API_URL}/api/v1/athletes/${athleteId}/refresh`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${import.meta.env.VITE_SCRAPER_API_KEY}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    const data = await response.json();
    toast.success(data.message);
  } catch (error) {
    toast.error('Failed to refresh data');
  }
};
```

### Real-time Updates

Subscribe to Supabase changes:

```typescript
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

// Subscribe to athlete updates
supabase
  .channel(`athlete-${athleteId}`)
  .on('postgres_changes', {
    event: 'UPDATE',
    schema: 'public',
    table: 'gravity_scores',
    filter: `athlete_id=eq.${athleteId}`
  }, (payload) => {
    // Refresh UI with new data
    refetch();
  })
  .subscribe();
```

## Monitoring

### Job Status Dashboard

Monitor jobs via API or Supabase:

```sql
-- Recent jobs
SELECT * FROM scraper_jobs 
ORDER BY created_at DESC 
LIMIT 10;

-- Failed jobs
SELECT * FROM scraper_jobs 
WHERE status = 'failed' 
ORDER BY created_at DESC;

-- Job success rate
SELECT 
  job_type,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
  ROUND(100.0 * SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM scraper_jobs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY job_type;
```

### Test Results

```sql
-- Recent test results
SELECT * FROM test_executions 
ORDER BY created_at DESC 
LIMIT 20;

-- Test failure rate
SELECT 
  test_type,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
  ROUND(100.0 * SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) / COUNT(*), 2) as pass_rate
FROM test_executions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY test_type;
```

### Railway Logs

View logs in Railway dashboard:
- Deployment logs
- Application logs
- Error traces
- Performance metrics

## Troubleshooting

### Service Won't Start

1. Check Railway environment variables are set
2. Verify Supabase credentials
3. Check Railway logs for errors
4. Ensure database migrations ran

### Scrapers Not Working

1. Verify API keys in environment
2. Check specific scraper availability in logs
3. Test individual scraper with `pytest tests/test_scrapers.py -v`
4. Review scraper service initialization logs

### GitHub Actions Failing

1. Verify secrets are set in repository settings
2. Check Railway URL is accessible
3. Test endpoint manually: `curl https://[your-app].up.railway.app/health`
4. Review workflow logs in GitHub Actions tab

### Database Connection Issues

1. Verify Supabase service role key (not anon key)
2. Check Supabase project is active
3. Test connection: `curl [SUPABASE_URL]/rest/v1/`
4. Verify tables exist: Run migrations again

## Performance Targets

- **API Response Time**: < 200ms (excluding background tasks)
- **Single Athlete Scrape**: < 60 seconds
- **Daily Job (100 athletes)**: < 30 minutes
- **Weekly Job (all athletes)**: < 6 hours
- **Test Coverage**: > 80%

## Support

For issues or questions:
1. Check Railway logs
2. Review GitHub Actions logs
3. Check Supabase logs
4. Verify environment variables
5. Run tests locally to isolate issues

## License

Proprietary - Gravity Score Platform
