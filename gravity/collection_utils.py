"""
Collection Utilities - Retry logic, caching, and helper functions
for improved news and social media collection
"""

import time
import logging
import functools
from typing import Callable, Any, Optional
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import re

logger = logging.getLogger(__name__)


# ============================================================================
# RETRY LOGIC WITH EXPONENTIAL BACKOFF
# ============================================================================

def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0, 
                       backoff_factor: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Decorator for retrying functions with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.warning(f"{func.__name__} failed after {max_retries} attempts: {e}")
            
            # Return None or empty result on final failure
            return None
            
        return wrapper
    return decorator


# ============================================================================
# SIMPLE CACHE FOR SOCIAL MEDIA LOOKUPS
# ============================================================================

class SimpleCache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, default_ttl: int = 3600):  # 1 hour default
        self.cache = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self.cache:
            value, expiry = self.cache[key]
            if datetime.now() < expiry:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with TTL"""
        ttl = ttl or self.default_ttl
        expiry = datetime.now() + timedelta(seconds=ttl)
        self.cache[key] = (value, expiry)
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()


# Global cache instance
_social_cache = SimpleCache(default_ttl=86400)  # 24 hours for social media


def cached_social_lookup(cache_key_func: Callable = None, ttl: int = 86400):
    """
    Decorator to cache social media lookup results
    
    Args:
        cache_key_func: Function to generate cache key from args/kwargs
        ttl: Time to live in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(*args, **kwargs)
            else:
                # Default: use function name + first arg
                cache_key = f"{func.__name__}_{args[0] if args else 'default'}"
            
            # Check cache
            cached = _social_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached
            
            # Call function
            result = func(*args, **kwargs)
            
            # Cache result if not None
            if result is not None:
                _social_cache.set(cache_key, result, ttl)
            
            return result
            
        return wrapper
    return decorator


# ============================================================================
# IMPROVED DATE PARSING
# ============================================================================

def parse_news_date(date_str: str) -> Optional[datetime]:
    """
    Parse news article date with multiple fallback strategies
    
    Handles:
    - RFC 2822 format (Google News RSS)
    - ISO 8601 format
    - Relative dates ("2 hours ago", "3 days ago")
    - Various date formats
    """
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip()
    
    # Try dateutil parser first (handles most formats)
    try:
        return date_parser.parse(date_str, fuzzy=True, default=datetime.now())
    except:
        pass
    
    # Try RFC 2822 format (common in RSS feeds)
    try:
        # Remove timezone if present for simpler parsing
        date_str_clean = re.sub(r'\s+[A-Z]{3,5}$', '', date_str)
        return datetime.strptime(date_str_clean, '%a, %d %b %Y %H:%M:%S')
    except:
        pass
    
    # Try relative dates
    date_str_lower = date_str.lower()
    now = datetime.now()
    
    # Hours ago
    hour_match = re.search(r'(\d+)\s*hour', date_str_lower)
    if hour_match:
        return now - timedelta(hours=int(hour_match.group(1)))
    
    # Days ago
    day_match = re.search(r'(\d+)\s*day', date_str_lower)
    if day_match:
        return now - timedelta(days=int(day_match.group(1)))
    
    # Weeks ago
    week_match = re.search(r'(\d+)\s*week', date_str_lower)
    if week_match:
        return now - timedelta(weeks=int(week_match.group(1)))
    
    # Months ago
    month_match = re.search(r'(\d+)\s*month', date_str_lower)
    if month_match:
        return now - timedelta(days=int(month_match.group(1)) * 30)
    
    # Today/yesterday
    if 'today' in date_str_lower or 'just now' in date_str_lower:
        return now
    if 'yesterday' in date_str_lower:
        return now - timedelta(days=1)
    
    # Try common date formats
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%B %d, %Y',
        '%b %d, %Y',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    
    logger.debug(f"Could not parse date: {date_str}")
    return None


def categorize_article_date(article_date: datetime, now: datetime = None) -> dict:
    """
    Categorize article by recency
    
    Returns:
        dict with 'is_7d', 'is_30d', 'is_365d', 'is_1095d', 'age_days'
    """
    if now is None:
        now = datetime.now()
    
    age_days = (now - article_date).days if article_date else None
    
    return {
        'is_7d': age_days is not None and age_days <= 7,
        'is_30d': age_days is not None and age_days <= 30,
        'is_365d': age_days is not None and age_days <= 365,
        'is_1095d': age_days is not None and age_days <= 1095,  # 3 years
        'age_days': age_days
    }

