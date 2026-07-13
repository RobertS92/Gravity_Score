"""Brand-heritage / family-name equity detection for CSC Brand Strength.

Uses a curated surname registry (not open-ended NLP) so only high-confidence
dynasty brands — Manning, Griffey, etc. — influence Interpretation copy.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_CANDIDATES = (
    _REPO_ROOT / "config" / "brand_heritage_surnames.json",
    Path(__file__).resolve().parents[1] / "docker-bundle" / "config" / "brand_heritage_surnames.json",
)


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    for path in _CONFIG_CANDIDATES:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            surnames = raw.get("surnames") if isinstance(raw, dict) else None
            if isinstance(surnames, dict) and surnames:
                return {str(k).lower(): v for k, v in surnames.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load brand heritage registry from %s: %s", path, exc)
    return {}


def _split_name(name: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    if not cleaned:
        return "", ""
    parts = cleaned.split(" ")
    if len(parts) == 1:
        return "", parts[0].lower()
    return parts[0].lower(), parts[-1].lower()


def detect_brand_heritage(
    athlete_name: Optional[str],
    *,
    sport: Optional[str] = None,
) -> Optional[dict[str, str]]:
    """Return heritage metadata when the athlete surname matches the registry.

    Returns keys: label, prose_fragment, insight, tier — or None.
    """
    if not athlete_name:
        return None
    first, surname = _split_name(athlete_name)
    if not surname:
        return None
    entry = _load_registry().get(surname)
    if not entry:
        return None

    sports = entry.get("sports")
    if sports and sport:
        sport_u = str(sport).strip().upper()
        allowed = {str(s).strip().upper() for s in sports}
        # Soft filter: if sport is known and not in the list, still allow
        # iconic/elite tiers (Manning in CFB is the primary case). Skip only
        # when the entry is lower-tier and sport is clearly mismatched.
        tier = str(entry.get("tier") or "notable").lower()
        if sport_u and allowed and sport_u not in allowed and tier not in {"iconic", "elite"}:
            return None

    required_first = entry.get("require_exact_first_names")
    if required_first:
        allowed_first = {str(x).strip().lower() for x in required_first}
        if first not in allowed_first:
            return None

    prose = str(entry.get("prose_fragment") or "").strip()
    insight = str(entry.get("insight") or "").strip()
    label = str(entry.get("label") or f"{surname.title()} family legacy").strip()
    if not prose:
        return None
    return {
        "label": label,
        "prose_fragment": prose,
        "insight": insight
        or "family-name recognition amplifies commercial pull beyond measured social reach",
        "tier": str(entry.get("tier") or "notable"),
    }


def clear_brand_heritage_cache() -> None:
    """Test helper — reset the loaded registry cache."""
    _load_registry.cache_clear()
