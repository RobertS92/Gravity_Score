"""Social profile parsing and authenticity scoring."""

from __future__ import annotations

import re
from typing import Any

from gravity_api.scrapers.parsers.common import extract_handles, parse_count


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
) -> dict[str, Any]:
    score = 0.35
    if verified:
        score += 0.35
    if linked_from_roster:
        score += 0.2
    bio_lower = bio_text.lower()
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
