#!/usr/bin/env python3
"""
Quick Age Fixer - Add ages to existing player data
Uses Wikipedia and NFL.com to get player ages
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuickAgeFixer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def get_player_age(self, name, team=None):
        """Get player age from multiple sources"""
        
        # Try Wikipedia first (most reliable for birthdate)
        age = self._get_age_from_wikipedia(name)
        if age:
            return age
        
        # Try NFL.com player page
        age = self._get_age_from_nfl_player_page(name)
        if age:
            return age
        
        return None
    
    def _get_age_from_wikipedia(self, player_name):
        """Extract age from Wikipedia"""
        try:
            # Search Wikipedia
            search_url = f"https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': f"{player_name} NFL football",
                'srlimit': 3
            }
            
            response = self.session.get(search_url, params=params, timeout=10)
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            for result in data.get('query', {}).get('search', []):
                page_title = result['title']
                
                # Get page content
                content_url = f"https://en.wikipedia.org/w/api.php"
                content_params = {
                    'action': 'query',
                    'format': 'json',
                    'titles': page_title,
                    'prop': 'extracts',
                    'exintro': True,
                    'explaintext': True
                }
                
                content_response = self.session.get(content_url, params=content_params, timeout=10)
                if content_response.status_code == 200:
                    content_data = content_response.json()
                    pages = content_data.get('query', {}).get('pages', {})
                    
                    for page_id, page_info in pages.items():
                        extract = page_info.get('extract', '')
                        
                        # Look for birth date patterns
                        birth_patterns = [
                            r'born (\w+ \d{1,2}, \d{4})',
                            r'Born: (\w+ \d{1,2}, \d{4})',
                            r'\(born (\w+ \d{1,2}, \d{4})\)',
                            r'(\w+ \d{1,2}, \d{4})',
                        ]
                        
                        for pattern in birth_patterns:
                            match = re.search(pattern, extract, re.IGNORECASE)
                            if match:
                                try:
                                    birth_str = match.group(1)
                                    birth_date = datetime.strptime(birth_str, '%B %d, %Y')
                                    age = (datetime.now() - birth_date).days // 365
                                    
                                    if 18 <= age <= 45:  # Reasonable NFL age
                                        return age
                                except:
                                    continue
                
                time.sleep(0.5)  # Be respectful to Wikipedia
                
        except Exception as e:
            logger.debug(f"Wikipedia age lookup failed for {player_name}: {e}")
        
        return None
    
    def _get_age_from_nfl_player_page(self, player_name):
        """Try to get age from NFL.com player page"""
        try:
            # Clean name for URL
            clean_name = player_name.lower().replace(' ', '-').replace('.', '').replace("'", '')
            player_url = f"https://www.nfl.com/players/{clean_name}/"
            
            response = self.session.get(player_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                text = soup.get_text()
                
                # Look for age patterns
                age_patterns = [
                    r'Age:\s*(\d+)',
                    r'AGE:\s*(\d+)',
                    r'(\d+)\s*years\s*old',
                ]
                
                for pattern in age_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        age = int(match.group(1))
                        if 18 <= age <= 45:
                            return age
                            
        except Exception as e:
            logger.debug(f"NFL.com age lookup failed for {player_name}: {e}")
        
        return None
    
    def enhance_dataset_with_ages(self, csv_file, max_players=50):
        """Add ages to existing dataset"""
        logger.info(f"Loading dataset from {csv_file}")
        
        df = pd.read_csv(csv_file)
        logger.info(f"Found {len(df)} players")
        
        # Limit to first N players for testing
        df_sample = df.head(max_players).copy()
        
        ages_found = 0
        for i, row in df_sample.iterrows():
            player_name = row.get('name', '')
            team = row.get('team', '')
            
            if player_name:
                logger.info(f"Looking up age for {player_name} ({i+1}/{len(df_sample)})")
                
                age = self.get_player_age(player_name, team)
                if age:
                    df_sample.at[i, 'age'] = age
                    ages_found += 1
                    logger.info(f"  ✅ Found age {age}")
                else:
                    logger.info(f"  ❌ No age found")
                
                # Rate limiting
                time.sleep(1.5)
        
        logger.info(f"Ages found: {ages_found}/{len(df_sample)}")
        
        # Save enhanced dataset
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"data/players_with_ages_{timestamp}.csv"
        df_sample.to_csv(output_file, index=False)
        
        logger.info(f"Enhanced dataset saved to {output_file}")
        return output_file, ages_found

def main():
    """Main function to enhance existing dataset with ages"""
    
    # Find the most recent players file with good heights
    import glob
    
    files = glob.glob('data/players_*.csv')
    if not files:
        print("❌ No player data files found")
        return
    
    # Use the file with good heights
    good_files = []
    for file in files:
        try:
            df_test = pd.read_csv(file)
            if len(df_test) > 1000:  # Large dataset
                sample_height = df_test['height'].dropna().iloc[0] if len(df_test['height'].dropna()) > 0 else ''
                if sample_height and "'" in sample_height:
                    parts = sample_height.replace('"', '').split("'")
                    if len(parts) == 2 and parts[0].isdigit():
                        feet = int(parts[0])
                        if 5 <= feet <= 6:  # Realistic height
                            good_files.append((file, len(df_test)))
        except:
            continue
    
    if not good_files:
        print("❌ No files with good height data found")
        return
    
    # Use the largest file with good heights
    best_file = max(good_files, key=lambda x: x[1])[0]
    print(f"Using file: {best_file}")
    
    # Enhance with ages
    fixer = QuickAgeFixer()
    output_file, ages_found = fixer.enhance_dataset_with_ages(best_file, max_players=30)
    
    print(f"✅ Enhanced {ages_found} players with age data")
    print(f"📁 Saved to: {output_file}")

if __name__ == "__main__":
    main()