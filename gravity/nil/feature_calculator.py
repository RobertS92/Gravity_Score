"""Minimal stub — full feature calculator was removed with connector stack."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from uuid import UUID


class FeatureCalculator:
    def calculate_all_features(
        self,
        athlete_id: UUID,
        season_id: str,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        return {"raw_metrics": {}}

    def store_features(
        self,
        athlete_id: UUID,
        season_id: str,
        features: dict[str, Any],
    ) -> uuid.UUID:
        return uuid.uuid4()
