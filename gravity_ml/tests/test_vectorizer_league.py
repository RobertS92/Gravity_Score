"""Tests for league-tier ML feature keys."""

from gravity_ml.inference.vectorizer import build_feature_manifest


def test_college_value_manifest_excludes_target_and_pro_contracts():
    keys = build_feature_manifest("value", sport="cfb")
    # nil_valuation is the college value target. Including it as an input leaks
    # the answer and makes held-out accuracy meaningless.
    assert "nil_valuation" not in keys
    assert "contract_aav_usd" not in keys


def test_pro_manifest_uses_contracts_not_nil():
    keys = build_feature_manifest("value", sport="nfl")
    assert "contract_aav_usd" in keys
    assert "nil_valuation" not in keys
    assert "recruiting_stars" not in keys
