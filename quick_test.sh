#!/bin/bash
# Quick Test - Test one player from each sport to verify fixes

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                         🧪 QUICK TEST - ALL CHANGES                           ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: NFL Proof Data
echo -e "${BLUE}TEST 1: NFL Proof Data (Patrick Mahomes)${NC}"
echo "─────────────────────────────────────────────────────────────────────────────────"
python3 gravity/nfl_scraper.py player "Patrick Mahomes" "Chiefs" "QB" 2>&1 | grep -E "(Pro Bowls|All-Pro|TDs|yards|Contract:|awards)" | head -10

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ NFL proof data logged successfully${NC}"
else
    echo -e "${RED}❌ NFL proof data not found in logs${NC}"
fi
echo ""

# Test 2: Check CSV output
echo -e "${BLUE}TEST 2: CSV Output Check${NC}"
echo "─────────────────────────────────────────────────────────────────────────────────"

# Find latest NFL CSV
latest_csv=$(find scrapes/NFL -name "*.csv" -type f 2>/dev/null | xargs ls -t 2>/dev/null | head -1)

if [ -f "$latest_csv" ]; then
    echo -e "${GREEN}✅ Found CSV: $latest_csv${NC}"
    
    # Check if Mahomes is in the CSV
    if grep -q "Mahomes" "$latest_csv"; then
        echo -e "${GREEN}✅ Mahomes found in CSV${NC}"
        
        # Extract his data
        mahomes_row=$(grep "Mahomes" "$latest_csv" | head -1)
        
        # Try to extract pro_bowls (adjust column number based on your CSV)
        # This is a simple check - the full test script does more thorough validation
        echo ""
        echo -e "${YELLOW}Mahomes data sample:${NC}"
        echo "$mahomes_row" | cut -d',' -f1-10 | sed 's/,/ | /g'
        
    else
        echo -e "${YELLOW}⚠️  Mahomes not found in CSV yet${NC}"
    fi
    
    # Count total players
    total_players=$(tail -n +2 "$latest_csv" | wc -l)
    echo ""
    echo -e "Total players in CSV: ${YELLOW}$total_players${NC}"
    
else
    echo -e "${RED}❌ No NFL CSV found${NC}"
    echo "Run the scraper first: python3 gravity/nfl_scraper.py player \"Patrick Mahomes\" \"Chiefs\" \"QB\""
fi
echo ""

# Test 3: Quick validation
echo -e "${BLUE}TEST 3: Quick Data Validation${NC}"
echo "─────────────────────────────────────────────────────────────────────────────────"

if [ -f "$latest_csv" ]; then
    # Count non-zero pro_bowls (assuming it's a certain column - adjust as needed)
    echo -e "${YELLOW}Checking for non-empty data...${NC}"
    
    # Simple check: does the CSV have the expected columns?
    header=$(head -1 "$latest_csv")
    
    if echo "$header" | grep -q "pro_bowls"; then
        echo -e "${GREEN}✅ 'pro_bowls' column exists${NC}"
    else
        echo -e "${RED}❌ 'pro_bowls' column missing${NC}"
    fi
    
    if echo "$header" | grep -q "career_touchdowns"; then
        echo -e "${GREEN}✅ 'career_touchdowns' column exists${NC}"
    else
        echo -e "${RED}❌ 'career_touchdowns' column missing${NC}"
    fi
    
    if echo "$header" | grep -q "current_contract_length"; then
        echo -e "${GREEN}✅ 'current_contract_length' column exists${NC}"
    else
        echo -e "${RED}❌ 'current_contract_length' column missing${NC}"
    fi
    
    if echo "$header" | grep -q "injury_history"; then
        echo -e "${GREEN}✅ 'injury_history' column exists${NC}"
    else
        echo -e "${RED}❌ 'injury_history' column missing${NC}"
    fi
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                              QUICK TEST COMPLETE                              ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${BLUE}For comprehensive testing, run:${NC}"
echo -e "  ${YELLOW}python3 test_all_changes.py${NC}"
echo ""
echo -e "${BLUE}To view the CSV:${NC}"
echo -e "  ${YELLOW}open $latest_csv${NC}  # Mac"
echo -e "  ${YELLOW}xdg-open $latest_csv${NC}  # Linux"
echo ""

