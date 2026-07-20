#!/usr/bin/env python3
"""Ingest real market-value labels from public sources into athlete_value_labels.

Sources (all public, reproducible):
  - NFL  : nflverse historical_contracts.parquet (OverTheCap) -> contract APY (USD).
  - NBA  : Basketball-Reference /contracts/players.html      -> current-season salary.
  - WNBA : Spotrac wnba rankings                             -> annual salary (best-effort).

Matching is by normalized name within the sport, disambiguated by position/team.
These labels are the supervised targets for per-sport value models.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/ingest_value_labels.py --sports nfl nba
"""
from __future__ import annotations

import argparse
import asyncio
import io
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg
import httpx
import pandas as pd

from gravity_api.config import get_settings

NFL_CONTRACTS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/contracts/historical_contracts.parquet"
)
NBA_CONTRACTS_URL = "https://www.basketball-reference.com/contracts/players.html"

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# Common first-name / public-name aliases so OTC "Patrick Surtain II" matches
# roster "Pat Surtain II", and "Ahmad Gardner" matches "Sauce Gardner".
_FIRST_NAME_ALIASES: dict[str, frozenset[str]] = {
    "pat": frozenset({"patrick"}),
    "patrick": frozenset({"pat"}),
    "alex": frozenset({"alexander"}),
    "alexander": frozenset({"alex"}),
    "chris": frozenset({"christopher"}),
    "christopher": frozenset({"chris"}),
    "mike": frozenset({"michael"}),
    "michael": frozenset({"mike"}),
    "will": frozenset({"william"}),
    "william": frozenset({"will", "bill"}),
    "bill": frozenset({"william", "will"}),
    "rob": frozenset({"robert"}),
    "robert": frozenset({"rob", "bob"}),
    "bob": frozenset({"robert", "rob"}),
    "josh": frozenset({"joshua"}),
    "joshua": frozenset({"josh"}),
    "matt": frozenset({"matthew"}),
    "matthew": frozenset({"matt"}),
    "nick": frozenset({"nicholas"}),
    "nicholas": frozenset({"nick"}),
    "joe": frozenset({"joseph"}),
    "joseph": frozenset({"joe"}),
    "sam": frozenset({"samuel"}),
    "samuel": frozenset({"sam"}),
}
_FULL_NAME_ALIASES: dict[str, str] = {
    "sauce gardner": "ahmad gardner",
    "ahmad gardner": "sauce gardner",
}


def norm_name(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t and t not in _SUFFIXES]
    return " ".join(toks)


def name_lookup_keys(s: str | None) -> list[str]:
    """Normalized name plus first-name / public-name alias variants."""
    base = norm_name(s)
    if not base:
        return []
    keys = [base]
    parts = base.split()
    if len(parts) >= 2:
        first, rest = parts[0], parts[1:]
        for alt in _FIRST_NAME_ALIASES.get(first, ()):
            keys.append(" ".join([alt, *rest]))
    alias = _FULL_NAME_ALIASES.get(base)
    if alias:
        keys.append(alias)
        # Also expand first-name aliases of the full-name alias target.
        alias_parts = alias.split()
        if len(alias_parts) >= 2:
            for alt in _FIRST_NAME_ALIASES.get(alias_parts[0], ()):
                keys.append(" ".join([alt, *alias_parts[1:]]))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


# ----------------------------- athlete lookup ------------------------------
async def load_athlete_lookup(conn: asyncpg.Connection, sport: str) -> dict[str, list[dict]]:
    rows = await conn.fetch(
        """SELECT id::text AS id, name, position, current_team, team
           FROM athletes WHERE sport = $1 AND COALESCE(is_active, TRUE) = TRUE""",
        sport,
    )
    lookup: dict[str, list[dict]] = {}
    for r in rows:
        entry = {
            "id": r["id"],
            "position": (r["position"] or "").upper(),
            "team": norm_name(r["current_team"] or r["team"] or ""),
        }
        for key in name_lookup_keys(r["name"]):
            bucket = lookup.setdefault(key, [])
            if not any(existing["id"] == entry["id"] for existing in bucket):
                bucket.append(entry)
    return lookup


def _resolve(
    candidates: list[dict], *, position: str | None = None, team: str | None = None
) -> str | None:
    """Pick a single athlete id from name-matched candidates using position/team."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]["id"]
    pos = (position or "").upper()
    if pos:
        pos_hits = [c for c in candidates if c["position"] and (c["position"] in pos or pos in c["position"])]
        if len(pos_hits) == 1:
            return pos_hits[0]["id"]
        candidates = pos_hits or candidates
    if team:
        tnorm = norm_name(team)
        team_hits = [c for c in candidates if c["team"] and (c["team"] in tnorm or tnorm in c["team"])]
        if len(team_hits) == 1:
            return team_hits[0]["id"]
    return None  # still ambiguous -> skip (don't guess)


# ----------------------------- upsert --------------------------------------
async def upsert_label(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    label_type: str,
    value_usd: float,
    source: str,
    season_year: int,
    confidence: float,
    meta: dict,
) -> None:
    import json

    await conn.execute(
        """INSERT INTO athlete_value_labels
             (athlete_id, sport, label_type, value_usd, source, as_of, season_year, confidence, meta)
           VALUES ($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
           ON CONFLICT (athlete_id, label_type, source, season_year)
           DO UPDATE SET value_usd=EXCLUDED.value_usd, confidence=EXCLUDED.confidence,
             meta=EXCLUDED.meta, as_of=EXCLUDED.as_of, updated_at=NOW()""",
        athlete_id,
        sport,
        label_type,
        float(value_usd),
        source,
        date.today(),
        season_year,
        float(confidence),
        json.dumps(meta),
    )


# ----------------------------- NFL -----------------------------------------
async def ingest_nfl(conn: asyncpg.Connection) -> dict:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(NFL_CONTRACTS_URL)
        resp.raise_for_status()
    df = pd.read_parquet(io.BytesIO(resp.content))
    # Current contract per player: prefer active, then latest year_signed.
    df = df[df["apy"].notna() & (df["apy"] > 0)].copy()
    df["is_active"] = df["is_active"].fillna(False)
    df = df.sort_values(["player", "is_active", "year_signed"], ascending=[True, False, False])
    current = df.groupby("player", as_index=False).first()

    lookup = await load_athlete_lookup(conn, "nfl")
    matched = ambiguous = unmatched = 0
    season = int(date.today().year)
    for _, row in current.iterrows():
        cands: list[dict] = []
        seen_ids: set[str] = set()
        for key in name_lookup_keys(str(row["player"])):
            for cand in lookup.get(key) or []:
                if cand["id"] not in seen_ids:
                    seen_ids.add(cand["id"])
                    cands.append(cand)
        if not cands:
            unmatched += 1
            continue
        aid = _resolve(cands, position=str(row.get("position") or ""), team=str(row.get("team") or ""))
        if not aid:
            ambiguous += 1
            continue
        apy_usd = float(row["apy"]) * 1_000_000.0
        await upsert_label(
            conn,
            athlete_id=aid,
            sport="nfl",
            label_type="contract_apy",
            value_usd=apy_usd,
            source="nflverse_otc",
            season_year=season,
            confidence=0.9,
            meta={
                "total_value_usd": float(row.get("value") or 0) * 1_000_000.0,
                "guaranteed_usd": float(row.get("guaranteed") or 0) * 1_000_000.0,
                "apy_cap_pct": float(row.get("apy_cap_pct") or 0),
                "year_signed": int(row.get("year_signed") or 0),
                "years": float(row.get("years") or 0),
                "position": str(row.get("position") or ""),
            },
        )
        matched += 1
    return {"source_rows": len(current), "matched": matched, "ambiguous": ambiguous, "unmatched": unmatched}


# ----------------------------- NBA -----------------------------------------
def _money_to_usd(txt: str | None) -> float | None:
    if not txt:
        return None
    m = re.sub(r"[^0-9.]", "", str(txt))
    if not m:
        return None
    try:
        return float(m)
    except ValueError:
        return None


async def ingest_nba(conn: asyncpg.Connection) -> dict:
    from bs4 import BeautifulSoup

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        resp = await client.get(NBA_CONTRACTS_URL)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="player-contracts")
    if table is None:
        return {"error": "player-contracts table not found"}

    lookup = await load_athlete_lookup(conn, "nba")
    matched = ambiguous = unmatched = norow = 0
    season = int(date.today().year)
    for tr in table.select("tbody tr"):
        if "thead" in (tr.get("class") or []):
            continue
        # Player is a <th> on bbref; salary/team are <td>. Match both via data-stat.
        pcell = tr.find(attrs={"data-stat": "player"})
        y1cell = tr.find(attrs={"data-stat": "y1"})
        tcell = tr.find(attrs={"data-stat": "team_id"})
        if pcell is None or y1cell is None:
            continue
        name = pcell.get_text(strip=True)
        salary = _money_to_usd(y1cell.get_text(strip=True))
        if not name or not salary or salary <= 0:
            norow += 1
            continue
        cands = lookup.get(norm_name(name))
        if not cands:
            unmatched += 1
            continue
        team = tcell.get_text(strip=True) if tcell else None
        aid = _resolve(cands, team=team)
        if not aid:
            ambiguous += 1
            continue
        await upsert_label(
            conn,
            athlete_id=aid,
            sport="nba",
            label_type="salary_annual",
            value_usd=salary,
            source="basketball_reference",
            season_year=season,
            confidence=0.9,
            meta={"team": team or ""},
        )
        matched += 1
    return {"matched": matched, "ambiguous": ambiguous, "unmatched": unmatched, "skipped": norow}


INGESTORS = {"nfl": ingest_nfl, "nba": ingest_nba}


async def main_async(sports: list[str]) -> None:
    conn = await asyncpg.connect(get_settings().pg_dsn, statement_cache_size=0, timeout=90, command_timeout=120)
    try:
        for sport in sports:
            fn = INGESTORS.get(sport)
            if fn is None:
                print(f"[{sport}] no ingestor configured — skipping")
                continue
            print(f"[{sport}] ingesting value labels ...")
            stats = await fn(conn)
            print(f"[{sport}] {stats}")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest market-value labels from public sources")
    parser.add_argument("--sports", nargs="+", default=["nfl", "nba"])
    args = parser.parse_args()
    asyncio.run(main_async(args.sports))


if __name__ == "__main__":
    main()
