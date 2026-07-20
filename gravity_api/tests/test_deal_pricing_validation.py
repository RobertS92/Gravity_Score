import json
from pathlib import Path

import pytest

from gravity_api.services.deal_pricing_validation import evaluate_public_collective_panel


FIXTURE = Path(__file__).resolve().parents[1] / "validation" / "public_collective_stress_20.json"


def _cases():
    return json.loads(FIXTURE.read_text())["cases"]


def test_public_panel_has_twenty_distinct_athletes_and_at_least_five_qbs():
    cases = _cases()
    assert len(cases) == 20
    assert len({case["athlete"] for case in cases}) == 20
    assert sum(case["position_group"] == "QB" for case in cases) >= 5
    assert all(case["reported_low_usd"] > 0 for case in cases)
    assert all(case["reported_high_usd"] >= case["reported_low_usd"] for case in cases)


def test_public_collective_stress_exposes_scope_gap_in_baseline_and_aggressive_profiles():
    baseline = evaluate_public_collective_panel(_cases(), profile="baseline")
    aggressive = evaluate_public_collective_panel(_cases(), profile="aggressive")

    assert baseline["n"] == aggressive["n"] == 20
    assert baseline["qb_n"] == aggressive["qb_n"] == 8
    assert baseline["coverage"] == 0.0
    assert aggressive["coverage"] == 0.05
    assert aggressive["qb_coverage"] == 0.0
    assert baseline["median_signed_percentage_error"] < -0.70
    assert aggressive["median_signed_percentage_error"] < -0.65


def test_unknown_public_stress_profile_is_rejected():
    with pytest.raises(ValueError, match="unknown signal profile"):
        evaluate_public_collective_panel(_cases(), profile="unknown")
