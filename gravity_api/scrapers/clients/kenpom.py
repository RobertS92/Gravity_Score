"""KenPom licensed API client for men's college basketball."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)

KENPOM_BASE = "https://kenpom.com"


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _map_kenpom_player_row(row: dict[str, Any]) -> dict[str, float]:
    """Map KenPom player row to canonical basketball stat keys."""
    out: dict[str, float] = {}
    mapping = {
        "kenpom_rating": row.get("ORtg") or row.get("ortg") or row.get("oRtg"),
        "bpm": row.get("BPM") or row.get("bpm"),
        "usage_rate": row.get("Usg") or row.get("usage") or row.get("usg"),
        "pts": row.get("Pts") or row.get("pts"),
        "reb": row.get("OR") or row.get("DR") or row.get("reb"),
        "ast": row.get("Ast") or row.get("ast"),
        "stl": row.get("Stl") or row.get("stl"),
        "blk": row.get("Blk") or row.get("blk"),
        "fg_pct": row.get("FGPct") or row.get("fg_pct"),
        "three_pct": row.get("3PPct") or row.get("three_pct"),
        "ft_pct": row.get("FTPct") or row.get("ft_pct"),
        "games_played_season": row.get("G") or row.get("games"),
    }
    for key, raw in mapping.items():
        val = _to_float(raw)
        if val is not None:
            out[key] = val
    return out


def parse_kenpom_markdown(md: str) -> dict[str, float]:
    """Best-effort parse when API key is unavailable."""
    out: dict[str, float] = {}
    patterns = {
        "kenpom_rating": r"(?:ORtg|Off(?:ensive)?\s*Rating)[^\d]*([\d.]+)",
        "bpm": r"BPM[^\d-]*(-?[\d.]+)",
        "usage_rate": r"(?:Usg|Usage)[^\d]*([\d.]+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, md, re.I)
        if m:
            val = _to_float(m.group(1))
            if val is not None:
                out[key] = val
    return out


class KenPomClient:
    def __init__(self, *, api_key: str | None = None, timeout_s: float = 30.0):
        settings = get_settings()
        self.api_key = (api_key or getattr(settings, "kenpom_api_key", None) or "").strip()
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.enabled:
            return None
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{KENPOM_BASE}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout_s, headers=headers) as client:
            resp = await client.get(url, params=params or {})
            if resp.status_code in (401, 403, 404):
                logger.debug("KenPom %s -> %s", path, resp.status_code)
                return None
            resp.raise_for_status()
            return resp.json()

    async def player_stats(self, *, season: int, name: str) -> dict[str, float]:
        data = await self._get(
            "api/v1/player/stats",
            {"season": season, "name": name},
        )
        if isinstance(data, list):
            name_lower = name.lower()
            for row in data:
                if not isinstance(row, dict):
                    continue
                row_name = str(row.get("Player") or row.get("player") or row.get("name") or "")
                if name_lower in row_name.lower():
                    return _map_kenpom_player_row(row)
            if data and isinstance(data[0], dict):
                return _map_kenpom_player_row(data[0])
        if isinstance(data, dict):
            return _map_kenpom_player_row(data)
        return {}


__all__ = ["KenPomClient", "parse_kenpom_markdown", "_map_kenpom_player_row"]
