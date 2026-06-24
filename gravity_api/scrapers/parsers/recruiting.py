"""247Sports recruiting profile parsing."""

from __future__ import annotations

import re
from typing import Any

_STAR_COUNT_PAT = re.compile(r"(\d)\s*[- ]?star", re.I)
_STAR_GLYPH_PAT = re.compile(r"[★⭐]{1,5}")
_COMPOSITE_PAT = re.compile(r"composite[^\d.]*([\d.]+)", re.I)
_PLAYER_ID_PAT = re.compile(r"247sports\.com/player/[^/\s]+-(\d+)", re.I)
_NATIONAL_RANK_PAT = re.compile(
    r"(?:national|overall)\s*(?:rank|ranking)?[^\d#]*#?\s*(\d{1,4})",
    re.I,
)
_POSITION_RANK_PAT = re.compile(
    r"(?:position|pos\.?)\s*(?:rank|ranking)?[^\d#]*#?\s*(\d{1,4})",
    re.I,
)
_STATE_RANK_PAT = re.compile(
    r"state\s*(?:rank|ranking)?[^\d#]*#?\s*(\d{1,4})",
    re.I,
)


def _to_int(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val.replace(",", "")))
    except (TypeError, ValueError):
        return None


def parse_247_recruiting_profile(text: str) -> dict[str, Any]:
    """Extract structured recruiting fields from 247Sports page or search snippet."""
    out: dict[str, Any] = {}

    m = _PLAYER_ID_PAT.search(text)
    if m:
        out["external_id_247"] = m.group(1)

    stars = None
    m = _STAR_COUNT_PAT.search(text)
    if m:
        stars = _to_int(m.group(1))
    else:
        glyphs = _STAR_GLYPH_PAT.search(text)
        if glyphs:
            stars = len(glyphs.group(0))
    if stars is not None and 1 <= stars <= 5:
        out["recruiting_stars"] = float(stars)

    m = _NATIONAL_RANK_PAT.search(text)
    if m:
        out["recruiting_rank_national"] = float(_to_int(m.group(1)) or 0)

    m = _POSITION_RANK_PAT.search(text)
    if m:
        out["recruiting_rank_position"] = float(_to_int(m.group(1)) or 0)

    m = _STATE_RANK_PAT.search(text)
    if m:
        out["recruiting_state_rank"] = float(_to_int(m.group(1)) or 0)

    m = _COMPOSITE_PAT.search(text)
    if m:
        try:
            out["recruiting_composite"] = float(m.group(1))
        except ValueError:
            pass

    return out


__all__ = ["parse_247_recruiting_profile"]
