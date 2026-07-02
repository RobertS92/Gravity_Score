"""Scoring imputations: manual overrides + deterministic heuristics."""

from __future__ import annotations

from typing import Any, Dict, Optional

import asyncpg

from gravity_api.scraper_registry.field_sufficiency import PLACEHOLDER_NUMBERS


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _position_multiplier(position: Optional[str]) -> float:
    if not position:
        return 1.0
    p = position.upper()
    if p in {"QB", "PG", "SG"}:
        return 1.4
    if p in {"WR", "RB", "SF", "PF"}:
        return 1.15
    if p in {"TE", "C"}:
        return 1.05
    if p in {"DL", "OL", "LB", "DB", "K"}:
        return 0.85
    return 1.0


def _sport_base_followers(sport: Optional[str]) -> float:
    if not sport:
        return 8000.0
    s = sport.lower()
    if s == "cfb":
        return 12000.0
    if s in {"ncaab_mens", "mcbb"}:
        return 9000.0
    if s in {"ncaab_womens", "wcbb"}:
        return 7000.0
    return 8000.0


async def load_manual_imputations(
    conn: asyncpg.Connection,
    athlete_id: str,
    org_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load manual imputation values.
    Precedence:
    - org-scoped manual values (if org_id provided)
    - global manual values
    """
    out: Dict[str, Any] = {}
    if org_id:
        org_rows = await conn.fetch(
            """SELECT field_name, field_value
               FROM athlete_manual_imputations
               WHERE athlete_id = $1::uuid
                 AND scope = 'org'
                 AND org_id = $2::uuid""",
            athlete_id,
            org_id,
        )
        for r in org_rows:
            out[str(r["field_name"])] = r["field_value"]

    global_rows = await conn.fetch(
        """SELECT field_name, field_value
           FROM athlete_manual_imputations
           WHERE athlete_id = $1::uuid
             AND scope = 'global'""",
        athlete_id,
    )
    for r in global_rows:
        # org-level stays highest precedence
        out.setdefault(str(r["field_name"]), r["field_value"])
    return out


from gravity_api.scrapers.parsers.handle_discovery import apply_user_instagram_upload


def apply_manual_imputations(raw: Dict[str, Any], manual: Dict[str, Any]) -> list[str]:
    if manual.get("instagram_handle"):
        manual = apply_user_instagram_upload(dict(manual))
    applied: list[str] = []
    for field, value in manual.items():
        if value is None:
            continue
        raw[field] = value
        applied.append(field)
    return applied


# Effective data-quality is capped at this value when any follower/social
# feature had to be fabricated, so downstream confidence reflects that the
# brand/reach signal is synthetic rather than scraped.
_FABRICATED_SOCIAL_DQ_CAP = 0.5


def apply_heuristic_imputations(raw: Dict[str, Any], athlete: asyncpg.Record) -> list[str]:
    """
    Fill critical missing features deterministically so scoring can proceed.
    These are conservative defaults and should be superseded by real/manual data.

    Fabricated follower counts keep the ML vector out of the all-zero regime,
    but they are synthetic — so when any social follower field is fabricated we
    cap ``data_quality_score`` (see ``_FABRICATED_SOCIAL_DQ_CAP``). The list of
    imputed field names is returned so the caller can persist provenance.
    """
    applied: list[str] = []
    sport = athlete.get("sport")
    position = athlete.get("position")
    pos_mult = _position_multiplier(position)
    base = _sport_base_followers(sport)

    fabricated_social = False
    ig = _as_float(raw.get("instagram_followers"))
    if ig is None or ig in PLACEHOLDER_NUMBERS:
        if ig in PLACEHOLDER_NUMBERS:
            applied.append("instagram_followers_placeholder_cleared")
        raw["instagram_followers"] = int(base * pos_mult)
        raw["instagram_followers_observed"] = 0
        applied.append("instagram_followers")
        fabricated_social = True
    if _as_float(raw.get("twitter_followers")) is None:
        raw["twitter_followers"] = int(base * 0.45 * pos_mult)
        raw["twitter_followers_observed"] = 0
        applied.append("twitter_followers")
        fabricated_social = True
    if _as_float(raw.get("tiktok_followers")) is None:
        raw["tiktok_followers"] = int(base * 0.65 * pos_mult)
        raw["tiktok_followers_observed"] = 0
        applied.append("tiktok_followers")
        fabricated_social = True
    if _as_float(raw.get("news_count_30d")) is None:
        raw["news_count_30d"] = 0
        applied.append("news_count_30d")
    if _as_float(raw.get("google_trends_score")) is None:
        raw["google_trends_score"] = 50.0
        applied.append("google_trends_score")
    if _as_float(raw.get("data_quality_score")) is None:
        raw["data_quality_score"] = 0.55
        applied.append("data_quality_score")

    if fabricated_social:
        current_dq = _as_float(raw.get("data_quality_score"))
        if current_dq is None or current_dq > _FABRICATED_SOCIAL_DQ_CAP:
            raw["data_quality_score"] = _FABRICATED_SOCIAL_DQ_CAP
    return applied
