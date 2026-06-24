"""Sports Reference site mapping and honors parsing."""

from __future__ import annotations

import re
from typing import Any

from gravity_api.scrapers.parsers.achievements import parse_achievements_from_text

SPORT_REF_DOMAINS: dict[str, str] = {
    "cfb": "sports-reference.com/cfb",
    "nfl": "pro-football-reference.com",
    "nba": "basketball-reference.com",
    "wnba": "basketball-reference.com/wnba",
    "ncaab_mens": "sports-reference.com/cbb",
    "ncaab_womens": "sports-reference.com/cbb/women",
    "ncaa_baseball": "baseball-reference.com",
    "ncaa_volleyball": "sports-reference.com/cbb/women",
}

_ALL_PRO_PAT = re.compile(r"all[- ]pro", re.I)
_ALL_STAR_PAT = re.compile(r"all[- ]star", re.I)
_PRO_BOWL_PAT = re.compile(r"pro\s*bowl", re.I)
_MVP_PAT = re.compile(
    r"(?:mvp|most valuable player|defensive player of the year|"
    r"offensive player of the year|cy young|heisman|naismith)",
    re.I,
)


def ref_domain_for_sport(sport: str) -> str | None:
    return SPORT_REF_DOMAINS.get(sport)


def parse_sports_ref_honors(text: str) -> dict[str, Any]:
    """Parse honors tables and award lines from Sports Reference markdown."""
    parsed = parse_achievements_from_text(text)
    achievements = list(parsed.get("achievements_json") or [])

    all_pro = len(_ALL_PRO_PAT.findall(text))
    all_star = len(_ALL_STAR_PAT.findall(text))
    pro_bowl = len(_PRO_BOWL_PAT.findall(text))

    major_awards: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 6:
            continue
        if _MVP_PAT.search(line):
            major_awards.append({"title": line[:200], "source": "sports_reference"})

    if all_pro:
        parsed["all_pro_count"] = float(all_pro)
    if all_star:
        parsed["all_star_count"] = float(all_star)
    if pro_bowl and not parsed.get("all_pro_count"):
        parsed["pro_bowl_count"] = float(pro_bowl)
    if major_awards:
        parsed["major_awards_json"] = major_awards[:30]
        parsed["national_awards_count"] = float(
            (parsed.get("national_awards_count") or 0) + len(major_awards)
        )

    # Preserve merged achievement list when SR adds pro-specific lines.
    if achievements:
        parsed["achievements_json"] = achievements
    return parsed


__all__ = ["SPORT_REF_DOMAINS", "parse_sports_ref_honors", "ref_domain_for_sport"]
