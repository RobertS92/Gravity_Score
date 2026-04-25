"""Production-grade ingest gate for athlete & team news.

This is the **only** code path that should write to ``athlete_events`` /
``team_events`` / ``athlete_nil_deals``.  External scrapers reach it via
the admin-gated ``/v1/ingest`` router; internal jobs call it directly.

The gate enforces, in order:

1. **Source allowlist + tier check.**  The ``source_domain`` must exist
   in ``news_sources`` and be ``enabled``.  Tier 4 (blocked) is rejected
   regardless.  This kills random-domain spam.
2. **URL provenance.**  ``source_url`` must be non-empty and parse to a
   real http(s) URL.  No URL → no ingest.
3. **URL dedupe.**  Hash the canonical URL and reject if we already have
   that URL in the relevant table — same article, same domain, no
   re-ingest.
4. **LLM fact-check (optional but recommended).**  When the caller hands
   us an extracted ``claim`` plus the article text, we ask Claude whether
   the article actually states that claim.  If ``supports=false`` or
   ``confidence<0.7`` we *do not persist* — we log to
   ``extraction_rejections`` and return.  Hallucinations stop here.
5. **Cross-source verification.**  Every claim gets a ``claim_hash``
   (athlete_id|category|key_fact, normalized).  When a 2nd row with the
   same ``claim_hash`` lands from a *different* tier-1/2 domain within
   24h, both rows flip to ``MULTI_SOURCE``.  This is how items earn
   trust without manual review.
6. **Verification level on insert.**  Default policy:

      tier 1 + LLM-verified         -> SINGLE_SOURCE (promotable)
      tier 2 + LLM-verified         -> SINGLE_SOURCE
      tier 3                        -> LOW_CONFIDENCE
      official social / press box   -> OFFICIAL  (caller passes flag)
      no LLM check                  -> SINGLE_SOURCE if tier<=2 else LOW_CONFIDENCE

   ``UNVERIFIED`` is reserved for legacy / pre-migration rows.

All rejections are logged to ``extraction_rejections`` so we can
post-mortem any "why didn't this story show up" question.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import asyncpg

from gravity_api.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public errors
# ---------------------------------------------------------------------------
class IngestRejected(Exception):
    """Raised when an item fails the gate.  ``reason`` is a short token
    suitable for the ``extraction_rejections.reason`` column."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# Result shapes
# ---------------------------------------------------------------------------
@dataclass
class IngestResult:
    inserted: bool
    event_id: Optional[uuid.UUID]
    verification: str
    promoted_to_multi_source: bool = False
    rejected_reason: Optional[str] = None
    rejected_detail: Optional[str] = None


# ---------------------------------------------------------------------------
# URL & claim helpers
# ---------------------------------------------------------------------------
_URL_TRACKING_PARAMS = re.compile(
    r"(?i)(^|&)(utm_[^=&]+|gclid|fbclid|mc_cid|mc_eid|ref|ref_src|ref_url)=[^&]*"
)


def _canonicalize_url(url: str) -> str:
    """Strip tracking params + lowercase host so we can dedupe across
    Twitter / Facebook / newsletter rewrites of the same article."""
    try:
        p = urlparse(url.strip())
    except Exception:
        return url.strip().lower()
    if not p.scheme or not p.netloc:
        return url.strip().lower()
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = p.query or ""
    query = _URL_TRACKING_PARAMS.sub("", query).lstrip("&")
    rebuilt = f"{p.scheme.lower()}://{host}{p.path or ''}"
    if query:
        rebuilt += f"?{query}"
    if p.fragment and not p.fragment.startswith("/"):
        # Drop client-only fragments — they don't change the article.
        pass
    return rebuilt.rstrip("/")


def _domain_of(url: str) -> Optional[str]:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host


def _hash_url(url: str) -> str:
    return hashlib.sha256(_canonicalize_url(url).encode("utf-8")).hexdigest()


def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def claim_hash(
    *,
    athlete_id: Optional[uuid.UUID],
    team_id: Optional[uuid.UUID],
    category: str,
    key_fact: str,
) -> str:
    """Stable hash of a claim so the same fact from two outlets collides.

    ``key_fact`` should be the *content* of the claim, not the headline —
    e.g. for an NIL deal it's ``"{brand}|{value_bucket}|{deal_type}"``;
    for a transfer it's ``"transfer|{from}|{to}"``; for an injury it's
    ``"{status}|{date_iso}"``.  Slugified before hashing so case &
    whitespace don't fork the hash.
    """
    parts = [
        str(athlete_id or ""),
        str(team_id or ""),
        (category or "").upper(),
        _slugify(key_fact or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# LLM fact-check
# ---------------------------------------------------------------------------
async def llm_verify_claim(
    *,
    article_text: str,
    claim: str,
    timeout_s: float = 25.0,
) -> dict[str, Any]:
    """Ask Claude whether ``article_text`` actually supports ``claim``.

    Returns ``{supports: bool, confidence: float (0-1), exact_quote: str
    | None, reasoning: str}``.  On any error returns
    ``{supports: False, confidence: 0.0, exact_quote: None, reasoning:
    "llm_unavailable"}`` so callers can decide policy.
    """
    settings = get_settings()
    api_key = settings.anthropic_api_key
    if not api_key:
        return {"supports": False, "confidence": 0.0, "exact_quote": None,
                "reasoning": "llm_unavailable"}

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return {"supports": False, "confidence": 0.0, "exact_quote": None,
                "reasoning": "llm_unavailable"}

    # Keep the prompt extractive and JSON-only so we don't burn tokens.
    article_snippet = (article_text or "").strip()
    if len(article_snippet) > 12000:
        article_snippet = article_snippet[:12000] + "\n[truncated]"

    system = (
        "You are a strict fact-checker. Decide whether the ARTICLE explicitly "
        "supports the CLAIM. Return ONLY JSON of the form "
        '{"supports": <bool>, "confidence": <0-1>, "exact_quote": <string|null>, '
        '"reasoning": <short string>}. '
        "If the article does not contain the claim verbatim or in obvious "
        "paraphrase, set supports=false."
    )
    user = f"CLAIM: {claim.strip()}\n\nARTICLE:\n{article_snippet}"

    client = AsyncAnthropic(api_key=api_key, timeout=timeout_s)
    model = (settings.anthropic_model or "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        logger.warning("llm_verify_claim failed: %s", e)
        return {"supports": False, "confidence": 0.0, "exact_quote": None,
                "reasoning": f"llm_error:{type(e).__name__}"}

    raw = ""
    try:
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                raw += block.text
    except Exception:
        raw = ""

    raw = raw.strip()
    # Strip ```json fences if the model is being chatty.
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except Exception:
        return {"supports": False, "confidence": 0.0, "exact_quote": None,
                "reasoning": "llm_unparseable"}

    return {
        "supports": bool(parsed.get("supports", False)),
        "confidence": float(parsed.get("confidence") or 0.0),
        "exact_quote": parsed.get("exact_quote") or None,
        "reasoning": str(parsed.get("reasoning") or "")[:500],
    }


# ---------------------------------------------------------------------------
# Source allowlist lookup
# ---------------------------------------------------------------------------
async def _source_for_domain(
    db: asyncpg.Connection, domain: str
) -> Optional[asyncpg.Record]:
    return await db.fetchrow(
        "SELECT domain, display_name, tier, enabled FROM news_sources WHERE domain = $1",
        domain,
    )


# ---------------------------------------------------------------------------
# Verification policy
# ---------------------------------------------------------------------------
def _initial_verification(
    *,
    tier: int,
    llm: Optional[dict[str, Any]],
    is_official: bool,
    require_llm: bool,
) -> tuple[str, float]:
    if is_official:
        return "OFFICIAL", 1.0
    if tier >= 4:
        return "LOW_CONFIDENCE", 0.0
    if llm is None:
        if require_llm:
            return "LOW_CONFIDENCE", 0.0
        # No claim was extracted (e.g. ranking, roster move) — trust by tier.
        return ("SINGLE_SOURCE" if tier <= 2 else "LOW_CONFIDENCE"), (0.7 if tier == 1 else 0.6 if tier == 2 else 0.4)
    if not llm.get("supports"):
        return "REJECT", 0.0  # sentinel; caller turns this into IngestRejected
    conf = float(llm.get("confidence") or 0.0)
    if conf < 0.7:
        return "REJECT", conf
    if tier == 1:
        return "SINGLE_SOURCE", conf
    if tier == 2:
        return "SINGLE_SOURCE", conf
    return "LOW_CONFIDENCE", conf


# ---------------------------------------------------------------------------
# Cross-source promotion
# ---------------------------------------------------------------------------
async def _promote_if_multi_source(
    db: asyncpg.Connection,
    *,
    table: str,
    new_event_id: uuid.UUID,
    claim_hash_value: str,
    new_domain: str,
    new_tier: int,
    new_occurred_at: datetime,
) -> bool:
    """If another row with the same claim_hash exists from a *different*
    tier-1/2 domain within 24h, flip both rows to MULTI_SOURCE.  Returns
    True if a promotion happened."""
    if not claim_hash_value or new_tier > 2:
        return False
    window_start = new_occurred_at - timedelta(hours=24)
    other = await db.fetchrow(
        f"""SELECT id, source_domain, source_tier
              FROM {table}
             WHERE claim_hash = $1
               AND source_domain IS DISTINCT FROM $2
               AND source_tier <= 2
               AND occurred_at >= $3
               AND id <> $4
             LIMIT 1""",
        claim_hash_value,
        new_domain,
        window_start,
        new_event_id,
    )
    if other is None:
        return False
    await db.execute(
        f"UPDATE {table} SET verification = 'MULTI_SOURCE' WHERE id IN ($1, $2) "
        f"AND verification IN ('SINGLE_SOURCE','LOW_CONFIDENCE')",
        new_event_id,
        other["id"],
    )
    return True


# ---------------------------------------------------------------------------
# Rejection logger
# ---------------------------------------------------------------------------
async def _log_rejection(
    db: asyncpg.Connection,
    *,
    athlete_id: Optional[uuid.UUID],
    team_id: Optional[uuid.UUID],
    category: Optional[str],
    title: Optional[str],
    claim: Optional[str],
    source_domain: Optional[str],
    source_url: Optional[str],
    reason: str,
    llm_response: Optional[dict[str, Any]],
    scraper_run_id: Optional[uuid.UUID],
) -> None:
    try:
        await db.execute(
            """INSERT INTO extraction_rejections
                   (athlete_id, team_id, attempted_category, attempted_title,
                    attempted_claim, source_domain, source_url, reason,
                    llm_response, scraper_run_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)""",
            athlete_id,
            team_id,
            category,
            title,
            claim,
            source_domain,
            source_url,
            reason,
            json.dumps(llm_response) if llm_response else None,
            scraper_run_id,
        )
    except Exception as e:  # noqa: BLE001 — never fail ingest because of audit
        logger.warning("failed to log extraction_rejection: %s", e)


# ---------------------------------------------------------------------------
# Public ingest API
# ---------------------------------------------------------------------------
async def ingest_athlete_event(
    db: asyncpg.Connection,
    *,
    athlete_id: uuid.UUID,
    category: str,
    title: str,
    description: Optional[str],
    occurred_at: datetime,
    published_at: Optional[datetime],
    source_url: str,
    article_text: Optional[str] = None,
    extracted_claim: Optional[str] = None,
    key_fact: Optional[str] = None,
    is_official: bool = False,
    require_llm: bool = True,
    metadata: Optional[dict[str, Any]] = None,
    scraper_run_id: Optional[uuid.UUID] = None,
) -> IngestResult:
    """Validate, fact-check, and persist a single athlete event.

    Raises ``IngestRejected`` for hard policy failures (unknown domain,
    blocked tier, missing URL, dedupe collision, LLM refutation).
    Returns ``IngestResult`` on success.
    """
    if not source_url or not source_url.strip():
        raise IngestRejected("missing_source_url")

    domain = _domain_of(source_url)
    if not domain:
        raise IngestRejected("unparseable_source_url", source_url)

    src = await _source_for_domain(db, domain)
    if src is None:
        await _log_rejection(
            db, athlete_id=athlete_id, team_id=None, category=category,
            title=title, claim=extracted_claim, source_domain=domain,
            source_url=source_url, reason="unknown_source",
            llm_response=None, scraper_run_id=scraper_run_id,
        )
        raise IngestRejected("unknown_source", domain)
    if not src["enabled"] or src["tier"] >= 4:
        await _log_rejection(
            db, athlete_id=athlete_id, team_id=None, category=category,
            title=title, claim=extracted_claim, source_domain=domain,
            source_url=source_url, reason="blocked_source",
            llm_response=None, scraper_run_id=scraper_run_id,
        )
        raise IngestRejected("blocked_source", domain)

    tier = int(src["tier"])
    display_name = str(src["display_name"])
    url_hash = _hash_url(source_url)

    # Dedupe by URL — same article, no re-ingest.
    dup = await db.fetchrow(
        "SELECT id FROM athlete_events WHERE source_url_hash = $1 AND athlete_id = $2",
        url_hash,
        athlete_id,
    )
    if dup is not None:
        return IngestResult(inserted=False, event_id=dup["id"],
                            verification="duplicate",
                            rejected_reason="duplicate_url")

    # LLM fact-check when caller provided a claim + article body.
    llm_result: Optional[dict[str, Any]] = None
    if extracted_claim and article_text:
        llm_result = await llm_verify_claim(
            article_text=article_text, claim=extracted_claim
        )

    verification, confidence = _initial_verification(
        tier=tier, llm=llm_result, is_official=is_official,
        require_llm=require_llm and bool(extracted_claim),
    )
    if verification == "REJECT":
        await _log_rejection(
            db, athlete_id=athlete_id, team_id=None, category=category,
            title=title, claim=extracted_claim, source_domain=domain,
            source_url=source_url, reason="llm_refuted",
            llm_response=llm_result, scraper_run_id=scraper_run_id,
        )
        raise IngestRejected(
            "llm_refuted",
            f"confidence={confidence:.2f} reasoning={(llm_result or {}).get('reasoning')}",
        )

    chash = (
        claim_hash(athlete_id=athlete_id, team_id=None, category=category,
                   key_fact=key_fact)
        if key_fact else None
    )
    exact_quote = (llm_result or {}).get("exact_quote") if llm_result else None

    row = await db.fetchrow(
        """INSERT INTO athlete_events
               (athlete_id, event_type, category, title, description,
                occurred_at, published_at, metadata, event_source,
                source_name, source_domain, source_url, source_url_hash,
                source_tier, scraper_run_id, verification,
                confidence_score, claim_hash, exact_quote)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,
                   $10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
           RETURNING id, occurred_at""",
        athlete_id,
        category,        # event_type kept for legacy queries
        category,
        title,
        description,
        occurred_at,
        published_at,
        json.dumps(metadata or {}),
        domain,          # event_source = domain (replaces 'unknown')
        display_name,
        domain,
        source_url,
        url_hash,
        tier,
        scraper_run_id,
        verification,
        round(confidence, 3),
        chash,
        exact_quote,
    )

    promoted = False
    if chash:
        promoted = await _promote_if_multi_source(
            db,
            table="athlete_events",
            new_event_id=row["id"],
            claim_hash_value=chash,
            new_domain=domain,
            new_tier=tier,
            new_occurred_at=row["occurred_at"],
        )
    final_verif = "MULTI_SOURCE" if promoted else verification
    return IngestResult(
        inserted=True,
        event_id=row["id"],
        verification=final_verif,
        promoted_to_multi_source=promoted,
    )


async def ingest_team_event(
    db: asyncpg.Connection,
    *,
    team_id: uuid.UUID,
    category: str,
    title: str,
    body: Optional[str],
    occurred_at: datetime,
    published_at: Optional[datetime],
    source_url: str,
    article_text: Optional[str] = None,
    extracted_claim: Optional[str] = None,
    key_fact: Optional[str] = None,
    is_official: bool = False,
    require_llm: bool = True,
    metadata: Optional[dict[str, Any]] = None,
    scraper_run_id: Optional[uuid.UUID] = None,
) -> IngestResult:
    """Same gate, team-level edition."""
    if not source_url or not source_url.strip():
        raise IngestRejected("missing_source_url")

    domain = _domain_of(source_url)
    if not domain:
        raise IngestRejected("unparseable_source_url", source_url)

    src = await _source_for_domain(db, domain)
    if src is None:
        await _log_rejection(
            db, athlete_id=None, team_id=team_id, category=category,
            title=title, claim=extracted_claim, source_domain=domain,
            source_url=source_url, reason="unknown_source",
            llm_response=None, scraper_run_id=scraper_run_id,
        )
        raise IngestRejected("unknown_source", domain)
    if not src["enabled"] or src["tier"] >= 4:
        raise IngestRejected("blocked_source", domain)

    tier = int(src["tier"])
    display_name = str(src["display_name"])
    url_hash = _hash_url(source_url)

    dup = await db.fetchrow(
        "SELECT id FROM team_events WHERE source_url_hash = $1 AND team_id = $2",
        url_hash,
        team_id,
    )
    if dup is not None:
        return IngestResult(inserted=False, event_id=dup["id"],
                            verification="duplicate",
                            rejected_reason="duplicate_url")

    llm_result: Optional[dict[str, Any]] = None
    if extracted_claim and article_text:
        llm_result = await llm_verify_claim(
            article_text=article_text, claim=extracted_claim
        )

    verification, confidence = _initial_verification(
        tier=tier, llm=llm_result, is_official=is_official,
        require_llm=require_llm and bool(extracted_claim),
    )
    if verification == "REJECT":
        await _log_rejection(
            db, athlete_id=None, team_id=team_id, category=category,
            title=title, claim=extracted_claim, source_domain=domain,
            source_url=source_url, reason="llm_refuted",
            llm_response=llm_result, scraper_run_id=scraper_run_id,
        )
        raise IngestRejected("llm_refuted")

    chash = (
        claim_hash(athlete_id=None, team_id=team_id, category=category,
                   key_fact=key_fact)
        if key_fact else None
    )
    exact_quote = (llm_result or {}).get("exact_quote") if llm_result else None

    row = await db.fetchrow(
        """INSERT INTO team_events
               (team_id, event_type, category, title, body,
                occurred_at, published_at, metadata, source, source_url,
                source_name, source_domain, source_url_hash, source_tier,
                scraper_run_id, verification, confidence_score,
                claim_hash, exact_quote)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,
                   $11,$12,$13,$14,$15,$16,$17,$18,$19)
           RETURNING id, occurred_at""",
        team_id,
        category,
        category,
        title,
        body,
        occurred_at,
        published_at,
        json.dumps(metadata or {}),
        display_name,
        source_url,
        display_name,
        domain,
        url_hash,
        tier,
        scraper_run_id,
        verification,
        round(confidence, 3),
        chash,
        exact_quote,
    )

    promoted = False
    if chash:
        promoted = await _promote_if_multi_source(
            db,
            table="team_events",
            new_event_id=row["id"],
            claim_hash_value=chash,
            new_domain=domain,
            new_tier=tier,
            new_occurred_at=row["occurred_at"],
        )
    final_verif = "MULTI_SOURCE" if promoted else verification
    return IngestResult(
        inserted=True,
        event_id=row["id"],
        verification=final_verif,
        promoted_to_multi_source=promoted,
    )
