"""Instagram handle discovery, bio verification, and multi-source consensus."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from gravity_api.scrapers.parsers.common import extract_handles
from gravity_api.scrapers.parsers.social import (
    MIN_REAL_INSTAGRAM_FOLLOWERS,
    authenticity_score,
    handles_from_page,
)

AUTO_TRUST_SOURCES = frozenset({"espn", "user"})
TRUSTED_PROMOTED_SOURCES = frozenset({"espn", "user", "consensus", "bio_verified"})
CONSENSUS_MIN_SOURCES = 2
MIN_AUTHENTICITY_SCORE = 50.0

_SPORT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cfb": ("football", "cfb", "quarterback", "linebacker", "wide receiver"),
    "nfl": ("nfl", "football"),
    "ncaab_mens": ("basketball", "hoops", "ncaa", "d1"),
    "ncaab_womens": ("basketball", "wbb", "ncaa"),
    "nba": ("nba", "basketball"),
    "wnba": ("wnba", "basketball"),
}

_BIO_PATTERNS = (
    re.compile(r"bio\s*\n+\s*(.{20,500})", re.I),
    re.compile(r"biography\s*\n+\s*(.{20,500})", re.I),
    re.compile(r'"biography"\s*:\s*"([^"]{10,500})"', re.I),
    re.compile(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', re.I),
)


def is_user_provided_instagram(raw: dict[str, Any]) -> bool:
    src = str(raw.get("instagram_handle_source") or raw.get("handle_source") or "").lower()
    return src == "user" or bool(raw.get("instagram_handle_user_provided"))


def has_trusted_instagram_handle(raw: dict[str, Any]) -> bool:
    handle = raw.get("instagram_handle")
    if not handle or not str(handle).strip():
        return False
    if is_user_provided_instagram(raw):
        return True
    src = str(raw.get("instagram_handle_source") or raw.get("handle_source") or "").lower()
    if src in TRUSTED_PROMOTED_SOURCES:
        return True
    return bool(raw.get("instagram_handle_bio_verified"))


def normalize_handle(handle: str) -> str:
    return handle.lstrip("@").strip().lower()


def name_tokens(name: str) -> list[str]:
    parts = re.split(r"[\s\-'.]+", name.lower())
    return [p for p in parts if len(p) >= 2]


def school_tokens(school: str | None) -> list[str]:
    if not school:
        return []
    stop = frozenset({"university", "college", "of", "the", "state", "at", "and"})
    return [
        w
        for w in re.split(r"[\s\-]+", school.lower())
        if w and w not in stop and len(w) >= 3
    ]


def sport_keywords(sport: str) -> tuple[str, ...]:
    return _SPORT_KEYWORDS.get(sport, (sport.replace("_", " "),))


def extract_bio_from_page(text: str) -> str:
    if not text:
        return ""
    for pat in _BIO_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    # Fallback: first substantial paragraph after handle line.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if "follower" in ln.lower() and i + 1 < len(lines):
            nxt = lines[i + 1]
            if len(nxt) >= 8 and not nxt.startswith("http"):
                return nxt
    return text[:800]


def bio_matches_athlete(
    bio: str,
    *,
    name: str,
    school: str | None,
    sport: str,
    position: str | None = None,
) -> bool:
    if not bio or not name:
        return False
    bio_l = bio.lower()
    tokens = name_tokens(name)
    if not tokens:
        return False
    if tokens[-1] not in bio_l and not any(t in bio_l for t in tokens):
        return False
    if any(s in bio_l for s in school_tokens(school)):
        return True
    if any(k in bio_l for k in sport_keywords(sport)):
        return True
    if position and len(position.strip()) >= 2 and position.strip().lower() in bio_l:
        return True
    if len(tokens) >= 2 and tokens[0] in bio_l and tokens[-1] in bio_l:
        return True
    return False


def google_instagram_search_url(name: str, school: str | None, position: str | None) -> str:
    parts = [f'"{name}"']
    if school:
        parts.append(f'"{school}"')
    if position:
        parts.append(position.strip())
    parts.append("site:instagram.com")
    q = " ".join(parts)
    return f"https://www.google.com/search?q={urllib.parse.quote(q)}"


def google_site_search_url(name: str, school: str | None, domain: str) -> str:
    parts = [f'"{name}"']
    if school:
        parts.append(f'"{school}"')
    parts.append(f"site:{domain}")
    q = " ".join(parts)
    return f"https://www.google.com/search?q={urllib.parse.quote(q)}"


def group_instagram_candidates(sources: list[dict[str, str]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for src in sources:
        handle = src.get("instagram")
        if not handle:
            continue
        key = normalize_handle(handle)
        if not key:
            continue
        grouped.setdefault(key, [])
        source_name = str(src.get("_source") or "unknown")
        if source_name not in grouped[key]:
            grouped[key].append(source_name)
    return grouped


def resolve_instagram_fields(
    sources: list[dict[str, str]],
    *,
    name: str,
    school: str | None,
    sport: str,
    position: str | None,
    bio_by_handle: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Promote handles only from ESPN (auto-trust), 2+ source consensus (+ bio), or bio verify.
    Single non-ESPN hits stay in instagram_handle_candidate.
    """
    bio_by_handle = bio_by_handle or {}
    grouped = group_instagram_candidates(sources)
    if not grouped:
        return {}

    espn_handle: str | None = None
    for src in sources:
        if src.get("_source") == "espn" and src.get("instagram"):
            espn_handle = normalize_handle(str(src["instagram"]))
            break

    out: dict[str, Any] = {}
    if espn_handle:
        out["instagram_handle"] = espn_handle
        out["instagram_handle_source"] = "espn"
        out["handle_source"] = "espn"
        out["handle_confidence"] = 0.92
        return out

    best_handle: str | None = None
    best_sources: list[str] = []
    for handle, srcs in grouped.items():
        if len(srcs) > len(best_sources):
            best_handle = handle
            best_sources = srcs

    if not best_handle:
        return {}

    bio = bio_by_handle.get(best_handle, "")
    bio_ok = bio_matches_athlete(
        bio, name=name, school=school, sport=sport, position=position
    ) if bio else False

    if len(best_sources) >= CONSENSUS_MIN_SOURCES:
        if bio_ok or not bio:
            out["instagram_handle"] = best_handle
            out["instagram_handle_source"] = "consensus"
            out["handle_source"] = "consensus"
            out["instagram_handle_sources"] = best_sources
            out["handle_confidence"] = min(0.88, 0.65 + 0.1 * len(best_sources))
            if bio_ok:
                out["instagram_handle_bio_verified"] = 1
            return out
        out["instagram_handle_candidate"] = best_handle
        out["instagram_handle_candidate_sources"] = best_sources
        out["handle_confidence"] = 0.55
        return out

    single_source = best_sources[0] if best_sources else "unknown"
    if bio_ok:
        out["instagram_handle"] = best_handle
        out["instagram_handle_source"] = "bio_verified"
        out["handle_source"] = "bio_verified"
        out["instagram_handle_bio_verified"] = 1
        out["handle_confidence"] = 0.72
        return out

    out["instagram_handle_candidate"] = best_handle
    out["instagram_handle_candidate_source"] = single_source
    out["handle_confidence"] = 0.45
    return out


def apply_user_instagram_upload(fields: dict[str, Any]) -> dict[str, Any]:
    """Normalize manual/user-provided instagram fields."""
    handle = fields.get("instagram_handle")
    if not handle or not str(handle).strip():
        return fields
    out = dict(fields)
    out["instagram_handle"] = normalize_handle(str(handle))
    out["instagram_handle_source"] = "user"
    out["handle_source"] = "user"
    out["instagram_handle_observed"] = 1
    out["instagram_handle_user_provided"] = 1
    out["handle_confidence"] = 1.0
    if out.get("instagram_followers"):
        out["instagram_followers_observed"] = 1
    return out


def passes_authenticity_gate(
    *,
    handle: str | None,
    followers: int | None,
    bio_text: str,
    name: str,
    school: str | None,
    sport: str,
    position: str | None,
    handle_source: str | None,
) -> tuple[bool, dict[str, Any]]:
    """Reject handles with low authenticity and no bio match (unless ESPN/user)."""
    src = (handle_source or "").lower()
    if src in AUTO_TRUST_SOURCES:
        auth = authenticity_score(
            handle=handle,
            followers=followers,
            linked_from_roster=src == "espn",
            bio_text=bio_text,
        )
        return True, auth

    bio_ok = bio_matches_athlete(
        bio_text, name=name, school=school, sport=sport, position=position
    )
    auth = authenticity_score(
        handle=handle,
        followers=followers,
        bio_text=bio_text,
        linked_from_roster=False,
    )
    score = float(auth.get("social_authenticity_score") or 0)
    if bio_ok and score >= MIN_AUTHENTICITY_SCORE:
        auth["instagram_handle_bio_verified"] = 1
        return True, auth
    if followers and followers >= MIN_REAL_INSTAGRAM_FOLLOWERS and bio_ok:
        return True, auth
    if score >= MIN_AUTHENTICITY_SCORE and bio_ok:
        return True, auth
    return False, auth


def merge_non_instagram_handles(*sources: dict[str, str]) -> dict[str, Any]:
    """Twitter/tiktok/youtube — first source wins (ESPN first when ordered)."""
    platforms = ("tiktok", "twitter", "youtube")
    out: dict[str, Any] = {}
    for src in sources:
        if not src:
            continue
        for p in platforms:
            h = src.get(p)
            if h and f"{p}_handle" not in out:
                out[f"{p}_handle"] = h.lstrip("@")
    return out


__all__ = [
    "AUTO_TRUST_SOURCES",
    "CONSENSUS_MIN_SOURCES",
    "MIN_AUTHENTICITY_SCORE",
    "apply_user_instagram_upload",
    "bio_matches_athlete",
    "extract_bio_from_page",
    "google_instagram_search_url",
    "google_site_search_url",
    "group_instagram_candidates",
    "handles_from_page",
    "has_trusted_instagram_handle",
    "is_user_provided_instagram",
    "merge_non_instagram_handles",
    "passes_authenticity_gate",
    "resolve_instagram_fields",
]
