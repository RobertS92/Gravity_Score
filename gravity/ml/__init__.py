"""Stage 1 Gravity Score: feature engineering, training, SHAP, inference."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["GravityResult", "score_athlete"]

if TYPE_CHECKING:
    from gravity.ml.inference import GravityResult as GravityResult
    from gravity.ml.inference import score_athlete as score_athlete


def __getattr__(name: str) -> Any:
    if name == "GravityResult":
        from gravity.ml.inference import GravityResult as _GR

        return _GR
    if name == "score_athlete":
        from gravity.ml.inference import score_athlete as _sa

        return _sa
    raise AttributeError(name)
