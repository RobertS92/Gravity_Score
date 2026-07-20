"""JSON CSC report builder for the terminal."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence

import asyncpg

from gravity_api.services.csc_report_llm import (
    generate_confidence_rationale,
    generate_driver_explanation,
    generate_executive_summary,
    generate_risk_rationale,
    generate_value_interpretation,
)
from gravity_api.services.athlete_enrichment import (
    enrich_athlete_dict,
    parse_raw_data,
    score_delta_30d,
    value_delta_30d,
)
from gravity_api.services.csc_report_rollout import (
    ReportRolloutState,
    load_report_rollout_state,
)
from gravity_api.services.brand_heritage import detect_brand_heritage
from gravity_api.services.athlete_eligibility import live_eligibility_reason
from gravity_api.services.deal_pricing import price_standard_activation
from gravity_api.services.deal_scope_pricing import DEAL_SCOPES, price_all_deal_scopes
from gravity_api.services.model_health import classify_model_version
from gravity_api.services.nil_valuation import elite_signal_strength, nil_from_row
from gravity_api.services.position_group_match import derive_position_group, position_aliases_for_group
from gravity_api.services.team_conferences import (
    ConferenceNotMappedError,
    try_get_conference,
)


def _first_number(*values: Any) -> Optional[float]:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _text_or_fallback(value: Any, fallback: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _format_nil_value(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if abs(value) < 1_000_000:
        return f"${value / 1_000:.1f}K"
    return f"${value / 1_000_000:.1f}M"


def _format_score(value: Optional[float]) -> str:
    return f"{value:.1f}" if value is not None else "n/a"


def _normalize_confidence(value: Any) -> Optional[float]:
    raw = _first_number(value)
    if raw is None:
        return None
    if raw <= 0:
        return 0.0
    while raw > 1.0:
        raw /= 100.0
    return max(0.0, min(1.0, raw))


def _normalize_deal_structure(value: Any) -> str:
    raw = _text_or_fallback(value, "Structure pending verification")
    mapping = {
        "hybrid": "Hybrid",
        "cash + appearances": "Cash + Appearances",
        "cash+appearances": "Cash + Appearances",
        "cash + performance": "Cash + Performance Bonus",
        "cash + performance bonus": "Cash + Performance Bonus",
        "fixed": "Cash / Flat Fee",
        "fixed fee": "Cash / Flat Fee",
        "flat fee": "Cash / Flat Fee",
        "equity": "Equity / Options",
        "revenue share": "Revenue Share / Affiliate",
        "affiliate": "Revenue Share / Affiliate",
        "in kind": "Product / In-Kind",
        "in-kind": "Product / In-Kind",
    }
    return mapping.get(raw.lower(), raw)


def _normalize_verified_source(verified: Any, comp_nil: Optional[float]) -> str:
    if bool(verified):
        return "Direct Verification"
    if comp_nil is not None:
        return "Model Estimate"
    return "Source pending verification"


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_model_revision(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "unknown revision"


def _format_scored_at(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip() if value is not None else ""
    if not text:
        return "unknown date"
    return text[:10] if len(text) >= 10 else text


def _signal_level(score: Optional[float], *, invert: bool = False) -> str:
    if score is None:
        return "Moderate"
    value = 100.0 - score if invert else score
    if value >= 70:
        return "High"
    if value >= 40:
        return "Moderate"
    return "Low"


def _signal_rank(score: Optional[float], *, invert: bool = False) -> float:
    if score is None:
        return 50.0
    return (100.0 - score) if invert else score


def _fmt_followers(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    n = float(value)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{round(n / 1_000)}K"
    return str(round(n))


def _news_visibility_label(mentions: Optional[float]) -> str:
    if mentions is None:
        return "N/A"
    if mentions >= 20:
        return "High"
    if mentions >= 5:
        return "Emerging"
    return "Limited"


def _wiki_activity_label(views: Optional[float]) -> str:
    if views is None:
        return "N/A"
    if views >= 50_000:
        return "High"
    if views >= 10_000:
        return "Moderate"
    return "Emerging"


def _trends_label(score: Optional[float]) -> str:
    if score is None:
        return "N/A"
    if score >= 60:
        return "Rising"
    if score >= 35:
        return "Stable"
    return "Limited"


def _commercial_readiness_score(
    brand_score: Optional[float],
    engagement: Optional[float],
    deals: Optional[float],
) -> Optional[float]:
    parts: list[float] = []
    if brand_score is not None:
        parts.append(float(brand_score))
    if engagement is not None:
        parts.append(min(100.0, float(engagement) * 10.0))
    if deals is not None and deals > 0:
        parts.append(min(100.0, 40.0 + float(deals) * 8.0))
    if not parts:
        return None
    return sum(parts) / len(parts)


def _driver_signal_inputs(
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Shared follower/engagement extraction for the driver helpers.

    Both the qualitative (`_supporting_signals_for_driver`) and numeric
    (`_supporting_metrics_for_driver`) helpers read the same four base signals;
    resolving them in one place keeps the two surfaces from drifting.
    """
    ig = _first_number(athlete_d.get("instagram_followers"), latest_dict.get("instagram_followers"))
    tw = _first_number(athlete_d.get("twitter_followers"), latest_dict.get("twitter_followers"))
    tt = _first_number(athlete_d.get("tiktok_followers"), latest_dict.get("tiktok_followers"))
    engagement = _first_number(
        athlete_d.get("instagram_engagement_rate"),
        latest_dict.get("instagram_engagement_rate"),
    )
    return ig, tw, tt, engagement


def _supporting_metrics_for_driver(
    label: str,
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return structured numeric metrics for the inline metric grid.

    Distinct from `_supporting_signals_for_driver`, which surfaces
    interpretive (qualitative) labels. `supporting_metrics` carry raw
    numeric values + units so the frontend can render a stats grid and
    so the same data can feed sparklines/charts.
    """

    def metric(label: str, value: Any, unit: str | None = None) -> dict[str, Any]:
        return {"label": label, "value": value, "unit": unit}

    ig, tw, tt, engagement = _driver_signal_inputs(athlete_d, latest_dict)
    if label == "Brand Strength":
        return [
            metric("Instagram", ig, "followers"),
            metric("TikTok", tt, "followers"),
            metric("X", tw, "followers"),
            metric("IG Engagement", engagement, "%"),
        ]
    if label == "Exposure":
        return [
            metric("News Mentions", _first_number(athlete_d.get("news_mentions_30d")), "30d"),
            metric("Wiki Views", _first_number(athlete_d.get("wikipedia_page_views_30d")), "30d"),
            metric(
                "Search Trend",
                _first_number(athlete_d.get("google_trends_score")),
                "score",
            ),
        ]
    if label == "Market Proof":
        return [
            metric(
                "Verified Deals",
                int(_first_number(athlete_d.get("verified_deals_count")) or 0),
                "count",
            ),
            metric("Proof Score", _first_number(latest_dict.get("proof_score")), "/100"),
            metric("Brand Score", _first_number(latest_dict.get("brand_score")), "/100"),
        ]
    if label == "Momentum":
        return [
            metric("Velocity", _first_number(latest_dict.get("velocity_score")), "/100"),
            metric(
                "30d NIL Δ",
                _first_number(athlete_d.get("nil_valuation_delta_30d")),
                "$",
            ),
            metric(
                "30d Gravity Δ",
                _first_number(athlete_d.get("gravity_delta_30d")),
                "pts",
            ),
        ]
    if label == "Commercial Readiness":
        return [
            metric(
                "Combined Reach",
                _first_number(athlete_d.get("social_combined_reach")),
                "followers",
            ),
            metric("IG Engagement", engagement, "%"),
            metric(
                "Deals on File",
                int(_first_number(athlete_d.get("verified_deals_count")) or 0),
                "count",
            ),
            metric(
                "Data Quality",
                (
                    round(float(athlete_d["data_quality_score"]) * 100)
                    if _first_number(athlete_d.get("data_quality_score")) is not None
                    else None
                ),
                "%",
            ),
        ]
    if label == "Risk":
        return [
            metric("Risk Score", _first_number(latest_dict.get("risk_score")), "/100"),
            metric(
                "Roster",
                "Inactive" if bool(athlete_d.get("roster_inactive")) else "Active",
                None,
            ),
        ]
    return []


def _supporting_signals_for_driver(
    label: str,
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
) -> list[dict[str, str]]:
    ig, tw, tt, engagement = _driver_signal_inputs(athlete_d, latest_dict)
    if label == "Brand Strength":
        return [
            {"label": "Instagram", "value": _fmt_followers(ig)},
            {"label": "TikTok", "value": _fmt_followers(tt)},
            {"label": "X", "value": _fmt_followers(tw)},
            {
                "label": "Instagram Engagement Rate",
                "value": f"{_format_score(engagement)}%" if engagement is not None else "N/A",
            },
        ]
    if label == "Exposure":
        return [
            {
                "label": "News Visibility",
                "value": _news_visibility_label(_first_number(athlete_d.get("news_mentions_30d"))),
            },
            {
                "label": "Wikipedia Activity",
                "value": _wiki_activity_label(_first_number(athlete_d.get("wikipedia_page_views_30d"))),
            },
            {
                "label": "Search Interest",
                "value": _trends_label(_first_number(athlete_d.get("google_trends_score"))),
            },
        ]
    if label == "Market Proof":
        return [
            {"label": "Conference", "value": _text_or_fallback(athlete_d.get("conference"), "N/A")},
            {"label": "Position", "value": _text_or_fallback(athlete_d.get("position"), "N/A")},
            {
                "label": "Verified deals",
                "value": str(int(_first_number(athlete_d.get("verified_deals_count")) or 0)),
            },
            {
                "label": "Proof score",
                "value": _format_score(_first_number(latest_dict.get("proof_score"))),
            },
        ]
    if label == "Momentum":
        return [
            {
                "label": "Velocity score",
                "value": _format_score(_first_number(latest_dict.get("velocity_score"))),
            },
            {
                "label": "30d NIL delta",
                "value": _format_nil_value(_first_number(athlete_d.get("nil_valuation_delta_30d")))
                if _first_number(athlete_d.get("nil_valuation_delta_30d")) is not None
                else "N/A",
            },
            {
                "label": "30d Gravity delta",
                "value": _format_score(_first_number(athlete_d.get("gravity_delta_30d")))
                if _first_number(athlete_d.get("gravity_delta_30d")) is not None
                else "N/A",
            },
        ]
    if label == "Commercial Readiness":
        return [
            {
                "label": "Combined reach",
                "value": _fmt_followers(_first_number(athlete_d.get("social_combined_reach"))),
            },
            {
                "label": "Engagement rate (IG)",
                "value": f"{_format_score(engagement)}%" if engagement is not None else "N/A",
            },
            {
                "label": "Deals on file",
                "value": str(int(_first_number(athlete_d.get("verified_deals_count")) or 0)),
            },
            {
                "label": "Data quality",
                "value": (
                    f"{round(float(athlete_d['data_quality_score']) * 100)}%"
                    if _first_number(athlete_d.get("data_quality_score")) is not None
                    else "N/A"
                ),
            },
        ]
    if label == "Risk":
        inactive = bool(athlete_d.get("roster_inactive"))
        return [
            {"label": "Risk score", "value": _format_score(_first_number(latest_dict.get("risk_score")))},
            {"label": "Roster status", "value": "Inactive" if inactive else "Active"},
            {
                "label": "Model confidence",
                "value": _text_or_fallback(
                    (latest_dict.get("dollar_confidence") or {}).get("dollar_confidence_label")
                    if isinstance(latest_dict.get("dollar_confidence"), dict)
                    else None,
                    "N/A",
                ),
            },
        ]
    return []


def _fmt_followers_prose(value: Optional[float]) -> Optional[str]:
    """Whole-number follower phrasing safe for decimal-score prose validators."""
    if value is None:
        return None
    n = float(value)
    if n >= 1_000_000:
        millions = max(1, int(round(n / 1_000_000)))
        return "1 million" if millions == 1 else f"{millions} million"
    if n >= 1_000:
        return f"{int(round(n / 1_000))}K"
    return str(int(round(n)))


_DRIVER_ACTIONABILITY: dict[str, str] = {
    "Brand Strength": (
        "This level of visibility makes the athlete especially attractive for "
        "awareness campaigns, national brand launches, and premium consumer partnerships."
    ),
    "Market Proof": (
        "Verified market activity strengthens collective and brand negotiation posture "
        "for cash, hybrid, and performance-tied deal structures."
    ),
    "Exposure": (
        "Elevated exposure supports time-sensitive activations around high-leverage "
        "moments, product launches, and regional-to-national awareness pushes."
    ),
    "Momentum": (
        "Momentum informs timing — rising profiles favor shorter exclusive windows "
        "and faster deal cycles before market pricing resets."
    ),
    "Commercial Readiness": (
        "Commercial readiness signals how quickly the athlete can execute deliverables "
        "for brand campaigns without heavy production overhead."
    ),
    "Risk": (
        "Risk posture should shape contract protections, morals clauses, and "
        "whether partners prioritize shorter-term or heavily contingent structures."
    ),
}


def _join_prose_clauses(parts: list[str]) -> str:
    clean = [p for p in parts if p]
    if not clean:
        return "limited available signal coverage"
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return f"{', '.join(clean[:-1])}, and {clean[-1]}"


def _brand_strength_actionability(
    *,
    owned_platforms: int,
    has_earned: bool,
    has_context: bool,
    has_heritage: bool,
    signal: str,
) -> str:
    """Tailor commercial guidance to the brand-signal mix, not a static blurb."""
    if signal == "Low" and not has_heritage:
        return (
            "Until owned reach and earned demand deepen, partners should favor "
            "local or category-test activations rather than national brand launches."
        )
    if has_heritage and (owned_platforms >= 1 or has_earned):
        return (
            "Family-name recognition compounds owned and earned reach — partners get "
            "immediate cultural shorthand and trust transfer that follower counts alone "
            "understate, which fits awareness campaigns, national launches, and premium "
            "consumer partnerships."
        )
    if has_heritage:
        return (
            "Even before full platform coverage lands, heritage name equity supports "
            "selective national awareness and halo partnerships that lean on recognition "
            "and trust transfer."
        )
    if owned_platforms >= 2 and has_earned:
        return (
            "That blend of multi-platform owned reach and earned attention supports "
            "national brand launches, always-on consumer campaigns, and premium "
            "partnerships that need both audience scale and cultural relevance."
        )
    if owned_platforms == 1 and has_earned:
        return (
            "Even with brand equity concentrated on one primary social channel, the "
            "earned-media and search overlay makes him especially attractive for "
            "awareness campaigns, national launches, and premium consumer partnerships "
            "that can lean on recognition beyond a single feed."
        )
    if owned_platforms >= 1 and not has_earned:
        return (
            "With brand value currently led by owned social, the strongest near-term "
            "fits are creator-style awareness, product seeding, and always-on consumer "
            "partnerships, while partners should treat broader media reach as still "
            "maturing until more platform and demand data arrive."
        )
    if has_earned or has_context:
        return (
            "Recognition and market context still support selective awareness and "
            "halo partnerships, but deal construction should stay disciplined until "
            "owned-audience coverage is more complete."
        )
    return _DRIVER_ACTIONABILITY["Brand Strength"]


def _brand_strength_bundle(
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str,
    athlete_name: str = "",
) -> dict[str, str]:
    """Multi-layer Brand Strength evidence: heritage + owned + earned + context.

    Brand interpretation must not collapse to a single Instagram line when other
    brand-relevant signals exist (family name equity, news, search, wiki,
    school/conference).
    """
    name = (
        athlete_name
        or _text_or_fallback(athlete_d.get("name"), "")
    )
    sport = _text_or_fallback(athlete_d.get("sport"), "")
    heritage = detect_brand_heritage(name, sport=sport or None)

    ig, tw, tt, engagement = _driver_signal_inputs(athlete_d, latest_dict)
    news = _first_number(athlete_d.get("news_mentions_30d"))
    wiki = _first_number(athlete_d.get("wikipedia_page_views_30d"))
    trends = _first_number(athlete_d.get("google_trends_score"))
    combined = _first_number(athlete_d.get("social_combined_reach"))
    school = _text_or_fallback(athlete_d.get("school"), "")
    conference = _text_or_fallback(athlete_d.get("conference"), "")
    position = _text_or_fallback(
        athlete_d.get("position_group") or athlete_d.get("position"), ""
    )

    owned_bits: list[str] = []
    missing_platforms: list[str] = []
    ig_t = _fmt_followers_prose(ig)
    tt_t = _fmt_followers_prose(tt)
    tw_t = _fmt_followers_prose(tw)
    if ig_t:
        owned_bits.append(f"an Instagram audience of {ig_t}")
    else:
        missing_platforms.append("Instagram")
    if tt_t:
        owned_bits.append(f"a TikTok audience of {tt_t}")
    else:
        missing_platforms.append("TikTok")
    if tw_t:
        owned_bits.append(f"an X audience of {tw_t}")
    else:
        missing_platforms.append("X")

    eng_bit = ""
    if engagement is not None and engagement > 0:
        if engagement >= 5:
            eng_bit = "strong engagement quality"
        elif engagement >= 2:
            eng_bit = "solid engagement quality"
        else:
            eng_bit = "modest engagement quality"

    owned_platforms = len(owned_bits)
    if owned_platforms == 0:
        owned_clause = "limited measured owned-social coverage"
    elif owned_platforms == 1:
        owned_clause = (
            f"a concentrated owned channel — {owned_bits[0]}"
            + (f" with {eng_bit}" if eng_bit else "")
        )
    else:
        owned_clause = (
            f"owned reach across {_join_prose_clauses(owned_bits)}"
            + (f", with {eng_bit}" if eng_bit else "")
        )
        if combined and combined >= 1_000_000:
            combined_t = _fmt_followers_prose(combined)
            if combined_t:
                owned_clause += f" (about {combined_t} combined)"

    earned_bits: list[str] = []
    if news is not None:
        earned_bits.append(f"{_news_visibility_label(news).lower()} recent news visibility")
    if wiki is not None:
        earned_bits.append(f"{_wiki_activity_label(wiki).lower()} Wikipedia demand")
    if trends is not None:
        earned_bits.append(f"{_trends_label(trends).lower()} search interest")
    has_earned = bool(earned_bits)
    earned_clause = _join_prose_clauses(earned_bits) if earned_bits else ""

    context_bits: list[str] = []
    if school and school != "N/A":
        context_bits.append(school)
    if conference and conference != "N/A" and position and position != "N/A":
        context_bits.append(f"{conference} {position} stage")
    elif conference and conference != "N/A":
        context_bits.append(f"{conference} stage")
    elif position and position != "N/A":
        context_bits.append(f"{position} visibility")
    has_context = bool(context_bits)
    if len(context_bits) >= 2:
        context_clause = f"{context_bits[0]} ({' / '.join(context_bits[1:])})"
    elif context_bits:
        context_clause = context_bits[0]
    else:
        context_clause = ""

    has_heritage = heritage is not None
    heritage_fragment = heritage["prose_fragment"] if heritage else ""
    heritage_insight = heritage["insight"] if heritage else ""

    # Insight: heritage is a primary brand pillar when present.
    if has_heritage and owned_platforms >= 1 and has_earned:
        insight = (
            f"{heritage_insight}; owned reach is reinforced by {earned_clause}, "
            "so this is not a one-platform or followers-only brand story"
        )
    elif has_heritage and owned_platforms >= 1:
        insight = (
            f"{heritage_insight}, and measured owned social remains concentrated "
            "while additional platform coverage catches up"
        )
    elif has_heritage:
        insight = heritage_insight
    elif owned_platforms == 1 and has_earned:
        insight = (
            "brand equity is not Instagram-only — owned reach is reinforced by "
            f"{earned_clause}"
        )
    elif owned_platforms >= 2 and has_earned:
        insight = (
            "brand equity is diversified across owned social and earned demand, "
            f"including {earned_clause}"
        )
    elif owned_platforms >= 1 and not has_earned:
        insight = (
            "brand equity is currently led by owned social, with earned-media and "
            "search overlays still thin in the available data"
        )
    elif has_earned:
        insight = (
            f"brand recognition is showing up more in earned demand ({earned_clause}) "
            "than in fully measured owned-social coverage"
        )
    else:
        insight = (
            "available brand signals are still sparse, so interpretation leans on "
            "cohort positioning until platform and demand coverage improves"
        )

    # Sentence-1 stack: heritage first when present, then owned + context.
    evidence_parts: list[str] = []
    if heritage_fragment:
        evidence_parts.append(heritage_fragment)
    evidence_parts.append(owned_clause)
    if context_clause:
        evidence_parts.append(f"{context_clause} market context")
    evidence = _join_prose_clauses(evidence_parts)

    gap_parts: list[str] = []
    if missing_platforms:
        if len(missing_platforms) == 1:
            gap_parts.append(f"{missing_platforms[0]} audience data is unavailable")
        else:
            gap_parts.append(
                f"{' and '.join(missing_platforms[:2])} audience data are unavailable"
            )
    if news is None and wiki is None and trends is None:
        gap_parts.append("earned-media and search overlays are incomplete")
    if gap_parts:
        gaps = "While " + (", and ".join(gap_parts) if len(gap_parts) > 1 else gap_parts[0])
    else:
        gaps = ""

    return {
        "evidence": evidence,
        "gaps": gaps,
        "insight": insight,
        "actionability": _brand_strength_actionability(
            owned_platforms=owned_platforms,
            has_earned=has_earned,
            has_context=has_context,
            has_heritage=has_heritage,
            signal=signal,
        ),
    }


def _exposure_bundle(
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str,
) -> dict[str, str]:
    news = _first_number(athlete_d.get("news_mentions_30d"))
    wiki = _first_number(athlete_d.get("wikipedia_page_views_30d"))
    trends = _first_number(athlete_d.get("google_trends_score"))
    proximity = _first_number(latest_dict.get("proximity_score"))
    school = _text_or_fallback(athlete_d.get("school"), "")
    conference = _text_or_fallback(athlete_d.get("conference"), "")

    present: list[str] = []
    missing: list[str] = []
    if news is not None:
        present.append(f"{_news_visibility_label(news).lower()} news visibility")
    else:
        missing.append("news mentions")
    if wiki is not None:
        present.append(f"{_wiki_activity_label(wiki).lower()} Wikipedia demand")
    else:
        missing.append("Wikipedia activity")
    if trends is not None:
        present.append(f"{_trends_label(trends).lower()} search interest")
    else:
        missing.append("search interest")
    if proximity is not None:
        if proximity >= 70:
            present.append("high proximity to leverage moments")
        elif proximity >= 40:
            present.append("moderate proximity to leverage moments")
        else:
            present.append("limited proximity to leverage moments")

    context_bits: list[str] = []
    if school and school != "N/A":
        context_bits.append(school)
    if conference and conference != "N/A":
        context_bits.append(f"{conference} media market")
    if context_bits:
        present.append(_join_prose_clauses(context_bits) + " context")

    strong_earned = sum(
        1
        for v, thresh in ((news, 20), (wiki, 50_000), (trends, 60))
        if v is not None and v >= thresh
    )
    if strong_earned >= 2:
        insight = (
            "exposure is broad-based across earned media and demand channels, "
            "not a single-spike story"
        )
        action = (
            "That profile supports time-sensitive national activations, launch windows, "
            "and campaigns that need cultural heat in addition to owned audience."
        )
    elif strong_earned == 1 or (news is not None or trends is not None):
        insight = (
            "exposure is present but uneven — one or two demand channels are carrying "
            "most of the visibility signal"
        )
        action = (
            "Partners should time campaigns to the strongest visibility windows and "
            "avoid assuming continuous national heat from a single channel."
        )
    else:
        insight = (
            "earned exposure is thin in the available data, so visibility may be more "
            "roster- and schedule-dependent than media-driven"
        )
        action = (
            "Until news and search demand deepen, favor regional or event-tied activations "
            "over national always-on awareness buys."
        )
    if signal == "Low":
        action = (
            "Low exposure means partners should anchor deals to owned social and "
            "guaranteed deliverables rather than ambient media lift."
        )

    gaps = ""
    if missing:
        gaps = (
            f"While {missing[0]} data is unavailable"
            if len(missing) == 1
            else f"While {' and '.join(missing[:2])} data are unavailable"
        )
    return {
        "evidence": _join_prose_clauses(present) if present else "limited exposure coverage",
        "gaps": gaps,
        "insight": insight,
        "actionability": action,
    }


def _market_proof_bundle(
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str,
) -> dict[str, str]:
    deals = int(_first_number(athlete_d.get("verified_deals_count")) or 0)
    proof = _first_number(latest_dict.get("proof_score"))
    brand = _first_number(latest_dict.get("brand_score"))
    conference = _text_or_fallback(athlete_d.get("conference"), "")
    school = _text_or_fallback(athlete_d.get("school"), "")
    nil_delta = _first_number(athlete_d.get("nil_valuation_delta_30d"))

    present: list[str] = []
    missing: list[str] = []
    if deals > 0:
        present.append(f"{deals} verified deal{'s' if deals != 1 else ''} on file")
    else:
        missing.append("verified deals")
    if proof is not None:
        if proof >= 70:
            present.append("strong modeled market-proof signal")
        elif proof >= 40:
            present.append("moderate modeled market-proof signal")
        else:
            present.append("developing modeled market-proof signal")
    if brand is not None and brand >= 70:
        present.append("high brand score supporting monetization potential")
    if conference and conference != "N/A":
        present.append(f"{conference} market context")
    elif school and school != "N/A":
        present.append(f"{school} market context")
    if nil_delta is not None and abs(nil_delta) >= 5_000:
        direction = "rising" if nil_delta > 0 else "softening"
        present.append(f"{direction} recent NIL trajectory")

    if deals >= 3:
        insight = (
            "market proof is transaction-backed — multiple verified deals reduce "
            "reliance on modeled value alone"
        )
        action = (
            "That proof depth strengthens negotiation posture for cash and hybrid "
            "structures and supports using comps as live pricing anchors."
        )
    elif deals >= 1:
        insight = (
            "some verified deal activity exists, but proof depth is still thin enough "
            "that comps and cohort context matter"
        )
        action = (
            "Use the verified activity as a floor signal, then widen deal construction "
            "with cohort comps rather than treating one deal as a full market clear."
        )
    else:
        insight = (
            "market proof is mostly model- and cohort-inferred because verified deal "
            "history is sparse"
        )
        action = (
            "Keep terms flexible and comps-led until more verified transactions land; "
            "avoid over-indexing on a single modeled point estimate."
        )
    if signal == "Low":
        action = (
            "Low market proof argues for conservative pricing, milestone structures, "
            "and stronger verification requirements before scaling spend."
        )

    gaps = ""
    if missing:
        gaps = f"While {missing[0]} data is unavailable"
    return {
        "evidence": _join_prose_clauses(present) if present else "limited market-proof coverage",
        "gaps": gaps,
        "insight": insight,
        "actionability": action,
    }


def _momentum_bundle(
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str,
) -> dict[str, str]:
    vel = _first_number(latest_dict.get("velocity_score"))
    nil_delta = _first_number(athlete_d.get("nil_valuation_delta_30d"))
    grav_delta = _first_number(athlete_d.get("gravity_delta_30d"))
    news = _first_number(athlete_d.get("news_mentions_30d"))
    trends = _first_number(athlete_d.get("google_trends_score"))

    present: list[str] = []
    missing: list[str] = []
    if vel is not None:
        if vel >= 70:
            present.append("high velocity versus peers")
        elif vel >= 40:
            present.append("steady velocity versus peers")
        else:
            present.append("soft velocity versus peers")
    else:
        missing.append("velocity")
    if nil_delta is not None and abs(nil_delta) >= 1_000:
        direction = "rising" if nil_delta > 0 else "softening"
        present.append(f"{direction} 30-day NIL trajectory")
    elif nil_delta is None:
        missing.append("30-day NIL trajectory")
    if grav_delta is not None and abs(grav_delta) >= 1:
        direction = "rising" if grav_delta > 0 else "softening"
        present.append(f"{direction} 30-day Gravity trajectory")
    if news is not None and news >= 5:
        present.append(f"{_news_visibility_label(news).lower()} recent news flow")
    if trends is not None and trends >= 35:
        present.append(f"{_trends_label(trends).lower()} search interest")

    rising = (nil_delta is not None and nil_delta > 0) or (grav_delta is not None and grav_delta > 0) or (
        vel is not None and vel >= 70
    )
    softening = (nil_delta is not None and nil_delta < 0) or (grav_delta is not None and grav_delta < 0) or (
        vel is not None and vel < 40
    )
    if rising and not softening:
        insight = (
            "momentum is constructive — multiple trajectory signals point up, which "
            "usually compresses the window before market pricing resets"
        )
        action = (
            "Favor shorter exclusive windows and faster close cycles; delay risks "
            "paying a higher clearing price as peer comps catch up."
        )
    elif softening and not rising:
        insight = (
            "momentum is cooling — recent trajectory signals suggest less urgency for "
            "rush pricing"
        )
        action = (
            "Use the softer tape to negotiate patience on exclusivity and to stage "
            "spend against clearer performance or visibility milestones."
        )
    else:
        insight = (
            "momentum is mixed — some channels are moving while others are flat, so "
            "timing should be selective rather than blanket-aggressive"
        )
        action = (
            "Structure optionality around the strongest rising signals and avoid "
            "locking long exclusives on the weaker legs of the profile."
        )
    if signal == "Low":
        action = (
            "Low momentum favors waiting for a clearer catalyst before paying "
            "acceleration premiums."
        )

    gaps = ""
    if missing:
        gaps = (
            f"While {missing[0]} data is unavailable"
            if len(missing) == 1
            else f"While {' and '.join(missing[:2])} data are unavailable"
        )
    return {
        "evidence": _join_prose_clauses(present) if present else "limited momentum coverage",
        "gaps": gaps,
        "insight": insight,
        "actionability": action,
    }


def _commercial_readiness_bundle(
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str,
) -> dict[str, str]:
    ig, _tw, _tt, engagement = _driver_signal_inputs(athlete_d, latest_dict)
    reach = _fmt_followers_prose(_first_number(athlete_d.get("social_combined_reach")) or ig)
    deals = int(_first_number(athlete_d.get("verified_deals_count")) or 0)
    dq = _first_number(athlete_d.get("data_quality_score"))
    inactive = bool(athlete_d.get("roster_inactive"))

    present: list[str] = []
    missing: list[str] = []
    if reach:
        present.append(f"combined reach of {reach}")
    else:
        missing.append("combined reach")
    if engagement is not None and engagement > 0:
        if engagement >= 5:
            present.append("strong engagement quality")
        elif engagement >= 2:
            present.append("solid engagement quality")
        else:
            present.append("modest engagement quality")
    else:
        missing.append("engagement")
    if deals > 0:
        present.append(f"{deals} deal{'s' if deals != 1 else ''} on file")
    else:
        missing.append("deal history")
    if dq is not None:
        pct = int(round(dq * 100)) if dq <= 1 else int(round(dq))
        present.append(f"data quality around {pct} percent")
    present.append("inactive roster status" if inactive else "active roster status")

    ready = (engagement is not None and engagement >= 2) and bool(reach) and not inactive
    if ready and deals > 0:
        insight = (
            "commercial readiness looks execution-ready — reach, engagement, and prior "
            "deal history suggest the athlete can carry deliverables without heavy lift"
        )
        action = (
            "That supports faster creative cycles, multi-deliverable packages, and "
            "partners who need reliable turnaround on campaign assets."
        )
    elif ready:
        insight = (
            "audience and engagement are workable, but thin deal history means "
            "onboarding and production process still need proving"
        )
        action = (
            "Start with clear scopes and short first packages to validate turnaround "
            "before expanding into always-on retainers."
        )
    elif inactive:
        insight = (
            "roster inactivity is a practical drag on commercial readiness even when "
            "audience metrics look solid"
        )
        action = (
            "Prioritize compliance review and availability confirmation before locking "
            "appearance-heavy or season-tied deliverables."
        )
    else:
        insight = (
            "commercial readiness is still forming — gaps in reach, engagement, or "
            "deal history raise execution friction"
        )
        action = (
            "Keep packages simple, production-light, and contingent on confirmed "
            "content capacity until readiness signals improve."
        )
    if signal == "Low":
        action = (
            "Low commercial readiness argues for agency-assisted production or "
            "lighter organic deliverables rather than complex multi-platform campaigns."
        )

    gaps = ""
    if missing:
        gaps = (
            f"While {missing[0]} data is unavailable"
            if len(missing) == 1
            else f"While {' and '.join(missing[:2])} data are unavailable"
        )
    return {
        "evidence": _join_prose_clauses(present) if present else "limited readiness coverage",
        "gaps": gaps,
        "insight": insight,
        "actionability": action,
    }


def _risk_bundle(
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str,
) -> dict[str, str]:
    """Note: `signal` is already inverted (High = low risk / clean posture)."""
    inactive = bool(athlete_d.get("roster_inactive"))
    risk = _first_number(latest_dict.get("risk_score"))
    conf = latest_dict.get("dollar_confidence")
    conf_label = None
    if isinstance(conf, dict):
        conf_label = conf.get("dollar_confidence_label")
    conf_label = _text_or_fallback(conf_label, "")

    present: list[str] = []
    missing: list[str] = []
    present.append("inactive roster status" if inactive else "active roster status")
    if risk is not None:
        level = _signal_level(risk, invert=True)
        present.append(f"{level.lower()} modeled risk posture")
    else:
        missing.append("risk score")
    if conf_label and conf_label != "N/A":
        present.append(f"{conf_label} valuation confidence")

    if inactive:
        insight = (
            "roster inactivity is the dominant operational risk — it can impair "
            "eligibility, availability, and campaign timing"
        )
        action = (
            "Require roster/eligibility confirmation, shorten terms, and lean on "
            "morals and availability clauses before scaling spend."
        )
    elif signal == "High":
        insight = (
            "risk posture looks clean relative to peers, which supports more "
            "confident multi-deliverable packaging"
        )
        action = (
            "Standard protections still apply, but partners can prioritize upside "
            "structures over heavy contingency loading."
        )
    elif signal == "Low":
        insight = (
            "elevated risk signals argue for defensive deal construction even when "
            "brand or exposure look strong"
        )
        action = (
            "Use stronger morals clauses, shorter terms, and milestone gating so "
            "commercial upside is not over-committed against operational uncertainty."
        )
    else:
        insight = (
            "risk is manageable but not negligible — enough uncertainty remains to "
            "shape term length and contingency design"
        )
        action = (
            "Balance commercial ambition with standard protections and avoid "
            "long exclusives without review triggers."
        )

    gaps = ""
    if missing:
        gaps = f"While {missing[0]} data is unavailable"
    return {
        "evidence": _join_prose_clauses(present),
        "gaps": gaps,
        "insight": insight,
        "actionability": action,
    }


def _driver_evidence_bundle(
    label: str,
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str = "Moderate",
    athlete_name: str = "",
) -> dict[str, str]:
    """Concrete evidence + gap notes for driver interpretation (LLM + fallback)."""
    if label == "Brand Strength":
        return _brand_strength_bundle(
            athlete_d,
            latest_dict,
            signal=signal,
            athlete_name=athlete_name,
        )
    if label == "Exposure":
        return _exposure_bundle(athlete_d, latest_dict, signal=signal)
    if label == "Market Proof":
        return _market_proof_bundle(athlete_d, latest_dict, signal=signal)
    if label == "Momentum":
        return _momentum_bundle(athlete_d, latest_dict, signal=signal)
    if label == "Commercial Readiness":
        return _commercial_readiness_bundle(athlete_d, latest_dict, signal=signal)
    if label == "Risk":
        return _risk_bundle(athlete_d, latest_dict, signal=signal)

    return {
        "evidence": "limited available signal coverage",
        "gaps": "",
        "insight": "",
        "actionability": (
            "Use this driver alongside peer context when structuring NIL conversations."
        ),
    }


_DRIVER_PEER_NOUN: dict[str, str] = {
    "Brand Strength": "personal brands",
    "Exposure": "exposure profiles",
    "Market Proof": "market-proof profiles",
    "Momentum": "momentum profiles",
    "Commercial Readiness": "commercially ready profiles",
    "Risk": "risk postures",
}


def _peer_verb_for_driver(label: str, signal: str) -> str:
    if label == "Risk":
        return {
            "High": "places him among the cleanest risk postures in",
            "Moderate": "tracks him near typical risk levels in",
            "Low": "leaves him with elevated operational risk versus",
        }.get(signal, "tracks him within")
    peer_noun = _DRIVER_PEER_NOUN.get(label, "profiles")
    return {
        "High": f"places him among the strongest {peer_noun} in",
        "Moderate": f"tracks him near the middle of",
        "Low": f"leaves him trailing typical {peer_noun} in",
    }.get(signal, "tracks him within")


def build_driver_interpretation_fallback(
    *,
    athlete_name: str,
    label: str,
    signal: str,
    cohort_label: str,
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
) -> str:
    """High-quality deterministic Interpretation copy (same bar as LLM target)."""
    bundle = _driver_evidence_bundle(
        label, athlete_d, latest_dict, signal=signal, athlete_name=athlete_name
    )
    peer_verb = _peer_verb_for_driver(label, signal)

    label_l = label.lower()
    first = f"{athlete_name}'s {label_l} is built from {bundle['evidence']}."
    insight = (bundle.get("insight") or "").strip()
    if bundle["gaps"] and insight:
        second = (
            f"{bundle['gaps']}, {insight}. That profile still {peer_verb} "
            f"the {cohort_label} market."
        )
    elif bundle["gaps"]:
        second = (
            f"{bundle['gaps']}, the available {label_l} picture still {peer_verb} "
            f"the {cohort_label} market."
        )
    elif insight:
        second = (
            f"{insight[0].upper()}{insight[1:]}. That profile {peer_verb} "
            f"the {cohort_label} market."
        )
    else:
        second = f"That {label_l} profile {peer_verb} the {cohort_label} market."
    return f"{first} {second} {bundle['actionability']}"


def _driver_evidence_summary_for_prompt(
    label: str,
    athlete_d: Mapping[str, Any],
    latest_dict: Mapping[str, Any],
    *,
    signal: str = "Moderate",
    athlete_name: str = "",
) -> str:
    bundle = _driver_evidence_bundle(
        label,
        athlete_d,
        latest_dict,
        signal=signal,
        athlete_name=athlete_name,
    )
    parts = [f"Evidence: {bundle['evidence']}."]
    if bundle.get("insight"):
        parts.append(f"Key insight: {bundle['insight']}.")
    if bundle["gaps"]:
        parts.append(f"Data gaps: {bundle['gaps']}.")
    parts.append(f"Actionability guide: {bundle['actionability']}")
    return " ".join(parts)


def _cap_confidence(level: str, *, max_level: str | None = None, min_level: str | None = None) -> str:
    order = {"Low": 0, "Moderate": 1, "High": 2}
    idx = order.get(level, 1)
    if max_level is not None:
        idx = min(idx, order[max_level])
    if min_level is not None:
        idx = max(idx, order[min_level])
    for k, v in order.items():
        if v == idx:
            return k
    return "Moderate"


def compute_final_confidence(
    base: str,
    *,
    cohort_fallback_step: int,
    comparable_state: str,
    model_status: str,
    cohort_fit: str | None = None,
) -> str:
    """Apply the spec's forced override chain.

    Lowest result wins; the order below is the canonical execution order
    documented in the CSC v3 spec.
    """
    levels = ("Low", "Moderate", "High")
    if base not in levels:
        base = "Moderate"
    if model_status == "fallback":
        # Hard cap — a fallback scorer cannot back a binding deal.
        return "Low"
    final = base
    if cohort_fallback_step >= 2:
        final = _cap_confidence(final, max_level="Low")
    elif cohort_fallback_step >= 1:
        final = _cap_confidence(final, max_level="Moderate")
    if comparable_state == "none":
        final = _cap_confidence(final, max_level="Low")
    elif comparable_state == "sparse":
        final = _cap_confidence(final, max_level="Moderate")
    if cohort_fit == "poor":
        final = _cap_confidence(final, max_level="Moderate")
    return final


def _quantile(values: Sequence[float], q: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    seq = sorted(values)
    idx = (len(seq) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(seq) - 1)
    frac = idx - lo
    return seq[lo] * (1 - frac) + seq[hi] * frac


def _build_shap_narrative(
    latest_score: Optional[Dict[str, Any]],
    latest_explainable: Optional[Dict[str, Any]],
) -> str:
    latest_score = latest_score or {}
    latest_explainable = latest_explainable or {}
    latest_version = _format_model_revision(latest_score.get("model_version"))
    latest_scored_on = _format_scored_at(latest_score.get("calculated_at"))
    latest_revision_id = (latest_version, latest_scored_on)

    source_row = latest_explainable if latest_explainable else latest_score
    shap = source_row.get("shap_values")
    if isinstance(shap, dict) and shap:
        numeric_drivers: List[tuple[str, float]] = []
        for key, value in shap.items():
            numeric = _coerce_float(value)
            if numeric is not None:
                numeric_drivers.append((str(key), numeric))

        source_version = _format_model_revision(source_row.get("model_version"))
        source_scored_on = _format_scored_at(source_row.get("calculated_at"))
        source_revision_id = (source_version, source_scored_on)
        is_latest_revision = source_revision_id == latest_revision_id
        if numeric_drivers:
            numeric_drivers.sort(key=lambda item: (-abs(item[1]), item[0]))
            top = numeric_drivers[:5]
            prefix = (
                "Top score drivers"
                if is_latest_revision
                else "Top score drivers (most recent explainable revision)"
            )
            details = ", ".join(f"{key} ({value:+.2f})" for key, value in top)
            return f"{prefix}: {details}. Source model {source_version} scored on {source_scored_on}."

    return (
        f"Latest score revision ({latest_version}, {latest_scored_on}) does not expose SHAP detail. "
        "Use Gravity Score components (Brand, Proof, Proximity, Velocity, Risk) for deterministic attribution."
    )


def _tier_v1_absolute(benchmark: Optional[float]) -> str:
    if benchmark is None:
        return "Developing"
    if benchmark >= 150_000:
        return "Top-tier"
    if benchmark >= 50_000:
        return "Mid-tier"
    return "Developing"


async def _load_active_exposure_formula(db: asyncpg.Connection) -> dict[str, Any]:
    try:
        rows = await db.fetch(
            """SELECT version, proximity_weight, velocity_weight, is_active
               FROM exposure_formulas
               WHERE is_active = TRUE"""
        )
    except Exception:
        rows = []
    if len(rows) != 1:
        return {
            "version": "exposure_formula_v1",
            "proximity_weight": 0.6,
            "velocity_weight": 0.4,
        }
    row = rows[0]
    return {
        "version": str(row["version"]),
        "proximity_weight": float(row["proximity_weight"]),
        "velocity_weight": float(row["velocity_weight"]),
    }


async def _load_tier_rollout_state(
    db: asyncpg.Connection, user_id: str | None
) -> tuple[str, str]:
    phase = "phase1"
    try:
        row = await db.fetchrow(
            "SELECT current_phase FROM csc_tier_rollout LIMIT 1"
        )
        if row and row.get("current_phase"):
            phase = str(row["current_phase"])
    except Exception:
        phase = "phase1"
    if user_id:
        try:
            override = await db.fetchrow(
                """SELECT force_tier_version
                   FROM csc_tier_account_overrides
                   WHERE user_id = $1""",
                user_id,
            )
            if override and override.get("force_tier_version") in {"tier_v1", "tier_v2"}:
                return phase, str(override["force_tier_version"])
        except Exception:
            pass
    return phase, ("tier_v1" if phase in {"phase1", "phase2"} else "tier_v2")


async def _load_season_state(
    db: asyncpg.Connection, sport: str, as_of: date
) -> tuple[str, int]:
    try:
        row = await db.fetchrow(
            """SELECT state, cohort_window_days
               FROM season_states
               WHERE UPPER(sport) = UPPER($1)
                 AND start_date <= $2
                 AND end_date >= $2
               ORDER BY effective_year DESC
               LIMIT 1""",
            sport,
            as_of,
        )
    except Exception:
        row = None
    if not row:
        return "unknown", 21
    return str(row["state"]), int(row["cohort_window_days"])


def _position_group_value(athlete_row: Dict[str, Any], params: Dict[str, Any]) -> str:
    # Accept either `position_group` (canonical) or legacy `position` from
    # older terminal builds and agent payloads. When `position` looks like a
    # specific role (e.g. "QB", "WR") we let `derive_position_group` collapse
    # it into the canonical group; when it already looks like a group code we
    # use it directly.
    explicit = params.get("position_group") or params.get("position")
    if explicit:
        explicit_str = str(explicit).strip()
        if explicit_str:
            derived = derive_position_group(explicit_str)
            return (derived or explicit_str).strip().upper()
    raw = _text_or_fallback(
        athlete_row.get("position_group") or derive_position_group(athlete_row.get("position")),
        "UNK",
    )
    return raw.strip().upper()


async def _fetch_outlier_cohort_rows(
    db: asyncpg.Connection,
    *,
    sport: str,
    position_group: str,
    conference_tier: str | None,
    window_days: int,
    as_of: datetime,
    benchmark_floor: float,
) -> list[dict[str, Any]]:
    """Outlier-aware cohort fetch.

    Returns athletes whose `dollar_p50_usd >= benchmark_floor` within
    `(sport, position_group, conference_tier)`. Used when the standard
    fallback cohort has poor fit because the subject athlete sits far
    outside the broader cohort distribution.
    """
    aliases = position_aliases_for_group(position_group)
    since = as_of - timedelta(days=window_days)
    tier_pred = ""
    args: list[Any] = [sport, position_group, aliases, since, float(benchmark_floor)]
    if conference_tier:
        tier_pred = """AND EXISTS (
                  SELECT 1 FROM team_conferences tc
                  WHERE UPPER(TRIM(tc.team_id)) = UPPER(TRIM(a.school))
                    AND tc.sport = LOWER($1)
                    AND tc.conference_tier = $6
                    AND tc.effective_from <= CURRENT_DATE
                    AND (tc.effective_to IS NULL OR tc.effective_to >= CURRENT_DATE)
                )"""
        args.append(conference_tier)
    rows = await db.fetch(
        f"""WITH latest AS (
               SELECT DISTINCT ON (a.id)
                 a.id,
                 a.name,
                 a.position,
                 a.position_group,
                 a.conference,
                 a.school,
                 s.gravity_score,
                 s.velocity_score,
                 s.dollar_p50_usd,
                 s.calculated_at
               FROM athletes a
               JOIN athlete_gravity_scores s ON s.athlete_id = a.id
               WHERE UPPER(TRIM(COALESCE(a.sport, ''))) = UPPER(TRIM($1))
                 AND (
                   UPPER(TRIM(COALESCE(a.position_group, ''))) = $2
                   OR UPPER(TRIM(COALESCE(a.position, ''))) = ANY($3::text[])
                   OR string_to_array(UPPER(TRIM(COALESCE(a.position, ''))), '/') && $3::text[]
                 )
                 AND s.calculated_at >= $4
                 AND s.gravity_score IS NOT NULL
                 AND s.dollar_p50_usd IS NOT NULL
                 AND s.dollar_p50_usd >= $5
                 {tier_pred}
               ORDER BY a.id, s.calculated_at DESC
             )
             SELECT * FROM latest""",
        *args,
    )
    return [dict(r) for r in rows]


async def _fetch_cohort_rows(
    db: asyncpg.Connection,
    *,
    sport: str,
    position_group: str,
    conference: str | None,
    window_days: int,
    as_of: datetime,
) -> list[dict[str, Any]]:
    aliases = position_aliases_for_group(position_group)
    since = as_of - timedelta(days=window_days)
    conf_pred = ""
    args: list[Any] = [sport, position_group, aliases, since]
    if conference:
        conf_pred = "AND UPPER(TRIM(COALESCE(a.conference, ''))) = UPPER(TRIM($5))"
        args.append(conference)
    rows = await db.fetch(
        f"""WITH latest AS (
               SELECT DISTINCT ON (a.id)
                 a.id,
                 a.name,
                 a.position,
                 a.position_group,
                 a.conference,
                 s.gravity_score,
                 s.velocity_score,
                 s.dollar_p50_usd,
                 s.calculated_at
               FROM athletes a
               JOIN athlete_gravity_scores s ON s.athlete_id = a.id
               WHERE UPPER(TRIM(COALESCE(a.sport, ''))) = UPPER(TRIM($1))
                 AND (
                   UPPER(TRIM(COALESCE(a.position_group, ''))) = $2
                   OR UPPER(TRIM(COALESCE(a.position, ''))) = ANY($3::text[])
                   OR string_to_array(UPPER(TRIM(COALESCE(a.position, ''))), '/') && $3::text[]
                 )
                 {conf_pred}
                 AND s.calculated_at >= $4
                 AND s.gravity_score IS NOT NULL
               ORDER BY a.id, s.calculated_at DESC
             )
             SELECT * FROM latest""",
        *args,
    )
    return [dict(r) for r in rows]


def _cohort_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    benchmarks = [_first_number(r.get("dollar_p50_usd")) for r in rows]
    benchmarks = [b for b in benchmarks if b is not None]
    velocities = [_first_number(r.get("velocity_score")) for r in rows]
    velocities = [v for v in velocities if v is not None]
    return {
        "size": len(rows),
        "p10": _quantile(benchmarks, 0.10),
        "p25": _quantile(benchmarks, 0.25),
        "p50": _quantile(benchmarks, 0.50),
        "p75": _quantile(benchmarks, 0.75),
        "p90": _quantile(benchmarks, 0.90),
        "velocity_p75": _quantile(velocities, 0.75),
        "benchmark_values": benchmarks,
    }


def _percentile_rank(values: list[float], subject_value: Optional[float]) -> Optional[float]:
    if not values or subject_value is None:
        return None
    less_or_equal = sum(1 for v in values if v <= subject_value)
    return (less_or_equal / len(values)) * 100.0


def classify_cohort_fit(
    athlete_benchmark: Optional[float],
    cohort_stats: dict[str, Any],
) -> str:
    """Spec-exact cohort-fit classification: good / edge / poor.

    `poor` is returned when the cohort is too small to be informative or
    when the athlete sits more than 2x above P90 (or below half of P10).
    `edge` flags athletes near the tails. Everything else is `good`.
    """
    if cohort_stats.get("size", 0) < 5:
        return "poor"
    if athlete_benchmark is None:
        return "good"
    p10 = cohort_stats.get("p10")
    p90 = cohort_stats.get("p90")
    if p10 is None or p90 is None:
        return "poor"
    if athlete_benchmark > p90 * 2 or athlete_benchmark < p10 * 0.5:
        return "poor"
    if athlete_benchmark > p90 or athlete_benchmark < p10:
        return "edge"
    return "good"


def _build_detail_blocks(
    *,
    latest_dict: dict[str, Any],
    latest_with_shap_dict: dict[str, Any] | None,
    sport: str,
    position_group: str,
    conference: str,
    conference_tier: str | None,
    season_state: str,
    cohort_window_days: int,
    cohort_fallback_step: int,
    cohort_size: int,
    exposure_formula: dict[str, Any],
    comparable_state: str,
    comparable_sets_computed_at: Any,
    rollout_phase: str,
    tier_version: str,
    report_id: str,
    model_version: Any,
    model_status: str,
) -> dict[str, Any]:
    """Assemble the nested Methodology/Cohort/Comparables/Provenance/SHAP blocks."""
    shap_rows: list[dict[str, Any]] = []
    shap_source: dict[str, Any] | None = None
    if isinstance(latest_with_shap_dict, dict):
        shap_source = latest_with_shap_dict
    elif isinstance(latest_dict.get("shap_values"), dict):
        shap_source = {"shap_values": latest_dict.get("shap_values")}
    if shap_source:
        shap_obj = shap_source.get("shap_values")
        if isinstance(shap_obj, dict):
            for feature, value in sorted(
                shap_obj.items(),
                key=lambda kv: abs(_first_number(kv[1]) or 0.0),
                reverse=True,
            )[:8]:
                num = _first_number(value)
                if num is None:
                    continue
                shap_rows.append(
                    {
                        "feature": str(feature),
                        "contribution": float(num),
                    }
                )
    return {
        "methodology": {
            "title": "Methodology",
            "summary": (
                "Component-based valuation model with cohort-relative market context."
            ),
            "components": [
                "Brand Strength — branded reach and audience alignment.",
                "Market Proof — verified deal density and pricing.",
                "Exposure — proximity to high-leverage moments + recent velocity.",
                "Risk — operational, eligibility, and stability factors.",
            ],
            "tier_methodology_version": tier_version,
        },
        "cohort": {
            "title": "Cohort",
            "sport": sport,
            "position_group": position_group,
            "conference": conference,
            "conference_tier": conference_tier,
            "size": cohort_size,
            "window_days": cohort_window_days,
            "season_state": season_state,
            "fallback_step": cohort_fallback_step,
        },
        "comparables": {
            "title": "Comparables",
            "state": comparable_state,
            "computed_at": (
                comparable_sets_computed_at.isoformat()
                if comparable_sets_computed_at
                else None
            ),
        },
        "provenance": {
            "title": "Provenance",
            "report_id": report_id,
            "rollout_phase": rollout_phase,
            "tier_version": tier_version,
            "exposure_formula_version": exposure_formula["version"],
            "model_version": str(model_version) if model_version is not None else None,
            "model_status": model_status,
        },
        "shap_attribution": {
            "title": "SHAP Attribution",
            "rows": shap_rows,
            "narrative": _build_shap_narrative(latest_dict, latest_with_shap_dict),
        },
    }


def _athlete_initials(name: str | None) -> str:
    """Up-to-3-letter initials from athlete name, uppercased.

    Falls back to "ATH" when the name has no parseable initials so report
    IDs are always emittable even for partially-populated rows.
    """
    if not name:
        return "ATH"
    parts = [p for p in str(name).strip().split() if p]
    letters = "".join(p[0].upper() for p in parts if p[0].isalpha())[:3]
    return letters or "ATH"


async def _allocate_report_id(
    db: asyncpg.Connection,
    *,
    report_date: date,
    initials: str,
) -> str:
    """Allocate the next deterministic report id for (date, initials).

    Returns YYYY-MM-DD-INITIALS-NNN. Atomically increments
    `csc_report_sequence.next_seq`; falls back to a timestamp-based ID if
    the sequence table is missing (e.g. fresh dev DB without migration).
    """
    try:
        row = await db.fetchrow(
            """INSERT INTO csc_report_sequence (report_date, athlete_initials, next_seq)
               VALUES ($1, $2, 1)
               ON CONFLICT (report_date, athlete_initials)
               DO UPDATE SET next_seq = csc_report_sequence.next_seq + 1
               RETURNING next_seq""",
            report_date,
            initials,
        )
        if row and row.get("next_seq") is not None:
            return f"{report_date.isoformat()}-{initials}-{int(row['next_seq']):03d}"
    except Exception:
        # Sequence table not present (or read-only DB during preview).
        # Falls through to deterministic timestamp suffix below.
        pass
    return f"{report_date.isoformat()}-{initials}-001"


def validate_range(
    benchmark: Optional[float],
    p10: Optional[float],
    p90: Optional[float],
    *,
    p25: Optional[float] = None,
    p75: Optional[float] = None,
) -> tuple[Optional[float], Optional[float], str]:
    """Sanity-check the displayed deal-construction range; tighten when too wide.

    The hero band is a deal-construction range around *this athlete*, not a
    peer market distribution. The spec defines `range_quality = "wide"` when
    (p90 - p10) > benchmark. When wide, prefer the interquartile band only if
    it still brackets the athlete benchmark; otherwise tighten symmetrically
    around the benchmark so the point estimate never sits outside the band.
    """
    if benchmark is None or p10 is None or p90 is None:
        return p10, p90, "normal"
    spread = max(0.0, p90 - p10)
    if benchmark <= 0:
        return p10, p90, "normal"
    if spread <= benchmark:
        return p10, p90, "normal"
    if (
        p25 is not None
        and p75 is not None
        and float(p25) <= float(benchmark) <= float(p75)
    ):
        return p25, p75, "wide"
    # Peer IQR missing or excludes the athlete: tighten around the benchmark.
    band = benchmark * 0.30
    return max(0.0, benchmark - band), benchmark + band, "wide"


def range_incoherent_with_benchmark(
    benchmark: Optional[float],
    lo: Optional[float],
    hi: Optional[float],
) -> bool:
    """True when the displayed range cannot be reconciled with the benchmark.

    Catches the Arch-Manning-style failure mode where the headline benchmark
    is anchored to the sanitized raw NIL (e.g. $21.9M) while the v2 model
    emits a collapsed P10/P90 band that sits far below it (e.g. $4.5M-$4.6M).
    The mismatch confuses users because the range looks "actionable" but
    contradicts the number above it.

    Four failure modes are flagged:

    1. ``hi < benchmark * 0.5`` — range entirely below the benchmark.
    2. ``lo > benchmark * 2.0`` — range entirely above the benchmark.
    3. ``(hi - lo) < benchmark * 0.05`` — collapsed model band whose width
       is <5% of the benchmark, regardless of where the band sits.
    4. ``benchmark < lo or benchmark > hi`` — point estimate outside the band.
    """
    if benchmark is None or lo is None or hi is None:
        return False
    if benchmark <= 0:
        return False
    if float(hi) < benchmark * 0.5:
        return True
    if float(lo) > benchmark * 2.0:
        return True
    if (float(hi) - float(lo)) < benchmark * 0.05:
        return True
    if float(benchmark) < float(lo) or float(benchmark) > float(hi):
        return True
    return False


def ensure_benchmark_within_range(
    benchmark: Optional[float],
    lo: Optional[float],
    hi: Optional[float],
    *,
    min_spread_ratio: float = 0.20,
) -> tuple[Optional[float], Optional[float]]:
    """Expand endpoints so ``lo <= benchmark <= hi`` with a usable deal width.

    Never moves the benchmark to fit a bad band — the hero number is the
    source of truth and the deal-construction range must bracket it.
    """
    if benchmark is None or lo is None or hi is None:
        return lo, hi
    b = float(benchmark)
    new_lo = float(lo)
    new_hi = float(hi)
    if new_lo > new_hi:
        new_lo, new_hi = new_hi, new_lo

    min_half = max(500.0, abs(b) * (min_spread_ratio / 2.0))
    if b < new_lo:
        gap = new_lo - b
        new_lo = b
        new_hi = max(new_hi, b + max(gap, min_half * 2.0))
    elif b > new_hi:
        gap = b - new_hi
        new_hi = b
        new_lo = min(new_lo, max(0.0, b - max(gap, min_half * 2.0)))

    # Guarantee a minimum deal-construction width once containment holds.
    if new_hi - new_lo < max(1_000.0, abs(b) * min_spread_ratio):
        half = max(500.0, abs(b) * (min_spread_ratio / 2.0))
        if (b - new_lo) < half:
            new_lo = max(0.0, b - half)
        if (new_hi - b) < half:
            new_hi = b + half
    return new_lo, new_hi


def deal_construction_band(
    benchmark: float,
    *,
    downside: float = 0.30,
    upside: float = 0.40,
) -> tuple[float, float]:
    """Athlete-anchored deal-construction band around a point estimate."""
    lo = max(0.0, float(benchmark) * (1.0 - downside))
    hi = float(benchmark) * (1.0 + upside)
    return lo, hi


OUTLIER_VALUE_RANGE_NOTE = (
    "Outlier profile — peer cohort range is not applicable for deal construction. "
    "Displayed band is a deal-construction range around this athlete's benchmark."
)


def cap_displayed_percentile(
    raw_percentile: Optional[float],
    *,
    cohort_size: int,
) -> tuple[Optional[float], Optional[str]]:
    """Cap displayed percentile at 99 per spec.

    Returns `(displayed_value, override_text)`. `override_text` is set
    when the raw rank was 100 — in that case the report should render
    "Highest of N" rather than a numeric percentile.
    """
    if raw_percentile is None:
        return None, None
    if raw_percentile >= 100:
        return 99.0, f"Highest of {cohort_size} cohort athletes"
    if raw_percentile <= 1:
        return 1.0, None
    return raw_percentile, None


def _build_market_context_text(
    *,
    conference: str,
    position_group: str,
    cohort_size: int,
    p10: Optional[float],
    p50: Optional[float],
    p90: Optional[float],
    window_days: int,
    fallback_step: int,
    cohort_fit: str = "good",
) -> str:
    label = f"{conference} {position_group}s (n={cohort_size})"
    if cohort_fit == "poor":
        # The athlete's benchmark is outside the cohort distribution; the
        # spec mandates that percentile and median be suppressed in favor
        # of an explicit "exceeds peer cohort distribution" framing.
        return (
            f"Peer Market Context ({label})\n"
            "Outlier profile — peer cohort range is not applicable for deal "
            "construction. Athlete valuation exceeds the peer cohort distribution. "
            "Standard percentile statistics are not applicable; refer to the "
            "Comparable Athletes section for peer reference.\n"
            f"Based on athletes scored in the last {window_days} days"
        )
    if fallback_step >= 3:
        return (
            f"Peer Market Context ({label})\n"
            f"Peer market range: {_format_nil_value(p10)} – {_format_nil_value(p90)}\n"
            f"Based on athletes scored in the last {window_days} days (absolute methodology)."
        )
    return (
        f"Peer Market Context ({label})\n"
        f"Peer market range: {_format_nil_value(p10)} – {_format_nil_value(p90)}\n"
        f"Median: {_format_nil_value(p50)}\n"
        f"Based on athletes scored in the last {window_days} days"
    )


async def build_csc_report_json(
    db: asyncpg.Connection,
    athlete_id: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """Assemble a CSC v3 report.

    Pipeline phases (in execution order):
      1. INPUT VALIDATION   — required identifiers, parameter normalization.
      2. DATA HYDRATION     — athlete row, latest score, conference, cohort, exposure formula, comparables.
      3. DERIVED FIELDS     — benchmark, range, percentile, cohort_fit, tier, exposure score, drivers.
      4. LLM GENERATION     — executive summary, driver explanations, validation takeaway, confidence/risk notes.
      5. RENDER             — assemble Pydantic-shaped payload (value / explanation / validation / confidence_risk / detail).
      6. PERSIST            — allocate report_id (persisted only at router layer).
      7. RETURN             — stamp metadata + return.
    """
    # ---------------- PHASE 1: INPUT VALIDATION ----------------
    params = params or {}
    athlete = await db.fetchrow("SELECT * FROM athletes WHERE id = $1", athlete_id)
    if not athlete:
        raise ValueError("athlete not found")
    athlete_d = dict(athlete)
    eligibility_block = live_eligibility_reason(athlete_d)
    if eligibility_block:
        raise ValueError(
            f"Live pricing unavailable: {eligibility_block}. Refresh the authoritative roster before generating a report."
        )

    report_dt = datetime.now(tz=UTC)
    name = _text_or_fallback(athlete_d.get("name"), "Selected athlete")
    sport_f = _text_or_fallback(params.get("sport") or athlete_d.get("sport"), "CFB").upper()
    # Conference and conference tier come from `team_conferences` (sourced via
    # the athlete's school). A missing mapping raises ConferenceNotMappedError
    # so the router can return HTTP 422 — never silently degrade to placeholder.
    school_text = _text_or_fallback(athlete_d.get("school"), "")
    conference_lookup = (
        await try_get_conference(db, school_text, sport_f, as_of=report_dt.date())
        if school_text
        else None
    )
    conference_mapping_status = "mapped"
    if conference_lookup is None:
        # Fallback chain when team_conferences has no entry for this school:
        #   1. Use the athlete row's stored conference (e.g. "Big 12").
        #   2. Use the school name itself as a display label.
        #   3. Use "Independent" as a last resort.
        # In all cases we stamp metadata.conference_mapping_status so ops
        # can backfill team_conferences for this school. We never 422 a
        # report on missing mapping alone — the cohort fallback chain
        # already handles the broader cohort definition.
        stored_conf = (athlete_d.get("conference") or "").strip()
        if stored_conf and stored_conf.lower() != "conference":
            conference_f = stored_conf
            conference_mapping_status = "stored_fallback"
        elif school_text:
            conference_f = school_text
            conference_mapping_status = "school_fallback"
        else:
            conference_f = "Independent"
            conference_mapping_status = "unmapped"
        conference_tier: str | None = None
    else:
        conference_f = conference_lookup.conference
        conference_tier = conference_lookup.conference_tier
    pos_group = _position_group_value(athlete_d, params)
    n_comp = int(params.get("comparables_count") or 12)
    conf_min = float(params.get("confidence_min") or 0.75)

    # ---------------- PHASE 1.5: SIMPLE-MODE PARAM WIRING ----------------
    # The terminal Simple mode resolves to a `market_view` preset
    # (conservative/balanced/aggressive) plus a `report_focus` and a few
    # verification/percentile toggles. The preset already shapes
    # comparables_count + confidence_min via the frontend resolver, but we
    # also apply server-side guards so manual API callers benefit.
    market_view = (params.get("market_view") or "balanced").lower()
    if market_view == "conservative":
        # Tighten the comparable bar a bit further than the preset alone.
        conf_min = max(conf_min, 0.85)
    elif market_view == "aggressive":
        conf_min = min(conf_min, 0.70)

    verified_only = bool(params.get("verified_only", True))

    # csc_band_low_pct / csc_band_high_pct override the displayed range when
    # both are present; we apply them after the model + cohort blend runs.
    band_low_pct = params.get("csc_band_low_pct")
    band_high_pct = params.get("csc_band_high_pct")

    report_focus = (params.get("report_focus") or "overall").lower()
    selected_deal_scope = str(params.get("deal_scope") or "standard_activation")
    if selected_deal_scope not in DEAL_SCOPES:
        raise ValueError(f"unsupported deal_scope: {selected_deal_scope}")

    # ---------------- PHASE 2: DATA HYDRATION ----------------
    latest = await db.fetchrow(
        """SELECT * FROM athlete_gravity_scores
           WHERE athlete_id = $1 ORDER BY calculated_at DESC LIMIT 1""",
        athlete_id,
    )
    latest_with_shap = await db.fetchrow(
        """SELECT shap_values, model_version, calculated_at
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
             AND shap_values IS NOT NULL
             AND jsonb_typeof(shap_values) = 'object'
             AND shap_values <> '{}'::jsonb
           ORDER BY calculated_at DESC
           LIMIT 1""",
        athlete_id,
    )
    latest_dict = dict(latest) if latest else {}
    latest_with_shap_dict = dict(latest_with_shap) if latest_with_shap else None

    gravity_score = _first_number(latest_dict.get("gravity_score"))
    brand_score = _first_number(latest_dict.get("brand_score"))
    proof_score = _first_number(latest_dict.get("proof_score"))
    proximity_score = _first_number(latest_dict.get("proximity_score"))
    velocity_score = _first_number(latest_dict.get("velocity_score"))
    risk_score = _first_number(latest_dict.get("risk_score"))
    model_confidence = _normalize_confidence(latest_dict.get("confidence"))
    athlete_model_p10 = _first_number(latest_dict.get("dollar_p10_usd"))
    athlete_model_p50 = _first_number(latest_dict.get("dollar_p50_usd"))
    athlete_model_p90 = _first_number(latest_dict.get("dollar_p90_usd"))
    scraped_nil_row: dict[str, Any] = {}
    try:
        raw_row = await db.fetchrow(
            """SELECT raw_data FROM raw_athlete_data
               WHERE athlete_id = $1 ORDER BY scraped_at DESC NULLS LAST LIMIT 1""",
            athlete_id,
        )
        if raw_row and raw_row["raw_data"]:
            scraped_nil_row = parse_raw_data(raw_row["raw_data"])
    except Exception:
        scraped_nil_row = {}

    nil_ctx = {**scraped_nil_row, **athlete_d}
    athlete_raw_nil = nil_from_row(nil_ctx)

    # Enrich the athlete row with the same scraped signals the profile
    # endpoint resolves (followers, engagement, news, search interest, etc.)
    # plus the resolved conference, verified-deal count, and 30-day deltas.
    # Without this merge the driver "supporting metrics" read keys that only
    # ever live in raw_athlete_data / social_snapshots and render as N/A.
    snap_row = await db.fetchrow(
        """SELECT instagram_followers, twitter_followers, tiktok_followers,
                  instagram_engagement_rate, news_mentions_30d, scraped_at
           FROM social_snapshots
           WHERE athlete_id = $1
           ORDER BY scraped_at DESC
           LIMIT 1""",
        athlete_id,
    )
    snap_dict = dict(snap_row) if snap_row else None
    verified_deals_count = await db.fetchval(
        """SELECT COUNT(*)::int FROM athlete_nil_deals
           WHERE athlete_id = $1 AND verified = true""",
        athlete_id,
    )
    score_history = await db.fetch(
        """SELECT gravity_score, calculated_at
           FROM athlete_gravity_scores
           WHERE athlete_id = $1
           ORDER BY calculated_at DESC
           LIMIT 52""",
        athlete_id,
    )
    gravity_delta_30d = score_delta_30d([dict(r) for r in (score_history or [])])
    nil_history_rows = await db.fetch(
        """SELECT scraped_at, raw_data FROM raw_athlete_data
           WHERE athlete_id = $1
             AND scraped_at >= NOW() - INTERVAL '75 days'
           ORDER BY scraped_at DESC
           LIMIT 40""",
        athlete_id,
    )
    nil_series: list[tuple[Any, Any]] = []
    for nh in nil_history_rows or []:
        nh_raw = parse_raw_data(nh.get("raw_data"))
        if not nh_raw:
            continue
        nh_nil = nil_from_row({**nh_raw, **athlete_d})
        if nh_nil is not None:
            nil_series.append((nh.get("scraped_at"), nh_nil))
    nil_valuation_delta_30d = value_delta_30d(nil_series)

    enrich_athlete_dict(
        athlete_d,
        raw_signals=scraped_nil_row,
        snap=snap_dict,
        conference=conference_f,
        verified_deals_count=verified_deals_count,
        gravity_delta_30d=gravity_delta_30d,
        nil_valuation_delta_30d=nil_valuation_delta_30d,
    )

    # Model status: classify the version of the latest score row. A
    # `fallback` value flips the per-report 503 gate in the router and
    # forces a hard Low confidence cap downstream.
    latest_model_version = latest_dict.get("model_version")
    model_status_classification = classify_model_version(latest_model_version)
    # Treat 'unknown' as production so reports still render in environments
    # where the model_version column is sparse. Per-report enforcement only
    # blocks confirmed `fallback` rows.
    model_status: str = (
        "fallback" if model_status_classification == "fallback" else "production"
    )

    exposure_formula = await _load_active_exposure_formula(db)
    exposure_score = _first_number(
        (exposure_formula["proximity_weight"] * (proximity_score or 0.0))
        + (exposure_formula["velocity_weight"] * (velocity_score or 0.0))
    )

    season_state, cohort_window_days = await _load_season_state(db, sport_f, report_dt.date())

    # date_from / date_to (when supplied) override the default cohort window.
    # We compute the implied span in days and clamp to a sane range so
    # callers can't accidentally trigger unbounded scans.
    date_from_param = params.get("date_from")
    date_to_param = params.get("date_to")
    if date_from_param and date_to_param:
        try:
            df = datetime.fromisoformat(str(date_from_param)).date()
            dt_ = datetime.fromisoformat(str(date_to_param)).date()
            span_days = (dt_ - df).days
            if 1 <= span_days <= 720:
                cohort_window_days = span_days
        except ValueError:
            pass

    # Market-view widens or tightens the cohort window — aggressive callers
    # see more recent activity; conservative ones look further back for
    # validated data.
    if market_view == "aggressive":
        cohort_window_days = max(7, int(cohort_window_days * 0.7))
    elif market_view == "conservative":
        cohort_window_days = int(cohort_window_days * 1.4)

    # Cohort fallback chain.
    cohort_fallback_step = 0
    cohort_rows = await _fetch_cohort_rows(
        db,
        sport=sport_f,
        position_group=pos_group,
        conference=conference_f,
        window_days=cohort_window_days,
        as_of=report_dt,
    )
    if len(cohort_rows) < 5:
        cohort_fallback_step = 1
        cohort_rows = await _fetch_cohort_rows(
            db,
            sport=sport_f,
            position_group=pos_group,
            conference=None,
            window_days=cohort_window_days,
            as_of=report_dt,
        )
    if len(cohort_rows) < 5:
        cohort_fallback_step = 2
        cohort_rows = await _fetch_cohort_rows(
            db,
            sport=sport_f,
            position_group=pos_group,
            conference=None,
            window_days=90,
            as_of=report_dt,
        )
    if len(cohort_rows) < 5:
        cohort_fallback_step = 3
    cohort_stats = _cohort_stats(cohort_rows)

    # ---------------- PHASE 3: DERIVED FIELDS ----------------
    def _dollar_suspect(p50: Optional[float], anchor_nil: Optional[float]) -> bool:
        if p50 is None or p50 <= 0:
            return False
        if anchor_nil is not None and anchor_nil > 100_000 and p50 < anchor_nil * 0.05:
            return True
        return p50 < 75_000 and elite_signal_strength(nil_ctx) >= 0.55

    model_p50 = _first_number(athlete_model_p50)
    if athlete_raw_nil is not None and (
        model_p50 is None
        or _dollar_suspect(model_p50, athlete_raw_nil)
        or athlete_raw_nil > model_p50 * 2
    ):
        benchmark = athlete_raw_nil
    else:
        benchmark = _first_number(model_p50, athlete_raw_nil, cohort_stats["p50"])

    raw_lo = _first_number(athlete_model_p10, cohort_stats["p10"])
    raw_hi = _first_number(athlete_model_p90, cohort_stats["p90"])
    use_nil_band = (
        athlete_raw_nil is not None
        and athlete_raw_nil > 10_000
        and (
            _dollar_suspect(model_p50, athlete_raw_nil)
            or (
                benchmark is not None
                and athlete_raw_nil >= benchmark * 0.99
                and model_p50 is not None
                and model_p50 < benchmark * 0.5
            )
        )
    )
    # Final safety net: if the headline benchmark was lifted to the sanitized
    # raw NIL but the model P10/P90 band still sits far below it (collapsed
    # or completely off-center), the report would show e.g. "$21.9M / RANGE:
    # $4.5M – $4.6M". Force the NIL-anchored band in that case so the range
    # is always reconcilable with the benchmark above it.
    if (
        not use_nil_band
        and athlete_raw_nil is not None
        and athlete_raw_nil > 10_000
        and range_incoherent_with_benchmark(benchmark, raw_lo, raw_hi)
    ):
        use_nil_band = True
    if use_nil_band:
        # Athlete-anchored deal-construction band around the point estimate.
        raw_lo, raw_hi = deal_construction_band(float(athlete_raw_nil))
    elif athlete_raw_nil is not None and athlete_raw_nil > 10_000:
        if raw_lo is None or raw_hi is None or raw_lo == raw_hi:
            raw_lo, raw_hi = deal_construction_band(float(athlete_raw_nil), downside=0.35, upside=0.50)
    if raw_lo is None or raw_hi is None:
        if benchmark is not None:
            raw_lo, raw_hi = (
                deal_construction_band(float(benchmark), downside=0.20, upside=0.20)
                if raw_lo is None and raw_hi is None
                else (
                    max(0.0, float(benchmark) * 0.8) if raw_lo is None else raw_lo,
                    float(benchmark) * 1.2 if raw_hi is None else raw_hi,
                )
            )

    # Range sanity: when the model-derived P10/P90 band is wider than the
    # benchmark itself, tighten to an IQR (only if it brackets the athlete)
    # or a symmetric deal-construction band around the benchmark.
    lo, hi, range_quality = validate_range(
        benchmark,
        raw_lo,
        raw_hi,
        p25=_first_number(cohort_stats.get("p25")),
        p75=_first_number(cohort_stats.get("p75")),
    )
    if use_nil_band and benchmark is not None:
        if lo is None or hi is None or range_incoherent_with_benchmark(benchmark, lo, hi):
            lo, hi = deal_construction_band(float(benchmark))
            range_quality = "normal"

    # csc_band_low_pct / csc_band_high_pct override the displayed band when
    # the caller explicitly asked for tighter or looser percentile bounds
    # (analyst mode). We re-read the cohort distribution at the requested
    # percentiles when both endpoints are available; otherwise we ignore
    # the override silently so a partial config doesn't break the report.
    if (
        band_low_pct is not None
        and band_high_pct is not None
        and cohort_stats["size"] >= 5
        and benchmark is not None
    ):
        try:
            low_pct = float(band_low_pct) / 100.0
            high_pct = float(band_high_pct) / 100.0
            if 0.0 < low_pct < high_pct < 1.0:
                override_lo = _quantile(cohort_stats["benchmark_values"], low_pct)
                override_hi = _quantile(cohort_stats["benchmark_values"], high_pct)
                if override_lo is not None and override_hi is not None:
                    lo = override_lo
                    hi = override_hi
                    range_quality = "normal"
        except (TypeError, ValueError):
            pass

    # Minimum band enforcement: if the band collapses to <5% of benchmark
    # (or <$1,000 absolute), tag the range as an `estimate` rather than
    # surfacing "$17.9K – $17.9K". The frontend collapses identical
    # endpoints into a single ESTIMATE label.
    if benchmark is not None and benchmark > 0 and lo is not None and hi is not None:
        min_band = max(1_000.0, benchmark * 0.05)
        if float(hi) - float(lo) < min_band:
            # Center the collapsed band on the midpoint, then re-expand to
            # the minimum width so callers that still display a range get a
            # meaningful one and downstream % deltas don't divide by zero.
            mid = (float(lo) + float(hi)) / 2.0
            half = min_band / 2.0
            lo = max(0.0, mid - half)
            hi = mid + half
            range_quality = "estimate"

    # Hard invariant: hero deal-construction range must bracket the benchmark.
    lo, hi = ensure_benchmark_within_range(benchmark, lo, hi)

    raw_percentile_rank = (
        None
        if cohort_fallback_step >= 3
        else _percentile_rank(cohort_stats["benchmark_values"], benchmark)
    )
    percentile_rank, percentile_override_text = cap_displayed_percentile(
        raw_percentile_rank, cohort_size=cohort_stats["size"]
    )
    # Cohort fit classifies how informative the cohort is for this athlete.
    # `poor` triggers percentile suppression and forces confidence ≤ Moderate.
    cohort_fit_label = classify_cohort_fit(benchmark, cohort_stats)
    if cohort_fit_label == "poor":
        # Step 4: outlier-aware retry — pull athletes >= 50% of cohort median
        # within the same (sport, position_group, conference_tier) to build a
        # peer-tier reference instead of the diluted full cohort.
        if (
            cohort_fallback_step < 4
            and conference_tier
            and benchmark is not None
            and cohort_stats.get("p50") is not None
        ):
            try:
                outlier_rows = await _fetch_outlier_cohort_rows(
                    db,
                    sport=sport_f,
                    position_group=pos_group,
                    conference_tier=conference_tier,
                    window_days=90,
                    as_of=report_dt,
                    benchmark_floor=float(cohort_stats["p50"]) * 0.5,
                )
            except asyncpg.PostgresError:
                # team_conferences referenced by the outlier query may not
                # exist in this env; skip the step instead of failing.
                outlier_rows = []
            if len(outlier_rows) >= 5:
                cohort_fallback_step = 4
                cohort_rows = outlier_rows
                cohort_stats = _cohort_stats(cohort_rows)
                raw_percentile_rank = _percentile_rank(
                    cohort_stats["benchmark_values"], benchmark
                )
                percentile_rank, percentile_override_text = cap_displayed_percentile(
                    raw_percentile_rank, cohort_size=cohort_stats["size"]
                )
                cohort_fit_label = classify_cohort_fit(benchmark, cohort_stats)
        if cohort_fit_label == "poor":
            percentile_rank = None
            percentile_override_text = None

    # Outlier Value-section handling: peer IQR is not the deal-construction
    # surface. Re-anchor the hero band around the athlete benchmark and stamp
    # an explicit note so the UI can separate peer market context from the
    # athlete deal range.
    value_range_note: Optional[str] = None
    peer_range_applicable = True
    if cohort_fit_label == "poor" and benchmark is not None:
        peer_range_applicable = False
        value_range_note = OUTLIER_VALUE_RANGE_NOTE
        if range_incoherent_with_benchmark(benchmark, lo, hi):
            lo, hi = deal_construction_band(float(benchmark))
            range_quality = "normal"
        lo, hi = ensure_benchmark_within_range(benchmark, lo, hi)

    scoring_history_days = None
    history_start = await db.fetchval(
        """SELECT MIN(calculated_at)
           FROM athlete_gravity_scores
           WHERE athlete_id = $1""",
        athlete_id,
    )
    if history_start:
        scoring_history_days = max(0, int((report_dt - history_start).days))

    tier_v1 = _tier_v1_absolute(benchmark)
    tier_v2 = tier_v1
    if cohort_fallback_step >= 3:
        tier_v2 = f"{tier_v1}*"
    else:
        if (
            scoring_history_days is not None
            and scoring_history_days < 60
            and velocity_score is not None
            and cohort_stats["velocity_p75"] is not None
            and velocity_score >= cohort_stats["velocity_p75"]
        ):
            tier_v2 = "Emerging"
        elif percentile_rank is not None and percentile_rank >= 75:
            tier_v2 = "Top-tier"
        elif percentile_rank is not None and percentile_rank >= 40:
            tier_v2 = "Mid-tier"
        else:
            tier_v2 = "Developing"

    rollout_phase, selected_tier_version = await _load_tier_rollout_state(db, user_id)
    report_rollout = await load_report_rollout_state(db, user_id)
    # The displayed tier tag must equal the methodology stamped in
    # metadata.tier_version. tier_v1 is the absolute-dollar methodology and
    # never carries the "*" footnote; tier_v2 already includes "*" when
    # cohort fallback step >= 3 (set above).
    if selected_tier_version == "tier_v2":
        tier_selected = tier_v2
    else:
        tier_selected = tier_v1

    # Deterministic comparables. When `verified_only=true`, the lateral
    # join filters on `verified = true`; otherwise it returns the most
    # recent deal regardless of verification status.
    deal_lateral = (
        """LEFT JOIN LATERAL (
               SELECT deal_type, verified, deal_value FROM athlete_nil_deals
               WHERE athlete_id = a.id AND verified = true
               ORDER BY (deal_value IS NOT NULL) DESC, ingested_at DESC
               LIMIT 1
           ) d ON true"""
        if verified_only
        else """LEFT JOIN LATERAL (
               SELECT deal_type, verified, deal_value FROM athlete_nil_deals
               WHERE athlete_id = a.id
               ORDER BY (deal_value IS NOT NULL) DESC, ingested_at DESC
               LIMIT 1
           ) d ON true"""
    )
    comp_rows = await db.fetch(
        f"""SELECT a.id, a.name, a.school, a.position, s.gravity_score, s.brand_score,
                  s.dollar_p50_usd, cs.similarity_score, d.deal_type, d.verified, d.deal_value,
                  dv.verified_deal_count, cs.created_at
           FROM comparable_sets cs
           JOIN athletes a ON a.id = cs.comparable_athlete_id
           LEFT JOIN LATERAL (
               SELECT * FROM athlete_gravity_scores
               WHERE athlete_id = a.id ORDER BY calculated_at DESC LIMIT 1
           ) s ON true
           {deal_lateral}
           LEFT JOIN LATERAL (
               SELECT COUNT(*)::int AS verified_deal_count
               FROM athlete_nil_deals
               WHERE athlete_id = a.id AND verified = true
           ) dv ON true
           WHERE cs.subject_athlete_id = $1
             AND cs.similarity_score >= $2
           ORDER BY cs.similarity_score DESC, cs.comparable_athlete_id ASC
           LIMIT $3""",
        athlete_id,
        conf_min,
        n_comp,
    )
    comparable_sets_computed_at = None
    comparables_analysis: List[Dict[str, Any]] = []
    deal_pricing_comparables: List[Dict[str, Any]] = []
    for c in comp_rows:
        d = dict(c)
        comp_nil = _first_number(d.get("deal_value"), d.get("dollar_p50_usd"))
        deal_pricing_comparables.append(
            {
                "deal_value": _first_number(d.get("deal_value")),
                "dollar_p50_usd": _first_number(d.get("dollar_p50_usd")),
                "nil_valuation_consensus": comp_nil,
            }
        )
        comparables_analysis.append(
            {
                "athlete_id": str(d["id"]),
                "name": d["name"],
                "school": d["school"],
                "position": d["position"],
                "gravity_score": _first_number(d.get("gravity_score")),
                "brand_score": _first_number(d.get("brand_score")),
                "nil_valuation_consensus": comp_nil,
                "nil_delta_vs_subject": (
                    float(d["gravity_score"]) - float(gravity_score)
                    if d.get("gravity_score") is not None and gravity_score is not None
                    else None
                ),
                "confidence": _normalize_confidence(d.get("similarity_score")),
                "verified_deal_count": int(d.get("verified_deal_count") or 0),
                "deal_structure": _normalize_deal_structure(d.get("deal_type")),
                "verified_source": _normalize_verified_source(d.get("verified"), comp_nil),
            }
        )
        created_at = d.get("created_at")
        if created_at and (
            comparable_sets_computed_at is None or created_at > comparable_sets_computed_at
        ):
            comparable_sets_computed_at = created_at

    comparable_state = "sufficient"
    positional_reference_rows: List[Dict[str, Any]] = []
    if len(comparables_analysis) == 0:
        comparable_state = "none"
        refs = await db.fetch(
            """SELECT a.id, a.name, a.school, a.position, s.gravity_score, s.brand_score, s.dollar_p50_usd
               FROM athletes a
               LEFT JOIN LATERAL (
                 SELECT gravity_score, brand_score, dollar_p50_usd
                 FROM athlete_gravity_scores
                 WHERE athlete_id = a.id
                 ORDER BY calculated_at DESC
                 LIMIT 1
               ) s ON true
               WHERE a.id <> $1
                 AND UPPER(TRIM(COALESCE(a.sport, ''))) = UPPER(TRIM($2))
                 AND (
                   UPPER(TRIM(COALESCE(a.position_group, ''))) = $3
                   OR UPPER(TRIM(COALESCE(a.position, ''))) = ANY($4::text[])
                   OR string_to_array(UPPER(TRIM(COALESCE(a.position, ''))), '/') && $4::text[]
                 )
                 AND s.gravity_score IS NOT NULL
               ORDER BY ABS(s.gravity_score - $5) ASC, a.id ASC
               LIMIT 3""",
            athlete_id,
            sport_f,
            pos_group,
            position_aliases_for_group(pos_group),
            gravity_score or 0.0,
        )
        for r in refs:
            rd = dict(r)
            positional_reference_rows.append(
                {
                    "athlete_id": str(rd["id"]),
                    "name": rd["name"],
                    "school": rd["school"],
                    "position": rd["position"],
                    "gravity_score": _first_number(rd.get("gravity_score")),
                    "brand_score": _first_number(rd.get("brand_score")),
                    "nil_valuation_consensus": _first_number(rd.get("dollar_p50_usd")),
                    "nil_delta_vs_subject": None,
                    "confidence": None,
                    "verified_deal_count": 0,
                    "deal_structure": "Positional Reference",
                    "verified_source": "Model Estimate",
                }
            )
    elif len(comparables_analysis) < 3:
        comparable_state = "sparse"

    deal_pricing = price_standard_activation(
        annual_benchmark=benchmark,
        model_p50=model_p50,
        cohort_stats=cohort_stats,
        comparables=deal_pricing_comparables,
        sport=sport_f,
        position_group=pos_group,
        brand_score=brand_score,
        proof_score=proof_score,
        exposure_score=exposure_score,
        velocity_score=velocity_score,
        risk_score=risk_score,
        model_confidence=model_confidence,
        verified_deals_count=verified_deals_count,
        cohort_fit=cohort_fit_label,
        market_view=market_view,
    )
    transaction_counts: dict[str, int] = {}
    calibrations: dict[str, dict[str, Any]] = {}
    try:
        count_rows = await db.fetch(
            """SELECT deal_scope::text AS deal_scope, COUNT(*)::int AS n
               FROM verified_deal_transactions
               WHERE retracted_at IS NULL
               GROUP BY deal_scope"""
        )
        transaction_counts = {str(row["deal_scope"]): int(row["n"]) for row in count_rows}
        calibration_rows = await db.fetch(
            """SELECT DISTINCT ON (deal_scope) deal_scope::text AS deal_scope,
                      model_version, validation_transactions, target_coverage,
                      empirical_coverage, median_absolute_percentage_error,
                      log_residual_lower, log_residual_upper, evaluated_through
               FROM deal_model_calibrations
               ORDER BY deal_scope, evaluated_through DESC, created_at DESC"""
        )
        calibrations = {str(row["deal_scope"]): dict(row) for row in calibration_rows}
    except Exception:
        # Migration rollout is backward compatible. The output remains visibly
        # uncalibrated until governed evidence tables are available.
        transaction_counts = {}
        calibrations = {}
    scoped_deal_pricing = price_all_deal_scopes(
        annual_benchmark=benchmark,
        signals={
            "brand_score": brand_score,
            "proof_score": proof_score,
            "exposure_score": exposure_score,
            "velocity_score": velocity_score,
            "risk_score": risk_score,
        },
        transaction_counts=transaction_counts,
        calibrations=calibrations,
    )
    selected_scope_estimate = scoped_deal_pricing[selected_deal_scope]
    # From here forward, `lo`/`hi` are transaction-level activation guidance,
    # not the annual NIL benchmark uncertainty band. This deliberately retires
    # the old "range must bracket benchmark" invariant for user-facing deal
    # construction.
    if (
        deal_pricing.activation_deal_low is not None
        and deal_pricing.activation_deal_high is not None
    ):
        lo = selected_scope_estimate["low"]
        hi = selected_scope_estimate["high"]
        range_quality = "normal" if selected_scope_estimate["calibrated"] else "estimate"
        value_range_note = (
            (
                "Recommended range is priced for a standard 4-6 week brand activation. "
                if selected_deal_scope == "standard_activation"
                else f"Recommended range is priced for {selected_scope_estimate['label'].lower()}. "
            )
            + "It is intentionally separate from the annual NIL market benchmark."
        )

    base_confidence = _signal_level((model_confidence or 0.5) * 100.0)
    confidence_level = compute_final_confidence(
        base_confidence,
        cohort_fallback_step=cohort_fallback_step,
        comparable_state=comparable_state,
        model_status=model_status,
        cohort_fit=cohort_fit_label,
    )
    if range_quality == "wide":
        # Wide range → force ≤ Moderate confidence per spec.
        confidence_level = _cap_confidence(confidence_level, max_level="Moderate")
    risk_level = _signal_level(risk_score, invert=True)

    commercial_score = _commercial_readiness_score(
        brand_score,
        _first_number(athlete_d.get("instagram_engagement_rate")),
        _first_number(athlete_d.get("verified_deals_count")),
    )
    drivers = [
        ("Brand Strength", brand_score, False),
        ("Market Proof", proof_score, False),
        ("Exposure", exposure_score, False),
        ("Momentum", velocity_score, False),
        ("Commercial Readiness", commercial_score, False),
        ("Risk", risk_score, True),
    ]
    top_driver = sorted(
        drivers,
        key=lambda item: _signal_rank(item[1], invert=item[2]),
        reverse=True,
    )[0][0]
    primary_constraint = sorted(
        drivers,
        key=lambda item: _signal_rank(item[1], invert=item[2]),
    )[0][0]

    # ---------------- PHASE 4: LLM GENERATION ----------------
    benchmark_text = _format_nil_value(benchmark)
    range_text = (
        f"{_format_nil_value(lo)} to {_format_nil_value(hi)}"
        if lo is not None and hi is not None
        else "an estimated reference band"
    )
    percentile_text = (
        "the middle tier"
        if percentile_rank is None
        else f"the {round(percentile_rank)}th percentile of the cohort"
    )

    # Deterministic fallback prose (cleaned to satisfy validator: no
    # decimals, no formula constants, no system internals).
    fallback_executive_parts = [
        (
            f"{name} carries a Total NIL Value Benchmark of {benchmark_text} "
            f"with standard activation guidance of {range_text}."
        ),
        (
            f"In {conference_f} {pos_group}s, this profile sits in {percentile_text}, "
            f"led by {top_driver.lower()}."
        ),
        (
            "The benchmark reflects annual market positioning; the activation range "
            "is priced separately using deliverable-level deal economics."
        ),
    ]
    if confidence_level != "High":
        fallback_executive_parts.append(
            f"Primary uncertainty is driven by {primary_constraint.lower()} and current comparable depth."
        )
    fallback_executive_summary = " ".join(fallback_executive_parts)

    cohort_label = f"{conference_f} {pos_group}s"
    uncertainty_note = (
        "None"
        if confidence_level == "High"
        else f"Primary uncertainty: {primary_constraint.lower()}."
    )
    executive_result = await generate_executive_summary(
        athlete_name=name,
        benchmark_text=benchmark_text,
        range_text=range_text,
        cohort_label=cohort_label,
        tier_tag=tier_selected,
        confidence_tag=f"{confidence_level} Confidence",
        dominant_driver=top_driver,
        uncertainty_note=uncertainty_note,
        fallback=fallback_executive_summary,
    )
    executive_summary = executive_result.text

    # Deterministic per-driver Interpretation — evidence + peer meaning +
    # actionability (same quality bar as the LLM target).
    raw_driver_rows = [
        ("Brand Strength", _signal_level(brand_score)),
        ("Market Proof", _signal_level(proof_score)),
        ("Exposure", _signal_level(exposure_score)),
        ("Momentum", _signal_level(velocity_score)),
        ("Commercial Readiness", _signal_level(commercial_score)),
        ("Risk", _signal_level(risk_score, invert=True)),
    ]
    key_value_drivers: list[dict[str, Any]] = []
    for label, signal in raw_driver_rows:
        fallback = build_driver_interpretation_fallback(
            athlete_name=name,
            label=label,
            signal=signal,
            cohort_label=cohort_label,
            athlete_d=athlete_d,
            latest_dict=latest_dict,
        )
        evidence_summary = _driver_evidence_summary_for_prompt(
            label, athlete_d, latest_dict, signal=signal, athlete_name=name
        )
        driver_result = await generate_driver_explanation(
            athlete_name=name,
            driver_label=label,
            signal_level=signal,
            position_group=pos_group,
            cohort_label=cohort_label,
            evidence_summary=evidence_summary,
            fallback=fallback,
        )
        key_value_drivers.append(
            {
                "label": label,
                "signal": signal,
                "explanation": driver_result.text,
                "supporting_signals": _supporting_signals_for_driver(
                    label,
                    athlete_d,
                    latest_dict,
                ),
                "supporting_metrics": _supporting_metrics_for_driver(
                    label,
                    athlete_d,
                    latest_dict,
                ),
            }
        )

    # Reorder drivers by `report_focus` so the most relevant value driver
    # for the caller's use case appears first. The canonical order
    # (Brand Strength → Market Proof → Exposure → Momentum → Commercial
    # Readiness → Risk) is preserved for the remaining drivers.
    focus_map = {
        "brand": "Brand Strength",
        "commercial": "Commercial Readiness",
        "recruiting": "Momentum",
    }
    focus_label = focus_map.get(report_focus)
    if focus_label:
        key_value_drivers.sort(
            key=lambda d: 0 if d.get("label") == focus_label else 1,
        )

    market_context = _build_market_context_text(
        conference=conference_f,
        position_group=pos_group,
        cohort_size=cohort_stats["size"],
        p10=_first_number(cohort_stats["p10"], lo),
        p50=_first_number(cohort_stats["p50"], benchmark),
        p90=_first_number(cohort_stats["p90"], hi),
        window_days=(90 if cohort_fallback_step >= 2 else cohort_window_days),
        fallback_step=cohort_fallback_step,
        cohort_fit=cohort_fit_label,
    )
    if percentile_override_text:
        # Suffix the override text so consumers see "Highest of N" instead of
        # a numeric percentile when the athlete is at the top of the cohort.
        market_context = f"{market_context}\n{percentile_override_text}"
    if comparable_state == "none":
        validation_takeaway = (
            f"{name}'s benchmark is presented against positional cohort context; direct similarity comparables were unavailable."
        )
    elif comparable_state == "sparse":
        validation_takeaway = (
            f"{name}'s benchmark aligns with available comparables, but sparse matches reduce certainty in the band."
        )
    else:
        validation_takeaway = (
            f"{name}'s benchmark aligns with similar comparables and current cohort market context."
        )

    # ---------------- PHASE 6: PERSIST (report id allocation) ----------------
    report_id = await _allocate_report_id(
        db,
        report_date=report_dt.date(),
        initials=_athlete_initials(name),
    )

    # Validation takeaway via LLM with deterministic fallback.
    comparables_summary = (
        f"{len(comparables_analysis)} comparable athletes"
        if comparable_state != "none"
        else "No direct comparables available; using positional reference athletes"
    )
    interpretation_result = await generate_value_interpretation(
        athlete_name=name,
        market_context=market_context.replace("\n", " "),
        comparables_summary=comparables_summary,
        benchmark_text=benchmark_text,
        percentile_text=percentile_text,
        fallback=validation_takeaway,
    )
    validation_takeaway = interpretation_result.text

    # Confidence + risk rationale via LLM with deterministic fallback.
    confidence_causes_parts: list[str] = []
    if model_status == "fallback":
        confidence_causes_parts.append("the scoring service is on a fallback model")
    if comparable_state == "none":
        confidence_causes_parts.append("no direct comparables were available")
    elif comparable_state == "sparse":
        confidence_causes_parts.append("comparable athlete depth is limited")
    if cohort_fallback_step >= 2:
        confidence_causes_parts.append("cohort data is sparse for this athlete")
    if cohort_fit_label == "poor":
        confidence_causes_parts.append("the athlete sits outside the typical peer cohort")
    if range_quality == "wide":
        confidence_causes_parts.append("the value range is wider than the benchmark")
    if not confidence_causes_parts:
        confidence_causes_parts.append("cohort quality and comparable depth are adequate")
    confidence_causes = "; ".join(confidence_causes_parts)
    fallback_confidence_note = (
        f"{confidence_level} confidence: {confidence_causes_parts[0]}."
    )
    confidence_result = await generate_confidence_rationale(
        athlete_name=name,
        confidence_level=confidence_level,
        causes=confidence_causes,
        fallback=fallback_confidence_note,
    )

    risk_factors = primary_constraint.lower() if confidence_level != "High" else "none material"
    fallback_risk_note = (
        f"{risk_level} risk: driven by {risk_factors}."
    )
    risk_result = await generate_risk_rationale(
        athlete_name=name,
        risk_level=risk_level,
        position_group=pos_group,
        risk_factors=risk_factors,
        fallback=fallback_risk_note,
    )

    detail_methodology = (
        "Component-based annual valuation with separate activation-level deal pricing. "
        f"Season state={season_state}, cohort window={90 if cohort_fallback_step >= 2 else cohort_window_days} days. "
        f"Exposure formula version={exposure_formula['version']}; "
        f"deal methodology={deal_pricing.method}; tier methodology=tier_v2 with phased rollout."
    )

    # ---------------- PHASE 5+7: RENDER + RETURN ----------------
    return {
        "value": {
            "total_benchmark": benchmark,
            "range_low": lo,
            "range_high": hi,
            "annual_nil_benchmark": deal_pricing.annual_nil_benchmark,
            "activation_deal_low": scoped_deal_pricing["standard_activation"]["low"],
            "activation_deal_mid": scoped_deal_pricing["standard_activation"]["mid"],
            "activation_deal_high": scoped_deal_pricing["standard_activation"]["high"],
            "season_partnership_low": deal_pricing.season_partnership_low,
            "season_partnership_high": deal_pricing.season_partnership_high,
            "deal_confidence": selected_scope_estimate["confidence"],
            "deal_uncertainty": (
                f"Measured on {selected_scope_estimate['validation_transactions']} later transactions; "
                f"median absolute error={selected_scope_estimate['median_absolute_percentage_error']:.0%}."
                if selected_scope_estimate["calibrated"]
                and selected_scope_estimate["median_absolute_percentage_error"] is not None
                else "Uncalibrated prior: historical error is not yet sufficient to claim confidence."
            ),
            "deal_pricing_method": selected_scope_estimate["model_version"],
            "deal_pricing_basis": selected_scope_estimate["basis"],
            "selected_deal_scope": selected_deal_scope,
            "deal_scopes": scoped_deal_pricing,
            "tier_tag": tier_selected,
            "confidence_tag": f"{confidence_level} Confidence",
            "range_note": value_range_note,
            "peer_range_applicable": peer_range_applicable,
        },
        "explanation": {
            "executive_summary": executive_summary,
            "key_value_drivers": key_value_drivers,
            "driver_takeaway": (
                f"{top_driver} is the dominant value driver, while {primary_constraint.lower()} "
                "is the primary constraint on upside."
            ),
        },
        "validation": {
            "market_context": market_context,
            "comparable_tier": f"{tier_selected} {pos_group}s with similar signal profile.",
            "example_comparables": comparables_analysis[: n_comp],
            "takeaway": validation_takeaway,
            "comparable_state": comparable_state,
            "positional_reference_athletes": positional_reference_rows,
        },
        "confidence_risk": {
            "confidence_level": confidence_level,
            "confidence_note": confidence_result.text,
            "risk_level": risk_level,
            "risk_note": risk_result.text,
        },
        "detail": {
            "shap_attribution": _build_shap_narrative(latest_dict, latest_with_shap_dict),
            "methodology": detail_methodology,
            "inputs": (
                f"Inputs: sport={sport_f}, position_group={pos_group}, conference={conference_f}, "
                f"comparables_count={n_comp}, confidence_threshold={int(conf_min * 100)}%, "
                f"report_date={report_dt.date().isoformat()}."
            ),
            "blocks": _build_detail_blocks(
                latest_dict=latest_dict,
                latest_with_shap_dict=latest_with_shap_dict,
                sport=sport_f,
                position_group=pos_group,
                conference=conference_f,
                conference_tier=conference_tier,
                season_state=season_state,
                cohort_window_days=(90 if cohort_fallback_step >= 2 else cohort_window_days),
                cohort_fallback_step=cohort_fallback_step,
                cohort_size=cohort_stats["size"],
                exposure_formula=exposure_formula,
                comparable_state=comparable_state,
                comparable_sets_computed_at=comparable_sets_computed_at,
                rollout_phase=rollout_phase,
                tier_version=selected_tier_version,
                report_id=report_id,
                model_version=latest_model_version,
                model_status=model_status,
            ),
        },
        "metadata": {
            "tier_version": selected_tier_version,
            "tier_v1": tier_v1,
            "tier_v2": tier_v2,
            "cohort_window_days_used": (90 if cohort_fallback_step >= 2 else cohort_window_days),
            "season_state": season_state,
            "cohort_size": cohort_stats["size"],
            "cohort_dollar_spread": (
                (_first_number(cohort_stats.get("p90")) - _first_number(cohort_stats.get("p10")))
                if cohort_stats.get("p10") is not None and cohort_stats.get("p90") is not None
                else None
            ),
            "cohort_dollar_dispersion_low": (
                cohort_stats.get("p50") is not None
                and cohort_stats.get("p10") is not None
                and cohort_stats.get("p90") is not None
                and (_first_number(cohort_stats.get("p90")) - _first_number(cohort_stats.get("p10")))
                < 0.05 * max(_first_number(cohort_stats.get("p50"), 1.0), 1.0)
            ),
            "cohort_fallback_step": cohort_fallback_step,
            "comparable_state": comparable_state,
            "comparable_sets_computed_at": (
                comparable_sets_computed_at.isoformat()
                if comparable_sets_computed_at
                else None
            ),
            "exposure_formula_version": exposure_formula["version"],
            "exposure_formula_weights": {
                "proximity_weight": exposure_formula["proximity_weight"],
                "velocity_weight": exposure_formula["velocity_weight"],
            },
            "rollout_phase": rollout_phase,
            "low_cohort_data": cohort_fallback_step >= 3,
            "athlete_benchmark_percentile_in_cohort": percentile_rank,
            "conference": conference_f,
            "conference_tier": conference_tier,
            "conference_mapping_status": conference_mapping_status,
            "model_status": model_status,
            "model_version": (
                str(latest_model_version) if latest_model_version is not None else None
            ),
            "cohort_fit": cohort_fit_label,
            "range_quality": range_quality,
            "deal_pricing_method": selected_scope_estimate["model_version"],
            "deal_pricing_confidence": selected_scope_estimate["confidence"],
            "deal_pricing_comparable_deal_count": deal_pricing.comparable_deal_count,
            "deal_pricing_cohort_size": deal_pricing.cohort_size,
            "selected_deal_scope": selected_deal_scope,
            "deal_scope_calibrated": bool(selected_scope_estimate["calibrated"]),
            "deal_scope_readiness": selected_scope_estimate["readiness"],
            # Echo back the analyst/simple-mode knobs that shaped this run so
            # the UI can show users which preset produced the report and so
            # ops can debug "why does X look different today" answers.
            "market_view": market_view,
            "report_focus": report_focus,
            "verified_only": verified_only,
            "csc_band_low_pct": band_low_pct,
            "csc_band_high_pct": band_high_pct,
            "date_from": date_from_param,
            "date_to": date_to_param,
            "report_id": report_id,
            "report_version": report_rollout.version,
            "report_rollout_phase": report_rollout.phase,
        },
    }
