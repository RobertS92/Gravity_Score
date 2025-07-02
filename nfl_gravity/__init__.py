"""
NFL Gravity - Modular Content Pipeline for NFL Data Analysis.

A production-ready Python package for scraping, enriching, and analyzing NFL data
with LLM-powered intelligence and modular architecture.
"""

__version__ = "1.0.0"
__author__ = "NFL Gravity Team"
__email__ = "contact@nflgravity.com"

from .mcp import MCP
from .core.config import Config
from .core.exceptions import NFLGravityError

__all__ = ["MCP", "Config", "NFLGravityError"]
