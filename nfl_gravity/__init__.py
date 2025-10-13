"""
NFL Gravity - Modular Content Pipeline for NFL Data Analysis.

A production-ready Python package for scraping, enriching, and analyzing NFL data
with LLM-powered intelligence and modular architecture.
"""

__version__ = "1.0.0"
__author__ = "NFL Gravity Team"
__email__ = "contact@nflgravity.com"

from importlib import import_module
from typing import Any

__all__ = ["MCP", "Config", "NFLGravityError"]


def __getattr__(name: str) -> Any:  # pragma: no cover - module level proxy
    if name == "MCP":
        module = import_module(".mcp", __name__)
        return module.MCP
    if name == "Config":
        module = import_module(".core.config", __name__)
        return module.Config
    if name == "NFLGravityError":
        module = import_module(".core.exceptions", __name__)
        return module.NFLGravityError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
