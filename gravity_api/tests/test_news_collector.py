"""Unit tests for the news collector classifier.

These pin down the classifier's behavior so we don't regress when
adding new rules.  Network calls (RSS pulls, article body fetch) are
covered by the live smoke test in CI / manual triggers, not here.
"""

from __future__ import annotations

import pytest

from gravity_api.services.news_collector import (
    FEED_REGISTRY,
    classify_text,
)


class TestClassifier:
    @pytest.mark.parametrize(
        "title,expected",
        [
            # NIL deals — clear signal
            ("Star QB signs NIL deal with Raising Cane's", "NIL_DEAL"),
            ("Top recruit announces brand partnership with Nike", "NIL_DEAL"),
            ("Star inks endorsement deal with Gatorade", "NIL_DEAL"),
            # Transfer portal
            ("Five-star QB enters the transfer portal", "TRANSFER"),
            ("CB transferring to USC after one season", "TRANSFER"),
            # Injury
            ("Heisman frontrunner out for season with torn ACL", "INJURY"),
            ("RB sidelined for two weeks with sprained ankle", "INJURY"),
            # Incidents
            ("Linebacker arrested on misdemeanor charge", "INCIDENT"),
            ("Coach suspended after investigation into NCAA rules", "INCIDENT"),
            # Recruiting
            ("Five-star prospect commits to Alabama", "RECRUITING"),
            ("Class of 2027 quarterback decommits from LSU", "RECRUITING"),
            # Awards
            ("RB named All-American by AP", "AWARD"),
            ("QB wins Heisman Trophy", "AWARD"),
            ("Player of the week honors go to ...", "AWARD"),
            # Business
            ("Big Ten signs new TV rights deal worth billions", "BUSINESS"),
            ("Texas A&M collective raises $5M", "BUSINESS"),
            # Announcements / NFL Draft
            ("RB declares for NFL Draft", "ANNOUNCEMENT"),
            ("Carson Beck selected by Cardinals in 3rd round of NFL Draft", "ANNOUNCEMENT"),
            ("New head coach hired at Florida State", "ANNOUNCEMENT"),
            # Performance
            ("QB threw for 450 yards and 5 TDs", "PERFORMANCE"),
            ("RB breaks school record", "PERFORMANCE"),
            # Ranking
            ("Alabama climbs to No. 3 in AP Top 25", "RANKING"),
            ("Georgia drops in Coaches Poll", "RANKING"),
            # Catch-all
            ("Random preseason scrimmage update", "NEWS"),
        ],
    )
    def test_classification(self, title: str, expected: str) -> None:
        cat, conf = classify_text(title, "")
        assert cat == expected, f"{title!r} → got {cat}, want {expected}"
        assert 0.0 < conf <= 1.0

    def test_nfl_draft_does_not_become_nil_deal(self) -> None:
        # The bug we fixed: NFL Draft headlines were incorrectly tagged
        # NIL_DEAL because the On3 feed defaulted to NIL_DEAL and the
        # classifier returned NEWS as a fallback.  ANNOUNCEMENT must
        # win at the rule level so feed default never overrides.
        cat, _ = classify_text("Carson Beck drafted in 3rd round of NFL Draft", "")
        assert cat == "ANNOUNCEMENT"

    def test_transfer_priority_over_news(self) -> None:
        # Transfer portal mentions must beat the catch-all NEWS rule
        # even when other words are present.
        cat, _ = classify_text(
            "Big news: Star QB enters the transfer portal after spring practice",
            "",
        )
        assert cat == "TRANSFER"

    def test_classifier_returns_news_for_empty_text(self) -> None:
        cat, conf = classify_text("", "")
        # Empty text shouldn't match the NEWS catch-all (which requires
        # at least one character) — should be NEWS with low confidence.
        # NEWS rule pattern .+ requires at least one char, so empty
        # falls through.  Verify graceful behavior.
        assert cat == "NEWS"
        assert conf <= 0.5


class TestFeedRegistry:
    def test_every_registered_feed_has_a_known_domain(self) -> None:
        # Every feed must reference a publisher we have in the trust
        # allowlist (news_sources table).  Hardcoded list mirrors the
        # migration so a typo in a new FeedSpec is caught at test time.
        allowlist = {
            "espn.com",
            "espn.go.com",
            "apnews.com",
            "reuters.com",
            "si.com",
            "yahoo.com",
            "sports.yahoo.com",
            "cbssports.com",
            "foxsports.com",
            "nbcsports.com",
            "theathletic.com",
            "247sports.com",
            "on3.com",
            "rivals.com",
            "sportico.com",
            "frontofficesports.com",
            "sportsbusinessjournal.com",
            "bleacherreport.com",
        }
        for spec in FEED_REGISTRY:
            assert spec.domain in allowlist, (
                f"{spec.name} ({spec.domain}) not in trust allowlist"
            )

    def test_feed_registry_covers_target_categories(self) -> None:
        from gravity_api.services.news_collector import TARGET_CATEGORIES

        # Every category the user wants should either:
        #   (a) have a dedicated/default feed, OR
        #   (b) be inferable from a general feed via classifier rules
        # Today (b) covers everything except SCORE/ROSTER/etc which
        # come from internal computation, so we just assert every
        # target category has at least one classifier rule.
        from gravity_api.services.news_collector import CATEGORY_RULES

        rule_cats = {r.category for r in CATEGORY_RULES}
        for cat in TARGET_CATEGORIES:
            assert cat in rule_cats, (
                f"{cat} has no classifier rule — feed will never produce it"
            )
