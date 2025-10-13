"""Lightweight web scrapers for the Gravity Score pipeline."""

from .wikipedia import fetch_wikipedia_profile
from .pfr import fetch_pfr_career
from .spotrac import fetch_spotrac_earnings
from .social import (
    fetch_twitter_profile,
    fetch_instagram_profile,
    fetch_tiktok_profile,
    fetch_youtube_channel,
)
from .news import fetch_news_metrics

__all__ = [
    "fetch_wikipedia_profile",
    "fetch_pfr_career",
    "fetch_spotrac_earnings",
    "fetch_twitter_profile",
    "fetch_instagram_profile",
    "fetch_tiktok_profile",
    "fetch_youtube_channel",
    "fetch_news_metrics",
]
