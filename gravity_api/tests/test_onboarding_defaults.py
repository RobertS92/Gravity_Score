"""Unit tests for onboarding_defaults (no DB)."""

import pytest

from gravity_api.services import onboarding_defaults as od


def test_normalize_sport_preferences_dedup_and_order():
    assert od.normalize_sport_preferences(["NCAAB", "CFB", "NCAAB"]) == ["NCAAB", "CFB"]


def test_normalize_sport_preferences_invalid():
    with pytest.raises(ValueError, match="Invalid sport"):
        od.normalize_sport_preferences(["NFL"])


def test_normalize_sport_preferences_empty():
    with pytest.raises(ValueError, match="at least one sport"):
        od.normalize_sport_preferences([])


def test_assert_org_type_ok():
    assert od.assert_org_type(" SCHOOL ") == "school"


def test_assert_org_type_invalid():
    with pytest.raises(ValueError, match="org_type"):
        od.assert_org_type("startup")


@pytest.mark.parametrize(
    "org, tab",
    [
        ("school", "roster"),
        ("nil_collective", "market"),
        ("brand_agency", "athletes"),
        ("law_firm_agent", "deals"),
        ("insurance_finance", "athletes"),
        ("media_research", "market"),
    ],
)
def test_default_dashboard_tab_for_org_type(org: str, tab: str):
    assert od.default_dashboard_tab_for_org_type(org) == tab


def test_default_athletes_sort():
    assert od.default_athletes_sort_for_org_type("insurance_finance") == "risk_desc"
    assert od.default_athletes_sort_for_org_type("brand_agency") == "gravity_desc"
    assert od.default_athletes_sort_for_org_type("school") is None


def test_valid_dashboard_tabs_contains_expected():
    assert {"roster", "market", "athletes", "deals"} == od.VALID_DASHBOARD_TABS
