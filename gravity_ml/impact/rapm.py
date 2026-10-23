"""Basketball stint RAPM (SCORING_ML_FIX_SPEC §4 I2).

Requires ESPN play-by-play substitution data reconstructing lineups for ≥80% of
possessions. Stub until scraper WP10 play-by-play ingestion lands.
"""

from __future__ import annotations

from gravity_ml.impact import BLOCKED_REASON


class RapmBlocked(NotImplementedError):
    """RAPM needs lineup-reconstructable PBP — not available yet."""


def fit_rapm(*_args, **_kwargs):  # noqa: ANN001
    raise RapmBlocked(
        "I2 RAPM blocked: need possession-level lineups covering ≥80% of "
        f"possessions per game. {BLOCKED_REASON}"
    )


__all__ = ["RapmBlocked", "fit_rapm"]
