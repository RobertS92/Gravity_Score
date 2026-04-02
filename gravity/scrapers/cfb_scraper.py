#!/usr/bin/env python3
"""
Power 5 college football player collector.

Pipeline order: ESPN identity → Wikipedia → Google News RSS → pytrends → Firecrawl batch
(Sports Reference search, On3 search, 247 search, social profiles) → ESPN stats → validate.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from gravity.scrapers.models import (
    CFBPlayer,
    CFB_TEAMS_BY_CONFERENCE,
    compute_data_quality_score,
    conference_containing_team,
    espn_team_id,
    field_completeness_percent,
    resolve_team_display_name,
)

logger = logging.getLogger(__name__)

USER_AGENT = "GravityScore/2.0 (college-data; +https://github.com/)"
FIRECRAWL_V2 = "https://api.firecrawl.dev/v2"

_pytrends_lock = threading.Lock()
_LAST_TRENDS_AT = 0.0


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def delayed_get(session: requests.Session, url: str, **params: Any) -> requests.Response | None:
    delay = _env_float("REQUEST_DELAY_SECONDS", 0.5)
    if delay > 0:
        time.sleep(delay)
    try:
        return session.get(url, timeout=30, **params)
    except requests.RequestException as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


def wikipedia_summary_and_handles(
    session: requests.Session, query: str
) -> tuple[str | None, str | None, str | None, list[str]]:
    """Returns (extract text, instagram, twitter, errors)."""
    errors: list[str] = []
    api = "https://en.wikipedia.org/w/api.php"
    r = delayed_get(
        session,
        api,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 5,
        },
    )
    if not r or r.status_code != 200:
        errors.append("wikipedia:search")
        return None, None, None, errors
    hits = (r.json().get("query") or {}).get("search") or []
    if not hits:
        return None, None, None, errors
    title = hits[0]["title"]
    r2 = delayed_get(
        session,
        api,
        params={
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "format": "json",
        },
    )
    wiki = None
    ig = None
    tw = None
    if r2 and r2.status_code == 200:
        wt = (
            ((r2.json().get("parse") or {}).get("wikitext") or {})
            .get("*", "")
        )
        wiki = wt[:8000] if wt else None
        for m in re.finditer(
            r"instagram\.com/([A-Za-z0-9_.]+)", wt, re.I
        ):
            ig = m.group(1).strip(" /")
            break
        for m in re.finditer(
            r"(?:twitter|x)\.com/([A-Za-z0-9_]+)", wt, re.I
        ):
            tw = m.group(1).strip(" /")
            break
    r3 = delayed_get(
        session,
        api,
        params={
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "exintro": "true",
            "explaintext": "true",
            "format": "json",
        },
    )
    extract = None
    if r3 and r3.status_code == 200:
        pages = (r3.json().get("query") or {}).get("pages") or {}
        for _pid, pdata in pages.items():
            if "extract" in pdata:
                extract = pdata["extract"]
                break
    return extract, ig, tw, errors


def google_news_rss_headlines(
    session: requests.Session, q: str, limit: int = 15
) -> tuple[int, list[str], list[str]]:
    enc = urllib.parse.quote(q)
    url = f"https://news.google.com/rss/search?q={enc}&hl=en-US&gl=US&ceid=US:en"
    r = delayed_get(session, url)
    errors: list[str] = []
    if not r or r.status_code != 200:
        errors.append("google_news_rss")
        return 0, [], errors
    try:
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        headlines: list[str] = []
        for it in items[:limit]:
            t = it.findtext("title")
            if t:
                headlines.append(t)
        return len(items), headlines, errors
    except ET.ParseError:
        errors.append("google_news_parse")
        return 0, [], errors


def pytrends_mean_score(keyword: str) -> tuple[float | None, list[str]]:
    errors: list[str] = []
    min_interval = 2.0
    global _LAST_TRENDS_AT
    try:
        from pytrends.request import TrendReq  # type: ignore[import-untyped]
    except ImportError:
        errors.append("pytrends_missing")
        return None, errors
    try:
        with _pytrends_lock:
            now = time.monotonic()
            wait = min_interval - (now - _LAST_TRENDS_AT)
            if wait > 0:
                time.sleep(wait)
            pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
            pytrends.build_payload([keyword], geo="US", timeframe="today 3-m")
            df = pytrends.interest_over_time()
            _LAST_TRENDS_AT = time.monotonic()
        if df is None or df.empty or keyword not in df.columns:
            return None, errors
        return float(df[keyword].mean()), errors
    except Exception as exc:  # noqa: BLE001 — outer pipeline classifies
        logger.info("pytrends failed for %s: %s", keyword, exc)
        errors.append("pytrends")
        return None, errors


def firecrawl_batch_markdown(
    urls: list[str],
    api_key: str,
) -> dict[str, dict[str, Any]]:
    """Map original URL string to {markdown, error, metadata, success}."""
    out: dict[str, dict[str, Any]] = {}
    urls = [u for u in urls if u]
    if not urls:
        return out
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "urls": urls,
        "formats": [{"type": "markdown"}],
        "onlyMainContent": True,
    }
    try:
        resp = requests.post(
            f"{FIRECRAWL_V2}/batch/scrape",
            headers=headers,
            json=body,
            timeout=90,
        )
        if resp.status_code >= 400:
            logger.warning("Firecrawl batch HTTP %s: %s", resp.status_code, resp.text[:500])
            return {u: {"success": False, "error": f"http_{resp.status_code}"} for u in urls}
        data = resp.json()
        bid = data.get("id")
        if not bid or not data.get("success", True):
            # immediate failure — fall back per-url
            return _firecrawl_scrape_single_urls(urls, api_key)
        deadline = time.time() + 180
        while time.time() < deadline:
            st = requests.get(
                f"{FIRECRAWL_V2}/batch/scrape/{bid}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60,
            )
            if st.status_code >= 400:
                break
            sj = st.json()
            status = sj.get("status")
            if status == "completed":
                items = sj.get("data") or []
                for i, u in enumerate(urls):
                    item = items[i] if i < len(items) else {}
                    meta = (item or {}).get("metadata") or {}
                    out[u] = {
                        "markdown": (item or {}).get("markdown"),
                        "error": meta.get("error"),
                        "success": meta.get("error") is None and bool((item or {}).get("markdown")),
                    }
                return out
            if status == "failed":
                break
            time.sleep(2.0)
        return _firecrawl_scrape_single_urls(urls, api_key)
    except requests.RequestException as exc:
        logger.warning("Firecrawl batch error: %s", exc)
        return {u: {"success": False, "error": str(exc)} for u in urls}


def _firecrawl_scrape_single_urls(
    urls: list[str],
    api_key: str,
) -> dict[str, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    out: dict[str, dict[str, Any]] = {}
    for u in urls:
        try:
            resp = requests.post(
                f"{FIRECRAWL_V2}/scrape",
                headers=headers,
                json={"url": u, "formats": [{"type": "markdown"}], "onlyMainContent": True},
                timeout=90,
            )
            if resp.status_code >= 400:
                out[u] = {"success": False, "error": f"http_{resp.status_code}"}
                continue
            sj = resp.json()
            if not sj.get("success"):
                out[u] = {"success": False, "error": sj.get("error", "scrape_failed")}
                continue
            item = sj.get("data") or {}
            md = item.get("markdown") if isinstance(item, dict) else None
            out[u] = {"markdown": md, "success": bool(md), "error": None}
        except requests.RequestException as exc:
            out[u] = {"success": False, "error": str(exc)}
    return out


def _parse_follower_count(markdown: str | None) -> int | None:
    if not markdown:
        return None
    patterns = [
        r"([\d,.]+)\s+Followers",
        r"([\d,.]+)\s+followers",
        r"\"follower_count\":\s*(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, markdown)
        if m:
            raw = m.group(1).replace(",", "").replace(".", "")
            try:
                return int(raw[:15])
            except ValueError:
                continue
    return None


def _parse_nil_usd(markdown: str | None) -> str | None:
    if not markdown:
        return None
    m = re.search(r"\$[\d,.]+(?:\s*(?:K|M|million|thousand))?", markdown, re.I)
    if m:
        return m.group(0)
    m2 = re.search(
        r"(?:valuation|NIL)[^\n$]{0,40}(\$[\d,.]+)",
        markdown,
        re.I,
    )
    return m2.group(1) if m2 else None


def _parse_recruiting_snippets(md: str | None) -> tuple[float | None, int | None, int | None]:
    stars = None
    nat = None
    pos = None
    if not md:
        return stars, nat, pos
    sm = re.search(r"(\d\.\d)\s*(?:⭐|stars?)", md, re.I)
    if sm:
        try:
            stars = float(sm.group(1))
        except ValueError:
            pass
    nm = re.search(r"(?:national|overall)\s*#?\s*(\d+)", md, re.I)
    if nm:
        try:
            nat = int(nm.group(1))
        except ValueError:
            pass
    pm = re.search(r"(?:position|pos)\s*#?\s*(\d+)", md, re.I)
    if pm:
        try:
            pos = int(pm.group(1))
        except ValueError:
            pass
    return stars, nat, pos


def _heisman_hits(md: str | None) -> int | None:
    if not md:
        return None
    if re.search(r"Heisman", md, re.I):
        votes = re.search(r"Heisman[^\d]{0,40}(\d+)\s*votes?", md, re.I)
        if votes:
            try:
                return int(votes.group(1))
            except ValueError:
                return 1
        return 1
    return None


def _all_american_count(md: str | None) -> int | None:
    if not md:
        return None
    m = re.findall(r"All-American", md, re.I)
    return len(m) if m else None


def fetch_espn_roster_items(
    session: requests.Session, team_id: str
) -> list[dict[str, Any]]:
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/football/"
        f"college-football/teams/{team_id}/roster"
    )
    r = delayed_get(session, url)
    if not r or r.status_code != 200:
        logger.error("ESPN roster failed for team %s", team_id)
        return []
    data = r.json()
    rows: list[dict[str, Any]] = []
    for group in data.get("athletes") or []:
        for pl in group.get("items") or []:
            rows.append(pl)
    return rows


def fetch_espn_athlete_stats(
    session: requests.Session, athlete_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    url = (
        "https://site.api.espn.com/apis/common/v3/sports/football/"
        f"college-football/athletes/{athlete_id}/stats"
    )
    r = delayed_get(session, url)
    if not r or r.status_code != 200:
        errors.append("espn_stats")
        return None, None, errors
    try:
        blob = r.json()
    except json.JSONDecodeError:
        errors.append("espn_stats_json")
        return None, None, errors
    return blob, blob, errors


def collect_one_cfb_player(
    session: requests.Session,
    roster_item: dict[str, Any],
    team: str,
    conference: str,
    firecrawl_key: str | None,
) -> tuple[CFBPlayer, dict[str, Any]]:
    """Strict sequence; passes ESPN row forward — no hidden shared player state."""
    p = CFBPlayer()
    completeness: dict[str, Any] = {"fields": {}, "sources": {}}

    def mark(field: str, ok: bool) -> None:
        completeness["fields"][field] = bool(ok)

    errors: list[str] = list(roster_item.get("_preflight_errors") or [])

    # --- ESPN identity (roster row) ---
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
    mark("team", True)
    mark("position", bool(p.position))

    # --- Wikipedia ---
    wiki_q = f"{name} {team} football"
    wiki_ex, ig_h, tw_h, wiki_err = wikipedia_summary_and_handles(session, wiki_q)
    errors.extend(wiki_err)
    if wiki_ex:
        mark("hometown_wiki", True)
    p.instagram_handle = ig_h
    p.twitter_handle = tw_h

    # --- Google News ---
    news_q = f"{name} {team} football"
    n_count, _heads, news_err = google_news_rss_headlines(session, news_q)
    errors.extend(news_err)
    if not news_err:
        p.news_count_30d = n_count
        mark("news_count_30d", True)

    # --- pytrends ---
    trend_kw = f"{name} {team}"
    gscore, trend_err = pytrends_mean_score(trend_kw)
    errors.extend(trend_err)
    if gscore is not None:
        p.google_trends_score = gscore
        mark("google_trends_score", True)
    elif trend_err:
        p.google_trends_score = "ERROR"

    # --- URLs for Firecrawl (Sports Reference, On3, 247, social) ---
    first = (roster_item.get("firstName") or "").strip()
    last = (roster_item.get("lastName") or "").strip()
    sr_q = urllib.parse.quote_plus(f"{first} {last} {team}")
    sr_url = f"https://www.sports-reference.com/cfb/search/search.fcgi?search={sr_q}"
    on3_url = f"https://www.on3.com/search/?q={urllib.parse.quote_plus(str(name) + ' ' + team)}"
    q247 = f"https://247sports.com/search/?Query={urllib.parse.quote(str(name) + ' ' + team)}"
    urls_fc: list[str] = [sr_url, on3_url, q247]
    if ig_h:
        urls_fc.append(f"https://www.instagram.com/{ig_h}/")
    if tw_h:
        urls_fc.append(f"https://twitter.com/{tw_h}")

    fc_results: dict[str, dict[str, Any]] = {}
    if firecrawl_key:
        fc_results = firecrawl_batch_markdown(urls_fc, firecrawl_key)
        completeness["sources"]["firecrawl_keys"] = list(fc_results.keys())
    else:
        for u in urls_fc:
            fc_results[u] = {"success": False, "error": "no_firecrawl_key"}
        errors.append("firecrawl_missing_key")

    # Map back by position in urls_fc list
    sr_md = (fc_results.get(sr_url) or {}).get("markdown")
    on3_md = (fc_results.get(on3_url) or {}).get("markdown")
    r247_md = (fc_results.get(q247) or {}).get("markdown")

    sr_ok = (fc_results.get(sr_url) or {}).get("success")
    if not sr_ok:
        p.career_stats = "ERROR"  # type: ignore[assignment]
        errors.append("firecrawl_sports_reference")
    else:
        # store raw markdown slice as stats proxy when table parsing is ambiguous
        p.career_stats = {"sports_reference_search_excerpt": (sr_md or "")[:12000]}
        hv = _heisman_hits(sr_md)
        if hv is not None:
            p.heisman_votes = hv
        aa = _all_american_count(sr_md)
        if aa:
            p.all_american_count = aa
        mark("career_stats", bool(sr_md))

    if not (fc_results.get(on3_url) or {}).get("success"):
        p.nil_valuation = "ERROR"
        errors.append("on3_nil")
    else:
        val = _parse_nil_usd(on3_md)
        p.nil_valuation = val
        mark("nil_valuation", bool(val))

    if (fc_results.get(q247) or {}).get("success"):
        rs, rn, rp = _parse_recruiting_snippets(r247_md)
        p.recruiting_stars = rs
        p.recruiting_rank_national = rn
        p.recruiting_rank_position = rp
        mark("recruiting_rank_national", rn is not None)
    else:
        errors.append("247_recruiting")

    if ig_h:
        ig_res = fc_results.get(f"https://www.instagram.com/{ig_h}/")
        if ig_res and ig_res.get("success") and ig_res.get("markdown"):
            cnt = _parse_follower_count(ig_res.get("markdown"))
            p.instagram_followers = cnt
            mark("instagram_followers", cnt is not None)
        else:
            p.instagram_followers = "ERROR"
            errors.append("instagram_fc")
    if tw_h:
        tw_res = fc_results.get(f"https://twitter.com/{tw_h}/")
        if tw_res and tw_res.get("success") and tw_res.get("markdown"):
            cnt = _parse_follower_count(tw_res.get("markdown"))
            p.twitter_followers = cnt
            mark("twitter_followers", cnt is not None)
        else:
            p.twitter_followers = "ERROR"
            errors.append("twitter_fc")

    # --- ESPN stats ---
    if pid:
        whole, _split, se = fetch_espn_athlete_stats(session, pid)
        errors.extend(se)
        if whole is not None:
            p.current_season_stats = whole
            mark("current_season_stats", True)
        else:
            p.current_season_stats = "ERROR"  # type: ignore[assignment]
    else:
        p.current_season_stats = None

    if errors:
        p.collection_errors = sorted(set(errors))

    tracked = [
        "player_name",
        "position",
        "hometown",
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
        "CFB collected player=%s field_hits=%s/%s errors=%s",
        name,
        filled,
        len(completeness["fields"]),
        len(errors),
    )

    return p, completeness


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return str(v)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _csv_cell(r.get(k)) for k in keys})


def run_for_team(
    conference: str,
    team_query: str,
    out_dir: Path,
    max_players: int | None = None,
) -> Path:
    os.environ.setdefault("SCRAPES_DIR", "scrapes")
    team = resolve_team_display_name(conference, team_query, "cfb")
    conf_canon = conference_containing_team(team, "cfb")
    tid = espn_team_id(team, "cfb")
    fc_key = os.environ.get("FIRECRAWL_API_KEY", "").strip() or None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = out_dir / ts
    batch_dir.mkdir(parents=True, exist_ok=True)

    session = http_session()
    roster = fetch_espn_roster_items(session, tid)
    if max_players is not None:
        roster = roster[: max(0, max_players)]

    workers = _env_int("MAX_CONCURRENT_PLAYERS", 6)
    results: list[CFBPlayer] = []
    complete_log: list[dict[str, Any]] = []

    def job(pl: dict[str, Any]) -> tuple[CFBPlayer, dict[str, Any]]:
        pl = dict(pl)
        player, comp = collect_one_cfb_player(session, pl, team, conf_canon, fc_key)
        comp["player"] = player.player_name
        return player, comp

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(job, pl) for pl in roster]
        for fu in as_completed(futs):
            try:
                player, comp = fu.result()
                results.append(player)
                complete_log.append(comp)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Player worker failed: %s", exc)

    stem = f"cfb_players_{ts}"
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
    ]
    rep = {
        "total_players": len(results),
        "field_completeness": field_completeness_percent(json_rows, fields_report),
        "errors_by_source": _errors_histogram(results),
        "timestamp_utc": ts,
    }
    (batch_dir / f"cfb_collection_report_{ts}.json").write_text(
        json.dumps(rep, indent=2), encoding="utf-8"
    )
    logger.info("Wrote %s players to %s", len(results), batch_dir)
    return batch_dir


def _errors_histogram(players: list[CFBPlayer]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for pl in players:
        for e in pl.collection_errors or []:
            hist[e] = hist.get(e, 0) + 1
    return hist


def run_all_power5(out_root: Path, max_players: int | None = None) -> None:
    for conf, teams in CFB_TEAMS_BY_CONFERENCE.items():
        for team in teams:
            logger.info("=== %s / %s ===", conf, team)
            run_for_team(conf, team, out_root, max_players=max_players)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Power 5 CFB collector")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("all", help="All Power 5 teams")
    p_all.add_argument("--limit", type=int, default=None, help="Max players per team")

    p_team = sub.add_parser("team", help="One team: team <Conference> <School>")
    p_team.add_argument("conference")
    p_team.add_argument("school")
    p_team.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()
    root = Path(os.environ.get("SCRAPES_DIR", "scrapes")) / "CFB"

    if args.cmd == "all":
        run_all_power5(root, max_players=args.limit)
    elif args.cmd == "team":
        run_for_team(args.conference, args.school, root, max_players=args.limit)


if __name__ == "__main__":
    main()
