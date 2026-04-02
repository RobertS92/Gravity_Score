#!/usr/bin/env python3
"""Power 5 college basketball (men's and women's) player collector."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import requests

from gravity.scrapers.cfb_scraper import (
    _write_csv,
    delayed_get,
    firecrawl_batch_markdown,
    google_news_rss_headlines,
    http_session,
    pytrends_mean_score,
    wikipedia_summary_and_handles,
)
from gravity.scrapers.cfb_scraper import (
    _all_american_count as _all_american_count_md,
)
from gravity.scrapers.cfb_scraper import (
    _parse_follower_count,
    _parse_nil_usd,
    _parse_recruiting_snippets,
)
from gravity.scrapers.models import (
    NCAABPlayer,
    NCAAB_ESPN_TEAM_ID,
    NCAAB_TEAMS_BY_CONFERENCE,
    compute_data_quality_score,
    conference_containing_team,
    espn_team_id,
    field_completeness_percent,
    resolve_team_display_name,
)

logger = logging.getLogger(__name__)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


def fetch_ncaab_roster_items(
    session: requests.Session,
    team_id: str,
    gender: Literal["mens", "womens"],
) -> list[dict[str, Any]]:
    league = (
        "mens-college-basketball"
        if gender == "mens"
        else "womens-college-basketball"
    )
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/"
        f"{league}/teams/{team_id}/roster"
    )
    r = delayed_get(session, url)
    if not r or r.status_code != 200:
        logger.error("ESPN %s roster failed for team %s", league, team_id)
        return []
    data = r.json()
    rows: list[dict[str, Any]] = []
    for entry in data.get("athletes") or []:
        if isinstance(entry, dict) and "items" in entry:
            for pl in entry.get("items") or []:
                rows.append(pl)
        elif isinstance(entry, dict) and entry.get("id"):
            rows.append(entry)
    return rows


def _bb_names_to_stats(stats_block: dict[str, Any]) -> dict[str, str]:
    names = stats_block.get("names") or []
    out: dict[str, str] = {}
    stats = stats_block.get("statistics") or []
    if not stats:
        return out
    row = stats[-1]
    vals = row.get("stats") or []
    for i, name in enumerate(names):
        if i < len(vals):
            out[name] = vals[i]
    return out


def _parse_avg(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def extract_cbb_box_fields(stats_blob: dict[str, Any] | None) -> dict[str, float | None]:
    if not stats_blob:
        return {}
    cats = stats_blob.get("categories") or []
    av = next((c for c in cats if c.get("name") == "averages"), cats[0] if cats else None)
    if not av:
        return {}
    m = _bb_names_to_stats(av)
    return {
        "ppg": _parse_avg(m.get("avgPoints")),
        "rpg": _parse_avg(m.get("avgRebounds")),
        "apg": _parse_avg(m.get("avgAssists")),
        "fg_pct": _parse_avg(m.get("fieldGoalPct")),
        "three_pt_pct": _parse_avg(m.get("threePointFieldGoalPct")),
        "ft_pct": _parse_avg(m.get("freeThrowPct")),
    }


def fetch_espn_cbb_stats(
    session: requests.Session,
    athlete_id: str,
    gender: Literal["mens", "womens"],
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    league = (
        "mens-college-basketball"
        if gender == "mens"
        else "womens-college-basketball"
    )
    url = (
        "https://site.api.espn.com/apis/common/v3/sports/basketball/"
        f"{league}/athletes/{athlete_id}/stats"
    )
    r = delayed_get(session, url)
    if not r or r.status_code != 200:
        errors.append("espn_stats")
        return None, errors
    try:
        return r.json(), errors
    except json.JSONDecodeError:
        errors.append("espn_stats_json")
        return None, errors


def _wooden_naismith_flags(md: str | None) -> tuple[bool | None, bool | None]:
    if not md:
        return None, None
    w = re.search(r"Wooden", md) is not None
    n = re.search(r"Naismith", md) is not None
    return (True if w else None), (True if n else None)


def _draft_projection(md: str | None, gender: Literal["mens", "womens"]) -> str | None:
    if not md:
        return None
    if gender == "mens":
        m = re.search(
            r"NBA\s*(?:Draft)?[^\n.]{0,80}",
            md,
            re.I,
        )
    else:
        m = re.search(
            r"WNBA\s*(?:Draft)?[^\n.]{0,80}",
            md,
            re.I,
        )
    return m.group(0).strip() if m else None


def collect_one_ncaab_player(
    session: requests.Session,
    roster_item: dict[str, Any],
    team: str,
    conference: str,
    gender: Literal["mens", "womens"],
    firecrawl_key: str | None,
) -> tuple[NCAABPlayer, dict[str, Any]]:
    p = NCAABPlayer(gender=gender)
    completeness: dict[str, Any] = {"fields": {}, "sources": {}}

    def mark(field: str, ok: bool) -> None:
        completeness["fields"][field] = bool(ok)

    errors: list[str] = []

    pid = str(roster_item.get("id") or "")
    name = roster_item.get("displayName") or roster_item.get("fullName")
    p.player_name = name
    p.team = team
    p.conference = conference
    pos = roster_item.get("position") or {}
    if isinstance(pos, dict):
        p.position = pos.get("abbreviation") or pos.get("name")
    if roster_item.get("jersey") is not None:
        p.jersey_number = str(roster_item.get("jersey"))
    if roster_item.get("displayHeight"):
        p.height = str(roster_item.get("displayHeight"))
    if roster_item.get("displayWeight"):
        p.weight = str(roster_item.get("displayWeight"))
    bp = roster_item.get("birthPlace")
    if isinstance(bp, dict):
        city = bp.get("city") or ""
        st = bp.get("state") or ""
        p.hometown = ", ".join(x for x in [city, st] if x)
    elif isinstance(bp, str):
        p.hometown = bp
    college = roster_item.get("college") or {}
    if isinstance(college, dict) and college.get("name"):
        p.college = str(college.get("name"))
    exp = roster_item.get("experience")
    if isinstance(exp, dict):
        p.class_year = str(exp.get("displayValue") or exp.get("years") or "")
    elif isinstance(exp, str):
        p.class_year = exp
    inj = roster_item.get("injuries") or []
    if inj:
        desc = [str(i.get("details") or i.get("status") or "") for i in inj if isinstance(i, dict)]
        p.current_injury_status = desc[0] if desc else "injured"
        p.injury_history = [x for x in desc if x]

    mark("player_name", bool(p.player_name))

    ball_word = "basketball"
    wiki_q = f"{name} {team} {ball_word}"
    wiki_ex, ig_h, tw_h, wiki_err = wikipedia_summary_and_handles(session, wiki_q)
    errors.extend(wiki_err)
    p.instagram_handle = ig_h
    p.twitter_handle = tw_h

    news_q = f"{name} {team} college basketball"
    n_count, _, news_err = google_news_rss_headlines(session, news_q)
    errors.extend(news_err)
    if not news_err:
        p.news_count_30d = n_count
        mark("news_count_30d", True)

    trend_kw = f"{name} {team}"
    gscore, trend_err = pytrends_mean_score(trend_kw)
    errors.extend(trend_err)
    if gscore is not None:
        p.google_trends_score = gscore
        mark("google_trends_score", True)
    elif trend_err:
        p.google_trends_score = "ERROR"

    first = (roster_item.get("firstName") or "").strip()
    last = (roster_item.get("lastName") or "").strip()
    sr_q = urllib.parse.quote_plus(f"{first} {last} {team}")
    sr_url = f"https://www.sports-reference.com/cbb/search/search.fcgi?search={sr_q}"
    on3_url = f"https://www.on3.com/search/?q={urllib.parse.quote_plus(str(name) + ' ' + team)}"
    q247 = f"https://247sports.com/search/?Query={urllib.parse.quote(str(name) + ' ' + team)}"
    urls_fc: list[str] = [sr_url, on3_url, q247]
    if ig_h:
        urls_fc.append(f"https://www.instagram.com/{ig_h}/")
    if tw_h:
        urls_fc.append(f"https://twitter.com/{tw_h}")

    if firecrawl_key:
        fc_results = firecrawl_batch_markdown(urls_fc, firecrawl_key)
    else:
        fc_results = {u: {"success": False, "error": "no_firecrawl_key"} for u in urls_fc}
        errors.append("firecrawl_missing_key")

    sr_md = (fc_results.get(sr_url) or {}).get("markdown")
    on3_md = (fc_results.get(on3_url) or {}).get("markdown")
    r247_md = (fc_results.get(q247) or {}).get("markdown")

    sr_ok = (fc_results.get(sr_url) or {}).get("success")
    if not sr_ok:
        p.career_stats = "ERROR"  # type: ignore[assignment]
        errors.append("firecrawl_sports_reference")
    else:
        p.career_stats = {"sports_reference_search_excerpt": (sr_md or "")[:12000]}
        w, n = _wooden_naismith_flags(sr_md)
        if w:
            p.wooden_award_finalist = w
        if n:
            p.naismith_finalist = n
        aa = _all_american_count_md(sr_md)
        if aa:
            p.all_american_count = aa
        draft = _draft_projection(sr_md, gender)
        if gender == "mens":
            p.nba_draft_projection = draft
        else:
            p.wnba_draft_projection = draft
        mark("career_stats", bool(sr_md))

    if not (fc_results.get(on3_url) or {}).get("success"):
        p.nil_valuation = "ERROR"
        errors.append("on3_nil")
    else:
        val = _parse_nil_usd(on3_md)
        p.nil_valuation = val

    if (fc_results.get(q247) or {}).get("success"):
        rs, rn, rp = _parse_recruiting_snippets(r247_md)
        p.recruiting_stars = rs
        p.recruiting_rank_national = rn
        p.recruiting_rank_position = rp
    else:
        errors.append("247_recruiting")

    if ig_h:
        ig_res = fc_results.get(f"https://www.instagram.com/{ig_h}/")
        if ig_res and ig_res.get("success") and ig_res.get("markdown"):
            p.instagram_followers = _parse_follower_count(ig_res.get("markdown"))
        elif ig_h:
            p.instagram_followers = "ERROR"
            errors.append("instagram_fc")
    if tw_h:
        tw_res = fc_results.get(f"https://twitter.com/{tw_h}/")
        if tw_res and tw_res.get("success") and tw_res.get("markdown"):
            p.twitter_followers = _parse_follower_count(tw_res.get("markdown"))
        elif tw_h:
            p.twitter_followers = "ERROR"
            errors.append("twitter_fc")

    if pid:
        blob, se = fetch_espn_cbb_stats(session, pid, gender)
        errors.extend(se)
        if blob is not None:
            p.current_season_stats = blob
            xf = extract_cbb_box_fields(blob)
            p.ppg = xf.get("ppg")
            p.rpg = xf.get("rpg")
            p.apg = xf.get("apg")
            p.fg_pct = xf.get("fg_pct")
            p.three_pt_pct = xf.get("three_pt_pct")
            p.ft_pct = xf.get("ft_pct")
            mark("current_season_stats", True)
        else:
            p.current_season_stats = "ERROR"  # type: ignore[assignment]

    if errors:
        p.collection_errors = sorted(set(errors))

    tracked = [
        "player_name",
        "position",
        "ppg",
        "rpg",
        "apg",
        "current_season_stats",
        "career_stats",
        "nil_valuation",
        "recruiting_rank_national",
        "instagram_followers",
        "twitter_followers",
        "news_count_30d",
        "google_trends_score",
    ]
    p.data_quality_score = compute_data_quality_score(asdict(p), tracked)

    filled = sum(1 for v in completeness["fields"].values() if v)
    logger.info(
        "NCAAB collected player=%s field_hits=%s/%s errors=%s",
        name,
        filled,
        len(completeness["fields"]),
        len(errors),
    )

    return p, completeness


def run_for_team(
    conference: str,
    team_query: str,
    gender: Literal["mens", "womens"],
    out_dir: Path,
    max_players: int | None = None,
) -> Path:
    os.environ.setdefault("SCRAPES_DIR", "scrapes")
    team = resolve_team_display_name(conference, team_query, "ncaab")
    conf_canon = conference_containing_team(team, "ncaab")
    tid = espn_team_id(team, "ncaab")
    fc_key = os.environ.get("FIRECRAWL_API_KEY", "").strip() or None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = out_dir / ts
    batch_dir.mkdir(parents=True, exist_ok=True)

    session = http_session()
    roster = fetch_ncaab_roster_items(session, tid, gender)
    if max_players is not None:
        roster = roster[: max(0, max_players)]

    workers = _env_int("MAX_CONCURRENT_PLAYERS", 6)
    results: list[NCAABPlayer] = []

    def job(pl: dict[str, Any]) -> NCAABPlayer:
        player, _comp = collect_one_ncaab_player(
            session, dict(pl), team, conf_canon, gender, fc_key
        )
        return player

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(job, pl) for pl in roster]
        for fu in as_completed(futs):
            try:
                results.append(fu.result())
            except Exception as exc:  # noqa: BLE001
                logger.exception("Player worker failed: %s", exc)

    gender_tag = "ncaab_mens" if gender == "mens" else "ncaab_womens"
    stem = f"{gender_tag}_players_{ts}"
    json_rows = [r.to_json_dict() for r in results]
    (batch_dir / f"{stem}.json").write_text(
        json.dumps(json_rows, indent=2, default=str), encoding="utf-8"
    )
    _write_csv(batch_dir / f"{stem}.csv", json_rows)

    fields_report = [
        "instagram_followers",
        "nil_valuation",
        "recruiting_rank_national",
        "career_stats",
        "current_season_stats",
        "ppg",
    ]
    rep = {
        "total_players": len(results),
        "field_completeness": field_completeness_percent(json_rows, fields_report),
        "errors_by_source": _errors_histogram(results),
        "gender": gender,
        "timestamp_utc": ts,
    }
    report_name = f"{gender_tag}_collection_report_{ts}.json"
    (batch_dir / report_name).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    logger.info("Wrote %s players to %s", len(results), batch_dir)
    return batch_dir


def _errors_histogram(players: list[NCAABPlayer]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for pl in players:
        for e in pl.collection_errors or []:
            hist[e] = hist.get(e, 0) + 1
    return hist


def run_all_power5(gender: Literal["mens", "womens"], out_root: Path, max_players: int | None) -> None:
    for conf, teams in NCAAB_TEAMS_BY_CONFERENCE.items():
        for team in teams:
            logger.info("=== %s / %s (%s) ===", conf, team, gender)
            run_for_team(conf, team, gender, out_root, max_players=max_players)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Power 5 NCAAB collector")
    parser.add_argument(
        "--gender",
        choices=("mens", "womens"),
        default="mens",
        help="mens or womens basketball",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("all")
    p_all.add_argument("--limit", type=int, default=None)

    p_team = sub.add_parser("team")
    p_team.add_argument("conference")
    p_team.add_argument("school")
    p_team.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()
    subdir = "NCAAB_Mens" if args.gender == "mens" else "NCAAB_Womens"
    root = Path(os.environ.get("SCRAPES_DIR", "scrapes")) / subdir

    if args.cmd == "all":
        run_all_power5(args.gender, root, args.limit)
    elif args.cmd == "team":
        run_for_team(args.conference, args.school, args.gender, root, max_players=args.limit)


if __name__ == "__main__":
    main()
