"""Per-category news collector.

Pulls RSS / Atom feeds from the publishers we trust (the ones in
``news_sources`` with tier <= 3), classifies each entry into our
category taxonomy, matches the entry to an athlete or team in our DB,
and routes everything through ``news_ingest`` so the trust pipeline is
enforced.

Design goals:

1. **Cover every category the user cares about.**  The ``FEED_REGISTRY``
   below explicitly lists which feed maps to which "default" category
   bucket.  Entries can also be re-classified at runtime via keyword
   patterns when an outlet's feed mixes types (ESPN's main CFB feed
   carries everything from injuries to AP polls).

2. **No bare LLM hallucinations.**  The classifier is rule-first
   (regex) with deterministic priority.  The LLM is only consulted for
   *fact verification* (already in ``news_ingest``), never for
   "what is this article about" — that's wholly deterministic.

3. **Athlete/team matching is opt-in per entry.**  News stories that
   don't reference an athlete in our DB still get recorded as
   *team-level* events when the body mentions one of our teams.
   Stories that reference neither are dropped (we are a college-sports
   product; arbitrary national news isn't useful).

4. **Bounded I/O.**  Each feed pull is capped at 50 entries.  Article
   body fetches use a 10s timeout and a 200 KB read cap.  No infinite
   crawling.

5. **Idempotent.**  ``news_ingest`` already dedupes by URL hash, so
   re-running the collector is safe.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import asyncpg
import feedparser  # type: ignore[import-untyped]
import httpx

from gravity_api.services.news_ingest import (
    IngestRejected,
    IngestResult,
    ingest_athlete_event,
    ingest_team_event,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category classifier
# ---------------------------------------------------------------------------
# Each pattern is checked against `f"{title} {body}"`.  First *winning*
# pattern wins (we evaluate by ``priority`` desc).  Patterns are
# anchored on word boundaries to avoid false matches like "transferable
# skills" matching TRANSFER.

@dataclass(frozen=True)
class CategoryRule:
    category: str
    pattern: re.Pattern[str]
    priority: int  # higher = wins
    confidence: float  # 0-1, used to set confidence_score on the event


# Order doesn't matter — we sort by priority desc at runtime.
CATEGORY_RULES: list[CategoryRule] = [
    # -------- High-priority, unambiguous categories ------------------------
    CategoryRule(
        "NIL_DEAL",
        re.compile(
            r"\b("
            r"NIL\s+(?:deal|deals|contract|agreement|partnership|endorsement)"
            r"|name[,\s]\s*image[,\s]\s*and\s+likeness"
            r"|(?:signs|signed|inks|inked|lands|landed|announces)\s+(?:a\s+)?(?:deal|partnership|endorsement|sponsorship)\s+with"
            r"|brand\s+(?:deal|partnership|ambassador|endorsement)"
            r"|endorsement\s+deal"
            r")\b",
            re.IGNORECASE,
        ),
        priority=100,
        confidence=0.85,
    ),
    CategoryRule(
        "TRANSFER",
        re.compile(
            r"\b("
            r"transfer\s+portal"
            r"|enters?\s+(?:the\s+)?transfer\s+portal"
            r"|transferr?ing\s+(?:to|from)"
            r"|commits?\s+to\s+\w+\s+(?:after|via|from)\s+transfer"
            r"|(?:portal|transfers?)\s+(?:to|out|in)\b"
            r")\b",
            re.IGNORECASE,
        ),
        priority=95,
        confidence=0.9,
    ),
    CategoryRule(
        "INJURY",
        re.compile(
            r"\b("
            r"(?:injur(?:ed|y|ies)|sprained|torn|fracture|concussion|surgery)"
            r"|(?:out|sidelined|miss(?:es|ed))\s+(?:for|with)\s+\w+\s+(?:injury|game|games|weeks)"
            r"|placed\s+on\s+injured\s+reserve"
            r"|return(?:s|ed)?\s+from\s+injury"
            r")\b",
            re.IGNORECASE,
        ),
        priority=90,
        confidence=0.85,
    ),
    CategoryRule(
        "INCIDENT",
        re.compile(
            r"\b("
            r"arrested|charged\s+with|cited\s+for|booked\s+on"
            r"|suspend(?:ed|s|ing|sion)"
            r"|expel(?:led|s)|dismiss(?:ed|al)\s+from\s+(?:team|program)"
            r"|investigation\s+into|under\s+investigation"
            r"|violat(?:ion|ed|ions)\s+of\s+(?:team|NCAA|school)\s+(?:rules|policy|conduct)"
            r"|DUI|misdemeanor|felony"
            r")\b",
            re.IGNORECASE,
        ),
        priority=88,
        confidence=0.85,
    ),
    CategoryRule(
        "RECRUITING",
        re.compile(
            r"\b("
            r"(?:five|four|three)[-\s]star\s+(?:recruit|prospect|commit)"
            r"|(?:commits?|committed|decommit(?:s|ted)?|pledg(?:es|ed))"
            r"|recruit(?:s|ing|ment)\s+class"
            r"|247(?:Sports|sports)\s+composite"
            r"|class\s+of\s+20\d{2}"
            r")\b",
            re.IGNORECASE,
        ),
        priority=80,
        confidence=0.8,
    ),
    CategoryRule(
        "AWARD",
        re.compile(
            r"\b("
            r"Heisman|All[\s-]American"
            r"|All[\s-](?:SEC|Big\s+Ten|Big\s+12|ACC|Pac[\s-]12|Conference)"
            r"|player\s+of\s+the\s+(?:week|month|year)"
            r"|wins?\s+(?:the\s+)?\w+\s+award"
            r"|(?:named|earns?)\s+\w+\s+(?:award|honors?)"
            r"|preseason\s+(?:All[\s-]American|honors?)"
            r")\b",
            re.IGNORECASE,
        ),
        priority=78,
        confidence=0.8,
    ),
    # -------- Business / Announcements ------------------------------------
    CategoryRule(
        "BUSINESS",
        re.compile(
            r"\b("
            r"collective(?:s)?\s+(?:rais(?:es?|ed|ing)|fund(?:s|ed|ing)?|launch(?:es|ed)?|announc(?:es|ed)?|reach(?:es|ed)?)"
            r"|revenue\s+sharing"
            r"|(?:conference|league)\s+(?:realignment|expansion|tv\s+deal|media\s+rights)"
            r"|(?:billion|million)[-\s](?:dollar)?\s+(?:deal|fund|rights\s+deal)"
            r"|sportsbook\s+sponsor(?:ship)?"
            r"|TV\s+rights"
            r"|sponsorship\s+(?:agreement|valued|worth)"
            r")\b",
            re.IGNORECASE,
        ),
        priority=75,
        confidence=0.8,
    ),
    CategoryRule(
        "ANNOUNCEMENT",
        re.compile(
            r"\b("
            r"head\s+coach\s+(?:hire|hired|fired|fires|named|out|resigns)"
            r"|(?:hires?|hires|hired|fires?|fired|promot(?:es|ed))\s+(?:as|new|head|assistant)"
            r"|coaching\s+(?:change|hire|search)"
            r"|(?:declares?|enters?|entering)\s+(?:the\s+)?(?:NFL|NBA|WNBA)\s+draft"
            r"|(?:NFL|NBA|WNBA)\s+Draft\b"  # generic draft coverage
            r"|(?:selected|drafted|picked)\s+(?:by|in\s+the\s+\d+)"
            r"|(?:1st|2nd|3rd|\d+(?:st|nd|rd|th))\s+round\s+(?:pick|of\s+the\s+(?:NFL|NBA))"
            r"|return(?:s|ing)?\s+for\s+(?:another|senior|final)\s+(?:season|year)"
            r"|(?:athletic\s+director|AD)\s+(?:hire|named|appointed)"
            r")\b",
            re.IGNORECASE,
        ),
        priority=85,  # higher than NIL_DEAL/TRANSFER so draft news routes correctly
        confidence=0.82,
    ),
    # -------- Performance & Score (lower priority — game stats are noisy) -
    CategoryRule(
        "PERFORMANCE",
        re.compile(
            r"\b("
            r"(?:scores|threw|passed)\s+(?:for|\d+)\s+\w+\s+(?:yards|TDs|points)"
            r"|(?:career|season|school)\s+high"
            r"|breaks?\s+\w+\s+record"
            r"|(?:double|triple)[-\s]double"
            r"|\d+[-]point\s+(?:effort|game|performance)"
            r")\b",
            re.IGNORECASE,
        ),
        priority=60,
        confidence=0.7,
    ),
    CategoryRule(
        "RANKING",
        re.compile(
            r"\b("
            r"(?:AP|Coaches'?)\s+(?:Top\s+25|Poll)"
            r"|(?:CFP|College\s+Football\s+Playoff)\s+rankings?"
            r"|(?:climbs?|drops?|falls?|rises?)\s+(?:in|to|out\s+of)\s+(?:rankings?|top\s+\d+)"
            r")\b",
            re.IGNORECASE,
        ),
        priority=55,
        confidence=0.85,
    ),
    # -------- Catch-all NEWS -- always wins last among priority<=50 ------
    CategoryRule(
        "NEWS",
        re.compile(r".+", re.IGNORECASE),
        priority=1,
        confidence=0.45,
    ),
]


def classify_text(title: str, body: str) -> tuple[str, float]:
    """Return ``(category, confidence)`` for a headline + body.

    Deterministic.  No LLM call.  The first rule (in priority desc) that
    matches wins.  ``NEWS`` is a fallback that always matches when
    nothing else does, with low confidence so the UI shows a less
    decisive badge.
    """
    text = f"{title or ''} {body or ''}"
    for rule in sorted(CATEGORY_RULES, key=lambda r: -r.priority):
        if rule.pattern.search(text):
            return rule.category, rule.confidence
    return "NEWS", 0.4


# ---------------------------------------------------------------------------
# Feed registry — the canonical list of sources we pull from.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FeedSpec:
    name: str               # human label
    domain: str             # must match a row in news_sources
    url: str                # RSS / Atom URL
    default_category: str   # informational only — published category bias
    sport_hint: Optional[str] = None  # 'cfb' / 'ncaab_mens' / etc. or None
    description: str = ""
    # Only set ``mono_topic=True`` when EVERY entry in the feed is
    # reliably the default_category (e.g. a dedicated NIL deals RSS).
    # When True, the classifier's NEWS fallback is overridden to
    # default_category.  Leave False (default) for general news feeds.
    mono_topic: bool = False


FEED_REGISTRY: list[FeedSpec] = [
    # ----- Tier-1 / Tier-2: NIL & business --------------------------------
    FeedSpec(
        name="On3 News (top stories)",
        domain="on3.com",
        url="https://www.on3.com/feed/",
        default_category="NIL_DEAL",
        description="On3 covers NIL deals, transfer portal, recruiting.",
    ),
    FeedSpec(
        name="Sportico",
        domain="sportico.com",
        url="https://www.sportico.com/feed/",
        default_category="BUSINESS",
        description="Sports business: deals, rights, valuations.",
    ),
    FeedSpec(
        name="Front Office Sports",
        domain="frontofficesports.com",
        url="https://frontofficesports.com/feed/",
        default_category="BUSINESS",
        description="Sports business newsletter & analysis.",
    ),
    FeedSpec(
        name="Sports Business Journal",
        domain="sportsbusinessjournal.com",
        url="https://www.sportsbusinessjournal.com/RSS",
        default_category="BUSINESS",
        description="College & pro sports business.",
    ),
    # ----- Tier-2: ESPN college coverage ----------------------------------
    FeedSpec(
        name="ESPN College Football",
        domain="espn.com",
        url="https://www.espn.com/espn/rss/ncf/news",
        default_category="NEWS",
        sport_hint="cfb",
        description="ESPN CFB news, injuries, transfers, awards.",
    ),
    FeedSpec(
        name="ESPN Men's College Basketball",
        domain="espn.com",
        url="https://www.espn.com/espn/rss/ncb/news",
        default_category="NEWS",
        sport_hint="ncaab_mens",
        description="ESPN MCBB news.",
    ),
    FeedSpec(
        name="ESPN Women's College Basketball",
        domain="espn.com",
        url="https://www.espn.com/espn/rss/ncw/news",
        default_category="NEWS",
        sport_hint="ncaab_womens",
        description="ESPN WCBB news.",
    ),
    # ----- Tier-2: CBS Sports ---------------------------------------------
    FeedSpec(
        name="CBS Sports CFB",
        domain="cbssports.com",
        url="https://www.cbssports.com/rss/headlines/college-football/",
        default_category="NEWS",
        sport_hint="cfb",
        description="CBS Sports CFB headlines.",
    ),
    FeedSpec(
        name="CBS Sports CBB",
        domain="cbssports.com",
        url="https://www.cbssports.com/rss/headlines/college-basketball/",
        default_category="NEWS",
        sport_hint="ncaab_mens",
        description="CBS Sports CBB headlines.",
    ),
    # ----- Tier-2: 247Sports (recruiting + transfer) ----------------------
    FeedSpec(
        name="247Sports - Football",
        domain="247sports.com",
        url="https://247sports.com/rss",
        default_category="RECRUITING",
        description="247Sports recruiting + portal news.",
    ),
    # ----- Tier-1: AP wire ------------------------------------------------
    FeedSpec(
        name="AP - College Sports",
        domain="apnews.com",
        url="https://apnews.com/hub/college-sports/feed",
        default_category="NEWS",
        description="AP wire college coverage.",
    ),
    # ----- Tier-2: Yahoo Sports CFB ---------------------------------------
    FeedSpec(
        name="Yahoo Sports College",
        domain="sports.yahoo.com",
        url="https://sports.yahoo.com/college/rss",
        default_category="NEWS",
        description="Yahoo Sports college coverage.",
    ),
]


# ---------------------------------------------------------------------------
# Athlete / team matcher
# ---------------------------------------------------------------------------
@dataclass
class MatchResult:
    athlete_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None
    athlete_name: Optional[str] = None
    team_name: Optional[str] = None
    confidence: float = 0.0


_NAME_TOKEN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")


async def match_entity(
    db: asyncpg.Connection,
    *,
    title: str,
    body: str,
    sport_hint: Optional[str] = None,
) -> MatchResult:
    """Find the athlete or team this entry is most likely about.

    Strategy:
      1. Pull capitalized two-or-three-word phrases from title (people).
      2. For each phrase, look up ``athletes.name`` exact match
         (optionally filtered by sport hint).  First hit wins.
      3. If no athlete, scan title+body for any team's school_name
         substring; match the longest one.
      4. Return ``MatchResult`` with whichever fired (or empty).

    No fuzzy matching — exact case-folded match on names — to avoid
    pulling the wrong athlete when surnames collide.
    """
    text = f"{title or ''} {body or ''}"

    # ---- 1) Athlete match ----
    candidates: list[str] = []
    for m in _NAME_TOKEN.finditer(title or ""):
        candidates.append(m.group(1))
    # Also try the first capitalized phrase in the body (lead sentence
    # often names the subject).
    body_match = _NAME_TOKEN.search(body or "")
    if body_match:
        candidates.append(body_match.group(1))

    for name in candidates:
        rows = await db.fetch(
            """SELECT id, name, sport
                 FROM athletes
                WHERE LOWER(name) = LOWER($1)
                ORDER BY (sport = $2) DESC, name
                LIMIT 2""",
            name,
            sport_hint or "",
        )
        if len(rows) == 1:
            return MatchResult(
                athlete_id=rows[0]["id"],
                athlete_name=rows[0]["name"],
                confidence=0.9,
            )
        if len(rows) > 1 and sport_hint:
            for r in rows:
                if (r["sport"] or "").lower() == sport_hint.lower():
                    return MatchResult(
                        athlete_id=r["id"],
                        athlete_name=r["name"],
                        confidence=0.85,
                    )
        # Multiple candidates with no hint -> ambiguous, skip rather
        # than guess wrong.

    # ---- 2) Team match ----
    if sport_hint:
        team_rows = await db.fetch(
            "SELECT id, school_name FROM teams WHERE sport = $1",
            sport_hint,
        )
    else:
        team_rows = await db.fetch("SELECT id, school_name FROM teams")
    best_team = None
    best_len = 0
    text_lower = text.lower()
    for tr in team_rows:
        sn = (tr["school_name"] or "").strip()
        if len(sn) < 4:
            continue
        if sn.lower() in text_lower and len(sn) > best_len:
            best_team = tr
            best_len = len(sn)
    if best_team is not None:
        return MatchResult(
            team_id=best_team["id"],
            team_name=best_team["school_name"],
            confidence=0.7,
        )
    return MatchResult()


# ---------------------------------------------------------------------------
# Article-body fetcher (best-effort)
# ---------------------------------------------------------------------------
async def fetch_article_text(url: str) -> Optional[str]:
    """Best-effort fetch of the article HTML, stripped to plain text.

    Used only as input to the LLM fact-check.  If the fetch fails we
    return ``None`` and the ingest gate will fall back to tier-only
    trust (no LLM call).  We cap at 200 KB to avoid huge pages.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": "GravityScoreNewsBot/1.0 (+https://gravityscore.ai)"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return None
            html = resp.text[:200_000]
    except Exception as e:
        logger.info("article fetch failed for %s: %s", url, e)
        return None

    # Strip tags conservatively; we don't need DOM correctness, just the
    # words for the LLM to match against.
    text = re.sub(r"(?is)<script.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


# ---------------------------------------------------------------------------
# Collection result aggregator
# ---------------------------------------------------------------------------
@dataclass
class CollectionStats:
    feeds_processed: int = 0
    entries_seen: int = 0
    inserted: int = 0
    duplicates: int = 0
    rejected: int = 0
    unmatched: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def bump_category(self, c: str) -> None:
        self.by_category[c] = self.by_category.get(c, 0) + 1

    def bump_source(self, s: str) -> None:
        self.by_source[s] = self.by_source.get(s, 0) + 1


# ---------------------------------------------------------------------------
# Per-entry processing
# ---------------------------------------------------------------------------
def _published_dt(entry: Any) -> Optional[datetime]:
    for key in ("published_parsed", "updated_parsed"):
        st = getattr(entry, key, None) or entry.get(key) if isinstance(entry, dict) else None
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    return None


async def _process_entry(
    db: asyncpg.Connection,
    *,
    entry: Any,
    feed_spec: FeedSpec,
    scraper_run_id: uuid.UUID,
    use_llm: bool,
    stats: CollectionStats,
) -> None:
    title = (entry.get("title") if isinstance(entry, dict) else getattr(entry, "title", None)) or ""
    summary = (entry.get("summary") if isinstance(entry, dict) else getattr(entry, "summary", None)) or ""
    link = (entry.get("link") if isinstance(entry, dict) else getattr(entry, "link", None)) or ""

    if not title or not link:
        return
    stats.entries_seen += 1

    # Strip HTML out of summary so the classifier and matcher see plain
    # text (RSS summaries often include <p>, <a> tags).
    body = re.sub(r"<[^>]+>", " ", summary or "")
    body = re.sub(r"\s+", " ", body).strip()

    # Category resolution: rule-based classifier always wins.  We only
    # fall back to the feed's default_category when the classifier
    # bottomed out at NEWS *and* the feed is mono-topic (e.g. a
    # dedicated NIL deals RSS where every story is by definition a NIL
    # deal).  General news feeds (On3 main, ESPN, CBS) always honor
    # the classifier's verdict so we don't mis-tag NFL Draft stories
    # as NIL deals just because On3 happens to cover both.
    classified, conf = classify_text(title, body)
    if classified == "NEWS" and feed_spec.mono_topic and feed_spec.default_category != "NEWS":
        category = feed_spec.default_category
        conf = 0.55
    else:
        category = classified

    occurred_at = _published_dt(entry) or datetime.now(timezone.utc)
    published_at = _published_dt(entry)

    # Match to athlete/team
    match = await match_entity(
        db, title=title, body=body, sport_hint=feed_spec.sport_hint
    )
    if not match.athlete_id and not match.team_id:
        stats.unmatched += 1
        return

    # Optional LLM verification — only invoked for high-stakes
    # categories where false claims would hurt most (NIL deals,
    # incidents, transfers).  Other categories trust tier-only to keep
    # the LLM bill bounded.
    needs_llm = use_llm and category in ("NIL_DEAL", "INCIDENT", "TRANSFER", "BUSINESS")
    article_text: Optional[str] = None
    extracted_claim: Optional[str] = None
    if needs_llm:
        article_text = await fetch_article_text(link)
        # We use the headline as the "claim" because that is the
        # promise the article makes; the LLM checks the body actually
        # supports it.
        extracted_claim = title

    try:
        if match.athlete_id:
            result: IngestResult = await ingest_athlete_event(
                db,
                athlete_id=match.athlete_id,
                category=category,
                title=title[:400],
                description=body[:1000] if body else None,
                occurred_at=occurred_at,
                published_at=published_at,
                source_url=link,
                article_text=article_text,
                extracted_claim=extracted_claim,
                key_fact=f"{category}|{title}",
                require_llm=False,  # we already decided whether to LLM above
                scraper_run_id=scraper_run_id,
                metadata={
                    "feed": feed_spec.name,
                    "classifier_confidence": conf,
                    "matcher_confidence": match.confidence,
                },
            )
        else:
            assert match.team_id is not None
            result = await ingest_team_event(
                db,
                team_id=match.team_id,
                category=category,
                title=title[:400],
                body=body[:1000] if body else None,
                occurred_at=occurred_at,
                published_at=published_at,
                source_url=link,
                article_text=article_text,
                extracted_claim=extracted_claim,
                key_fact=f"{category}|{title}",
                require_llm=False,
                scraper_run_id=scraper_run_id,
                metadata={
                    "feed": feed_spec.name,
                    "classifier_confidence": conf,
                    "matcher_confidence": match.confidence,
                },
            )
        if result.inserted:
            stats.inserted += 1
            stats.bump_category(category)
            stats.bump_source(feed_spec.domain)
        elif result.rejected_reason == "duplicate_url":
            stats.duplicates += 1
        else:
            stats.rejected += 1
    except IngestRejected as e:
        stats.rejected += 1
        # Already logged to extraction_rejections inside news_ingest.
        logger.debug("ingest rejected: %s [%s] (%s)", e.reason, link, e.detail)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
async def collect_feed(
    db: asyncpg.Connection,
    spec: FeedSpec,
    *,
    scraper_run_id: uuid.UUID,
    max_entries: int = 50,
    use_llm: bool = True,
    stats: Optional[CollectionStats] = None,
) -> CollectionStats:
    """Pull a single feed, process up to ``max_entries`` items."""
    stats = stats or CollectionStats()
    try:
        # feedparser is sync — push it off the event loop.
        loop = asyncio.get_running_loop()
        parsed = await loop.run_in_executor(None, feedparser.parse, spec.url)
        entries = list(parsed.entries[:max_entries])
        for entry in entries:
            try:
                await _process_entry(
                    db,
                    entry=entry,
                    feed_spec=spec,
                    scraper_run_id=scraper_run_id,
                    use_llm=use_llm,
                    stats=stats,
                )
            except Exception as e:  # noqa: BLE001
                stats.errors.append(f"{spec.domain}: {type(e).__name__}: {e}")
                logger.exception("entry failed for %s", spec.url)
        stats.feeds_processed += 1
    except Exception as e:  # noqa: BLE001
        stats.errors.append(f"{spec.domain} parse error: {e}")
        logger.exception("feed parse failed for %s", spec.url)
    return stats


async def collect_all(
    db: asyncpg.Connection,
    *,
    feeds: Optional[Iterable[FeedSpec]] = None,
    use_llm: bool = True,
    max_entries_per_feed: int = 50,
) -> CollectionStats:
    """Run every feed in ``FEED_REGISTRY`` (or a subset) sequentially.

    Sequential rather than parallel so we don't spawn 12 simultaneous
    LLM calls.  Each feed is independent — if one source returns an
    empty body or 4xx we keep going.
    """
    stats = CollectionStats()
    run_id = uuid.uuid4()
    t0 = time.time()
    target = list(feeds) if feeds is not None else FEED_REGISTRY
    for spec in target:
        await collect_feed(
            db,
            spec,
            scraper_run_id=run_id,
            max_entries=max_entries_per_feed,
            use_llm=use_llm,
            stats=stats,
        )
    logger.info(
        "news collection complete: feeds=%d entries=%d inserted=%d dupes=%d rejected=%d unmatched=%d in %.1fs",
        stats.feeds_processed,
        stats.entries_seen,
        stats.inserted,
        stats.duplicates,
        stats.rejected,
        stats.unmatched,
        time.time() - t0,
    )
    return stats


# ---------------------------------------------------------------------------
# Coverage report — what we *expect* to surface vs. what we have
# ---------------------------------------------------------------------------
TARGET_CATEGORIES = [
    "NIL_DEAL",
    "TRANSFER",
    "INJURY",
    "NEWS",
    "AWARD",
    "RECRUITING",
    "PERFORMANCE",
    "ANNOUNCEMENT",
    "BUSINESS",
    "INCIDENT",
]


async def coverage_report(db: asyncpg.Connection) -> dict[str, Any]:
    """Per-category counts from the live DB plus the registered feeds
    that should populate each category."""
    rows = await db.fetch(
        """SELECT category, source_domain, source_tier,
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE occurred_at > NOW() - INTERVAL '7 days') AS last_7d,
                  MAX(occurred_at) AS most_recent
             FROM athlete_events
            WHERE retracted_at IS NULL
            GROUP BY category, source_domain, source_tier
            ORDER BY category, source_tier"""
    )
    team_rows = await db.fetch(
        """SELECT category, source_domain, source_tier,
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE occurred_at > NOW() - INTERVAL '7 days') AS last_7d,
                  MAX(occurred_at) AS most_recent
             FROM team_events
            WHERE retracted_at IS NULL
            GROUP BY category, source_domain, source_tier
            ORDER BY category, source_tier"""
    )

    # Reshape into per-category buckets.
    categories: dict[str, dict[str, Any]] = {}
    for cat in TARGET_CATEGORIES:
        feeds_for_cat = [
            {
                "name": s.name,
                "domain": s.domain,
                "url": s.url,
                "sport": s.sport_hint,
            }
            for s in FEED_REGISTRY
            if s.default_category == cat
            or any(r.category == cat for r in CATEGORY_RULES if r.category == cat)
        ]
        categories[cat] = {
            "category": cat,
            "expected_feeds": feeds_for_cat,
            "athlete_event_total": 0,
            "athlete_event_last_7d": 0,
            "team_event_total": 0,
            "team_event_last_7d": 0,
            "most_recent": None,
            "by_source": [],
        }

    for r in rows:
        cat = r["category"]
        if cat not in categories:
            continue
        bucket = categories[cat]
        bucket["athlete_event_total"] += int(r["total"])
        bucket["athlete_event_last_7d"] += int(r["last_7d"])
        most = r["most_recent"]
        if most and (bucket["most_recent"] is None or most > bucket["most_recent"]):
            bucket["most_recent"] = most
        bucket["by_source"].append(
            {
                "domain": r["source_domain"],
                "tier": r["source_tier"],
                "kind": "athlete_event",
                "total": int(r["total"]),
                "last_7d": int(r["last_7d"]),
            }
        )
    for r in team_rows:
        cat = r["category"]
        if cat not in categories:
            continue
        bucket = categories[cat]
        bucket["team_event_total"] += int(r["total"])
        bucket["team_event_last_7d"] += int(r["last_7d"])
        most = r["most_recent"]
        if most and (bucket["most_recent"] is None or most > bucket["most_recent"]):
            bucket["most_recent"] = most
        bucket["by_source"].append(
            {
                "domain": r["source_domain"],
                "tier": r["source_tier"],
                "kind": "team_event",
                "total": int(r["total"]),
                "last_7d": int(r["last_7d"]),
            }
        )

    out = []
    for cat in TARGET_CATEGORIES:
        bucket = categories[cat]
        bucket["most_recent"] = (
            bucket["most_recent"].isoformat() if bucket["most_recent"] else None
        )
        # Health flag: red = no rows in 7d, yellow = some but no expected
        # source matched, green = recent rows landed.
        recent = bucket["athlete_event_last_7d"] + bucket["team_event_last_7d"]
        if recent > 0:
            bucket["status"] = "ok"
        elif bucket["expected_feeds"]:
            bucket["status"] = "stale"
        else:
            bucket["status"] = "no_feed_configured"
        out.append(bucket)

    return {
        "categories": out,
        "feeds_registered": len(FEED_REGISTRY),
    }
