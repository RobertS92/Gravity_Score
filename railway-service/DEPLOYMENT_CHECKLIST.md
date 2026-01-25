# Railway Deployment Checklist

## Pre-Deployment

- [x] Project structure created
- [x] FastAPI application implemented
- [x] All services (scraper, crawler, scheduler) built
- [x] API endpoints implemented
- [x] Tests written
- [x] Documentation complete
- [x] Docker configuration ready
- [x] GitHub workflows configured

## Database Setup

### 1. Run Supabase Migration

1. Open Supabase Dashboard → SQL Editor
2. Copy contents from `../gravity/db/migrations/add_scraper_jobs.sql`
3. Execute the SQL to create:
   - `scraper_jobs` table
   - `test_executions` table
   - Indexes

**Verify:**
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('scraper_jobs', 'test_executions');
```

## Railway Deployment

### 2. Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Name it: `gravity-scrapers-service`

### 3. Configure Root Directory

In Railway project settings:
- Set **Root Directory**: `railway-service`
- Railway will auto-detect Dockerfile

### 4. Set Environment Variables

Add these in Railway project → Variables:

#### Required Variables

```env
# API
API_KEY=[Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"]
PORT=8000

# Supabase (IMPORTANT: Use SERVICE ROLE key, not anon key)
SUPABASE_URL=https://[your-project].supabase.co
SUPABASE_SERVICE_KEY=[Get from Supabase → Settings → API → service_role]

# External APIs
PERPLEXITY_API_KEY=[your_key]
OPENAI_API_KEY=[your_key]
ANTHROPIC_API_KEY=[your_key]
FIRECRAWL_API_KEY=[your_key]

# Reddit
REDDIT_CLIENT_ID=[your_id]
REDDIT_CLIENT_SECRET=[your_secret]

# CORS (Update with your Lovable app URL)
CORS_ORIGINS=["https://your-app.lovable.app","http://localhost:5173"]
```

#### Generate API Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Deploy

1. Click "Deploy" in Railway
2. Wait for build to complete (~3-5 minutes)
3. Railway will provide a public URL: `https://[your-app].up.railway.app`

### 6. Verify Deployment

```bash
# Test health endpoint
curl https://[your-app].up.railway.app/health

# Should return:
# {"status":"healthy","timestamp":"...","service":"gravity-scrapers"}

# Test API docs
open https://[your-app].up.railway.app/docs
```

## GitHub Actions Setup

### 7. Add Repository Secrets

Go to GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

```
RAILWAY_API_URL = https://[your-app].up.railway.app
SCRAPER_API_KEY = [Same API_KEY from Railway]
SUPABASE_URL = https://[your-project].supabase.co
SUPABASE_SERVICE_KEY = [service_role key for tests]
```

### 8. Enable Workflows

1. Go to GitHub → Actions tab
2. Enable workflows if prompted
3. Workflows to verify:
   - Daily VIP Scrape
   - Weekly Full Scrape
   - Run Tests

### 9. Test Manual Trigger

1. Go to GitHub → Actions → "Daily VIP Scrape"
2. Click "Run workflow" → Select branch → "Run workflow"
3. Wait for completion
4. Verify in Railway logs

## Verification

### 10. Test API Endpoints

```bash
# Health check
curl https://[your-app].up.railway.app/health

# Get crawler status
curl https://[your-app].up.railway.app/api/v1/crawlers/status

# Get jobs status
curl https://[your-app].up.railway.app/api/v1/jobs/status

# Test protected endpoint (should fail without auth)
curl https://[your-app].up.railway.app/api/v1/jobs/daily

# Test with auth (should succeed)
curl -X POST https://[your-app].up.railway.app/api/v1/jobs/daily \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 11. Verify Database Integration

Check Supabase:

```sql
-- Check for jobs
SELECT * FROM scraper_jobs ORDER BY created_at DESC LIMIT 5;

-- Check for test executions
SELECT * FROM test_executions ORDER BY created_at DESC LIMIT 5;
```

### 12. Monitor First Scheduled Run

Wait for scheduled runs:
- **Daily Job**: 2 AM UTC
- **Weekly Job**: 3 AM UTC Sunday
- **Test Job**: 6 AM UTC daily

Or trigger manually via GitHub Actions.

## Lovable Integration (Optional)

### 13. Update Lovable Environment

Add to Lovable project settings:

```
VITE_SCRAPER_API_URL=https://[your-app].up.railway.app
VITE_SCRAPER_API_KEY=[your_api_key]
```

### 14. Test Integration

Implement refresh button in Lovable:

```typescript
const refreshData = async (athleteId: string) => {
  const response = await fetch(
    `${import.meta.env.VITE_SCRAPER_API_URL}/api/v1/athletes/${athleteId}/refresh`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${import.meta.env.VITE_SCRAPER_API_KEY}`
      }
    }
  );
  return response.json();
};
```

## Monitoring

### 15. Set Up Monitoring

**Railway Dashboard:**
- Check deployment logs
- Monitor resource usage
- Review error logs

**Supabase:**
- Monitor job executions
- Track test results
- Review data freshness

**GitHub Actions:**
- Check workflow runs
- Review test results
- Monitor scheduled jobs

## Success Criteria

- [ ] Railway service deployed and accessible
- [ ] Health endpoint returns 200
- [ ] API documentation accessible at /docs
- [ ] Database tables created in Supabase
- [ ] GitHub Actions workflows enabled
- [ ] Manual job trigger works
- [ ] Scheduled jobs run successfully
- [ ] Tests pass in CI/CD
- [ ] Lovable integration working (if applicable)

## Rollback Plan

If deployment fails:

1. **Check Railway logs** for errors
2. **Verify environment variables** are correct
3. **Test database connection** from Railway
4. **Revert to previous deployment** in Railway dashboard
5. **Review recent changes** in Git

## Cost Monitoring

**Railway:**
- Free tier: $5/month credit
- Estimated cost: ~$5-10/month
- Monitor in Railway dashboard

**Supabase:**
- Free tier sufficient for development
- Monitor database size and API calls

**External APIs:**
- Perplexity: Monitor usage
- OpenAI: Set budget limits
- Track in `ai_request_log` table

## Maintenance

### Regular Tasks

- **Daily**: Review job execution logs
- **Weekly**: Check success rates and errors
- **Monthly**: Review API costs and optimize

### Updates

```bash
# Update dependencies
cd railway-service
pip list --outdated
pip install -U [package]

# Update requirements.txt
pip freeze > requirements.txt

# Commit and push - Railway auto-deploys
git add requirements.txt
git commit -m "Update dependencies"
git push
```

## Support Resources

- **README.md**: Complete usage guide
- **Railway Docs**: https://docs.railway.app
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Supabase Docs**: https://supabase.com/docs
- **API Docs**: https://[your-app].up.railway.app/docs

---

## Quick Reference

### Important URLs

- **Railway Dashboard**: https://railway.app/project/[id]
- **API Service**: https://[your-app].up.railway.app
- **API Docs**: https://[your-app].up.railway.app/docs
- **Supabase**: https://app.supabase.com/project/[id]
- **GitHub Actions**: https://github.com/[owner]/[repo]/actions

### Important Commands

```bash
# Local development
uvicorn app.main:app --reload

# Run tests
pytest

# Trigger daily job
curl -X POST $RAILWAY_API_URL/api/v1/jobs/daily \
  -H "Authorization: Bearer $SCRAPER_API_KEY"

# Check job status
curl $RAILWAY_API_URL/api/v1/jobs/status | jq
```
