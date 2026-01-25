#!/bin/bash
###############################################################################
# View Latest Scraper Results
###############################################################################
# 
# This script helps you quickly find and view the most recent scraper outputs.
# All outputs are now organized by date in the following structure:
#
#   scrapes/
#   ├── NFL/{YYYYMMDD_HHMMSS}/
#   ├── NBA/{YYYYMMDD_HHMMSS}/
#   ├── CFB/{YYYYMMDD_HHMMSS}/
#   ├── NCAAB_Mens/{YYYYMMDD_HHMMSS}/
#   ├── NCAAB_Womens/{YYYYMMDD_HHMMSS}/
#   └── WNBA/{YYYYMMDD_HHMMSS}/
#
#   test_results/
#   ├── NFL/{YYYYMMDD_HHMMSS}/
#   ├── NBA/{YYYYMMDD_HHMMSS}/
#   └── CFB/{YYYYMMDD_HHMMSS}/
#
# Usage:
#   ./view_latest_results.sh [sport] [type]
#
# Examples:
#   ./view_latest_results.sh nfl scrapes       # Latest NFL scraper results
#   ./view_latest_results.sh nba test          # Latest NBA test results
#   ./view_latest_results.sh cfb scrapes       # Latest CFB scraper results
#   ./view_latest_results.sh                   # Interactive mode
###############################################################################

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to find latest directory
find_latest() {
    local sport=$1
    local type=$2  # "scrapes" or "test_results"
    
    case $type in
        scrapes)
            base_dir="scrapes"
            ;;
        test|test_results)
            base_dir="test_results"
            ;;
        *)
            echo "❌ Invalid type: $type (must be 'scrapes' or 'test')"
            return 1
            ;;
    esac
    
    # Map sport name to directory name
    case $(echo "$sport" | tr '[:upper:]' '[:lower:]') in
        nfl)
            sport_dir="NFL"
            ;;
        nba)
            sport_dir="NBA"
            ;;
        cfb|college-football)
            sport_dir="CFB"
            ;;
        ncaab|ncaab-mens|mens-basketball)
            sport_dir="NCAAB_Mens"
            ;;
        ncaab-womens|womens-basketball)
            sport_dir="NCAAB_Womens"
            ;;
        wnba)
            sport_dir="WNBA"
            ;;
        *)
            echo "❌ Unknown sport: $sport"
            echo "   Valid: nfl, nba, cfb, ncaab, ncaab-womens, wnba"
            return 1
            ;;
    esac
    
    # Find the latest directory
    target_dir="${base_dir}/${sport_dir}"
    
    if [ ! -d "$target_dir" ]; then
        echo "❌ No results found for $sport_dir in $base_dir/"
        echo "   Directory does not exist: $target_dir"
        return 1
    fi
    
    # Get the most recent timestamped directory
    latest=$(ls -t "$target_dir" 2>/dev/null | head -n 1)
    
    if [ -z "$latest" ]; then
        echo "❌ No results found in $target_dir"
        return 1
    fi
    
    echo "${target_dir}/${latest}"
}

# Function to display directory contents
show_results() {
    local dir=$1
    
    if [ ! -d "$dir" ]; then
        echo "❌ Directory not found: $dir"
        return 1
    fi
    
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Latest Results: $(basename $(dirname $dir))/$(basename $dir)${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Show directory info
    echo -e "${BLUE}📁 Directory:${NC} $dir"
    echo -e "${BLUE}📅 Created:${NC} $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$dir" 2>/dev/null || stat -c "%y" "$dir" 2>/dev/null | cut -d'.' -f1)"
    echo ""
    
    # List files with sizes
    echo -e "${BLUE}📄 Files:${NC}"
    if [ -d "$dir" ]; then
        for file in "$dir"/*; do
            if [ -f "$file" ]; then
                size=$(du -h "$file" | cut -f1)
                filename=$(basename "$file")
                
                # Highlight CSV and validation reports
                if [[ "$filename" == *.csv ]]; then
                    lines=$(wc -l < "$file" 2>/dev/null || echo "?")
                    echo -e "   ${GREEN}✓${NC} $filename ${YELLOW}($size, $lines rows)${NC}"
                elif [[ "$filename" == *validation*.txt ]]; then
                    echo -e "   ${BLUE}📊${NC} $filename ($size)"
                elif [[ "$filename" == *.json ]]; then
                    echo -e "   ${BLUE}📋${NC} $filename ($size)"
                else
                    echo -e "   • $filename ($size)"
                fi
            fi
        done
    fi
    echo ""
    
    # Show CSV preview if exists
    csv_file=$(find "$dir" -name "*.csv" -type f | head -n 1)
    if [ -n "$csv_file" ]; then
        echo -e "${BLUE}📊 CSV Preview (first 5 rows):${NC}"
        head -n 6 "$csv_file" | cut -c1-120
        echo ""
    fi
    
    # Show validation report summary if exists
    report_file=$(find "$dir" -name "*validation*.txt" -type f | head -n 1)
    if [ -n "$report_file" ]; then
        echo -e "${BLUE}📈 Validation Report Summary:${NC}"
        grep -E "(Players collected:|Avg completeness:|completeness by section:)" "$report_file" -A 10 | head -n 15
        echo ""
    fi
    
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "💡 Tips:"
    echo "   • Open CSV: open $csv_file"
    echo "   • View validation report: cat $report_file"
    echo "   • Navigate to folder: cd $dir"
    echo ""
}

# Interactive mode
interactive_menu() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  View Latest Scraper Results - Interactive Mode${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Select result type:"
    echo "  1) Main Scraper Results (full data collection)"
    echo "  2) Test Results (2 players per team)"
    echo "  3) Exit"
    echo ""
    read -p "Enter choice [1-3]: " choice
    
    case $choice in
        1)
            result_type="scrapes"
            ;;
        2)
            result_type="test_results"
            ;;
        3)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "❌ Invalid choice"
            exit 1
            ;;
    esac
    
    echo ""
    echo "Select sport:"
    echo "  1) NFL"
    echo "  2) NBA"
    echo "  3) CFB (College Football)"
    echo "  4) NCAAB Mens (College Basketball - Men)"
    echo "  5) NCAAB Womens (College Basketball - Women)"
    echo "  6) WNBA"
    echo ""
    read -p "Enter choice [1-6]: " sport_choice
    
    case $sport_choice in
        1) sport="nfl" ;;
        2) sport="nba" ;;
        3) sport="cfb" ;;
        4) sport="ncaab" ;;
        5) sport="ncaab-womens" ;;
        6) sport="wnba" ;;
        *)
            echo "❌ Invalid choice"
            exit 1
            ;;
    esac
    
    latest_dir=$(find_latest "$sport" "$result_type")
    if [ $? -eq 0 ]; then
        show_results "$latest_dir"
    fi
}

# Main logic
if [ $# -eq 0 ]; then
    # No arguments - interactive mode
    interactive_menu
elif [ $# -eq 2 ]; then
    # Direct mode with sport and type
    latest_dir=$(find_latest "$1" "$2")
    if [ $? -eq 0 ]; then
        show_results "$latest_dir"
    fi
else
    echo "Usage: $0 [sport] [type]"
    echo ""
    echo "Sports: nfl, nba, cfb, ncaab, ncaab-womens, wnba"
    echo "Types: scrapes, test"
    echo ""
    echo "Examples:"
    echo "  $0 nfl scrapes       # Latest NFL scraper results"
    echo "  $0 nba test          # Latest NBA test results"
    echo "  $0                   # Interactive mode"
    exit 1
fi

