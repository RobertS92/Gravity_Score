"""
Contract Data Collector - FREE (No Firecrawl needed)
Scrapes contract data from Spotrac and Over The Cap
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, Optional
from urllib.parse import quote
import time

logger = logging.getLogger(__name__)


class ContractCollector:
    """Collect contract data from free public sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def collect_contract_data(self, player_name: str, team: str, sport: str = 'nfl') -> Dict:
        """
        Collect comprehensive contract data
        
        Args:
            player_name: Player's name
            team: Team name
            sport: 'nfl' or 'nba'
        
        Returns:
            Dict with contract details
        """
        logger.info(f"💰 Collecting contract data for {player_name} ({team})...")
        
        contract_data = {
            'contract_value': None,
            'guaranteed_money': None,
            'avg_annual_value': None,
            'contract_years': None,
            'years_remaining': None,
            'cap_hit_current': None,
            'cap_hit_next_year': None,
            'signing_bonus': None,
            'contract_status': None,
            'free_agent_year': None,
            'agent': None,
            'management_company': None,
            'career_earnings': None,
            'source': None
        }
        
        # Try Spotrac first (best for contract details)
        try:
            spotrac_data = self._get_spotrac_data(player_name, team, sport)
            if spotrac_data and spotrac_data.get('contract_value'):
                contract_data.update(spotrac_data)
                contract_data['source'] = 'spotrac'
                logger.info(f"✅ Spotrac: Found contract data for {player_name}")
        except Exception as e:
            logger.warning(f"Spotrac collection failed for {player_name}: {e}")
        
        # Try Over The Cap for additional cap data
        if sport == 'nfl':
            otc_data = self._get_overthecap_data(player_name, team)
            if otc_data:
                # Merge data, preferring Spotrac for main values
                contract_data['cap_hit_current'] = otc_data.get('cap_hit_current') or contract_data.get('cap_hit_current')
                contract_data['cap_hit_next_year'] = otc_data.get('cap_hit_next_year')
                if not contract_data['source']:
                    contract_data['source'] = 'overthecap'
        
        # Collect agent and management info
        agent_mgmt = self.get_agent_and_management(player_name, team, sport)
        contract_data['agent'] = agent_mgmt.get('agent')
        contract_data['management_company'] = agent_mgmt.get('management_company')
        
        # Collect career earnings
        career_earnings = self.get_career_earnings(player_name, team, sport)
        contract_data['career_earnings'] = career_earnings
        
        contract_val = contract_data.get('contract_value') or 0
        guaranteed_val = contract_data.get('guaranteed_money') or 0
        if contract_val or contract_data.get('cap_hit_current'):
            logger.info(f"✅ Contract data: ${contract_val:,} total, ${guaranteed_val:,} guaranteed")
        else:
            logger.warning(f"⚠️  No contract data found for {player_name}")
        
        return contract_data
    
    def _get_spotrac_data(self, player_name: str, team: str, sport: str) -> Optional[Dict]:
        """Scrape contract data from Spotrac.com"""
        try:
            # Clean player name for URL - try multiple formats
            name_variants = [
                player_name.lower().replace('.', '').replace("'", '').replace('-', ' '),
                player_name.lower().replace('.', '').replace("'", ''),
                player_name.lower().replace("'", ''),
            ]
            
            # Team name to slug - try multiple formats
            team_variants = [
                team.lower().replace(' ', '-').replace('.', '').replace("'", ''),
                team.lower().replace(' ', '-'),
                team.split()[-1].lower() if ' ' in team else team.lower(),  # Just last word
            ]
            
            data = {}
            
            # Try multiple URL combinations
            for name_variant in name_variants:
                name_parts = name_variant.split()
                player_slug = '-'.join(name_parts)
                
                for team_slug in team_variants:
                    # Try standard format
                    url = f"https://www.spotrac.com/{sport}/{team_slug}/{player_slug}/"
                    
                    logger.debug(f"Trying Spotrac: {url}")
                    try:
                        response = self.session.get(url, timeout=15, allow_redirects=True)
                        
                        if response.status_code == 200:
                            # Check if we were redirected to overview page - if so, try to find player link
                            final_url = response.url
                            if '/overview' in final_url or '/nfl' in final_url and '/overview' not in final_url and player_slug not in final_url:
                                # We're on team overview or wrong page, need to find player's individual page
                                soup_temp = BeautifulSoup(response.content, 'html.parser')
                                # Look for link to player's page - try multiple patterns
                                player_links = soup_temp.find_all('a', href=re.compile(rf'/{sport}/.*{player_slug}.*', re.I))
                                if not player_links:
                                    # Try the /player/_/id/ format
                                    player_links = soup_temp.find_all('a', href=re.compile(rf'/{sport}/player/.*{player_slug}', re.I))
                                
                                if player_links:
                                    # Get the first matching player link
                                    player_path = player_links[0].get('href')
                                    if not player_path.startswith('http'):
                                        player_path = f"https://www.spotrac.com{player_path}"
                                    # Try to get the actual player page
                                    logger.debug(f"Found player link, trying: {player_path}")
                                    response = self.session.get(player_path, timeout=15, allow_redirects=True)
                                    final_url = response.url
                            
                            soup = BeautifulSoup(response.content, 'html.parser')
                            page_text = soup.get_text()
                            page_html = str(soup)
                            
                            # Method 1: Look for "Contract Terms:" in page text - this is the CURRENT contract summary
                            # Format appears as: "Contract Terms:" followed by "X yr(s) / $Y,YYY,YYY" on next line
                            if 'Contract Terms:' in page_text:
                                # Find all occurrences of "Contract Terms:" and get the contract info from the next line
                                lines = page_text.split('\n')
                                contracts_found = []
                                
                                for i, line in enumerate(lines):
                                    if 'Contract Terms:' in line and i < len(lines) - 1:
                                        # Check the next line for contract value
                                        next_line = lines[i + 1] if i + 1 < len(lines) else ''
                                        contract_match = re.search(r'(\d+)\s*yr\(s\)\s*/\s*\$([\d,]+)', next_line, re.I)
                                        if contract_match:
                                            years = int(contract_match.group(1))
                                            value_str = contract_match.group(2).replace(',', '')
                                            contract_value = int(value_str)
                                            
                                            # Validate: contract should be reasonable
                                            if 1_000_000 <= contract_value <= 1_000_000_000 and 1 <= years <= 15:
                                                contracts_found.append({
                                                    'years': years,
                                                    'value': contract_value,
                                                    'line_idx': i
                                                })
                                
                                # If multiple contracts found, take the largest one (usually the current contract)
                                if contracts_found:
                                    # Sort by value (descending) and take the largest
                                    contracts_found.sort(key=lambda x: x['value'], reverse=True)
                                    best_contract = contracts_found[0]
                                    
                                    data['contract_value'] = best_contract['value']
                                    data['contract_years'] = best_contract['years']
                                    
                                    # Try to extract additional info from the section
                                    line_idx = best_contract['line_idx']
                                    section_text = '\n'.join(lines[max(0, line_idx-2):min(len(lines), line_idx+10)])
                                    
                                    # Extract average salary if available
                                    avg_match = re.search(r'Average Salary:\s*\$([\d,]+)', section_text, re.I)
                                    if avg_match:
                                        data['avg_annual_value'] = int(avg_match.group(1).replace(',', ''))
                                    
                                    # Extract free agent year
                                    fa_match = re.search(r'Free Agent:\s*(\d{4})', section_text, re.I)
                                    if fa_match:
                                        data['free_agent_year'] = int(fa_match.group(1))
                                    
                                    logger.debug(f"Found contract from Contract Terms: {best_contract['years']} years / ${best_contract['value']:,}")
                            
                            # Method 2: Look for divs with contract-related classes that contain the summary format
                            if 'contract_value' not in data or not data['contract_value']:
                                contract_divs = soup.find_all('div', class_=re.compile(r'.*contract|.*summary|.*deal', re.I))
                                for div in contract_divs:
                                    text = div.get_text(strip=True)
                                    # Look for the "X yr(s) / $Y,YYY,YYY" pattern
                                    contract_match = re.search(r'(\d+)\s*yr\(s\)\s*/\s*\$([\d,]+)', text, re.I)
                                    if contract_match:
                                        years = int(contract_match.group(1))
                                        value_str = contract_match.group(2).replace(',', '')
                                        contract_value = int(value_str)
                                        
                                        # Prioritize if this div is marked as CURRENT
                                        is_current = 'CURRENT' in text.upper() or 'EXTENSION' in text.upper()
                                        
                                        if 1_000_000 <= contract_value <= 1_000_000_000 and 1 <= years <= 15:
                                            # If we already found a contract but this one is CURRENT, prefer this one
                                            if not data.get('contract_value') or is_current:
                                                data['contract_value'] = contract_value
                                                data['contract_years'] = years
                                                logger.debug(f"Found contract from div: {years} years / ${contract_value:,} (CURRENT: {is_current})")
                                                if is_current:
                                                    break
                            
                            # Method 3: Look for contract value in text near "Extension (CURRENT)" or "CURRENT" keywords
                            if 'contract_value' not in data or not data['contract_value']:
                                lines = page_text.split('\n')
                                for i, line in enumerate(lines):
                                    # Prioritize lines with "CURRENT" marker
                                    is_current_line = 'CURRENT' in line.upper() or ('EXTENSION' in line.upper() and 'CURRENT' in line.upper())
                                    
                                    if is_current_line and '$' in line:
                                        # Extract years and value from this line
                                        year_match = re.search(r'(\d+)\s*yr', line, re.I)
                                        money_matches = re.findall(r'\$([\d,]+)', line)
                                        if year_match and money_matches:
                                            # Take the largest dollar amount in this line
                                            values = [int(m.replace(',', '')) for m in money_matches]
                                            max_value = max(values)
                                            years = int(year_match.group(1))
                                            
                                            # Validate value
                                            if 1_000_000 <= max_value <= 1_000_000_000 and 1 <= years <= 15:
                                                data['contract_value'] = max_value
                                                data['contract_years'] = years
                                                logger.debug(f"Found contract from CURRENT line: {years} years / ${max_value:,}")
                                                break
                            
                            # Method 4: Look for the contract summary pattern in HTML (fallback)
                            if 'contract_value' not in data or not data['contract_value']:
                                contract_summary_pattern = r'(\d+)\s*yr\(s\)\s*/\s*\$([\d,]+)'
                                summary_match = re.search(contract_summary_pattern, page_html, re.I)
                                if summary_match:
                                    years = int(summary_match.group(1))
                                    value_str = summary_match.group(2).replace(',', '')
                                    contract_value = int(value_str)
                                    
                                    if 1_000_000 <= contract_value <= 1_000_000_000 and 1 <= years <= 15:
                                        data['contract_value'] = contract_value
                                        data['contract_years'] = years
                                        logger.debug(f"Found contract from HTML pattern: {years} years / ${contract_value:,}")
                            
                            # Method 5: Extract years if we have value but not years
                            if data.get('contract_value') and not data.get('contract_years'):
                                # Look for years near the contract value in the page
                                value_str = f"${data['contract_value']:,}"
                                lines = page_text.split('\n')
                                for i, line in enumerate(lines):
                                    if value_str.replace(',', '') in line.replace(',', ''):
                                        # Check this line and nearby lines for years
                                        for j in range(max(0, i-2), min(len(lines), i+3)):
                                            year_match = re.search(r'(\d+)\s*yr', lines[j], re.I)
                                            if year_match:
                                                years = int(year_match.group(1))
                                                if 1 <= years <= 15:
                                                    data['contract_years'] = years
                                                    break
                                        if 'contract_years' in data:
                                            break
                            
                            # Calculate average annual value if we have both value and years
                            if data.get('contract_value') and data.get('contract_years'):
                                if not data.get('avg_annual_value'):
                                    data['avg_annual_value'] = data['contract_value'] // data['contract_years']
                            
                            if data.get('contract_value'):
                                logger.info(f"✅ Found contract data from Spotrac: ${data.get('contract_value', 0):,.0f}")
                                return data
                    
                    except Exception as e:
                        logger.debug(f"Spotrac URL {url} failed: {e}")
                        continue
            
            # If standard format failed, try search
            logger.debug(f"Trying Spotrac search for {player_name}")
            search_url = f"https://www.spotrac.com/search/results/?q={quote(player_name)}"
            try:
                response = self.session.get(search_url, timeout=15)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # Look for player links
                    links = soup.find_all('a', href=re.compile(rf'/{sport}/.*/{player_slug}'))
                    if links:
                        player_url = links[0].get('href')
                        if not player_url.startswith('http'):
                            player_url = f"https://www.spotrac.com{player_url}"
                        # Recursively try this URL
                        return self._get_spotrac_data(player_name, team, sport)
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.warning(f"Spotrac scraping failed for {player_name}: {e}")
            return None
    
    def _get_overthecap_data(self, player_name: str, team: str) -> Optional[Dict]:
        """Scrape cap data from Over The Cap"""
        try:
            # Clean names
            name_parts = player_name.lower().replace('.', '').replace("'", '').split()
            player_slug = '-'.join(name_parts)
            team_slug = team.lower().replace(' ', '-')
            
            url = f"https://overthecap.com/player/{player_slug}/{team_slug}/"
            
            logger.debug(f"Trying Over The Cap: {url}")
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            data = {}
            
            # Current year cap hit
            cap_hit = soup.find('div', class_='cap-hit')
            if cap_hit:
                cap_text = cap_hit.get_text(strip=True)
                data['cap_hit_current'] = self._parse_money(cap_text)
            
            # Next year cap hit
            next_year_cap = soup.find('div', class_='next-year-cap')
            if next_year_cap:
                next_cap_text = next_year_cap.get_text(strip=True)
                data['cap_hit_next_year'] = self._parse_money(next_cap_text)
            
            return data if data else None
            
        except Exception as e:
            logger.debug(f"Over The Cap scraping failed: {e}")
            return None
    
    def _parse_money(self, text: str) -> Optional[int]:
        """Parse money string to integer (e.g., '$50M' -> 50000000)"""
        try:
            # Remove everything except numbers, M, K, B
            text = text.upper().strip()
            
            # Extract number and multiplier
            match = re.search(r'[\$]?\s*([\d,.]+)\s*([MKB])?', text)
            if not match:
                return None
            
            number = float(match.group(1).replace(',', ''))
            multiplier = match.group(2)
            
            if multiplier == 'M':
                return int(number * 1_000_000)
            elif multiplier == 'K':
                return int(number * 1_000)
            elif multiplier == 'B':
                return int(number * 1_000_000_000)
            else:
                return int(number)
        
        except Exception as e:
            logger.debug(f"Money parsing failed for '{text}': {e}")
            return None
    
    def get_agent_and_management(self, player_name: str, team: str, sport: str = 'nfl') -> Dict:
        """
        Get player's agent and management company from Spotrac
        
        Returns:
            Dict with 'agent' and 'management_company'
        """
        logger.info(f"🤝 Collecting agent/management for {player_name}...")
        
        result = {
            'agent': None,
            'management_company': None
        }
        
        try:
            # Build Spotrac URL
            name_variant = player_name.lower().replace('.', '').replace("'", '').replace('-', ' ')
            name_parts = name_variant.split()
            player_slug = '-'.join(name_parts)
            team_slug = team.lower().replace(' ', '-').replace('.', '').replace("'", '')
            
            url = f"https://www.spotrac.com/{sport}/{team_slug}/{player_slug}/"
            
            response = self.session.get(url, timeout=15, allow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                page_text = soup.get_text()
                
                # Look for "Agent:" or "Representation:" on Spotrac pages
                # Format: "Agent: Name" or "Representative: Name"
                agent_patterns = [
                    r'Agent:\s*([A-Za-z\s\-\.]+)(?:\n|$|\s{2,})',
                    r'Representation:\s*([A-Za-z\s\-\.]+)(?:\n|$|\s{2,})',
                    r'Represented by:\s*([A-Za-z\s\-\.]+)(?:\n|$|\s{2,})',
                ]
                
                for pattern in agent_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        agent_name = match.group(1).strip()
                        # Clean up the name
                        agent_name = re.sub(r'\s+', ' ', agent_name)
                        if len(agent_name) > 3 and len(agent_name) < 50:  # Reasonable name length
                            result['agent'] = agent_name
                            logger.info(f"   ✅ Found agent: {agent_name}")
                            break
                
                # Look for management company (often listed with agent or in bio)
                mgmt_patterns = [
                    r'(?:Agency|Management):\s*([A-Za-z\s\-\.&]+)(?:\n|$|\s{2,})',
                    r'([A-Z][A-Za-z\s&]+(?:Sports|Management|Agency|Group))(?:\n|$|\s{2,})',
                ]
                
                for pattern in mgmt_patterns:
                    match = re.search(pattern, page_text)
                    if match:
                        mgmt_name = match.group(1).strip()
                        mgmt_name = re.sub(r'\s+', ' ', mgmt_name)
                        if len(mgmt_name) > 5 and len(mgmt_name) < 60:
                            result['management_company'] = mgmt_name
                            logger.info(f"   ✅ Found management: {mgmt_name}")
                            break
                
        except Exception as e:
            logger.warning(f"Agent/management collection failed: {e}")
        
        # Fallback: Try Google search for agent
        if not result['agent']:
            try:
                search_url = f"https://www.google.com/search?q={quote(player_name + ' agent ' + sport)}"
                response = self.session.get(search_url, timeout=10)
                if response.status_code == 200:
                    # Look for common patterns in search results
                    text = response.text
                    # Pattern: "represented by [Agent Name]"
                    agent_match = re.search(r'represented by ([A-Z][a-z]+ [A-Z][a-z]+)', text)
                    if agent_match:
                        result['agent'] = agent_match.group(1)
                        logger.info(f"   ✅ Found agent from Google: {result['agent']}")
            except:
                pass
        
        if not result['agent']:
            logger.info(f"   ⚠️  No agent found for {player_name}")
        
        return result
    
    def get_career_earnings(self, player_name: str, team: str, sport: str = 'nfl') -> Optional[int]:
        """
        Calculate career earnings from Spotrac cash earnings page
        
        Returns:
            Total career cash earned (int) or None
        """
        logger.info(f"💵 Collecting career earnings for {player_name}...")
        
        try:
            # Build Spotrac cash earnings URL
            name_variant = player_name.lower().replace('.', '').replace("'", '').replace('-', ' ')
            name_parts = name_variant.split()
            player_slug = '-'.join(name_parts)
            team_slug = team.lower().replace(' ', '-').replace('.', '').replace("'", '')
            
            # Try cash-earnings specific page first
            url = f"https://www.spotrac.com/{sport}/{team_slug}/{player_slug}/cash-earnings/"
            
            response = self.session.get(url, timeout=15, allow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                page_text = soup.get_text()
                
                # Look for "Career Cash Earned:" or similar patterns
                career_patterns = [
                    r'Career\s+(?:Cash\s+)?Earned?:\s*\$\s*([\d,]+)',
                    r'Total\s+(?:Career\s+)?Earnings?:\s*\$\s*([\d,]+)',
                    r'Career\s+Total:\s*\$\s*([\d,]+)',
                ]
                
                for pattern in career_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        career_earnings_str = match.group(1).replace(',', '')
                        career_earnings = int(career_earnings_str)
                        if career_earnings > 0:
                            logger.info(f"   ✅ Career earnings: ${career_earnings:,}")
                            return career_earnings
                
                # Alternative: Sum up all yearly earnings from the table
                # Look for table rows with year and dollar amount
                earnings_rows = soup.find_all('tr')
                total_earnings = 0
                for row in earnings_rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # Check if first cell is a year
                        year_text = cells[0].get_text().strip()
                        if re.match(r'^\d{4}$', year_text):
                            # Look for dollar amount in subsequent cells
                            for cell in cells[1:]:
                                money_text = cell.get_text().strip()
                                money_match = re.search(r'\$\s*([\d,]+)', money_text)
                                if money_match:
                                    amount = int(money_match.group(1).replace(',', ''))
                                    total_earnings += amount
                                    break
                
                if total_earnings > 0:
                    logger.info(f"   ✅ Career earnings (calculated): ${total_earnings:,}")
                    return total_earnings
            
            logger.info(f"   ⚠️  No career earnings found for {player_name}")
            return None
            
        except Exception as e:
            logger.warning(f"Career earnings collection failed: {e}")
            return None


# Standalone usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    collector = ContractCollector()
    
    # Test with Patrick Mahomes
    contract = collector.collect_contract_data("Patrick Mahomes", "Kansas City Chiefs", "nfl")
    print(f"\nContract Data: {contract}")

