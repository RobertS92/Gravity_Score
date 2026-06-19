import json
from datetime import datetime, timedelta, timezone

from gravity_api.services.athlete_enrichment import (
    enrich_athlete_dict,
    parse_raw_data,
    score_delta_30d,
    social_signal_fields,
    value_delta_30d,
)


def test_parse_raw_data_handles_dict_str_and_garbage():
    assert parse_raw_data({"a": 1}) == {"a": 1}
    assert parse_raw_data(json.dumps({"b": 2})) == {"b": 2}
    assert parse_raw_data(None) == {}
    assert parse_raw_data("") == {}
    assert parse_raw_data("not json") == {}
    assert parse_raw_data("[1, 2, 3]") == {}  # non-object JSON


def test_social_signal_fields_prefers_raw_then_snapshot():
    raw = {
        "instagram_followers": 500_000,
        "google_trends_score": 71,
        "news_count_30d": 14,
        "nil_valuation": 21_900_000,
    }
    snap = {
        "instagram_followers": 1,  # should be ignored (raw wins)
        "twitter_followers": 120_000,
        "instagram_engagement_rate": 6.2,
        "news_mentions_30d": 99,  # raw news_count_30d wins
    }
    fields = social_signal_fields(raw, snap)
    assert fields["instagram_followers"] == 500_000
    assert fields["twitter_followers"] == 120_000
    assert fields["instagram_engagement_rate"] == 6.2
    # raw news_count_30d takes precedence over snapshot news_mentions_30d
    assert fields["news_mentions_30d"] == 14
    assert fields["google_trends_score"] == 71
    assert fields["nil_valuation_raw"] == 21_900_000
    assert fields["social_combined_reach"] == 620_000.0


def test_social_signal_fields_never_fabricates_when_empty():
    fields = social_signal_fields({}, None)
    assert fields["instagram_followers"] is None
    assert fields["social_combined_reach"] is None
    assert fields["news_mentions_30d"] is None


def test_enrich_does_not_clobber_existing_values_with_none():
    athlete = {"conference": "SEC", "verified_deals_count": 5}
    enrich_athlete_dict(
        athlete,
        raw_signals={},
        snap=None,
        conference="Big 12",
        verified_deals_count=None,
    )
    # Resolved conference overrides the stored row value.
    assert athlete["conference"] == "Big 12"
    # Existing deal count is preserved when no fresh count is supplied.
    assert athlete["verified_deals_count"] == 5
    # Missing social keys exist (as None) so the UI renders N/A, not KeyError.
    assert "instagram_followers" in athlete


def test_enrich_fills_signals_and_deltas():
    athlete = {"name": "Arch", "conference": ""}
    enrich_athlete_dict(
        athlete,
        raw_signals={"instagram_followers": 750_000, "nil_valuation": 21_900_000},
        conference="SEC",
        verified_deals_count=3,
        gravity_delta_30d=4.2,
        nil_valuation_delta_30d=1_500_000.0,
    )
    assert athlete["instagram_followers"] == 750_000
    assert athlete["conference"] == "SEC"
    assert athlete["verified_deals_count"] == 3
    assert athlete["gravity_delta_30d"] == 4.2
    assert athlete["nil_valuation_delta_30d"] == 1_500_000.0


def _ts(days_ago: float) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=days_ago)


def test_score_delta_30d_picks_closest_to_30d():
    scores = [
        {"gravity_score": 80.0, "calculated_at": _ts(0)},
        {"gravity_score": 75.0, "calculated_at": _ts(31)},  # closest to 30d
        {"gravity_score": 60.0, "calculated_at": _ts(90)},
    ]
    assert score_delta_30d(scores) == 5.0


def test_score_delta_30d_requires_two_points():
    assert score_delta_30d([{"gravity_score": 80.0, "calculated_at": _ts(0)}]) is None
    assert score_delta_30d([]) is None


def test_value_delta_30d_with_iso_strings():
    series = [
        (_ts(0).isoformat(), 21_900_000),
        (_ts(30).isoformat(), 20_400_000),
    ]
    assert value_delta_30d(series) == 1_500_000.0
