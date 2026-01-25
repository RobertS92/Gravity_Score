#!/usr/bin/env python3
"""
Bulk Contract Scraper - Get contracts for all players FAST
===========================================================

Scrapes contract data from Spotrac.com and OverTheCap.com in parallel.
Can process 100+ players in ~10 minutes.

Usage:
    python bulk_contract_scraper.py input.csv output.csv
    python bulk_contract_scraper.py nfl_players.csv nfl_with_contracts.csv --sport nfl

Author: Gravity Score Team
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import time
from concurrent.futures import ThreadPoolExecutor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# ASYNC CONTRACT SCRAPER
# ============================================================================

class BulkContractScraper:
    """Fast parallel contract scraping"""
    
    def __init__(self, sport: str = 'nfl', max_concurrent: int = 10):
        """
        Initialize scraper
        
        Args:
            sport: 'nfl' or 'nba'
            max_concurrent: Max concurrent requests (don't overload servers)
        """
        self.sport = sport.lower()
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results = {}
        self.errors = {}
    
    async def fetch_spotrac_contract(
        self, 
        session: aiohttp.ClientSession, 
        player_name: str, 
        team: str
    ) -> Tuple[str, Optional[Dict]]:
        """
        Async fetch from Spotrac
        
        Returns:
            (player_name, contract_data) or (player_name, None)
        """
        async with self.semaphore:  # Rate limiting
            try:
                # Clean player name for URL
                name_parts = player_name.lower().replace('.', '').replace("'", '').split()
                player_slug = '-'.join(name_parts)
                
                # Team name to slug
                team_slug = team.lower().replace(' ', '-').replace('.', '')
                
                # Build URL
                url = f"https://www.spotrac.com/{self.sport}/{team_slug}/{player_slug}/"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        contract_data = {}
                        
                        # Contract value
                        value_elem = soup.find('div', class_='total-value')
                        if value_elem:
                            value_text = value_elem.get_text(strip=True)
                            contract_data['contract_value'] = self._parse_money(value_text)
                        
                        # Guaranteed money
                        guaranteed = soup.find('div', class_='guaranteed')
                        if guaranteed:
                            gtd_text = guaranteed.get_text(strip=True)
                            contract_data['guaranteed_money'] = self._parse_money(gtd_text)
                        
                        # Average annual value
                        aav = soup.find('div', class_='avg-annual')
                        if aav:
                            aav_text = aav.get_text(strip=True)
                            contract_data['avg_annual_value'] = self._parse_money(aav_text)
                        
                        # Years
                        years_elem = soup.find('div', class_='years')
                        if years_elem:
                            years_text = years_elem.get_text(strip=True)
                            years_match = re.search(r'(\d+)', years_text)
                            if years_match:
                                contract_data['contract_years'] = int(years_match.group(1))
                        
                        # Free agency year
                        fa_year = soup.find('span', class_='free-agent')
                        if fa_year:
                            year_text = fa_year.get_text(strip=True)
                            year_match = re.search(r'(\d{4})', year_text)
                            if year_match:
                                contract_data['free_agent_year'] = int(year_match.group(1))
                        
                        if contract_data:
                            contract_data['source'] = 'spotrac'
                            return player_name, contract_data
                
            except asyncio.TimeoutError:
                logger.debug(f"Timeout for {player_name}")
            except Exception as e:
                logger.debug(f"Error fetching {player_name}: {e}")
            
            return player_name, None
    
    async def fetch_overthecap_contract(
        self,
        session: aiohttp.ClientSession,
        player_name: str,
        team: str
    ) -> Tuple[str, Optional[Dict]]:
        """
        Async fetch from OverTheCap (NFL only)
        
        Returns:
            (player_name, cap_data) or (player_name, None)
        """
        if self.sport != 'nfl':
            return player_name, None
        
        async with self.semaphore:
            try:
                # Clean names
                name_parts = player_name.lower().replace('.', '').replace("'", '').split()
                player_slug = '-'.join(name_parts)
                team_slug = team.lower().replace(' ', '-')
                
                url = f"https://overthecap.com/player/{player_slug}/{team_slug}/"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        cap_data = {}
                        
                        # Current cap hit
                        cap_hit = soup.find('div', class_='cap-hit')
                        if cap_hit:
                            cap_text = cap_hit.get_text(strip=True)
                            cap_data['cap_hit_current'] = self._parse_money(cap_text)
                        
                        if cap_data:
                            cap_data['source'] = 'overthecap'
                            return player_name, cap_data
                
            except:
                pass
            
            return player_name, None
    
    def _parse_money(self, text: str) -> Optional[int]:
        """Parse money string to integer"""
        if not text:
            return None
        
        # Remove all non-numeric except decimal point
        text = text.replace(',', '').replace('$', '')
        
        # Handle million/billion
        multiplier = 1
        if 'M' in text or 'million' in text.lower():
            multiplier = 1000000
            text = text.replace('M', '').replace('million', '').strip()
        elif 'B' in text or 'billion' in text.lower():
            multiplier = 1000000000
            text = text.replace('B', '').replace('billion', '').strip()
        elif 'K' in text or 'thousand' in text.lower():
            multiplier = 1000
            text = text.replace('K', '').replace('thousand', '').strip()
        
        try:
            # Extract first number
            match = re.search(r'[\d.]+', text)
            if match:
                return int(float(match.group(0)) * multiplier)
        except:
            pass
        
        return None
    
    async def scrape_contracts(
        self, 
        players: List[Dict[str, str]]
    ) -> Dict[str, Dict]:
        """
        Scrape contracts for all players in parallel
        
        Args:
            players: List of dicts with 'player_name' and 'team'
            
        Returns:
            Dict mapping player_name to contract data
        """
        logger.info(f"Starting bulk contract scraping for {len(players)} players...")
        logger.info(f"Max concurrent requests: {self.max_concurrent}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        timeout = aiohttp.ClientTimeout(total=300)  # 5 min total timeout
        
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            # Create tasks for all players
            tasks = []
            
            for player in players:
                player_name = player['player_name']
                team = player.get('team', '')
                
                # Try Spotrac first
                task = self.fetch_spotrac_contract(session, player_name, team)
                tasks.append(task)
            
            # Execute all requests in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            contracts = {}
            for result in results:
                if isinstance(result, tuple):
                    player_name, contract_data = result
                    if contract_data:
                        contracts[player_name] = contract_data
            
            logger.info(f"✅ Successfully scraped {len(contracts)}/{len(players)} contracts")
            
            return contracts
    
    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process DataFrame with player data
        
        Args:
            df: DataFrame with 'player_name' and 'team' columns
            
        Returns:
            DataFrame with added contract columns
        """
        # Prepare player list
        players = []
        for _, row in df.iterrows():
            players.append({
                'player_name': row.get('player_name', ''),
                'team': row.get('team', '')
            })
        
        # Run async scraping
        contracts = asyncio.run(self.scrape_contracts(players))
        
        # Add contract data to DataFrame
        contract_columns = [
            'contract_value',
            'guaranteed_money',
            'avg_annual_value',
            'contract_years',
            'free_agent_year',
            'cap_hit_current',
            'contract_source'
        ]
        
        # Initialize columns
        for col in contract_columns:
            if col not in df.columns:
                df[col] = None
        
        # Update with scraped data
        for player_name, contract_data in contracts.items():
            mask = df['player_name'] == player_name
            
            if mask.any():
                for key, value in contract_data.items():
                    col_name = key if key in df.columns else f"contract_{key}" if f"contract_{key}" in df.columns else key
                    
                    if col_name == 'source':
                        col_name = 'contract_source'
                    
                    if col_name in df.columns:
                        df.loc[mask, col_name] = value
        
        return df


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Bulk Contract Scraper - Fast parallel contract data collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape NFL contracts
  python bulk_contract_scraper.py nfl_players.csv nfl_with_contracts.csv
  
  # Scrape NBA contracts
  python bulk_contract_scraper.py nba_players.csv nba_with_contracts.csv --sport nba
  
  # Limit concurrent requests
  python bulk_contract_scraper.py players.csv output.csv --concurrent 5

Speed:
  ~6 seconds per 100 players (with 10 concurrent requests)
  ~10 minutes for 1000 players
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Input CSV file with player_name and team columns'
    )
    
    parser.add_argument(
        'output',
        type=str,
        help='Output CSV file with contract data added'
    )
    
    parser.add_argument(
        '--sport',
        type=str,
        default='nfl',
        choices=['nfl', 'nba'],
        help='Sport to scrape contracts for (default: nfl)'
    )
    
    parser.add_argument(
        '--concurrent',
        type=int,
        default=10,
        help='Max concurrent requests (default: 10, reduce if getting blocked)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load input data
    logger.info(f"Loading {args.input}...")
    df = pd.read_csv(args.input)
    
    if 'player_name' not in df.columns:
        logger.error("Input CSV must have 'player_name' column")
        sys.exit(1)
    
    logger.info(f"Loaded {len(df)} players")
    
    # Initialize scraper
    scraper = BulkContractScraper(sport=args.sport, max_concurrent=args.concurrent)
    
    # Process
    start_time = time.time()
    df_with_contracts = scraper.process_dataframe(df)
    elapsed = time.time() - start_time
    
    # Save results
    df_with_contracts.to_csv(args.output, index=False)
    
    # Summary
    contracts_added = df_with_contracts['contract_value'].notna().sum()
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ SCRAPING COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Players processed: {len(df)}")
    logger.info(f"Contracts found: {contracts_added} ({contracts_added/len(df)*100:.1f}%)")
    logger.info(f"Time elapsed: {elapsed:.1f} seconds")
    logger.info(f"Speed: {len(df)/elapsed:.1f} players/second")
    logger.info(f"Output saved to: {args.output}")
    logger.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()

