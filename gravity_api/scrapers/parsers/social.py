"""Social profile parsing and authenticity scoring."""

from __future__ import annotations

import re
from typing import Any

from gravity_api.scrapers.parsers.common import extract_handles, parse_count

_AGGREGATOR_URLS = (
    "https://socialblade.com/instagram/user/{handle}",
    "https://www.picuki.com/profile/{handle}",
)

MIN_REAL_INSTAGRAM_FOLLOWERS = 100

_FOLLOWER_PATTERNS = (
    re.compile(r"([\d,.]+)\s*(K|M|B)?\s*followers", re.IGNORECASE),
    re.compile(r"followers\s*\n+\s*([\d,.]+)\s*(K|M|B)?", re.IGNORECASE),
    re.compile(r"followers\s*\n+\s*([\d,.]+)", re.IGNORECASE),
    re.compile(r'"edge_followed_by":\{"count":(\d+)', re.IGNORECASE),
    re.compile(r'"follower_count":(\d+)', re.IGNORECASE),
)


def _followers_from_html(text: str) -> int | None:
    if not text:
        return None
    normalized = text.replace(",", "")
    for pat in _FOLLOWER_PATTERNS:
        m = pat.search(normalized)
        if not m:
            continue
        groups = m.groups()
        if len(groups) >= 2 and groups[1]:
            num = float(groups[0])
            suffix = (groups[1] or "").upper()
            mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
            return int(num * mult)
        try:
            return int(float(groups[0]))
        except (ValueError, TypeError):
            continue
    return None


def fetch_instagram_followers_from_text(text: str) -> int | None:
    """Parse follower count from Instagram or aggregator page markdown/html."""
    count = _followers_from_html(text)
    if count is None:
        # Last resort: explicit followers phrase only (never generic numbers).
        count = parse_count(text)
    if count is None or count < MIN_REAL_INSTAGRAM_FOLLOWERS:
        return None
    return count


def instagram_aggregator_urls(handle: str) -> list[str]:
    clean = handle.lstrip("@").strip()
    if not clean:
        return []
    return [u.format(handle=clean) for u in _AGGREGATOR_URLS] + [
        f"https://www.instagram.com/{clean}/"
    ]


def parse_engagement_from_markdown(markdown: str) -> dict[str, Any]:
    likes = [int(x.replace(",", "")) for x in re.findall(r"([\d,]+)\s+likes?", markdown, re.I)]
    comments = [
        int(x.replace(",", "")) for x in re.findall(r"([\d,]+)\s+comments?", markdown, re.I)
    ]
    posts = len(re.findall(r"^\s*(?:Photo|Video|Reel|Post)", markdown, re.I | re.M))
    avg_likes = sum(likes) / len(likes) if likes else None
    avg_comments = sum(comments) / len(comments) if comments else None
    followers_m = re.search(r"([\d,.]+)\s*(K|M)?\s*followers", markdown, re.I)
    followers = parse_count(followers_m.group(0) if followers_m else None)
    engagement_rate = None
    if followers and avg_likes is not None and followers > 0:
        engagement_rate = round(((avg_likes + (avg_comments or 0)) / followers) * 100, 4)
    return {
        "avg_likes_per_post": round(avg_likes, 2) if avg_likes is not None else None,
        "avg_comments_per_post": round(avg_comments, 2) if avg_comments is not None else None,
        "posts_sampled": max(posts, len(likes)),
        "instagram_engagement_rate": engagement_rate,
    }


def authenticity_score(
    *,
    handle: str | None,
    followers: int | None,
    verified: bool = False,
    linked_from_roster: bool = False,
    bio_text: str = "",
    bio_matches_athlete: bool = False,
) -> dict[str, Any]:
    score = 0.35
    if verified:
        score += 0.35
    if linked_from_roster:
        score += 0.2
    bio_lower = bio_text.lower()
    if bio_matches_athlete:
        score += 0.25
    if any(k in bio_lower for k in ("official", "athlete", "nil", "✓", "verified")):
        score += 0.1
    if followers and followers > 500:
        score += 0.05
    if not handle:
        score = 0.1
    score = min(1.0, score)
    return {
        "social_authenticity_score": round(score * 100, 2),
        "social_account_verified": verified or score >= 0.7,
    }


def merge_handle_sources(*sources: dict[str, str]) -> dict[str, Any]:
    """Pick best handle per platform with confidence."""
    platforms = ("instagram", "tiktok", "twitter", "youtube")
    out: dict[str, Any] = {}
    confidence = 0.5
    source_name = "unknown"
    for idx, src in enumerate(sources):
        if not src:
            continue
        weight = 0.9 - (idx * 0.15)
        for p in platforms:
            h = src.get(p)
            if h and f"{p}_handle" not in out:
                out[f"{p}_handle"] = h.lstrip("@")
                confidence = max(confidence, weight)
                source_name = src.get("_source", source_name)
    out["handle_confidence"] = round(confidence, 3)
    out["handle_source"] = source_name
    return out


def handles_from_page(text: str, source: str) -> dict[str, str]:
    found = extract_handles(text)
    found["_source"] = source
    return found
