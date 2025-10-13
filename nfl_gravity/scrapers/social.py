"""Social platform scraping adapters."""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .discovery import FirecrawlDiscovery
from .utils import AdapterResult, RequestManager, fields_with_values, log_request, to_int, utc_now_iso


def _handle_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    handle = parts[0]
    if handle.startswith("@"):  # TikTok often includes @
        handle = handle[1:]
    return handle


def fetch_twitter_profile(
    athlete: str,
    discovery: Optional[FirecrawlDiscovery] = None,
    session: Optional[RequestManager] = None,
) -> AdapterResult:
    start = time.perf_counter()
    data: Dict[str, Optional[str]] = {}
    manager = session or RequestManager()
    url: Optional[str] = None
    disc = discovery
    if disc is None:
        try:
            disc = FirecrawlDiscovery()
        except Exception:
            disc = None
    if disc is not None:
        for domain in ("https://x.com", "https://twitter.com"):
            try:
                url = disc.discover(athlete, domain, keyword="twitter")
            except Exception:
                url = None
            if url:
                break
    if url:
        handle = _handle_from_url(url)
        if handle:
            data["handle"] = handle
            info_url = (
                "https://cdn.syndication.twimg.com/widgets/followbutton/info.json?screen_names="
                f"{handle}"
            )
            try:
                response = manager.get(info_url)
                payload = response.json()
                if isinstance(payload, list) and payload:
                    entry = payload[0]
                    followers = entry.get("followers_count")
                    data["followers_count"] = to_int(str(followers)) if followers is not None else None
                    data["verified"] = entry.get("verified")
            except Exception:
                data["followers_count"] = None
                data["verified"] = None
    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("twitter", athlete, url, "success" if data else "empty", elapsed, list(fields_with_values(data)))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


def fetch_instagram_profile(
    athlete: str,
    discovery: Optional[FirecrawlDiscovery] = None,
) -> AdapterResult:
    start = time.perf_counter()
    url: Optional[str] = None
    data: Dict[str, Optional[str]] = {"followers_count": None}
    disc = discovery
    if disc is None:
        try:
            disc = FirecrawlDiscovery()
        except Exception:
            disc = None
    if disc is not None:
        try:
            url = disc.discover(athlete, "https://www.instagram.com", keyword="instagram")
        except Exception:
            url = None
    if url:
        handle = _handle_from_url(url)
        if handle:
            data["handle"] = handle
    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("instagram", athlete, url, "success" if data else "empty", elapsed, list(fields_with_values(data)))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


def fetch_tiktok_profile(
    athlete: str,
    discovery: Optional[FirecrawlDiscovery] = None,
    session: Optional[RequestManager] = None,
) -> AdapterResult:
    start = time.perf_counter()
    url: Optional[str] = None
    manager = session or RequestManager()
    data: Dict[str, Optional[str]] = {}
    disc = discovery
    if disc is None:
        try:
            disc = FirecrawlDiscovery()
        except Exception:
            disc = None
    if disc is not None:
        try:
            url = disc.discover(athlete, "https://www.tiktok.com", keyword="tiktok")
        except Exception:
            url = None
    html: Optional[str] = None
    if url:
        try:
            html = manager.get(url).text
        except Exception:
            html = None
    if html:
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", id="SIGI_STATE")
        if script and script.string:
            try:
                state = json.loads(script.string)
                user_module = state.get("UserModule", {})
                handles = user_module.get("users", {})
                handle = _handle_from_url(url)
                if handle and handle in handles:
                    profile = handles[handle]
                else:
                    profile = next(iter(handles.values())) if handles else {}
                stats = user_module.get("stats", {}).get(profile.get("id"), {})
                if profile:
                    data["handle"] = profile.get("uniqueId")
                if stats:
                    followers = stats.get("followerCount")
                    data["followers_count"] = int(followers) if isinstance(followers, (int, float)) else to_int(str(followers))
                items = state.get("ItemModule", {})
                recent: List[Dict[str, Optional[int]]] = []
                for _, item in list(items.items())[:3]:
                    stats_block = item.get("stats", {})
                    recent.append(
                        {
                            "id": item.get("id"),
                            "play_count": int(stats_block.get("playCount", 0)) if stats_block.get("playCount") else None,
                            "digg_count": int(stats_block.get("diggCount", 0)) if stats_block.get("diggCount") else None,
                        }
                    )
                if recent:
                    data["recent_videos"] = recent
            except json.JSONDecodeError:
                pass
    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("tiktok", athlete, url, "success" if data else "empty", elapsed, list(fields_with_values(data)))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


def fetch_youtube_channel(
    athlete: str,
    discovery: Optional[FirecrawlDiscovery] = None,
    session: Optional[RequestManager] = None,
) -> AdapterResult:
    start = time.perf_counter()
    manager = session or RequestManager()
    url: Optional[str] = None
    disc = discovery
    if disc is None:
        try:
            disc = FirecrawlDiscovery()
        except Exception:
            disc = None
    if disc is not None:
        try:
            url = disc.discover(athlete, "https://www.youtube.com", keyword="youtube")
        except Exception:
            url = None
    data: Dict[str, Optional[str]] = {}
    if url:
        handle = _handle_from_url(url)
        if handle:
            data["handle"] = handle
        try:
            html = manager.get(url).text
            soup = BeautifulSoup(html, "lxml")
            subscriber_meta = soup.find("meta", itemprop="subscriberCount")
            if subscriber_meta and subscriber_meta.get("content"):
                data["subscribers"] = to_int(str(subscriber_meta["content"]))
        except Exception:
            pass
    timestamp = utc_now_iso()
    elapsed = (time.perf_counter() - start) * 1000
    log_request("youtube", athlete, url, "success" if data else "empty", elapsed, list(fields_with_values(data)))
    return AdapterResult(data=data, url=url, timestamp=timestamp)


__all__ = [
    "fetch_twitter_profile",
    "fetch_instagram_profile",
    "fetch_tiktok_profile",
    "fetch_youtube_channel",
]
