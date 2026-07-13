"""Robustness tests for CSC driver Interpretation fallbacks across all drivers."""

from __future__ import annotations

from gravity_api.services.csc_report_builder import build_driver_interpretation_fallback

_ATHLETE = {
    "name": "Arch Manning",
    "sport": "CFB",
    "instagram_followers": 1_200_000,
    "tiktok_followers": None,
    "twitter_followers": None,
    "instagram_engagement_rate": 6.0,
    "social_combined_reach": 1_200_000,
    "news_mentions_30d": 22,
    "wikipedia_page_views_30d": 60_000,
    "google_trends_score": 78,
    "verified_deals_count": 2,
    "nil_valuation_delta_30d": 150_000,
    "gravity_delta_30d": 3.5,
    "data_quality_score": 0.82,
    "roster_inactive": False,
    "school": "Texas",
    "conference": "SEC",
    "position_group": "QB",
}

_LATEST = {
    "brand_score": 88.0,
    "proof_score": 72.0,
    "proximity_score": 80.0,
    "velocity_score": 76.0,
    "risk_score": 18.0,
    "dollar_confidence": {"dollar_confidence_label": "High"},
}

_DRIVERS = [
    "Brand Strength",
    "Market Proof",
    "Exposure",
    "Momentum",
    "Commercial Readiness",
    "Risk",
]


def _text(label: str, signal: str = "High") -> str:
    return build_driver_interpretation_fallback(
        athlete_name="Arch Manning",
        label=label,
        signal=signal,
        cohort_label="SEC QBs",
        athlete_d=_ATHLETE,
        latest_dict=_LATEST,
    )


def test_every_driver_interpretation_is_multi_sentence_and_named():
    for label in _DRIVERS:
        text = _text(label)
        assert "Arch Manning" in text, label
        assert label.lower() in text.lower() or label.split()[0].lower() in text.lower()
        sentences = [s for s in text.replace("!", ".").split(".") if s.strip()]
        assert len(sentences) >= 3, f"{label}: {text}"
        # Never the old generic one-liner.
        assert f"{label} leads the SEC QBs cohort." not in text


def test_exposure_cites_earned_channels_and_actionability():
    text = _text("Exposure")
    assert "news" in text.lower()
    assert "search" in text.lower() or "Wikipedia" in text
    assert "activation" in text.lower() or "campaign" in text.lower() or "window" in text.lower()


def test_market_proof_cites_deals_and_negotiation_posture():
    text = _text("Market Proof")
    assert "verified deal" in text.lower()
    assert "negotiat" in text.lower() or "comp" in text.lower() or "pricing" in text.lower()


def test_momentum_cites_trajectory_and_timing():
    text = _text("Momentum")
    assert "velocity" in text.lower() or "trajectory" in text.lower() or "NIL" in text
    assert "window" in text.lower() or "timing" in text.lower() or "close" in text.lower()


def test_commercial_readiness_cites_execution_signals():
    text = _text("Commercial Readiness")
    assert "reach" in text.lower() or "engagement" in text.lower()
    assert "deliverable" in text.lower() or "package" in text.lower() or "turnaround" in text.lower()


def test_risk_cites_posture_and_protections():
    text = _text("Risk", signal="High")
    assert "risk" in text.lower()
    assert "active roster" in text.lower()
    assert "protection" in text.lower() or "clause" in text.lower() or "structure" in text.lower()


def test_sparse_data_still_produces_honest_non_generic_copy():
    sparse = {"name": "Jordan Star", "sport": "CFB", "conference": "Big 12"}
    text = build_driver_interpretation_fallback(
        athlete_name="Jordan Star",
        label="Exposure",
        signal="Low",
        cohort_label="Big 12 QBs",
        athlete_d=sparse,
        latest_dict={},
    )
    assert "Jordan Star" in text
    assert "unavailable" in text.lower() or "thin" in text.lower() or "limited" in text.lower()
    assert text != "Exposure lags the Big 12 QBs cohort."
