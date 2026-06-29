"""Shared types for the partner API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

DEFAULT_SCOPES = frozenset({"scores:read", "search:read"})


@dataclass(frozen=True)
class PartnerContext:
    partner_id: Optional[uuid.UUID]
    partner_name: str
    scopes: frozenset[str]
    rate_limit_per_minute: int
    allowed_origins: Optional[tuple[str, ...]]
