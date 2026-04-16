"""
NIL package — data collection lives in the external scrapers repository.

Stubs keep legacy imports (e.g. Railway ``ConnectorOrchestrator``) importable.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def run_nil_collection(
    athlete_name: str,
    school: str = "",
    sport: str = "cfb",
) -> Dict[str, Any]:
    """Legacy entrypoint. NIL multi-connector pipeline was removed."""
    logger.warning(
        "run_nil_collection is stubbed; use external scrapers repo (%s)",
        athlete_name,
    )
    return {
        "status": "deprecated",
        "message": "College/NIL collection runs from the external scrapers repository.",
        "athlete_name": athlete_name,
        "school": school,
        "sport": sport,
    }


def calculate_and_store_features(
    athlete_id: Any,
    season_id: str,
    as_of_date: Optional[Any] = None,
) -> Any:
    """Legacy feature snapshot writer — removed with nil.feature_calculator."""
    logger.warning(
        "calculate_and_store_features stubbed for athlete_id=%s season=%s",
        athlete_id,
        season_id,
    )
    return None


class ConnectorOrchestrator:
    """Thin stub for railway-service / scripts that still instantiate this."""

    def collect_all(self, canonical_name: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return run_nil_collection(
            canonical_name,
            kwargs.get("school", "") or "",
            kwargs.get("sport", "cfb") or "cfb",
        )


# Placeholder types for any remaining `from gravity.nil.connectors import X` (should not occur)
On3Connector = None  # type: ignore
OpendorseConnector = None  # type: ignore
INFLCRConnector = None  # type: ignore
TeamworksConnector = None  # type: ignore
Sports247Connector = None  # type: ignore
RivalsConnector = None  # type: ignore

__all__ = [
    "ConnectorOrchestrator",
    "run_nil_collection",
    "calculate_and_store_features",
    "On3Connector",
    "OpendorseConnector",
    "INFLCRConnector",
    "TeamworksConnector",
    "Sports247Connector",
    "RivalsConnector",
]
