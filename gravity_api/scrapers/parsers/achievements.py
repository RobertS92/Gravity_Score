"""Achievements and awards parsing."""

from __future__ import annotations

import re
from typing import Any

ALL_AMERICAN_PAT = re.compile(r"all[- ]american", re.I)
CONFERENCE_HONOR_PAT = re.compile(r"all[- ]([a-z\s]+)?conference|conference player of the year", re.I)
NATIONAL_AWARD_PAT = re.compile(
    r"heisman|naismith|golden spikes|avca player|national player of the year|"
    r"finalist|semi-?finalist",
    re.I,
)
CHAMPIONSHIP_PAT = re.compile(
    r"national champion|conference champion|final four|college world series|"
    r"playoff|bowl game|ncaa tournament",
    re.I,
)


def parse_achievements_from_text(text: str) -> dict[str, Any]:
    achievements: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 8:
            continue
        if any(
            pat.search(line)
            for pat in (
                ALL_AMERICAN_PAT,
                CONFERENCE_HONOR_PAT,
                NATIONAL_AWARD_PAT,
                CHAMPIONSHIP_PAT,
            )
        ):
            achievements.append({"title": line[:200], "raw": line[:500]})

    all_american = sum(1 for a in achievements if ALL_AMERICAN_PAT.search(a["title"]))
    conference = sum(1 for a in achievements if CONFERENCE_HONOR_PAT.search(a["title"]))
    national = sum(1 for a in achievements if NATIONAL_AWARD_PAT.search(a["title"]))

    return {
        "achievements_json": achievements[:50],
        "achievements_count_season": len(achievements),
        "achievements_count_career": len(achievements),
        "all_american_count": all_american,
        "conference_honors_count": conference,
        "national_honors_count": national,
        "conference_poty": any("player of the year" in a["title"].lower() for a in achievements),
        "heisman_finalist": any("heisman" in a["title"].lower() for a in achievements),
        "naismith_candidate": any("naismith" in a["title"].lower() for a in achievements),
        "national_awards_count": national,
    }


def merge_espn_awards(espn_awards: list[dict[str, Any]]) -> dict[str, Any]:
    text = "\n".join(str(a.get("name") or "") for a in espn_awards)
    parsed = parse_achievements_from_text(text)
    parsed["achievements_json"] = espn_awards + parsed.get("achievements_json", [])
    return parsed
