"""Prop-shop style scraper primitives (queue + circuit breaker). Optional Redis later."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

COLLECTOR_MAP: Dict[str, List[str]] = {
    "transfer_portal": ["identity", "proximity", "risk"],
    "injury_report": ["risk", "velocity"],
    "nil_deal": ["proximity", "brand", "velocity"],
    "social_delta": ["brand", "velocity"],
    "stat_update": ["proof", "velocity"],
    "scheduled_full": ["identity", "brand", "proof", "proximity", "velocity", "risk"],
    "school_submission": ["identity", "proof", "brand"],
}


class CircuitOpenError(Exception):
    pass


class SourceCircuitBreaker:
    def __init__(
        self,
        source: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,
    ):
        self.source = source
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def call(self, fn: Callable[[], T], *args: Any, **kwargs: Any) -> T:
        with self._lock:
            if self.state == "open":
                if self.last_failure_time and time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "half-open"
                else:
                    raise CircuitOpenError(f"{self.source} circuit open")
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.state = "closed"

    def _on_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.critical(
                    "Circuit OPEN: %s — %s consecutive failures",
                    self.source,
                    self.failure_count,
                )

    def reset(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.state = "closed"
            self.last_failure_time = None

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "source": self.source,
                "state": self.state,
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time,
            }


@dataclass
class ScraperPipelineState:
    """Process-local queue + circuit breakers (replace with Redis Streams in gravity-scrapers)."""

    priorities: Dict[str, Deque[Dict[str, Any]]] = field(
        default_factory=lambda: {f"P{i}": deque(maxlen=10_000) for i in range(5)}
    )
    circuits: Dict[str, SourceCircuitBreaker] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for src in ("espn", "sports_reference", "on3", "firecrawl", "social"):
            self.circuits[src] = SourceCircuitBreaker(src)

    def enqueue(self, priority: str, event: Dict[str, Any]) -> None:
        if priority not in self.priorities:
            priority = "P3"
        self.priorities[priority].append(event)

    def queue_depth(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self.priorities.items()}

    def circuit_states(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.circuits.values()]


STATE = ScraperPipelineState()
