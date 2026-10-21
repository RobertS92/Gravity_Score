"""Season-year scoring anchor: never relabel prior seasons as current."""

from __future__ import annotations

from gravity_api.scrapers.parsers.espn_stats import _season_label_to_key
from gravity_api.services.sport_pipeline.season_stats import (
    _parse_season_year,
    resolve_scoring_season_year,
)


def test_parse_split_season_uses_ending_year():
    assert _parse_season_year("2024-25", fallback=2026) == 2025
    assert _parse_season_year("2024-2025", fallback=2026) == 2025
    assert _parse_season_year("2024 Regular Season", fallback=2026) == 2024
    assert _parse_season_year(2023, fallback=2026) == 2023


def test_espn_season_label_split_years():
    assert _season_label_to_key("2024-25 Regular Season") == "2025"
    assert _season_label_to_key("2024 Regular Season") == "2024"


def test_resolve_prefers_current_with_games():
    resolved = resolve_scoring_season_year(
        [2024, 2025, 2026],
        current_year=2026,
        games_by_year={2024: 12, 2025: 14, 2026: 6},
    )
    assert resolved["source_season_year"] == 2026
    assert resolved["policy"] == "current_in_progress"


def test_resolve_falls_back_to_completed_not_relabel():
    """When current has no games, use prior year as source — do not claim it is 2026."""
    resolved = resolve_scoring_season_year(
        [2023, 2024, 2025],
        current_year=2026,
        games_by_year={2023: 12, 2024: 13, 2025: 14},
    )
    assert resolved["source_season_year"] == 2025
    assert resolved["season_year"] == 2025
    assert resolved["policy"] == "latest_completed"


def test_resolve_two_year_stale_history():
    """Thin history (only 2023/2024) must surface as 2024, not masquerade as 2026."""
    resolved = resolve_scoring_season_year(
        [2023, 2024],
        current_year=2026,
        games_by_year={2023: 10, 2024: 12},
    )
    assert resolved["source_season_year"] == 2024
    assert resolved["policy"] == "latest_completed"


def test_team_record_needs_refresh_on_relabeled_prior():
    from gravity_api.services.team_season_records import _team_record_needs_refresh

    class _Row(dict):
        def get(self, k, default=None):
            return super().get(k, default)

        def __getitem__(self, k):
            return super().__getitem__(k)

    fresh = _Row(wins=8, losses=2, metadata={"espn_season_year": 2026})
    assert _team_record_needs_refresh(fresh, season_year=2026) is False

    prior = _Row(wins=10, losses=3, metadata={"espn_season_year": 2025})
    assert _team_record_needs_refresh(prior, season_year=2026) is True

    empty = _Row(wins=0, losses=0, metadata={})
    assert _team_record_needs_refresh(empty, season_year=2026) is True
