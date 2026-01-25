"""
Source Reliability Configuration
Tiered reliability weights for all data sources
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)


# Source reliability weights (0-1 scale)
# Higher weight = more reliable source
SOURCE_WEIGHTS: Dict[str, float] = {
    # Tier 1: Primary NIL platforms (0.90-0.98)
    'on3': 0.95,
    'opendorse': 0.90,
    'direct_api': 0.98,  # Direct API integrations
    
    # Tier 2: Social analytics and team platforms (0.80-0.89)
    'inflcr': 0.85,
    'teamworks': 0.80,
    
    # Tier 3: Recruiting/sports journalism (0.70-0.79)
    '247sports': 0.75,
    'rivals': 0.75,
    'espn': 0.95,  # ESPN for stats, not NIL
    
    # Tier 4: News sources (0.60-0.69)
    'news': 0.60,
    'press_release': 0.65,
    
    # Tier 5: Social media (0.40-0.59)
    'social': 0.50,
    'twitter': 0.45,
    'instagram': 0.45,
    'tiktok': 0.40,
    
    # Tier 6: User-generated (0.20-0.39)
    'wikipedia': 0.70,  # Actually quite reliable for basic facts
    'user_submitted': 0.25,
    'unverified': 0.20
}


# Source tiers for categorization
SOURCE_TIERS: Dict[str, int] = {
    'on3': 1,
    'opendorse': 1,
    'direct_api': 1,
    'espn': 1,
    'inflcr': 2,
    'teamworks': 2,
    '247sports': 3,
    'rivals': 3,
    'wikipedia': 3,
    'news': 4,
    'press_release': 4,
    'social': 5,
    'twitter': 5,
    'instagram': 5,
    'tiktok': 5,
    'user_submitted': 6,
    'unverified': 6
}


def get_source_reliability(source: str) -> float:
    """
    Get reliability weight for a source
    
    Args:
        source: Source name
    
    Returns:
        Reliability weight (0-1)
    """
    source_lower = source.lower().strip()
    return SOURCE_WEIGHTS.get(source_lower, 0.5)  # Default to 0.5


def get_source_tier(source: str) -> int:
    """
    Get tier for a source (1-6, lower is better)
    
    Args:
        source: Source name
    
    Returns:
        Tier number
    """
    source_lower = source.lower().strip()
    return SOURCE_TIERS.get(source_lower, 6)  # Default to tier 6


def get_tier_description(tier: int) -> str:
    """Get human-readable description of source tier"""
    descriptions = {
        1: "Primary NIL platforms - Highest reliability",
        2: "Social analytics and team platforms - High reliability",
        3: "Recruiting/sports journalism - Moderate-high reliability",
        4: "News sources - Moderate reliability",
        5: "Social media - Lower reliability",
        6: "User-generated - Lowest reliability"
    }
    return descriptions.get(tier, "Unknown tier")
