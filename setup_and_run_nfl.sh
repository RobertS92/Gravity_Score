#!/bin/bash
# Setup and Run NFL Scrape with Perplexity AI Fallback
# =====================================================

echo "🚀 NFL Gravity Score - Complete Scrape & Scoring Pipeline"
echo "=========================================================="
echo ""

# Check if API key is provided as argument
if [ -n "$1" ]; then
    export PERPLEXITY_API_KEY="$1"
    echo "✅ Using Perplexity API key from argument"
else
    # Check if already set in environment
    if [ -z "$PERPLEXITY_API_KEY" ]; then
        echo "⚠️  Perplexity API key not set"
        echo ""
        echo "To get a Perplexity API key:"
        echo "  1. Go to https://www.perplexity.ai/"
        echo "  2. Sign up or log in"
        echo "  3. Get your API key from the dashboard"
        echo ""
        echo -n "Enter your Perplexity API key (or press Enter to skip AI fallback): "
        read -r api_key
        
        if [ -n "$api_key" ]; then
            export PERPLEXITY_API_KEY="$api_key"
            echo "✅ API key set!"
        else
            echo "⚠️  Continuing without AI fallback"
        fi
    else
        echo "✅ Using existing PERPLEXITY_API_KEY from environment"
    fi
fi

echo ""
echo "Configuration:"
echo "  • AI Fallback: $([ -n "$PERPLEXITY_API_KEY" ] && echo 'ENABLED' || echo 'DISABLED')"
echo "  • Output: Gravity_Final_Scores/NFL/"
echo "  • Mode: Test (5 players) or Full (2600+ players)"
echo ""

# Ask user which mode
echo "Select scraping mode:"
echo "  1) Test mode (5 players - quick test, ~2 minutes)"
echo "  2) Fast mode (full NFL - all players, ~4 hours)"
echo "  3) Ultra-fast mode (full NFL - aggressive, ~2-3 hours)"
echo ""
echo -n "Enter choice (1, 2, or 3): "
read -r mode_choice

case $mode_choice in
    1)
        echo ""
        echo "📝 Running TEST MODE (5 players)..."
        export FAST_MODE=true
        python3 run_pipeline.py --scrape nfl --scrape-mode test
        ;;
    2)
        echo ""
        echo "🚀 Running FAST MODE (full NFL)..."
        export FAST_MODE=true
        python3 run_pipeline.py --scrape nfl --scrape-mode all
        ;;
    3)
        echo ""
        echo "⚡ Running ULTRA-FAST MODE (full NFL)..."
        export FAST_MODE=true
        export MAX_CONCURRENT_PLAYERS=150
        export MAX_CONCURRENT_DATA_COLLECTORS=40
        export PLAYER_TIMEOUT=30
        export REQUEST_DELAY=0.05
        export BATCH_SIZE=80
        export CACHE_TTL_HOURS=72
        python3 run_pipeline.py --scrape nfl --scrape-mode all
        ;;
    *)
        echo "❌ Invalid choice. Exiting."
        exit 1
        ;;
esac

# Check if successful
if [ $? -eq 0 ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ SCRAPE & SCORING COMPLETE!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📊 Results saved to: Gravity_Final_Scores/NFL/"
    echo ""
    echo "View your results:"
    echo "  • List files: ls -lth Gravity_Final_Scores/NFL/"
    echo "  • View latest: head \$(ls -t Gravity_Final_Scores/NFL/NFL_Final_*.csv | head -1)"
    echo "  • Count players: wc -l \$(ls -t Gravity_Final_Scores/NFL/NFL_Final_*.csv | head -1)"
    echo ""
    
    # Show AI fallback stats if it was used
    if [ -n "$PERPLEXITY_API_KEY" ]; then
        echo "🤖 Check logs above for AI fallback usage (look for 🤖 and 💰 symbols)"
        echo ""
    fi
    
    echo "Next steps:"
    echo "  • Analyze top players"
    echo "  • Compare with previous runs"
    echo "  • Export to different format"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo ""
    echo "❌ Scrape failed. Check logs above for errors."
    exit 1
fi

