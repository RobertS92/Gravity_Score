"""Common utilities shared across scraper adapters."""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

_LOGGER = logging.getLogger("nfl_gravity.scrapers")

_robot_cache: Dict[str, RobotFileParser] = {}


@dataclass(frozen=True)
class AdapterResult:
    """Structured response returned by each adapter."""

    data: Dict[str, Any]
    url: Optional[str]
    timestamp: str


class RequestError(RuntimeError):
    """Raised when a request cannot be completed after retries."""


class RequestManager:
    """Wrapper around :class:`requests.Session` that enforces polite crawling."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        min_delay: float = 0.3,
        max_delay: float = 1.0,
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.session = session or self._create_session()
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.logger = logger or _LOGGER

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        return session

    def _respect_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True

        base = f"{parsed.scheme}://{parsed.netloc}"
        parser = _robot_cache.get(base)
        if parser is None:
            robots_url = urljoin(base, "/robots.txt")
            parser = RobotFileParser()
            try:
                response = self.session.get(robots_url, timeout=5)
                response.raise_for_status()
                parser.parse(response.text.splitlines())
            except Exception as exc:  # pragma: no cover - network edge case
                self.logger.debug("Failed to read robots.txt at %s: %s", robots_url, exc)
                parser = RobotFileParser()
                parser.parse(["User-agent: *", "Allow: /"])
            _robot_cache[base] = parser

        return parser.can_fetch(DEFAULT_USER_AGENT, url)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Perform a GET request respecting robots, delays, and retries."""

        if not self._respect_robots(url):
            raise RequestError(f"Robots.txt disallows fetching {url}")

        attempt = 0
        delay = self.min_delay
        while attempt < self.max_attempts:
            attempt += 1
            try:
                self.logger.debug("Fetching %s (attempt %s)", url, attempt)
                response = self.session.get(url, timeout=kwargs.pop("timeout", 10), **kwargs)
                if response.status_code in {429, 500, 502, 503, 504}:
                    self.logger.warning("Received %s from %s", response.status_code, url)
                    time.sleep(delay)
                    delay *= self.backoff_factor
                    continue
                response.raise_for_status()
                time.sleep(random.uniform(self.min_delay, self.max_delay))
                return response
            except requests.RequestException as exc:
                if attempt >= self.max_attempts:
                    raise RequestError(f"Failed to fetch {url}: {exc}") from exc
                self.logger.warning("Request error for %s: %s (retrying)", url, exc)
                time.sleep(delay)
                delay *= self.backoff_factor
        raise RequestError(f"Unable to fetch {url}")


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def log_request(
    adapter: str,
    athlete: str,
    url: Optional[str],
    status: str,
    elapsed_ms: float,
    fields_found: Iterable[str],
) -> None:
    """Emit a structured log line for a scraping attempt."""

    payload = {
        "adapter": adapter,
        "athlete": athlete,
        "url": url,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 2),
        "fields_found": sorted(set(fields_found)),
    }
    _LOGGER.info(json.dumps(payload, sort_keys=True))


def normalise_handle(handle: str) -> str:
    """Return a normalised social handle for comparison."""

    return handle.lower().lstrip("@")


def fields_with_values(data: Dict[str, Any]) -> Iterable[str]:
    """Yield keys that have non-empty values."""

    for key, value in data.items():
        if value not in (None, "", [], {}):
            yield key


def to_int(value: str) -> Optional[int]:
    """Convert a numeric string into an integer when possible."""

    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def timed(func: Callable[..., AdapterResult]) -> Callable[..., AdapterResult]:
    """Decorator that measures execution time and records structured logs."""

    def wrapper(*args: Any, **kwargs: Any) -> AdapterResult:
        athlete = kwargs.get("athlete") or (args[0] if args else "unknown")
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            status = "success"
            data = result.data
        except Exception:
            status = "error"
            data = {}
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            url = kwargs.get("source_url")
            fields = fields_with_values(data) if isinstance(data, dict) else []
            log_request(func.__name__, str(athlete), url, status, elapsed_ms, fields)
        return result

    return wrapper


__all__ = [
    "AdapterResult",
    "RequestError",
    "RequestManager",
    "utc_now_iso",
    "log_request",
    "normalise_handle",
    "fields_with_values",
    "to_int",
    "timed",
]
