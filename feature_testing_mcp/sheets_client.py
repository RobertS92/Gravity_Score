"""Google Sheets client for reading/writing feature test data"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

try:
    import gspread
    from google.oauth2.service_account import Credentials
    from google.auth.exceptions import GoogleAuthError
except ImportError:
    gspread = None
    Credentials = None
    GoogleAuthError = Exception

from .config import FeatureTestingConfig
from .exceptions import SheetsError, ConfigurationError

logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """Google Sheets client for reading/writing feature data"""
    
    # Column structure for the Features sheet
    COLUMNS = {
        'feature_name': 0,      # Column A
        'description': 1,        # Column B
        'test_function': 2,      # Column C (optional - function name to call)
        'status': 3,             # Column D (PASS/FAIL/PENDING)
        'last_tested': 4,        # Column E (timestamp)
        'notes': 5,              # Column F (error messages, details)
        'test_result': 6         # Column G (detailed JSON result)
    }
    
    def __init__(self, config: FeatureTestingConfig):
        """Initialize Google Sheets client"""
        if not gspread:
            raise ImportError(
                "gspread not installed. Run: pip install gspread google-auth google-auth-oauthlib"
            )
        
        self.config = config
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self._connected = False
    
    def connect(self) -> Tuple[bool, str]:
        """
        Connect to Google Sheets.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate configuration
            if not self.config.GOOGLE_SHEET_ID:
                return False, "GOOGLE_SHEET_ID not configured"
            
            # Define required scopes
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Authenticate with service account
            creds = Credentials.from_service_account_file(
                self.config.GOOGLE_CREDENTIALS_PATH,
                scopes=scope
            )
            
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.config.GOOGLE_SHEET_ID)
            
            # Get or create worksheet
            try:
                self.worksheet = self.spreadsheet.worksheet(self.config.GOOGLE_WORKSHEET_NAME)
                logger.info(f"Connected to existing worksheet: {self.config.GOOGLE_WORKSHEET_NAME}")
            except gspread.exceptions.WorksheetNotFound:
                logger.info(f"Worksheet '{self.config.GOOGLE_WORKSHEET_NAME}' not found, creating...")
                self.worksheet = self.spreadsheet.add_worksheet(
                    title=self.config.GOOGLE_WORKSHEET_NAME,
                    rows=1000,
                    cols=10
                )
                # Add header row
                headers = [
                    'Feature Name', 'Description', 'Test Function', 
                    'Status', 'Last Tested', 'Notes', 'Test Result'
                ]
                self.worksheet.append_row(headers)
                logger.info(f"Created worksheet with headers: {self.config.GOOGLE_WORKSHEET_NAME}")
            
            self._connected = True
            return True, "Connected successfully"
            
        except FileNotFoundError:
            error_msg = f"Credentials file not found: {self.config.GOOGLE_CREDENTIALS_PATH}"
            logger.error(error_msg)
            return False, error_msg
        except GoogleAuthError as e:
            error_msg = f"Authentication failed: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Connection failed: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def ensure_connected(self):
        """Ensure client is connected, raise error if not"""
        if not self._connected or not self.worksheet:
            raise SheetsError("Not connected to Google Sheets. Call connect() first.")
    
    def read_features(self) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Read all features from the sheet.
        
        Returns:
            Tuple of (features: List[Dict], error: Optional[str])
        """
        try:
            self.ensure_connected()
            
            # Get all values (skip header row)
            all_values = self.worksheet.get_all_values()
            
            if len(all_values) <= 1:
                logger.info("No features found in sheet")
                return [], None
            
            features = []
            for i, row in enumerate(all_values[1:], start=2):  # Skip header, start at row 2
                if not row or not row[0].strip():  # Skip empty rows
                    continue
                
                feature = {
                    'row_number': i,
                    'feature_name': row[self.COLUMNS['feature_name']].strip() if len(row) > self.COLUMNS['feature_name'] else '',
                    'description': row[self.COLUMNS['description']].strip() if len(row) > self.COLUMNS['description'] else '',
                    'test_function': row[self.COLUMNS['test_function']].strip() if len(row) > self.COLUMNS['test_function'] else '',
                    'current_status': row[self.COLUMNS['status']].strip() if len(row) > self.COLUMNS['status'] else 'PENDING',
                    'last_tested': row[self.COLUMNS['last_tested']].strip() if len(row) > self.COLUMNS['last_tested'] else '',
                    'notes': row[self.COLUMNS['notes']].strip() if len(row) > self.COLUMNS['notes'] else '',
                }
                features.append(feature)
            
            logger.info(f"Read {len(features)} features from sheet")
            return features, None
            
        except Exception as e:
            error_msg = f"Error reading features: {e}"
            logger.error(error_msg)
            return [], error_msg
    
    def update_feature_result(
        self, 
        row_number: int, 
        status: str, 
        notes: str = "", 
        test_result: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Update a feature's test result in the sheet.
        
        Args:
            row_number: Row number to update (1-indexed, including header)
            status: Status to set (PASS/FAIL/PENDING)
            notes: Notes about the test result
            test_result: Optional dict with detailed test results
        
        Returns:
            Tuple of (success: bool, error: Optional[str])
        """
        try:
            self.ensure_connected()
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Prepare updates (using 1-indexed column numbers for gspread)
            updates = [
                {
                    'range': f'{self._col_letter(self.COLUMNS["status"])}{row_number}',
                    'values': [[status]]
                },
                {
                    'range': f'{self._col_letter(self.COLUMNS["last_tested"])}{row_number}',
                    'values': [[timestamp]]
                },
                {
                    'range': f'{self._col_letter(self.COLUMNS["notes"])}{row_number}',
                    'values': [[notes[:500]]]  # Truncate notes to 500 chars
                }
            ]
            
            if test_result:
                result_json = json.dumps(test_result, indent=2)
                updates.append({
                    'range': f'{self._col_letter(self.COLUMNS["test_result"])}{row_number}',
                    'values': [[result_json]]
                })
            
            # Batch update for efficiency
            self.worksheet.batch_update(updates)
            
            logger.info(f"Updated row {row_number} with status: {status}")
            return True, None
            
        except Exception as e:
            error_msg = f"Error updating row {row_number}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def find_feature_by_name(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a feature by name.
        
        Args:
            feature_name: Name of feature to find
        
        Returns:
            Feature dict if found, None otherwise
        """
        features, error = self.read_features()
        if error:
            return None
        
        for feature in features:
            if feature['feature_name'].lower() == feature_name.lower():
                return feature
        
        return None
    
    @staticmethod
    def _col_letter(col_index: int) -> str:
        """Convert 0-indexed column to Excel column letter (A, B, C, ...)"""
        result = ""
        col_index += 1  # Convert to 1-indexed
        while col_index > 0:
            col_index -= 1
            result = chr(col_index % 26 + ord('A')) + result
            col_index //= 26
        return result

