# How to Get Your Perplexity API Key

## Step 1: Sign Up for Perplexity

1. Go to **https://www.perplexity.ai/**
2. Click **Sign Up** (or **Log In** if you have an account)
3. Complete the registration

## Step 2: Get Your API Key

1. Once logged in, go to **https://www.perplexity.ai/settings/api**
   - Or click your profile → Settings → API
2. You should see an **API Key** section
3. Click **Generate API Key** or **Show API Key**
4. Copy the key (it should start with `pplx-`)

**Example key format:**
```
pplx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Step 3: Test Your API Key

Run this test to verify it works:

```bash
python3 test_perplexity_api.py 'pplx-your-key-here'
```

**Expected output if working:**
```
✅ API KEY WORKS!
   Test query response: 4
🎉 Your Perplexity API is configured correctly!
```

**If you get errors:**
- Check the key is copied correctly (no extra spaces)
- Verify the key starts with `pplx-`
- Make sure your account is activated
- Check if you have API credits/access

## Step 4: Set the API Key for Scraping

### Option A: Interactive Script (Recommended)
```bash
./setup_and_run_nfl.sh
```
The script will prompt you for the key.

### Option B: Export Environment Variable
```bash
export PERPLEXITY_API_KEY="pplx-your-key-here"
python3 run_pipeline.py --scrape nfl --scrape-mode test
```

### Option C: Add to Your Shell Profile (Permanent)
```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export PERPLEXITY_API_KEY="pplx-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

## Step 5: Run the Scrape

```bash
# Test mode (5 players)
python3 run_pipeline.py --scrape nfl --scrape-mode test

# Full mode
./run_fast_nfl_scrape.sh
```

## Troubleshooting

### "Invalid API key" or "401 Unauthorized"
- Key is wrong or expired
- Copy the key again from Perplexity dashboard
- Make sure there are no extra spaces

### "400 Bad Request"
- Model might not be available on your plan
- Try the test script to see the exact error
- Check Perplexity API documentation

### "403 Forbidden"
- API access not enabled on your account
- Check if you need to upgrade your plan
- Verify account is fully activated

### "429 Too Many Requests"
- You've hit the rate limit
- Wait a few minutes and try again
- Consider reducing concurrent players

## Pricing

**Perplexity API Costs (as of 2024):**
- ~$0.001 per query
- Test run (5 players): ~$0.02
- Full NFL scrape (2600 players): ~$8-10

Check current pricing at: https://docs.perplexity.ai/docs/pricing

## Need Help?

**Don't have a Perplexity account?**
- The scraper works fine without AI fallback
- You'll still get 90%+ of the data
- AI only fills in missing obscure player data

**Can't get API access?**
- Disable AI fallback: `export USE_AI_FALLBACK=false`
- Run without it: `python3 run_pipeline.py --scrape nfl`
- Everything else will work normally

## Quick Commands

```bash
# Test API key
python3 test_perplexity_api.py 'your-key'

# Set and test
export PERPLEXITY_API_KEY="your-key"
python3 test_perplexity_api.py

# Run test scrape
export PERPLEXITY_API_KEY="your-key"
python3 run_pipeline.py --scrape nfl --scrape-mode test

# View results
ls -lth Gravity_Final_Scores/NFL/
```

