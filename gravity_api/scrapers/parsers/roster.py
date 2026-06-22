"""Roster and transfer portal parsing."""

from __future__ import annotations

import re
from typing import Any


def parse_roster_presence(markdown: str, athlete_name: str) -> dict[str, Any]:
    name_parts = athlete_name.lower().split()
    lines = markdown.lower().splitlines()
    found = any(all(p in line for p in name_parts[:2]) for line in lines if len(name_parts) >= 2)
    jersey = None
    position = None
    for line in lines:
        if len(name_parts) >= 2 and name_parts[0] in line and name_parts[-1] in line:
            nums = re.findall(r"\b(\d{1,3})\b", line)
            pos = re.search(r"\b(QB|RB|WR|TE|OL|DL|LB|DB|K|PG|SG|SF|PF|C|OH|MB|S|L|DS|P|IF|OF)\b", line, re.I)
            if nums:
                jersey = int(nums[0])
            if pos:
                position = pos.group(1).upper()
            break
    return {
        "is_on_roster": found,
        "official_jersey": jersey,
        "official_position": position,
        "roster_verified_at": "now",
    }


def parse_transfer_portal(text: str) -> dict[str, Any]:
    lower = text.lower()
    in_portal = any(
        k in lower
        for k in (
            "entered the transfer portal",
            "in the transfer portal",
            "portal entry",
            "entered portal",
        )
    )
    destination = None
    m = re.search(r"(?:committed to|heading to|transfers to)\s+([A-Za-z\s&.'-]{3,40})", text, re.I)
    if m:
        destination = m.group(1).strip()
    date_m = re.search(r"(\d{4}-\d{2}-\d{2}|\w+ \d{1,2}, \d{4})", text)
    return {
        "in_transfer_portal": in_portal,
        "destination_school": destination,
        "portal_entry_date": date_m.group(1) if date_m else None,
    }
