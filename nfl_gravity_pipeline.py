#!/usr/bin/env python3
"""
NFL Gravity - Single-Cell Pipeline
Streamlined data pipeline for comprehensive NFL player analytics
"""

import os
import time
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NFLGravityPipeline:
    """Single-cell pipeline for comprehensive NFL player data extraction."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # NFL team slugs for 2024 season
        self.TEAM_SLUGS = [
            "arizona-cardinals", "atlanta-falcons", "baltimore-ravens", "buffalo-bills",
            "carolina-panthers", "chicago-bears", "cincinnati-bengals", "cleveland-browns",
            "dallas-cowboys", "denver-broncos", "detroit-lions", "green-bay-packers",
            "houston-texans", "indianapolis-colts", "jacksonville-jaguars", "kansas-city-chiefs",
            "las-vegas-raiders", "los-angeles-chargers", "los-angeles-rams", "miami-dolphins",
            "minnesota-vikings", "new-england-patriots", "new-orleans-saints", "new-york-giants",
            "new-york-jets", "philadelphia-eagles", "pittsburgh-steelers", "san-francisco-49ers",
            "seattle-seahawks", "tampa-bay-buccaneers", "tennessee-titans", "washington-commanders"
        ]
        
        # Data columns for comprehensive player analysis
        self.COLUMNS = [
            # Basic info
            "Team_Full", "Location", "Nickname", "Jersey", "Player",
            # Wikipedia data
            "Age", "Nationality", "Position", "CurrentTeam", "College", "DraftYear", 
            "Trophies", "Injury_Status", "Accomplishments",
            # Social media URLs
            "IG_URL", "Twitter_URL", "TikTok_URL", "YouTube_URL",
            # Instagram metrics
            "Instagram_Followers", "Instagram_Likes_Avg", "Instagram_Comments_Avg", "Instagram_Posts_per_Week",
            # Twitter metrics
            "Twitter_Followers", "Twitter_Likes_Avg", "Twitter_Retweets_Avg", "Twitter_Replies_Avg",
            # TikTok metrics
            "TikTok_Followers", "TikTok_Likes_Avg", "TikTok_Comments_Avg", "TikTok_Shares_Avg",
            # YouTube metrics
            "YouTube_Subscribers", "YouTube_Views_Avg",
            # Professional stats
            "PFR_PassYds", "PFR_PassTD", "PFR_RushRecYds", "PFR_Tackles", "PFR_Sacks", "PFR_Int", "PFR_FG", "PFR_PuntYds",
            # Financial data
            "Career_Earnings",
            # News presence
            "News_Headlines_Count"
        ]
        
    def scrape_team_roster(self, slug: str) -> pd.DataFrame:
        """Scrape roster data for a specific team."""
        url = f"https://www.nfl.com/teams/{slug}/roster"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract team name
            team_header = soup.find("h1") or soup.find("title")
            if team_header:
                team_full = team_header.get_text(strip=True).replace("Roster", "").replace("2024", "").strip()
            else:
                team_full = slug.replace("-", " ").title()
            
            # Parse team name into location and nickname
            parts = team_full.split()
            if len(parts) >= 2:
                location = " ".join(parts[:-1])
                nickname = parts[-1]
            else:
                location = team_full
                nickname = ""
            
            # Extract player data
            rows = []
            player_rows = soup.find_all("tr", class_=lambda x: x and "player" in x.lower() if x else False)
            
            if not player_rows:
                # Try alternative selector
                player_rows = soup.select("tbody tr")
            
            for row in player_rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    # Extract jersey number and player name
                    jersey = cells[0].get_text(strip=True) if cells[0] else ""
                    player_name = cells[1].get_text(strip=True) if cells[1] else ""
                    
                    if player_name and not player_name.lower() in ["player", "name", "no."]:
                        rows.append({
                            "Team_Full": team_full,
                            "Location": location,
                            "Nickname": nickname,
                            "Jersey": jersey,
                            "Player": player_name
                        })
            
            logger.info(f"Scraped {len(rows)} players for {team_full}")
            return pd.DataFrame(rows)
            
        except Exception as e:
            logger.error(f"Error scraping roster for {slug}: {e}")
            return pd.DataFrame()
    
    def discover_social_urls(self, player_name: str) -> Dict[str, Optional[str]]:
        """Discover social media URLs for a player using search strategies."""
        urls = {
            "IG_URL": None,
            "Twitter_URL": None,
            "TikTok_URL": None,
            "YouTube_URL": None
        }
        
        # Simple search-based discovery (fallback approach without Firecrawl)
        search_terms = [
            (f"{player_name} instagram", "instagram.com", "IG_URL"),
            (f"{player_name} twitter", "twitter.com", "Twitter_URL"),
            (f"{player_name} tiktok", "tiktok.com", "TikTok_URL"),
            (f"{player_name} youtube", "youtube.com", "YouTube_URL")
        ]
        
        for search_term, domain, url_key in search_terms:
            try:
                # This is a simplified approach - in production, you'd use Firecrawl or similar
                # For now, we'll construct likely URLs based on common patterns
                if "instagram" in domain:
                    # Try common Instagram username patterns
                    username = player_name.lower().replace(" ", "").replace("'", "").replace(".", "")
                    urls[url_key] = f"https://www.instagram.com/{username}/"
                elif "twitter" in domain:
                    username = player_name.lower().replace(" ", "").replace("'", "").replace(".", "")
                    urls[url_key] = f"https://twitter.com/{username}"
                
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.warning(f"Error discovering {url_key} for {player_name}: {e}")
        
        return urls
    
    def parse_wikipedia(self, player_name: str) -> Dict[str, Any]:
        """Parse Wikipedia data for a player."""
        wiki_data = {
            "Age": None, "Nationality": None, "Position": None, "CurrentTeam": None,
            "College": None, "DraftYear": None, "Trophies": None, "Injury_Status": None,
            "Accomplishments": None
        }
        
        try:
            # Search for Wikipedia page
            search_url = f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}"
            response = self.session.get(search_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Parse infobox
                infobox = soup.find("table", class_="infobox")
                if infobox:
                    for row in infobox.find_all("tr"):
                        row_text = row.get_text(separator="\n")
                        
                        if "Born" in row_text and wiki_data["Age"] is None:
                            age_match = re.search(r"\((\d+)\s+years", row_text)
                            if age_match:
                                wiki_data["Age"] = int(age_match.group(1))
                        
                        if "Position" in row_text and wiki_data["Position"] is None:
                            position = row_text.split("\n")[-1].strip()
                            wiki_data["Position"] = position
                        
                        if "College" in row_text and wiki_data["College"] is None:
                            college = row_text.split("\n")[-1].strip()
                            wiki_data["College"] = college
                        
                        if "Draft" in row_text and wiki_data["DraftYear"] is None:
                            draft_match = re.search(r"(\d{4})", row_text)
                            if draft_match:
                                wiki_data["DraftYear"] = int(draft_match.group(1))
                
                # Count career highlights
                highlights_section = soup.find("span", string=re.compile(r"career highlights|accomplishments", re.I))
                if highlights_section:
                    parent = highlights_section.find_parent()
                    if parent:
                        lists = parent.find_next_siblings("ul")
                        if lists:
                            wiki_data["Accomplishments"] = len(lists[0].find_all("li"))
                
                logger.info(f"Parsed Wikipedia data for {player_name}")
                
        except Exception as e:
            logger.warning(f"Error parsing Wikipedia for {player_name}: {e}")
        
        return wiki_data
    
    def parse_social_media(self, urls: Dict[str, str]) -> Dict[str, Any]:
        """Parse social media metrics from discovered URLs."""
        social_data = {
            "Instagram_Followers": None, "Instagram_Likes_Avg": None, "Instagram_Comments_Avg": None, "Instagram_Posts_per_Week": None,
            "Twitter_Followers": None, "Twitter_Likes_Avg": None, "Twitter_Retweets_Avg": None, "Twitter_Replies_Avg": None,
            "TikTok_Followers": None, "TikTok_Likes_Avg": None, "TikTok_Comments_Avg": None, "TikTok_Shares_Avg": None,
            "YouTube_Subscribers": None, "YouTube_Views_Avg": None
        }
        
        # Note: In production, you'd implement actual parsing here
        # For now, we'll return placeholder structure
        logger.info("Social media parsing would be implemented here")
        
        return social_data
    
    def get_news_count(self, player_name: str) -> int:
        """Get count of news headlines for a player."""
        try:
            # Use Google News RSS feed
            search_term = player_name.replace(" ", "%20")
            rss_url = f"https://news.google.com/rss/search?q={search_term}"
            
            response = self.session.get(rss_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "xml")
                items = soup.find_all("item")
                return len(items)
        except Exception as e:
            logger.warning(f"Error getting news count for {player_name}: {e}")
        
        return 0
    
    def enrich_player(self, idx: int, row: pd.Series, df: pd.DataFrame) -> None:
        """Enrich a single player's data with comprehensive information."""
        player_name = row["Player"]
        logger.info(f"[{idx+1}/{len(df)}] Enriching data for {player_name}")
        
        try:
            # 1. Wikipedia data
            wiki_data = self.parse_wikipedia(player_name)
            for key, value in wiki_data.items():
                df.at[idx, key] = value
            
            # 2. Social media discovery
            social_urls = self.discover_social_urls(player_name)
            for key, value in social_urls.items():
                df.at[idx, key] = value
            
            # 3. Social media metrics
            social_data = self.parse_social_media(social_urls)
            for key, value in social_data.items():
                df.at[idx, key] = value
            
            # 4. News presence
            news_count = self.get_news_count(player_name)
            df.at[idx, "News_Headlines_Count"] = news_count
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error enriching data for {player_name}: {e}")
    
    def run_pipeline(self, max_players: int = None) -> pd.DataFrame:
        """Run the complete NFL Gravity pipeline."""
        logger.info("Starting NFL Gravity Pipeline...")
        
        # 1. Scrape all team rosters
        all_rosters = []
        for slug in self.TEAM_SLUGS:
            logger.info(f"Scraping roster for {slug}")
            roster_df = self.scrape_team_roster(slug)
            if not roster_df.empty:
                all_rosters.append(roster_df)
            time.sleep(0.5)  # Rate limiting
        
        if not all_rosters:
            logger.error("No roster data found")
            return pd.DataFrame()
        
        # 2. Combine all rosters
        df = pd.concat(all_rosters, ignore_index=True)
        logger.info(f"Total players found: {len(df)}")
        
        # 3. Initialize all columns
        for col in self.COLUMNS:
            if col not in df.columns:
                df[col] = None
        
        # 4. Limit for testing if requested
        if max_players:
            df = df.head(max_players)
            logger.info(f"Limited to {max_players} players for testing")
        
        # 5. Enrich player data
        logger.info("Starting player enrichment...")
        for idx, row in df.iterrows():
            self.enrich_player(idx, row, df)
        
        # 6. Save results
        output_file = "nfl_2024_gravity_data.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"Pipeline complete! Results saved to {output_file}")
        
        return df

def main():
    """Main entry point for the NFL Gravity pipeline."""
    print("🏈 NFL Gravity - Single-Cell Pipeline")
    print("=" * 50)
    
    # Initialize pipeline
    pipeline = NFLGravityPipeline()
    
    # Ask user for testing mode
    test_mode = input("Run in test mode? (y/n - test mode processes only 5 players): ").strip().lower()
    max_players = 5 if test_mode == 'y' else None
    
    if test_mode == 'y':
        print("Running in test mode with 5 players...")
    else:
        print("Running full pipeline for all NFL players...")
        confirm = input("This will take several hours. Continue? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Pipeline cancelled.")
            return
    
    # Run pipeline
    try:
        df = pipeline.run_pipeline(max_players=max_players)
        
        print(f"\n✅ Pipeline completed successfully!")
        print(f"📊 Processed {len(df)} players")
        print(f"💾 Results saved to: nfl_2024_gravity_data.csv")
        
        # Show sample data
        if not df.empty:
            print("\n📋 Sample of collected data:")
            print(df[['Player', 'Team_Full', 'Position', 'Age', 'News_Headlines_Count']].head())
        
    except KeyboardInterrupt:
        print("\n⚠️  Pipeline interrupted by user")
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        logger.error(f"Pipeline failed: {e}")

if __name__ == "__main__":
    main()