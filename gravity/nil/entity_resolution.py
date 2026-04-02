"""Minimal stub — full NIL entity resolution was removed with connector stack."""

from __future__ import annotations

import uuid
from typing import Any


class EntityResolver:
    def create_or_resolve_athlete(self, **kwargs: Any) -> tuple[str, bool, float]:
        return str(uuid.uuid4()), True, 0.5
