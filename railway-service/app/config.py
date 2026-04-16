"""
Configuration management for Gravity Scrapers API
Loads environment variables and provides settings
"""

from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration
    API_KEY: str
    PORT: int = 8000
    CORS_ORIGINS: str = '["https://your-app.lovable.app","http://localhost:5173"]'
    
    # Supabase (optional — leave empty if this deploy has no database)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    
    # External APIs
    PERPLEXITY_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""
    
    # Reddit API
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def supabase_enabled(self) -> bool:
        """True when both URL and service key are set (non-whitespace)."""
        return bool(self.SUPABASE_URL.strip() and self.SUPABASE_SERVICE_KEY.strip())

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS from JSON string to list"""
        try:
            return json.loads(self.CORS_ORIGINS)
        except:
            return ["https://your-app.lovable.app", "http://localhost:5173"]


# Global settings instance
settings = Settings()
