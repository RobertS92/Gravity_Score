"""Risk score helpers.

The persisted model score is a raw risk score where larger means riskier.
Across API and UI surfaces we expose an inverted orientation where larger means safer.
"""

from __future__ import annotations

from typing import Optional


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def invert_risk_score(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return clamp_score(100.0 - value)

