"""
Configuration management for Gravity Scrapers API
Loads environment variables and provides settings
"""

import logging

from pydantic_settings import BaseSettings
from typing import List
import json

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration. API_KEY defaults to empty so the app boots (and /health answers) even when
    # the operator has not set a key yet. `API_KEY` is still enforced on protected routes.
    API_KEY: str = ""
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
        # Extra vars from shared Railway Variables (PG_DSN, JWT_SECRET, …) must not crash the service.
        extra = "ignore"
    
    @property
    def supabase_enabled(self) -> bool:
        """True when both URL and service key are set (non-whitespace)."""
        return bool(self.SUPABASE_URL.strip() and self.SUPABASE_SERVICE_KEY.strip())

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS (JSON array or comma-separated) to a clean list."""
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return ["http://localhost:5173"]
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
        except Exception:
            pass
        return [part.strip() for part in raw.split(",") if part.strip()]


try:
    settings = Settings()
except Exception as exc:
    logger.exception(
        "Failed to load Settings from environment (%s). Falling back to defaults so /health stays reachable.",
        exc,
    )
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
