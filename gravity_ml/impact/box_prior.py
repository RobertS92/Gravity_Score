"""Box-score prior for low-sample players (SCORING_ML_FIX_SPEC §4 I4).

Regresses APM/RAPM estimates on per-season box rates. Stub until I1 produces
live posteriors on WP10 game data.
"""

from __future__ import annotations

from gravity_ml.impact import BLOCKED_REASON


class BoxPriorBlocked(NotImplementedError):
    pass


def fit_box_prior(*_args, **_kwargs):  # noqa: ANN001
    raise BoxPriorBlocked(
        "I4 box prior needs I1/I2/I3 estimates on high-participation player-seasons. "
        f"{BLOCKED_REASON}"
    )


__all__ = ["BoxPriorBlocked", "fit_box_prior"]
