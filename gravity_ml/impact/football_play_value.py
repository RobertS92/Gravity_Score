"""CFB play value from CFBD PPA / WPA (SCORING_ML_FIX_SPEC §4 I3).

Blocked until scraper WP10 fills ``cfb_plays`` / ``cfb_play_players``.
"""

from __future__ import annotations

from gravity_ml.impact import BLOCKED_REASON


class FootballPlayValueBlocked(NotImplementedError):
    pass


def aggregate_play_value(*_args, **_kwargs):  # noqa: ANN001
    raise FootballPlayValueBlocked(
        "I3 needs CFBD plays + play_players (PPA, WPA, roles). " + BLOCKED_REASON
    )


__all__ = ["FootballPlayValueBlocked", "aggregate_play_value"]
