"""
Supabase Client Singleton
Provides a single reusable Supabase client instance
"""

from supabase import create_client, Client
from app.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global singleton instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Get or create the Supabase client singleton.

    Returns None when SUPABASE_URL / SUPABASE_SERVICE_KEY are unset (empty).
    """
    global _supabase_client

    if not settings.supabase_enabled:
        return None

    if _supabase_client is None:
        logger.info("Initializing Supabase client for %s", settings.SUPABASE_URL)
        _supabase_client = create_client(
            settings.SUPABASE_URL.strip(),
            settings.SUPABASE_SERVICE_KEY.strip(),
        )
        logger.info("Supabase client initialized successfully")

    return _supabase_client


def reset_supabase_client():
    """Reset the client (useful for testing)"""
    global _supabase_client
    _supabase_client = None
