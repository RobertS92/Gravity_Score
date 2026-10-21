"""P0: women's basketball guard must not resolve to football OL / male pronouns.

Regression for JuJu Watkins (ESPN 5175946): profile showed Guard/G while CSC
analysis labeled the cohort as OLs and used him/he language.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from gravity_api.feature_engineering.positions import derive_position_group as fe_derive
from gravity_api.services.csc_report_builder import (
    _position_group_value,
    build_csc_report_json,
    build_driver_interpretation_fallback,
    pronouns_for_athlete_sport,
)
from gravity_api.services.position_group_match import (
    canonical_feature_sport,
    derive_position_group,
    position_aliases_for_group,
)


def test_basketball_g_is_pg_not_ol():
    assert fe_derive("G", "ncaab_womens") == "PG"
    assert fe_derive("G", "ncaab_mens") == "PG"
    assert fe_derive("C", "ncaab_womens") == "C"
    assert derive_position_group("G", "NCAAW") == "PG"
    assert derive_position_group("G", "ncaab_womens") == "PG"
    assert derive_position_group("C", "NCAAW") == "C"
    # Football still maps guard/center tokens to OL.
    assert derive_position_group("G", "CFB") == "OL"
    assert derive_position_group("C", "cfb") == "OL"
    # Legacy sport-agnostic path remains football-first.
    assert derive_position_group("G") == "OL"


def test_canonical_feature_sport_maps_ncaaw():
    assert canonical_feature_sport("NCAAW") == "ncaab_womens"
    assert canonical_feature_sport("wcbb") == "ncaab_womens"
    assert canonical_feature_sport("ncaab_womens") == "ncaab_womens"
    assert canonical_feature_sport("CFB") == "cfb"


def test_basketball_aliases_do_not_use_ol_for_g():
    pg_aliases = position_aliases_for_group("PG", "NCAAW")
    assert "G" in pg_aliases
    ol_aliases = position_aliases_for_group("OL", "NCAAW")
    # OL is not a basketball group; sport-aware aliases fall back to the key only.
    assert "G" not in ol_aliases


def test_position_group_value_rejects_stale_ol_on_ncaaw():
    athlete = {
        "name": "JuJu Watkins",
        "sport": "NCAAW",
        "position": "G",
        "position_group": "OL",  # corrupt / football-first write
        "conference": "Big Ten",
    }
    assert _position_group_value(athlete, {}, "NCAAW") == "PG"
    assert _position_group_value(athlete, {"position": "G"}, "NCAAW") == "PG"
    assert _position_group_value(
        {"sport": "CFB", "position": "G", "position_group": None}, {}, "CFB"
    ) == "OL"


def test_pronouns_for_womens_sports():
    assert pronouns_for_athlete_sport("NCAAW")["object"] == "her"
    assert pronouns_for_athlete_sport("ncaab_womens")["object"] == "her"
    assert pronouns_for_athlete_sport("WNBA")["object"] == "her"
    assert pronouns_for_athlete_sport("CFB")["object"] == "him"
    assert pronouns_for_athlete_sport("NCAAB")["object"] == "him"


def test_driver_fallback_uses_her_for_ncaaw():
    text = build_driver_interpretation_fallback(
        athlete_name="JuJu Watkins",
        label="Brand Strength",
        signal="High",
        cohort_label="Big Ten PGs",
        athlete_d={
            "name": "JuJu Watkins",
            "sport": "NCAAW",
            "instagram_followers": 1_500_000,
            "news_mentions_30d": 40,
            "school": "USC",
            "conference": "Big Ten",
        },
        latest_dict={"brand_score": 84.0},
    )
    assert "JuJu Watkins" in text
    assert "him" not in text.lower()
    assert " her " in f" {text.lower()} " or "places her" in text.lower()


class _FakeDb:
    def __init__(self, athlete, latest_score):
        self._athlete = athlete
        self._latest_score = latest_score
        self._cohort_call = 0

    async def fetchrow(self, query, *args):
        if "FROM athletes WHERE id = $1" in query:
            return self._athlete
        if "jsonb_typeof(shap_values)" in query:
            return None
        if "FROM athlete_gravity_scores" in query:
            return self._latest_score
        if "FROM season_states" in query:
            return {"state": "in_season", "cohort_window_days": 21}
        if "SELECT current_phase FROM csc_tier_rollout" in query:
            return {"current_phase": "phase1"}
        if "FROM csc_tier_account_overrides" in query:
            return None
        return None

    async def fetch(self, query, *args):
        if "FROM exposure_formulas" in query:
            return [
                {
                    "version": "exposure_formula_v1",
                    "proximity_weight": 0.6,
                    "velocity_weight": 0.4,
                    "is_active": True,
                }
            ]
        if "FROM comparable_sets cs" in query:
            return []
        if "WITH latest AS" in query:
            return []
        if "ORDER BY ABS(s.gravity_score - $5) ASC" in query:
            return []
        return []

    async def fetchval(self, query, *args):
        if "SELECT MIN(calculated_at)" in query:
            return datetime.now(tz=timezone.utc) - timedelta(days=45)
        return None


def test_csc_report_juju_cohort_is_pg_not_ol(monkeypatch):
    monkeypatch.setenv("CSC_REPORT_LLM_ENABLED", "0")
    athlete = {
        "id": "juju-1",
        "name": "JuJu Watkins",
        "sport": "NCAAW",
        "conference": "Big Ten",
        "position": "G",
        "position_group": None,
        "school": "USC",
        "nil_valuation_raw": 820_000,
        "instagram_followers": 1_500_000,
        "news_mentions_30d": 50,
    }
    score = {
        "gravity_score": 79.6,
        "brand_score": 84.0,
        "proof_score": 76.0,
        "proximity_score": 78.0,
        "velocity_score": 74.0,
        "risk_score": 16.0,
        "confidence": 0.8,
        "dollar_p10_usd": 680_000,
        "dollar_p50_usd": 820_000,
        "dollar_p90_usd": 1_050_000,
        "model_version": "v3.2",
        "calculated_at": "2026-10-01T10:15:00Z",
        "shap_values": {"brand_fit": 0.4},
    }
    db = _FakeDb(athlete, score)
    report = asyncio.run(build_csc_report_json(db, "juju-1", {}))

    cohort = report["detail"]["blocks"]["cohort"]
    assert cohort["sport"] == "NCAAW"
    assert cohort["position_group"] == "PG"
    assert cohort["position_group"] != "OL"

    assert report["metadata"]["position_group"] == "PG"
    assert report["metadata"]["object_pronoun"] == "her"

    # Cohort label / comparable tier must not say OLs.
    blob = " ".join(
        [
            report["validation"]["comparable_tier"],
            report["detail"]["inputs"],
            report["explanation"]["executive_summary"],
            *[d["explanation"] for d in report["explanation"]["key_value_drivers"]],
        ]
    ).lower()
    assert " ol" not in f" {blob} " and "ols" not in blob
    assert "him" not in blob
