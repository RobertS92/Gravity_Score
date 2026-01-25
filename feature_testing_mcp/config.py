"""Configuration for Google Sheets Feature Testing MCP Server"""

import os
from typing import Optional


class FeatureTestingConfig:
    """Configuration for Google Sheets Feature Testing MCP Server"""
    
    # Google Sheets credentials
    GOOGLE_CREDENTIALS_PATH: str = os.getenv(
        "GOOGLE_CREDENTIALS_PATH", 
        "credentials.json"
    )
    
    # Google Sheet ID (from URL)
    GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
    
    # Worksheet name for features
    GOOGLE_WORKSHEET_NAME: str = os.getenv("GOOGLE_WORKSHEET_NAME", "Features")
    
    # Project root for running tests
    PROJECT_ROOT: str = os.getenv("PROJECT_ROOT", "/Users/robcseals/Gravity_Score")
    
    # Server configuration
    FASTMCP_HOST: str = os.getenv("FASTMCP_HOST", "0.0.0.0")
    FASTMCP_PORT: int = int(os.getenv("FASTMCP_PORT", "8018"))
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        if not cls.GOOGLE_SHEET_ID:
            raise ValueError("GOOGLE_SHEET_ID environment variable is required")
        if not os.path.exists(cls.GOOGLE_CREDENTIALS_PATH):
            raise ValueError(f"Google credentials file not found: {cls.GOOGLE_CREDENTIALS_PATH}")
        return True

