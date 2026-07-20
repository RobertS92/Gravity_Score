"""Cross-sport commercial scoring and within-sport percentile helpers."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

from gravity_api.services.nil_valuation import nil_from_row


def _number(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def _season_average(raw: Mapping[str, Any], total_key: str, *avg_keys: str) -> float:
    avg = _number(raw, *avg_keys)
    if avg is not None and avg > 0:
        return avg
    total = _number(raw, total_key)
    gp = _number(raw, "games_played_season", "gp", "gamesPlayed")
    if total is not None and total > 0 and gp is not None and gp > 0:
        return total / gp
    return 0.0


def _interpolate(value: float, knots: Sequence[tuple[float, float]]) -> float:
    if value <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if value <= x1:
            return y0 + (value - x0) / (x1 - x0) * (y1 - y0)
    return knots[-1][1]


_MARKET_KNOTS: dict[str, tuple[tuple[float, float], ...]] = {
    # Compensation is evidence of economic scale, not a direct synonym for
    # commercial demand. In particular, elite NBA performance produces large
    # salaries without necessarily producing a globally elite consumer brand.
    "nfl": (
        (250_000.0, 32.0), (750_000.0, 42.0), (1_500_000.0, 49.0),
        (3_000_000.0, 56.0), (6_000_000.0, 63.0), (12_000_000.0, 70.0),
        (20_000_000.0, 76.0), (25_000_000.0, 79.0), (45_000_000.0, 88.0),
        (64_000_000.0, 94.0), (80_000_000.0, 96.0),
    ),
    "nba": (
        (500_000.0, 30.0), (1_000_000.0, 36.0), (3_000_000.0, 44.0),
        (8_000_000.0, 54.0), (15_000_000.0, 63.0), (25_000_000.0, 72.0),
        (37_000_000.0, 80.0), (46_000_000.0, 84.0), (55_000_000.0, 88.0),
        (70_000_000.0, 92.0),
    ),
    "wnba": (
        (25_000.0, 30.0), (75_000.0, 38.0), (125_000.0, 44.0),
        (175_000.0, 49.0), (250_000.0, 54.0), (500_000.0, 60.0),
    ),
    "college": (
        (25_000.0, 32.0), (100_000.0, 42.0), (250_000.0, 49.0),
        (500_000.0, 55.0), (1_000_000.0, 62.0), (2_000_000.0, 69.0),
        (5_000_000.0, 77.0), (10_000_000.0, 83.0), (25_000_000.0, 89.0),
    ),
}

_COLLEGE_MARKET_SPORTS = frozenset({"cfb", "ncaab_mens", "ncaab_womens"})

_REACH_KNOTS = (
    (0.0, 28.0), (10_000.0, 40.0), (100_000.0, 62.0),
    (300_000.0, 80.0), (1_000_000.0, 86.0), (5_000_000.0, 92.0),
    (10_000_000.0, 94.0), (50_000_000.0, 97.0), (100_000_000.0, 98.0),
)

_WIKI_KNOTS = (
    (0.0, 42.0), (1_000.0, 49.0), (5_000.0, 57.0),
    (20_000.0, 65.0), (100_000.0, 77.0), (300_000.0, 86.0),
    # Mega encyclopedic attention: global icons sit well above ordinary stars.
    (600_000.0, 92.0), (1_000_000.0, 95.5), (3_000_000.0, 97.5),
)

# Social authenticity below this is treated as untrusted (team/org handles,
# scraped roster accounts, etc.). Only personal Instagram is kept as a weak prior.
_TRUSTED_SOCIAL_AUTH_FLOOR = 70.0

# Team/org handle tokens — never treat these as personal identity corroboration.
_TEAM_ORG_HANDLE_TOKENS = frozenset(
    {
        "official", "fc", "club", "team", "athletics", "sports", "nba", "nfl",
        "wnba", "mlb", "nhl", "espn", "network", "news", "pr", "media",
    }
)


def _truthy(value: Any) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _clean_handle(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lstrip("@").lower()
    return text or None


def _handle_looks_like_team_or_org(handle: str | None) -> bool:
    if not handle:
        return True
    # Segment tokens so personal handles like "jokicnikolaofficial" are kept,
    # while "lakers_official" / "nba" / "jaguars" org accounts are rejected.
    parts = {p for p in re.split(r"[_\-.]+", handle) if p}
    if parts & _TEAM_ORG_HANDLE_TOKENS:
        return True
    if handle in _TEAM_ORG_HANDLE_TOKENS:
        return True
    return False


def _bio_verified_personal_instagram(raw: Mapping[str, Any]) -> bool:
    """True when Instagram was bio-matched to the athlete (not a team/org scrape).

    Social authenticity scrapes often under-score real personal accounts when
    the bio text is sparse or emoji-heavy. A bio-verified personal handle with
    observed followers is stronger evidence than the numeric authenticity prior.
    """
    if not (
        _truthy(raw.get("instagram_handle_bio_verified"))
        or str(raw.get("instagram_handle_source") or "").strip().lower() == "bio_verified"
        or str(raw.get("handle_source") or "").strip().lower() == "bio_verified"
    ):
        return False
    ig = _clean_handle(raw.get("instagram_handle"))
    if not ig or _handle_looks_like_team_or_org(ig):
        return False
    followers = _number(raw, "instagram_followers") or 0.0
    return followers > 0


def _social_audience_is_trusted(raw: Mapping[str, Any]) -> bool:
    """True when follower counts are likely the athlete's own audience."""
    if _truthy(raw.get("social_account_verified")):
        return True
    if _bio_verified_personal_instagram(raw):
        return True
    auth = _number(raw, "social_authenticity_score")
    return auth is not None and auth >= _TRUSTED_SOCIAL_AUTH_FLOOR


def _personal_identity_corroborated(raw: Mapping[str, Any]) -> bool:
    """True when a non-team personal handle is present (even without follower counts).

    Mega-wiki global icons often have a known personal Instagram handle in raw
    without a scraped follower count. That identity signal may corroborate
    encyclopedic attention for brand-led Gravity, but must never trust team
    Twitter handles attached to roster players.
    """
    if _social_audience_is_trusted(raw):
        return True
    ig = _clean_handle(raw.get("instagram_handle"))
    if ig and not _handle_looks_like_team_or_org(ig):
        return True
    # Only accept Twitter as identity when authenticity already cleared the
    # trusted floor (handled above) — bare team handles are rejected.
    return False


def _trusted_social_reach(raw: Mapping[str, Any]) -> tuple[float, bool]:
    """Return (reach, trusted) for absolute commercial brand evidence.

    Untrusted snapshots commonly attach team/org Twitter accounts (hundreds of
    thousands of followers) to low-visibility roster players. Those must not
    mint global 90+ Gravity. When authenticity is weak, keep only Instagram —
    usually the personal account — and ignore Twitter/TikTok/aggregate reach.
    """
    ig = max(0.0, _number(raw, "instagram_followers") or 0.0)
    tt = max(0.0, _number(raw, "tiktok_followers") or 0.0)
    tw = max(0.0, _number(raw, "twitter_followers") or 0.0)
    aggregate = max(
        0.0,
        _number(raw, "social_reach_total", "social_combined_reach") or 0.0,
    )
    trusted = _social_audience_is_trusted(raw)
    if trusted:
        return max(ig + tt + tw, aggregate), True
    # Untrusted: Instagram-only weak prior; never let team Twitter dominate.
    return ig, False


def calibrate_global_commercial_score(
    score_data: Mapping[str, Any],
    raw: Mapping[str, Any],
    sport: str,
) -> tuple[float, dict[str, Any]]:
    """Return an absolute commercial score, independent of sport cohort rank.

    Observed salary/APY/NIL supplies an economic floor, while absolute audience,
    search and verified partnership evidence can lift brand-led stars beyond a
    salary-only estimate. Heuristic dollar projections are deliberately ignored
    because they are derived from the old cohort-relative Gravity score.
    """
    dc = dict(score_data.get("dollar_confidence") or {})
    observed_market = _number(raw, "observed_market_value_usd")
    sport_key = (sport or "").lower()
    if observed_market is None and sport_key in _COLLEGE_MARKET_SPORTS:
        try:
            observed_nil = int(float(raw.get("nil_valuation_observed") or 0)) == 1
        except (TypeError, ValueError):
            observed_nil = bool(raw.get("nil_valuation_observed"))
        if observed_nil:
            observed_market = nil_from_row(raw)
    if observed_market is None and dc.get("market_anchor_used"):
        observed_market = _number(dc, "observed_market_value_usd")
    if observed_market is None and str(dc.get("source") or "") == "observed":
        observed_market = _number(score_data, "dollar_p50_usd")

    market_key = sport_key if sport_key in _MARKET_KNOTS else "college"
    market_score = (
        _interpolate(max(25_000.0, observed_market), _MARKET_KNOTS[market_key])
        if observed_market is not None and observed_market > 0
        else None
    )

    reach, audience_trusted = _trusted_social_reach(raw)
    personal_identity = _personal_identity_corroborated(raw)
    audience_score = _interpolate(reach, _REACH_KNOTS) if reach > 0 else None
    trends = _number(raw, "google_trends_score")
    wiki = _number(raw, "wikipedia_page_views_30d", "wikipedia_views_30d")
    partnership = _number(raw, "partnership_brand_score")
    component_brand = _number(score_data, "brand_score")

    wiki_score = _interpolate(wiki, _WIKI_KNOTS) if wiki and wiki > 0 else None
    # Model component brand is partly cohort-derived. Treat it as corroboration,
    # not absolute global evidence, unless observed reach is also present.
    component_prior = (
        55.0 + 0.30 * (component_brand - 55.0)
        if component_brand is not None
        else 55.0
    )
    wiki_brand = None
    if wiki_score is not None:
        # Mega-wiki (≥90) is absolute global evidence on its own. Strong wiki
        # (≥85) is absolute when a personal identity handle corroborates it;
        # otherwise blend lightly with the component prior.
        if wiki_score >= 90.0 or (wiki_score >= 85.0 and personal_identity):
            wiki_brand = wiki_score
        elif wiki_score >= 85.0:
            wiki_brand = 0.90 * wiki_score + 0.10 * component_prior
        else:
            wiki_brand = 0.75 * wiki_score + 0.25 * component_prior
    if audience_score is not None:
        if audience_trusted:
            observed_social = max(
                audience_score,
                min(component_brand or audience_score, audience_score + 8.0),
            )
        else:
            # Do not let an inflated BPXVR/ML brand component launder untrusted
            # team-handle reach into absolute commercial Gravity.
            observed_social = audience_score
        social_brand = 0.75 * observed_social + 0.25 * (wiki_score or observed_social)
        # A weak or mismatched social snapshot must not erase stronger absolute
        # search/encyclopedic attention evidence.
        brand_score = max(social_brand, wiki_brand or social_brand)
    elif partnership is not None:
        brand_score = 0.70 * partnership + 0.30 * (wiki_score or component_prior)
    elif wiki_brand is not None:
        brand_score = wiki_brand
    else:
        brand_score = component_prior
    if trends is not None:
        brand_score += max(-2.0, min(4.0, (trends - 50.0) * 0.08))
    verified = _number(raw, "partnership_verified_count", "verified_deals_count") or 0.0
    brand_score += min(3.0, verified * 0.75)
    brand_score = max(20.0, min(98.0, brand_score))

    if market_score is not None:
        # Salary/APY is a strong economic signal but cannot mint global 90+
        # without consumer evidence. NFL contract scale is somewhat more
        # commercially informative; NBA salary is more performance-driven.
        market_weight = (
            0.85
            if sport_key == "nfl"
            else 0.90
            if sport_key in _COLLEGE_MARKET_SPORTS
            else 0.55
        )
        absolute = market_weight * market_score + (1.0 - market_weight) * brand_score
        if sport_key in _COLLEGE_MARKET_SPORTS:
            # Verified NIL is itself the commercial market signal; sparse social
            # scrapes should not drag a known multi-million-dollar NIL athlete
            # below the appropriate college market tier.
            absolute = max(absolute, market_score)
        # Brand may dominate salary only with trusted consumer evidence
        # (authenticated audience, personal identity + mega wiki, and/or
        # verified partnerships). Untrusted team-handle reach must never
        # bypass the market blend.
        mega_wiki = (wiki_score or 0.0) >= 90.0
        strong_wiki = (wiki_score or 0.0) >= 85.0
        solid_wiki = (wiki_score or 0.0) >= 75.0
        brand_led_ok = brand_score >= 90.0 and (
            (audience_trusted and (audience_score or 0.0) >= 88.0)
            or (mega_wiki and (personal_identity or market_score >= 84.0))
            or (strong_wiki and personal_identity and market_score >= 80.0)
            or verified >= 2.0
        )
        if brand_led_ok:
            # Global icons with mega wiki + market floor can land in the mid-90s;
            # keep the hard ceiling at 97 so 90+ remains rare.
            icon_boost = 1.5 if mega_wiki and market_score >= 84.0 else 1.0
            absolute = max(absolute, min(97.0, brand_score + icon_boost))
        # Elite top-of-market contracts (rare APY/salary scale) with real
        # consumer corroboration should not be diluted by a missing social
        # scrape. Requires market_score ≥ 92 (e.g. ~$60M+ NFL APY) plus wiki,
        # trusted audience, personal identity, or verified deals — never
        # salary alone, and never team-Twitter reach.
        elite_market = market_score >= 92.0
        consumer_corroboration = (
            solid_wiki
            or (audience_trusted and (audience_score or 0.0) >= 80.0)
            or personal_identity
            or verified >= 1.0
        )
        if elite_market and consumer_corroboration:
            elite_floor = min(
                97.0,
                market_score + (1.5 if solid_wiki or audience_trusted else 0.5),
            )
            absolute = max(absolute, elite_floor)
        nba_star_floor = None
        if sport_key == "nba":
            # NBA commercial value has a distinct superstar tier: max/near-max
            # salary plus repeated star-level production is market evidence even
            # when social and wiki scrapes are sparse.
            all_star = _number(raw, "all_star_count", "nba_all_star_count") or 0.0
            all_nba = _number(raw, "all_nba_count", "all_league_count") or 0.0
            avg_points = _season_average(
                raw,
                "pts",
                "avgPoints",
                "avg_points",
                "points_per_game",
                "ppg",
            )
            gp = _number(raw, "games_played_season", "gp", "gamesPlayed") or 0.0
            elite_nba_star = market_score >= 80.0 and gp >= 50.0 and (
                all_nba >= 1.0
                or (all_star >= 2.0 and avg_points >= 20.0)
                or avg_points >= 25.0
            )
            if elite_nba_star:
                production_floor = 0.0
                if avg_points >= 30.0:
                    production_floor = 86.0 + min(2.5, (avg_points - 30.0) * 0.70)
                elif avg_points >= 27.0:
                    production_floor = 84.5 + min(1.5, (avg_points - 27.0) * 0.50)
                star_floor = min(
                    88.5,
                    max(
                        market_score
                        + min(2.0, all_star * 0.35)
                        + min(1.5, all_nba * 0.5)
                        + min(3.0, max(0.0, avg_points - 24.0) * 0.35),
                        production_floor,
                    ),
                )
                absolute = max(absolute, star_floor)
                nba_star_floor = star_floor
            strong_nba_attention = (
                market_score >= 84.0
                and (wiki_score or 0.0) >= 80.0
                and (
                    all_star >= 4.0
                    or all_nba >= 2.0
                    or avg_points >= 25.0
                    or (component_brand or 0.0) >= 85.0
                )
            )
            if strong_nba_attention:
                icon_floor = min(
                    92.5,
                    market_score
                    + min(3.0, max(0.0, (wiki_score or 0.0) - 80.0) * 0.30)
                    + min(2.0, all_star * 0.30)
                    + min(1.0, all_nba * 0.25),
                )
                absolute = max(absolute, icon_floor)
                nba_star_floor = max(nba_star_floor or 0.0, icon_floor)
    else:
        nba_star_floor = None
        absolute = 0.88 * brand_score + 0.12 * 50.0
        if (
            audience_trusted
            and audience_score is not None
            and (component_brand or 0.0) >= 80.0
        ):
            # Direct audience plus an independently strong component estimate is
            # enough to recognize brand-led stars without salary evidence.
            absolute = max(absolute, min(98.0, brand_score + 1.5))
        elif (wiki_score or 0.0) >= 90.0 and personal_identity:
            absolute = max(absolute, min(97.0, brand_score + 1.0))

    adjustment = 0.0
    if sport_key == "wnba":
        adjustment = -(1.0 + 6.0 * max(0.0, min(1.0, (82.0 - brand_score) / 40.0)))
    elif sport_key == "ncaab_womens":
        adjustment = -(1.5 + 4.5 * max(0.0, min(1.0, (78.0 - brand_score) / 38.0)))

    absolute = round(max(20.0, min(98.0, absolute + adjustment)), 4)
    return absolute, {
        "version": "global_commercial_v7",
        "market_score": round(market_score, 4) if market_score is not None else None,
        "brand_score_absolute": round(brand_score, 4),
        "audience_score": round(audience_score, 4) if audience_score is not None else None,
        "audience_trusted": audience_trusted,
        "personal_identity": personal_identity,
        "wiki_score": round(wiki_score, 4) if wiki_score is not None else None,
        "sport_market_adjustment": round(adjustment, 4),
        "observed_market_used": observed_market is not None,
        "nba_star_commercial_floor": round(nba_star_floor, 4) if nba_star_floor is not None else None,
    }


def midrank_percentile(value: float, values: Sequence[float]) -> float:
    """Tie-safe monotonic percentile on a bounded 1-99 display scale."""
    finite = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not finite:
        return 50.0
    less = sum(v < value for v in finite)
    equal = sum(v == value for v in finite)
    rank = less + (equal + 1.0) / 2.0
    percentile = 100.0 * rank / len(finite)
    return round(max(1.0, min(99.0, percentile)), 2)


__all__ = ["calibrate_global_commercial_score", "midrank_percentile"]
