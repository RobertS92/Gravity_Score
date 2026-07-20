"""Micro-scraper implementations — quality boosters, core, achievements, pro college."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.scrapers.base import BaseMicroScraper, sport_from_any_key
from gravity_api.scrapers.clients.cfbd import CfbdClient
from gravity_api.scrapers.clients.espn import EspnClient, normalize_sport
from gravity_api.scrapers.clients.firecrawl import FirecrawlClient
from gravity_api.scrapers.clients.kenpom import KenPomClient, parse_kenpom_markdown
from gravity_api.scrapers.clients.wikipedia import WikipediaClient
from gravity_api.scrapers.db_context import get_scrape_db
from gravity_api.scrapers.parsers.achievements import merge_espn_awards, parse_achievements_from_text
from gravity_api.scrapers.parsers.common import parse_count, slugify_school
from gravity_api.scrapers.parsers.nil import parse_nil_deals_from_text, parse_nil_from_text, verify_nil_consensus
from gravity_api.scraper_registry.field_sufficiency import MIN_REAL_INSTAGRAM_FOLLOWERS, is_sufficient
from gravity_api.scrapers.parsers.quality_label import apply_external_quality_fields
from gravity_api.scrapers.parsers.opendorse import parse_opendorse_profile
from gravity_api.scrapers.parsers.recruiting import parse_247_recruiting_profile
from gravity_api.scrapers.parsers.roster import parse_roster_presence, parse_transfer_portal
from gravity_api.scrapers.parsers.sports_reference import (
    parse_sports_ref_honors,
    ref_domain_for_sport,
)
from gravity_api.scrapers.parsers.handle_discovery import (
    apply_user_instagram_upload,
    bio_matches_athlete,
    extract_bio_from_page,
    google_instagram_search_url,
    google_site_search_url,
    has_trusted_instagram_handle,
    is_user_provided_instagram,
    merge_non_instagram_handles,
    passes_authenticity_gate,
    resolve_instagram_fields,
)
from gravity_api.scrapers.parsers.social import (
    authenticity_score,
    fetch_instagram_followers_from_text,
    handles_from_page,
    instagram_aggregator_urls,
    parse_engagement_from_markdown,
)
from gravity_api.scrapers.parsers.site_search import (
    SITE_SEARCH_CONFIG,
    scrape_site_fields,
    site_suffix_for_key,
)
from gravity_api.scrapers.types import AthleteScrapeContext, ScraperResult

logger = logging.getLogger(__name__)


class SocialHandleDiscoveryScraper(BaseMicroScraper):
    KEY_SUFFIX = "social_handle_discovery"
    SOURCE_KEY = "derived"

    async def _fetch_source_markdown(
        self, fc: FirecrawlClient, url: str, source: str
    ) -> dict[str, str] | None:
        try:
            md = await fc.scrape_markdown(url)
            if md:
                return handles_from_page(md, source)
        except Exception as e:
            logger.debug("handle discovery %s failed: %s", source, e)
        return None

    async def _bio_verify_candidate(
        self,
        fc: FirecrawlClient,
        handle: str,
        ctx: AthleteScrapeContext,
    ) -> tuple[bool, str]:
        for url in instagram_aggregator_urls(handle):
            try:
                md = await fc.scrape_markdown(url)
                bio = extract_bio_from_page(md)
                if bio and bio_matches_athlete(
                    bio,
                    name=ctx.name,
                    school=ctx.school or ctx.team,
                    sport=ctx.sport,
                    position=ctx.position,
                ):
                    return True, bio
            except Exception as e:
                logger.debug("bio verify failed for %s: %s", handle, e)
        return False, ""

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        raw = ctx.existing_raw
        if is_user_provided_instagram(raw) and raw.get("instagram_handle"):
            fields = apply_user_instagram_upload(dict(raw))
            return self._result(scraper_key, fields=fields, confidence=1.0)
        if has_trusted_instagram_handle(raw):
            return self._result(
                scraper_key,
                fields={
                    "instagram_handle": raw.get("instagram_handle"),
                    "instagram_handle_source": raw.get("instagram_handle_source")
                    or raw.get("handle_source"),
                    "handle_source": raw.get("handle_source"),
                    "handle_confidence": raw.get("handle_confidence") or 0.9,
                },
                confidence=float(raw.get("handle_confidence") or 0.9),
            )

        espn = EspnClient()
        fc = FirecrawlClient()
        wiki = WikipediaClient()
        sources: list[dict[str, str]] = []
        espn_id = ctx.espn_id or raw.get("espn_id")
        if not espn_id:
            espn_id = await espn.search_athlete(ctx.name, ctx.sport, team=ctx.school or ctx.team)
        if espn_id:
            profile = await espn.get_athlete_profile(str(espn_id), ctx.sport)
            ident = profile.get("identity") or {}
            for platform, url_key in (
                ("instagram", "instagram_profile_url"),
                ("twitter", "twitter_profile_url"),
                ("tiktok", "tiktok_profile_url"),
            ):
                url = ident.get(url_key)
                if url:
                    sources.append(handles_from_page(url + f"\n{platform}.com/", "espn"))

        if fc.enabled:
            school = ctx.school or ctx.team
            search_jobs: list[tuple[str, str]] = [
                (
                    google_instagram_search_url(ctx.name, school, ctx.position),
                    "google_instagram",
                ),
                (google_site_search_url(ctx.name, school, "247sports.com"), "247sports"),
                (google_site_search_url(ctx.name, school, "on3.com"), "on3_nil"),
            ]
            if school:
                q = urllib.parse.quote(f'"{ctx.name}" "{school}" roster instagram')
                search_jobs.append(
                    (f"https://www.google.com/search?q={q}", "team_roster")
                )
            for url, source in search_jobs:
                found = await self._fetch_source_markdown(fc, url, source)
                if found:
                    sources.append(found)

        try:
            title = await wiki.resolve_title(ctx.name)
            if title:
                extract = await wiki.fetch_page_extract(title)
                if extract:
                    sources.append(handles_from_page(extract, "wikipedia"))
        except Exception as e:
            logger.debug("wikipedia handle discovery: %s", e)

        bio_by_handle: dict[str, str] = {}
        ig_fields = resolve_instagram_fields(
            sources,
            name=ctx.name,
            school=ctx.school or ctx.team,
            sport=ctx.sport,
            position=ctx.position,
            bio_by_handle=bio_by_handle,
        )

        candidate = ig_fields.get("instagram_handle_candidate")
        if candidate and not ig_fields.get("instagram_handle") and fc.enabled:
            verified, bio = await self._bio_verify_candidate(fc, str(candidate), ctx)
            if verified:
                ig_fields["instagram_handle"] = candidate
                ig_fields["instagram_handle_source"] = "bio_verified"
                ig_fields["handle_source"] = "bio_verified"
                ig_fields["instagram_handle_bio_verified"] = 1
                ig_fields["instagram_bio"] = bio
                ig_fields.pop("instagram_handle_candidate", None)
                ig_fields.pop("instagram_handle_candidate_source", None)
                ig_fields.pop("instagram_handle_candidate_sources", None)
                ig_fields["handle_confidence"] = 0.78

        other = merge_non_instagram_handles(*sources)
        fields: dict[str, Any] = {**other, **ig_fields}
        if ig_fields.get("instagram_handle_candidate") and not ig_fields.get("instagram_handle"):
            fields.pop("instagram_handle", None)
        return self._result(
            scraper_key,
            fields=fields,
            confidence=float(fields.get("handle_confidence") or 0.5),
        )


class SocialEngagementInstagramScraper(BaseMicroScraper):
    KEY_SUFFIX = "social_engagement_instagram"
    SOURCE_KEY = "instagram"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        handle = ctx.existing_raw.get("instagram_handle")
        fc = FirecrawlClient()
        if not handle or not fc.enabled:
            return self._result(scraper_key, fields={}, error="missing handle or firecrawl")
        if (
            is_sufficient(ctx.existing_raw, "instagram_followers")
            and ctx.existing_raw.get("instagram_engagement_rate")
        ):
            return self._result(
                scraper_key,
                fields={
                    "instagram_followers": ctx.existing_raw.get("instagram_followers"),
                    "instagram_followers_observed": ctx.existing_raw.get(
                        "instagram_followers_observed", 1
                    ),
                    "instagram_engagement_rate": ctx.existing_raw.get(
                        "instagram_engagement_rate"
                    ),
                    "posts_30d": ctx.existing_raw.get("posts_30d"),
                },
                confidence=0.78,
            )
        try:
            md = await fc.scrape_markdown(f"https://www.instagram.com/{handle.lstrip('@')}/")
            parsed = parse_engagement_from_markdown(md)
            parsed["posts_30d"] = parsed.get("posts_sampled")
            return self._result(scraper_key, fields=parsed, confidence=0.78)
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))


class SocialEngagementTiktokScraper(BaseMicroScraper):
    KEY_SUFFIX = "social_engagement_tiktok"
    SOURCE_KEY = "tiktok"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        handle = ctx.existing_raw.get("tiktok_handle")
        fc = FirecrawlClient()
        if not handle or not fc.enabled:
            return self._result(scraper_key, fields={}, error="missing handle or firecrawl")
        try:
            md = await fc.scrape_markdown(f"https://www.tiktok.com/@{handle.lstrip('@')}")
            parsed = parse_engagement_from_markdown(md)
            if parsed.get("instagram_engagement_rate") is not None:
                parsed["tiktok_engagement_rate"] = parsed.pop("instagram_engagement_rate")
            views = parse_count(md)
            if views:
                parsed["tiktok_avg_views"] = views
            return self._result(scraper_key, fields=parsed, confidence=0.75)
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))


class InstagramFollowersScraper(BaseMicroScraper):
    KEY_SUFFIX = "instagram_followers"
    SOURCE_KEY = "instagram"

    async def _scrape_followers(self, handle: str, fc: FirecrawlClient) -> tuple[int | None, str | None]:
        """Try aggregator mirrors first, then direct Instagram."""
        last_error: str | None = None
        for url in instagram_aggregator_urls(handle):
            try:
                md = await fc.scrape_markdown(url)
                count = fetch_instagram_followers_from_text(md)
                if count and count >= MIN_REAL_INSTAGRAM_FOLLOWERS:
                    return count, None
            except Exception as e:
                last_error = str(e)
                logger.debug("instagram scrape failed for %s: %s", url, e)
        return None, last_error

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        raw = ctx.existing_raw
        handle = raw.get("instagram_handle")
        if not handle and raw.get("instagram_handle_candidate"):
            return self._result(
                scraper_key,
                fields={"instagram_handle_candidate": raw.get("instagram_handle_candidate")},
                error="instagram handle not verified (candidate only)",
                confidence=0.2,
            )
        if not has_trusted_instagram_handle(raw):
            return self._result(
                scraper_key,
                fields={},
                error="instagram handle not trusted",
                confidence=0.2,
            )
        fc = FirecrawlClient()
        fields: dict[str, Any] = {"instagram_handle": handle}
        if not handle:
            return self._result(
                scraper_key,
                fields=fields,
                error="missing instagram_handle",
                confidence=0.3,
            )
        if is_sufficient(raw, "instagram_followers"):
            return self._result(
                scraper_key,
                fields={
                    "instagram_handle": handle,
                    "instagram_followers": raw.get("instagram_followers"),
                    "instagram_followers_observed": raw.get(
                        "instagram_followers_observed", 1
                    ),
                    "instagram_handle_source": raw.get("instagram_handle_source"),
                },
                confidence=0.85,
            )
        if not fc.enabled:
            return self._result(
                scraper_key,
                fields=fields,
                error="firecrawl disabled",
                confidence=0.3,
            )
        count, err = await self._scrape_followers(str(handle), fc)
        bio_text = ""
        page_md = ""
        for url in instagram_aggregator_urls(str(handle)):
            try:
                page_md = await fc.scrape_markdown(url)
                bio_text = extract_bio_from_page(page_md)
                if bio_text:
                    break
            except Exception:
                continue
        handle_source = str(
            raw.get("instagram_handle_source") or raw.get("handle_source") or ""
        )
        ok, auth = passes_authenticity_gate(
            handle=str(handle),
            followers=count,
            bio_text=bio_text,
            name=ctx.name,
            school=ctx.school or ctx.team,
            sport=ctx.sport,
            position=ctx.position,
            handle_source=handle_source,
        )
        fields.update(auth)
        if bio_text:
            fields["instagram_bio"] = bio_text
        if not ok and not is_user_provided_instagram(raw):
            fields["instagram_followers"] = None
            fields["instagram_followers_observed"] = 0
            return self._result(
                scraper_key,
                fields=fields,
                error=err or "authenticity gate failed",
                confidence=0.25,
            )
        if count and count >= MIN_REAL_INSTAGRAM_FOLLOWERS:
            fields["instagram_followers"] = count
            fields["instagram_followers_observed"] = 1
            try:
                md = page_md or await fc.scrape_markdown(
                    f"https://www.instagram.com/{str(handle).lstrip('@')}/"
                )
                eng = parse_engagement_from_markdown(md)
                if eng.get("instagram_engagement_rate"):
                    fields["instagram_engagement_rate"] = eng["instagram_engagement_rate"]
                if eng.get("posts_sampled"):
                    fields["posts_30d"] = eng.get("posts_sampled")
            except Exception as e:
                logger.debug("instagram engagement scrape: %s", e)
            return self._result(scraper_key, fields=fields, confidence=0.82)
        if is_user_provided_instagram(raw) and raw.get("instagram_followers"):
            fields["instagram_followers"] = raw.get("instagram_followers")
            fields["instagram_followers_observed"] = 1
            return self._result(scraper_key, fields=fields, confidence=0.9)
        fields["instagram_followers"] = None
        fields["instagram_followers_observed"] = 0
        return self._result(
            scraper_key,
            fields=fields,
            error=err or "no follower count parsed",
            confidence=0.3,
        )


class TiktokFollowersScraper(BaseMicroScraper):
    KEY_SUFFIX = "tiktok_followers"
    SOURCE_KEY = "tiktok"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        handle = ctx.existing_raw.get("tiktok_handle")
        fc = FirecrawlClient()
        fields: dict[str, Any] = {"tiktok_handle": handle}
        if handle and fc.enabled:
            try:
                md = await fc.scrape_markdown(f"https://www.tiktok.com/@{handle.lstrip('@')}")
                count = parse_count(md)
                if count:
                    fields["tiktok_followers"] = count
                eng = parse_engagement_from_markdown(md)
                rate = eng.get("instagram_engagement_rate")
                if rate is not None:
                    fields["tiktok_engagement_rate"] = rate
                views = parse_count(md)
                if views and not fields.get("tiktok_followers"):
                    fields["tiktok_avg_views"] = views
            except Exception as e:
                return self._result(scraper_key, fields=fields, error=str(e))
        return self._result(scraper_key, fields=fields, confidence=0.78 if fields.get("tiktok_followers") else 0.3)


class TwitterFollowersScraper(BaseMicroScraper):
    KEY_SUFFIX = "twitter_followers"
    SOURCE_KEY = "twitter"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        handle = ctx.existing_raw.get("twitter_handle")
        fc = FirecrawlClient()
        fields: dict[str, Any] = {"twitter_handle": handle}
        if handle and fc.enabled:
            try:
                md = await fc.scrape_markdown(f"https://x.com/{handle.lstrip('@')}")
                count = parse_count(md)
                if count:
                    fields["twitter_followers"] = count
            except Exception as e:
                return self._result(scraper_key, fields=fields, error=str(e))
        return self._result(scraper_key, fields=fields, confidence=0.78 if fields.get("twitter_followers") else 0.3)


class NcaaOfficialRosterScraper(BaseMicroScraper):
    KEY_SUFFIX = "ncaa_official_roster"
    SOURCE_KEY = "official_roster"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        if ctx.existing_raw.get("is_on_roster") or ctx.existing_raw.get("espn_id"):
            return self._result(
                scraper_key,
                fields={"is_on_roster": ctx.existing_raw.get("is_on_roster", True)},
                confidence=0.85,
            )
        fc = FirecrawlClient()
        if not fc.enabled or not ctx.school:
            return self._result(scraper_key, fields={}, error="firecrawl or school missing")
        url = (
            f"https://www.google.com/search?q=site:go{slugify_school(ctx.school)[:8]}.com+"
            f"{ctx.name.replace(' ', '+')}+roster"
        )
        try:
            md = await fc.scrape_markdown(url)
            parsed = parse_roster_presence(md, ctx.name)
            parsed["roster_verified_at"] = datetime.now(tz=timezone.utc).isoformat()
            return self._result(scraper_key, fields=parsed, confidence=0.88 if parsed.get("is_on_roster") else 0.5)
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))


class TransferPortalScraper(BaseMicroScraper):
    KEY_SUFFIX = "transfer_portal"
    SOURCE_KEY = "on3"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fc = FirecrawlClient()
        fields: dict[str, Any] = {}
        if fc.enabled:
            try:
                q = ctx.name.replace(" ", "+")
                md = await fc.scrape_markdown(f"https://www.on3.com/search/?query={q}")
                fields.update(parse_transfer_portal(md))
            except Exception as e:
                logger.debug("portal firecrawl: %s", e)
        return self._result(scraper_key, fields=fields, confidence=0.85 if fields else 0.2)


class NilDealVerifiedScraper(BaseMicroScraper):
    KEY_SUFFIX = "nil_deal_verified"
    SOURCE_KEY = "verified_nil_deal"

    async def _on3_markdown(self, ctx: AthleteScrapeContext, scraper_key: str) -> str | None:
        from gravity_api.scrapers.clients.firecrawl import fetch_page_text

        slug = ctx.name.replace(" ", "-").lower()
        urls = [
            f"https://www.on3.com/nil/{slug}/",
        ]
        if ctx.school:
            urls.append(
                f"https://www.on3.com/nil/{slug}-{ctx.school.replace(' ', '-').lower()}/"
            )
        for url in urls:
            try:
                md = await fetch_page_text(url, scraper_key=scraper_key)
                if md and ("nil" in md.lower() or "$" in md):
                    return md
            except Exception as e:
                logger.debug("on3 fetch failed %s: %s", url, e)
        return None

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        from gravity_api.scraper_registry.field_sufficiency import _observed

        if is_sufficient(ctx.existing_raw, "nil_valuation") and _observed(
            ctx.existing_raw, "nil_valuation"
        ):
            return self._result(
                scraper_key,
                fields={
                    "nil_valuation": ctx.existing_raw.get("nil_valuation"),
                    "nil_valuation_observed": ctx.existing_raw.get("nil_valuation_observed"),
                    "nil_confidence": ctx.existing_raw.get("nil_confidence"),
                    "nil_valuation_source": ctx.existing_raw.get("nil_valuation_source"),
                },
                confidence=float(ctx.existing_raw.get("nil_confidence") or 0.85),
            )
        sources: list[dict[str, Any]] = []
        if ctx.existing_raw.get("nil_valuation") and _observed(ctx.existing_raw, "nil_valuation"):
            sources.append(
                {
                    "nil_valuation": ctx.existing_raw["nil_valuation"],
                    "source": "existing_raw",
                    "confidence": 0.6,
                }
            )
        fields_deals: dict[str, Any] = {}
        md = await self._on3_markdown(ctx, scraper_key)
        if md:
            val = parse_nil_from_text(md)
            if val:
                sources.append({"nil_valuation": val, "source": "on3", "confidence": 0.92})
            deals = parse_nil_deals_from_text(md)
            if deals:
                fields_deals = {"nil_deals": deals, "nil_deal_count": len(deals)}
        verified = verify_nil_consensus(sources)
        if verified.get("nil_valuation"):
            verified["nil_valuation_observed"] = 1
        verified.update(fields_deals)
        return self._result(
            scraper_key,
            fields=verified,
            confidence=float(verified.get("nil_confidence") or 0.5),
        )


class GoogleTrendsAthleteScraper(BaseMicroScraper):
    KEY_SUFFIX = "google_trends_athlete"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={"google_trends_score": 50.0}, confidence=0.3)
        q = ctx.name.replace(" ", "%20")
        try:
            md = await fc.scrape_markdown(
                f"https://trends.google.com/trends/explore?q={q}&geo=US"
            )
            score = 50.0
            if "Breakout" in md:
                score = 85.0
            elif "+%" in md:
                score = 70.0
            return self._result(
                scraper_key,
                fields={
                    "google_trends_score": score,
                    "google_trends_momentum_30d": score - 50.0,
                },
                confidence=0.65,
            )
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))


class WikipediaPageviewsScraper(BaseMicroScraper):
    KEY_SUFFIX = "wikipedia_pageviews"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        wiki = WikipediaClient()
        try:
            fields = await wiki.for_athlete(ctx.name)
            return self._result(scraper_key, fields=fields, confidence=0.72)
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))


class YoutubeSubscribersScraper(BaseMicroScraper):
    KEY_SUFFIX = "youtube_subscribers"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        handle = ctx.existing_raw.get("youtube_handle")
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={}, error="firecrawl disabled")
        url = f"https://www.youtube.com/@{handle}" if handle else (
            f"https://www.youtube.com/results?search_query={ctx.name.replace(' ', '+')}"
        )
        try:
            md = await fc.scrape_markdown(url)
            subs = parse_count(md)
            fields: dict[str, Any] = {}
            if subs:
                fields["youtube_subscribers"] = subs
            return self._result(scraper_key, fields=fields, confidence=0.8 if subs else 0.3)
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))


class MediaAppearancesScraper(BaseMicroScraper):
    KEY_SUFFIX = "media_appearances"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fc = FirecrawlClient()
        podcast = tv = 0
        if fc.enabled:
            try:
                md = await fc.scrape_markdown(
                    f"https://www.google.com/search?q={ctx.name.replace(' ', '+')}+podcast+interview"
                )
                podcast = md.lower().count("podcast") + md.lower().count("interview")
                tv = md.lower().count("espn") + md.lower().count("tv")
            except Exception:
                pass
        buzz = min(100.0, float(podcast * 3 + tv * 2))
        return self._result(
            scraper_key,
            fields={
                "podcast_appearances_30d": podcast,
                "tv_appearances_30d": tv,
                "media_buzz_score": buzz,
            },
            confidence=0.6,
        )


class IdentityConsensusScraper(BaseMicroScraper):
    KEY_SUFFIX = "identity_consensus"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        espn = EspnClient()
        espn_id = ctx.espn_id or ctx.existing_raw.get("espn_id")
        if not espn_id:
            espn_id = await espn.search_athlete(ctx.name, ctx.sport, team=ctx.school)
        stored = ctx.existing_raw.get("external_id_espn")
        score = 1.0 if stored and str(stored) == str(espn_id) else 0.85 if espn_id else 0.4
        return self._result(
            scraper_key,
            fields={
                "external_id_espn": espn_id,
                "external_id_247": ctx.existing_raw.get("external_id_247"),
                "identity_match_score": score,
            },
            confidence=score,
        )


class SocialAuthenticityScraper(BaseMicroScraper):
    KEY_SUFFIX = "social_authenticity"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        raw = ctx.existing_raw
        handle = raw.get("instagram_handle")
        bio_ok = False
        if handle:
            bio_ok = bio_matches_athlete(
                str(raw.get("instagram_bio") or ""),
                name=ctx.name,
                school=ctx.school or ctx.team,
                sport=ctx.sport,
                position=ctx.position,
            )
        auth = authenticity_score(
            handle=handle,
            followers=raw.get("instagram_followers"),
            linked_from_roster=bool(raw.get("is_on_roster")),
            bio_text=str(raw.get("instagram_bio") or ""),
            bio_matches_athlete=bio_ok or bool(raw.get("instagram_handle_bio_verified")),
        )
        return self._result(scraper_key, fields=auth, confidence=0.85)


class StatsFreshnessScraper(BaseMicroScraper):
    KEY_SUFFIX = "stats_freshness"
    SOURCE_KEY = "espn"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        return self._result(
            scraper_key,
            fields={
                "stats_as_of": ctx.existing_raw.get("stats_as_of")
                or datetime.now(tz=timezone.utc).isoformat(),
                "season_id": ctx.existing_raw.get("season_id"),
                "stats_source": ctx.existing_raw.get("stats_source") or "espn",
                "games_played_season": ctx.existing_raw.get("games_played_season"),
            },
            confidence=0.95,
        )


class InjuryStructuredScraper(BaseMicroScraper):
    KEY_SUFFIX = "injury_structured"
    SOURCE_KEY = "espn"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        espn = EspnClient()
        espn_id = ctx.espn_id or ctx.existing_raw.get("espn_id")
        if not espn_id:
            espn_id = await espn.search_athlete(ctx.name, ctx.sport, team=ctx.school)
        if not espn_id:
            return self._result(scraper_key, fields={}, error="espn id not found")
        profile = await espn.get_athlete_profile(str(espn_id), ctx.sport)
        injuries = profile.get("injuries") or []
        status = injuries[0].get("status") if injuries else "healthy"
        risk = min(95.0, 20.0 + len(injuries) * 25.0)
        return self._result(
            scraper_key,
            fields={
                "current_injury_status": status,
                "games_missed_season": len(injuries),
                "injury_risk_score": risk,
                "last_injury_date": injuries[0].get("date") if injuries else None,
            },
            confidence=0.88,
        )


class EspnRosterScraper(BaseMicroScraper):
    KEY_SUFFIX = "espn_roster"
    SOURCE_KEY = "espn"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        espn = EspnClient()
        espn_id = ctx.espn_id or await espn.search_athlete(ctx.name, ctx.sport, team=ctx.school)
        if not espn_id:
            return self._result(scraper_key, fields={}, error="athlete not found on espn")
        profile = await espn.get_athlete_profile(str(espn_id), ctx.sport)
        fields = dict(profile.get("identity") or {})
        fields["espn_id"] = espn_id
        return self._result(scraper_key, fields=fields, confidence=0.92)


class EspnStatsScraper(BaseMicroScraper):
    KEY_SUFFIX = "espn_stats"
    SOURCE_KEY = "espn"

    def _needs_sports_ref_fallback(self, fields: dict[str, Any], sport: str) -> bool:
        from gravity_api.scraper_registry.acceptance import _position_stat_count

        if _position_stat_count(fields, sport) < 3:
            return True
        gp = fields.get("games_played_season") or fields.get("gp")
        season = fields.get("season_stats")
        if isinstance(season, dict):
            gp = gp or season.get("games_played_season") or season.get("gp")
        return gp is None or int(gp) <= 0

    async def _sports_ref_fallback(
        self, ctx: AthleteScrapeContext, scraper_key: str
    ) -> dict[str, Any]:
        from gravity_api.scrapers.parsers.sports_reference_stats import fetch_sports_ref_stats
        from gravity_api.scrapers.parsers.stat_normalizer import merge_stat_layers
        from gravity_api.scrapers.clients.firecrawl import fetch_page_text
        from gravity_api.scrapers.parsers.sports_reference_stats import (
            parse_sports_ref_stats_from_markdown,
            sports_ref_google_search_url,
            sports_ref_search_url,
        )

        if ctx.sport not in {"nfl", "ncaab_mens", "ncaab_womens", "cfb"}:
            return {}

        parsed = await fetch_sports_ref_stats(ctx.sport, ctx.name, ctx.school or ctx.team)
        if parsed.get("season_stats"):
            merged = merge_stat_layers(ctx.sport, current=parsed.get("season_stats"))
            merged["stats_source"] = parsed.get("stats_source") or "sports_reference"
            if parsed.get("stats_as_of"):
                merged["stats_as_of"] = parsed["stats_as_of"]
            return merged

        urls = [sports_ref_search_url(ctx.name, ctx.sport, ctx.school or ctx.team)]
        google_url = sports_ref_google_search_url(ctx.name, ctx.sport, ctx.school or ctx.team)
        if google_url and google_url not in urls:
            urls.append(google_url)
        for url in [u for u in urls if u]:
            md = await fetch_page_text(url, scraper_key=scraper_key)
            parsed = parse_sports_ref_stats_from_markdown(ctx.sport, md)
            if parsed.get("season_stats"):
                merged = merge_stat_layers(ctx.sport, current=parsed.get("season_stats"))
                merged["stats_source"] = parsed.get("stats_source") or "sports_reference"
                if parsed.get("stats_as_of"):
                    merged["stats_as_of"] = parsed["stats_as_of"]
                return merged
        return {}

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        espn = EspnClient()
        espn_id = ctx.espn_id or ctx.existing_raw.get("espn_id")
        if not espn_id:
            espn_id = await espn.search_athlete(ctx.name, ctx.sport, team=ctx.school)
        if not espn_id:
            return self._result(scraper_key, fields={}, error="espn id missing")
        stats = await espn.get_season_stats(str(espn_id), ctx.sport)
        from gravity_api.scrapers.parsers.stat_normalizer import merge_stat_layers

        fields = merge_stat_layers(
            ctx.sport,
            current=stats.get("season_stats"),
            history=stats.get("season_stats_history"),
            career=stats.get("career_stats"),
        )
        # ESPN NFL athlete stats never include gamesStarted. For skill positions
        # with GP, persist gs=gp so win_impact / ASS see real starter participation.
        if ctx.sport == "nfl" and not (fields.get("games_started") or fields.get("gs")):
            from gravity_api.services.win_impact import resolve_games_started

            probe = {
                **fields,
                "position": ctx.position or fields.get("position"),
                "position_group": fields.get("position_group"),
            }
            inferred, observed = resolve_games_started(probe, sport="nfl", position=ctx.position)
            if inferred > 0 and not observed:
                fields["games_started"] = int(inferred)
                fields["gs"] = float(inferred)
                fields["games_started_inferred"] = 1
                season = fields.get("season_stats")
                if isinstance(season, dict):
                    season = dict(season)
                    season["games_started"] = float(inferred)
                    season["gs"] = float(inferred)
                    fields["season_stats"] = season
                history = fields.get("season_stats_history")
                if isinstance(history, dict):
                    patched_hist: dict[str, dict] = {}
                    for year, blob in history.items():
                        if not isinstance(blob, dict):
                            continue
                        row = dict(blob)
                        if not (row.get("games_started") or row.get("gs")):
                            gp = row.get("games_played_season") or row.get("gp")
                            if gp:
                                row["games_started"] = float(gp)
                                row["gs"] = float(gp)
                        patched_hist[str(year)] = row
                    fields["season_stats_history"] = patched_hist
        if self._needs_sports_ref_fallback(fields, ctx.sport):
            fb = await self._sports_ref_fallback(ctx, scraper_key)
            if fb.get("season_stats"):
                sr_source = fb.get("stats_source") or "sports_reference"
                merged = merge_stat_layers(
                    ctx.sport,
                    current=fb.get("season_stats"),
                    history=fields.get("season_stats_history"),
                    career=fields.get("career_stats"),
                )
                fields = {**fields, **merged}
                fields["stats_source"] = sr_source
                if fb.get("stats_as_of"):
                    fields["stats_as_of"] = fb["stats_as_of"]
                if fb.get("games_played_season"):
                    fields["games_played_season"] = fb["games_played_season"]
        if stats.get("stats_as_of") and not fields.get("stats_as_of"):
            fields["stats_as_of"] = stats["stats_as_of"]
        if stats.get("stats_source") and not fields.get("stats_source"):
            fields["stats_source"] = stats["stats_source"]
        if stats.get("season_id"):
            fields["season_id"] = stats["season_id"]
        return self._result(scraper_key, fields=fields, confidence=0.9 if fields else 0.3)


class EspnAwardsScraper(BaseMicroScraper):
    KEY_SUFFIX = "espn_awards"
    SOURCE_KEY = "espn"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        espn = EspnClient()
        espn_id = ctx.espn_id or ctx.existing_raw.get("espn_id")
        if not espn_id:
            espn_id = await espn.search_athlete(ctx.name, ctx.sport, team=ctx.school)
        if not espn_id:
            return self._result(scraper_key, fields={}, error="espn id missing")
        profile = await espn.get_athlete_profile(str(espn_id), ctx.sport)
        fields = merge_espn_awards(profile.get("awards") or [])
        fields = apply_external_quality_fields(fields, ctx.existing_raw)
        return self._result(scraper_key, fields=fields, confidence=0.9)


class AllAmericanScraper(BaseMicroScraper):
    KEY_SUFFIX = "all_american"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        text = json.dumps(ctx.existing_raw.get("achievements_json") or [])
        fields = parse_achievements_from_text(text)
        return self._result(scraper_key, fields=fields, confidence=0.85)


class NationalAwardsScraper(BaseMicroScraper):
    KEY_SUFFIX = "national_awards"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fields = parse_achievements_from_text(
            json.dumps(ctx.existing_raw.get("achievements_json") or [])
        )
        keep = {
            k: fields[k]
            for k in (
                "national_awards_json",
                "national_awards_count",
                "heisman_finalist",
                "naismith_candidate",
            )
            if k in fields
        }
        keep["national_awards_json"] = ctx.existing_raw.get("achievements_json") or []
        return self._result(scraper_key, fields=keep, confidence=0.88)


class ConferenceHonorsScraper(BaseMicroScraper):
    KEY_SUFFIX = "conference_honors"
    SOURCE_KEY = "espn"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fields = parse_achievements_from_text(
            json.dumps(ctx.existing_raw.get("achievements_json") or [])
        )
        return self._result(
            scraper_key,
            fields={
                "conference_honors_json": fields.get("achievements_json"),
                "conference_honors_count": fields.get("conference_honors_count"),
                "conference_poty": fields.get("conference_poty"),
            },
            confidence=0.85,
        )


class ChampionshipResultsScraper(BaseMicroScraper):
    KEY_SUFFIX = "championship_results"
    SOURCE_KEY = "espn"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        text = json.dumps(ctx.existing_raw, default=str)
        fields = {
            "national_championships": text.lower().count("national champion"),
            "conference_championships": text.lower().count("conference champion"),
            "tournament_final_four": text.lower().count("final four"),
            "playoff_appearances": text.lower().count("playoff"),
        }
        return self._result(scraper_key, fields=fields, confidence=0.7)


class CollegeExperienceProScraper(BaseMicroScraper):
    """Scrape college career for pro athletes — predictive modeling inputs."""

    KEY_SUFFIX = "college_experience_pro"
    SOURCE_KEY = "espn"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        if not ctx.is_pro:
            return self._result(scraper_key, fields={}, error="college experience is pro-only")
        espn = EspnClient()
        college = ctx.college or ctx.existing_raw.get("college") or ctx.school
        data = await espn.get_college_career_for_pro(ctx.name, college, ctx.sport)
        if not data.get("college_career_found"):
            return self._result(scraper_key, fields={"college_career_found": False}, confidence=0.3)
        flat: dict[str, Any] = {
            "college_career_found": True,
            "college_sport_scraped": data.get("college_sport_scraped"),
            "college_espn_id": data.get("college_espn_id"),
            "college_achievements_json": data.get("college_awards"),
            "college_stats_json": data.get("college_stats"),
            "college_stats_history": data.get("college_stats_history") or {},
            "college_career_stats": data.get("college_career_stats") or {},
        }
        ident = data.get("college_identity") or {}
        flat["college_team"] = ident.get("team") or ident.get("college")
        flat["college_position"] = ident.get("position")
        return self._result(scraper_key, fields=flat, confidence=0.9)


class ProgramContextScraper(BaseMicroScraper):
    KEY_SUFFIX = "program_context"
    SOURCE_KEY = "model_derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        # Per-athlete invocation inherits program-level fields when present on ctx
        fields = {
            k: ctx.existing_raw[k]
            for k in (
                "program_gravity_score",
                "school_market_rank",
                "nil_environment_score",
                "conference_media_index",
            )
            if ctx.existing_raw.get(k) is not None
        }
        return self._result(scraper_key, fields=fields, confidence=0.75 if fields else 0.3)


class CfbdStatsScraper(BaseMicroScraper):
    KEY_SUFFIX = "cfbd_api_stats"
    SOURCE_KEY = "cfbd"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        if ctx.sport != "cfb":
            return self._result(scraper_key, fields={}, error="cfbd is cfb-only")
        from gravity_api.scrapers.clients.cfbd import (
            CfbdClient,
            cfbd_is_rate_limited,
            player_id_from_row,
        )
        from gravity_api.services.sport_pipeline.season_stats import _current_season_year
        from gravity_api.scrapers.parsers.stat_normalizer import merge_stat_layers

        client = CfbdClient()
        if not client.enabled:
            return self._result(scraper_key, fields={}, error="CFBD_API_KEY not configured")
        team = ctx.team or ctx.school
        year = _current_season_year()

        if cfbd_is_rate_limited():
            return self._cfbd_fallback_result(ctx, scraper_key, note="cfbd rate limited")

        player, current, history = await client.fetch_player_stats_bundle(
            name=ctx.name,
            team=team,
            year=year,
        )
        player_id = player_id_from_row(player) if player else None

        if not player and not current and not history:
            return self._cfbd_fallback_result(ctx, scraper_key, note="cfbd player not found")

        fields = merge_stat_layers(
            "cfb",
            current=current,
            history=history,
        )
        if player_id is not None:
            fields["cfbd_player_id"] = player_id
        fields["stats_source"] = "cfbd"
        fields["advanced_stats"] = {"source": "cfbd", "season_year": year}
        return self._result(scraper_key, fields=fields, confidence=0.93 if current else 0.4)

    def _cfbd_fallback_result(
        self,
        ctx: AthleteScrapeContext,
        scraper_key: str,
        *,
        note: str,
    ) -> ScraperResult:
        """Keep existing ESPN/raw stats when CFBD is unavailable."""
        raw = ctx.existing_raw
        has_espn = bool(
            raw.get("season_stats")
            or raw.get("season_stats_history")
            or raw.get("pass_yards")
            or raw.get("rush_yards")
        )
        if has_espn:
            return self._result(
                scraper_key,
                fields={},
                confidence=0.35,
                error=f"{note}; using existing espn stats",
            )
        return self._result(scraper_key, fields={}, error=note)


class CfbdTeamRecordScraper(BaseMicroScraper):
    KEY_SUFFIX = "cfbd_team_record"
    SOURCE_KEY = "cfbd"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        if ctx.sport != "cfb":
            return self._result(scraper_key, fields={}, error="cfbd team record is cfb-only")
        from gravity_api.scrapers.clients.cfbd import CfbdClient, cfbd_is_rate_limited
        from gravity_api.services.sport_pipeline.season_stats import _current_season_year

        team = ctx.team or ctx.school
        if not team:
            return self._result(scraper_key, fields={}, error="no team/school on athlete")

        client = CfbdClient()
        if not client.enabled:
            return self._result(scraper_key, fields={}, error="CFBD_API_KEY not configured")
        if cfbd_is_rate_limited():
            return self._result(scraper_key, fields={}, error="cfbd rate limited")

        year = _current_season_year()
        record = await client.team_record(year=year, team=team)
        if not record:
            existing = ctx.existing_raw
            if existing.get("team_win_pct") is not None:
                return self._result(scraper_key, fields={}, confidence=0.35)
            return self._result(scraper_key, fields={}, error="team record not found")

        fields = {
            "team_wins": record["wins"],
            "team_losses": record["losses"],
            "team_ties": record["ties"],
            "team_win_pct": record["win_pct"],
            "team_record_observed": 1,
            "team_record_source": "cfbd",
            "season_year": year,
        }
        conn = get_scrape_db()
        if conn:
            from gravity_api.services.team_season_records import upsert_team_season_stats

            await upsert_team_season_stats(
                conn,
                sport="cfb",
                team_id=team,
                season_year=year,
                wins=int(record["wins"]),
                losses=int(record["losses"]),
                ties=int(record["ties"]),
                team_name=str(record.get("team") or team),
                conference_wins=int(record.get("conference_wins") or 0) or None,
                conference_losses=int(record.get("conference_losses") or 0) or None,
                source_key="cfbd",
            )
        return self._result(scraper_key, fields=fields, confidence=0.9)


class SocialGrowthDeltaScraper(BaseMicroScraper):
    KEY_SUFFIX = "social_growth_delta"
    SOURCE_KEY = "derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        conn = get_scrape_db()
        if not conn:
            return self._result(scraper_key, fields={}, error="db context unavailable")
        rows = await conn.fetch(
            """SELECT instagram_followers, tiktok_followers, twitter_followers, scraped_at
               FROM social_snapshots
               WHERE athlete_id = $1::uuid
               ORDER BY scraped_at DESC
               LIMIT 2""",
            ctx.athlete_id,
        )
        if len(rows) < 2:
            return self._result(scraper_key, fields={}, confidence=0.2)
        latest, prior = rows[0], rows[1]

        def delta(key: str) -> float | None:
            a = latest.get(key)
            b = prior.get(key)
            if a is None or b is None:
                return None
            try:
                return float(a) - float(b)
            except (TypeError, ValueError):
                return None

        fields: dict[str, Any] = {}
        for src, out in (
            ("instagram_followers", "instagram_growth_30d"),
            ("tiktok_followers", "tiktok_growth_30d"),
            ("twitter_followers", "twitter_growth_30d"),
        ):
            d = delta(src)
            if d is not None:
                fields[out] = round(d, 2)
        return self._result(scraper_key, fields=fields, confidence=0.85 if fields else 0.3)


class NewsAggregateScraper(BaseMicroScraper):
    KEY_SUFFIX = "news_rss"
    SOURCE_KEY = "on3"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        conn = get_scrape_db()
        if not conn:
            return self._result(scraper_key, fields={}, error="db context unavailable")
        count = await conn.fetchval(
            """SELECT COUNT(*)::int FROM athlete_events
               WHERE athlete_id = $1::uuid
                 AND retracted_at IS NULL
                 AND occurred_at > NOW() - INTERVAL '30 days'""",
            ctx.athlete_id,
        )
        headlines = await conn.fetch(
            """SELECT title, category, occurred_at, source_domain
               FROM athlete_events
               WHERE athlete_id = $1::uuid
                 AND retracted_at IS NULL
                 AND occurred_at > NOW() - INTERVAL '30 days'
               ORDER BY occurred_at DESC
               LIMIT 15""",
            ctx.athlete_id,
        )
        fields: dict[str, Any] = {"news_count_30d": int(count or 0)}
        if headlines:
            fields["news_headlines_json"] = [
                {
                    "title": r["title"],
                    "category": r["category"],
                    "occurred_at": r["occurred_at"].isoformat() if r["occurred_at"] else None,
                    "source": r["source_domain"],
                }
                for r in headlines
            ]
        brand_deals = [
            {
                "brand": r["title"][:120],
                "category": r["category"],
                "verified": True,
                "source": "athlete_events",
            }
            for r in headlines
            if str(r["category"] or "") == "NIL_DEAL"
        ]
        if brand_deals and ctx.is_pro:
            fields["brand_deals"] = brand_deals
        elif brand_deals:
            fields["nil_deals"] = brand_deals
        return self._result(scraper_key, fields=fields, confidence=0.8 if count else 0.3)


def _pro_proximity_aliases(fields: dict[str, Any]) -> dict[str, Any]:
    if fields.get("contract_aav_usd") is not None:
        fields["contract_aav"] = fields["contract_aav_usd"]
    if fields.get("endorsement_value_usd") is not None:
        fields["endorsement_earnings"] = fields["endorsement_value_usd"]
    return fields


class SpotracContractScraper(BaseMicroScraper):
    KEY_SUFFIX = "spotrac_contract"
    SOURCE_KEY = "spotrac"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={}, error="firecrawl disabled")
        sport = sport_from_any_key(scraper_key)
        league = {"nfl": "nfl", "nba": "nba", "wnba": "wnba"}.get(sport, sport)
        q = ctx.name.replace(" ", "+")
        try:
            md = await fc.scrape_markdown(
                f"https://www.google.com/search?q=site:spotrac.com+{q}+{league}+contract"
            )
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))
        total = parse_count(md)
        aav = None
        for pat in (r"avg\.?\s*(?:annual|salary)[^\d$]*(\$[\d,.]+[KMB]?)", r"AAV[^\d$]*(\$[\d,.]+[KMB]?)"):
            m = re.search(pat, md, re.I)
            if m:
                aav = parse_count(m.group(1))
                break
        fields: dict[str, Any] = {}
        if total:
            fields["contract_total_usd"] = float(total)
        if aav:
            fields["contract_aav_usd"] = float(aav)
        return self._result(
            scraper_key,
            fields=_pro_proximity_aliases(fields),
            confidence=0.75 if fields else 0.25,
        )


class ForbesEarningsScraper(BaseMicroScraper):
    KEY_SUFFIX = "forbes_earnings"
    SOURCE_KEY = "forbes"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={}, error="firecrawl disabled")
        sport = sport_from_any_key(scraper_key)
        q = ctx.name.replace(" ", "+")
        try:
            md = await fc.scrape_markdown(
                f"https://www.google.com/search?q=site:forbes.com+{q}+{sport}+earnings+endorsement"
            )
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))
        endorsement = None
        total = None
        for label, key in (
            (r"endorsement[^\d$]*(\$[\d,.]+[KMB]?)", "endorsement_value_usd"),
            (r"total[^\d$]*earnings[^\d$]*(\$[\d,.]+[KMB]?)", "total_earnings_usd"),
        ):
            m = re.search(label, md, re.I)
            if m:
                val = parse_count(m.group(1))
                if val:
                    if key == "endorsement_value_usd":
                        endorsement = float(val)
                    else:
                        total = float(val)
        fields: dict[str, Any] = {}
        if endorsement:
            fields["endorsement_value_usd"] = endorsement
        if total:
            fields["total_earnings_usd"] = total
        return self._result(
            scraper_key,
            fields=_pro_proximity_aliases(fields),
            confidence=0.7 if fields else 0.25,
        )


class KenPomStatsScraper(BaseMicroScraper):
    KEY_SUFFIX = "kenpom"
    SOURCE_KEY = "kenpom"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        if ctx.sport != "ncaab_mens":
            return self._result(scraper_key, fields={}, error="kenpom is ncaab_mens-only")
        from gravity_api.services.sport_pipeline.season_stats import _current_season_year

        year = _current_season_year()
        client = KenPomClient()
        fields: dict[str, Any] = {}
        if client.enabled:
            fields = await client.player_stats(season=year, name=ctx.name)
        else:
            fc = FirecrawlClient()
            if not fc.enabled:
                return self._result(scraper_key, fields={}, error="KENPOM_API_KEY and Firecrawl unavailable")
            try:
                md = await fc.scrape_markdown(
                    f"https://www.google.com/search?q=site:kenpom.com+{ctx.name.replace(' ', '+')}+stats"
                )
                fields = parse_kenpom_markdown(md)
            except Exception as e:
                return self._result(scraper_key, fields={}, error=str(e))
        if fields.get("usage_rate") is not None and fields.get("usage") is None:
            fields["usage"] = fields["usage_rate"]
        if fields:
            fields["advanced_stats"] = {"source": "kenpom", "season_year": year}
            fields["stats_source"] = "kenpom"
        return self._result(scraper_key, fields=fields, confidence=0.9 if fields else 0.25)


class SiteSearchScraper(BaseMicroScraper):
    """Google site-search scraper for sport-specific third-party sources."""

    KEY_SUFFIX = ""

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        suffix = site_suffix_for_key(scraper_key)
        if not suffix:
            return self._result(scraper_key, fields={}, error="unknown site-search scraper")
        cfg = SITE_SEARCH_CONFIG[suffix]
        expected_sport = cfg.get("sport")
        if expected_sport and ctx.sport != expected_sport:
            return self._result(
                scraper_key,
                fields={},
                error=f"{suffix} is {expected_sport}-only",
            )
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={}, error="firecrawl disabled")
        try:
            fields = await scrape_site_fields(
                fc,
                domain=str(cfg["domain"]),
                name=ctx.name,
                team=ctx.team or ctx.school,
                parse=cfg["parse"],
            )
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))
        if fields.get("usage") is None and fields.get("usage_rate") is not None:
            fields["usage"] = fields["usage_rate"]
        return self._result(scraper_key, fields=fields, confidence=0.75 if fields else 0.25)


class Recruiting247Scraper(BaseMicroScraper):
    KEY_SUFFIX = "recruiting_247"
    SOURCE_KEY = "247sports"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        if ctx.is_pro:
            return self._result(scraper_key, fields={}, error="recruiting_247 is college-only")
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={}, error="firecrawl disabled")
        parts = [ctx.name.replace(" ", "+")]
        if ctx.school:
            parts.append(ctx.school.replace(" ", "+"))
        q = "+".join(parts)
        md = ""
        try:
            md = await fc.scrape_markdown(f"https://www.google.com/search?q=site:247sports.com+{q}")
            fields = parse_247_recruiting_profile(md)
            player_id = fields.get("external_id_247") or ctx.existing_raw.get("external_id_247")
            if player_id and not fields.get("recruiting_stars"):
                profile_md = await fc.scrape_markdown(
                    f"https://247sports.com/player/-{player_id}/"
                )
                fields.update(parse_247_recruiting_profile(profile_md))
            elif not fields.get("recruiting_stars"):
                profile_md = await fc.scrape_markdown(
                    f"https://www.google.com/search?q=site:247sports.com/player+{q}+recruiting"
                )
                fields.update(parse_247_recruiting_profile(profile_md))
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))
        return self._result(scraper_key, fields=fields, confidence=0.78 if fields else 0.25)


class OpendorseProfileScraper(BaseMicroScraper):
    KEY_SUFFIX = "opendorse_profile"
    SOURCE_KEY = "opendorse"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        if ctx.is_pro:
            return self._result(scraper_key, fields={}, error="opendorse_profile is college-only")
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={}, error="firecrawl disabled")
        q = ctx.name.replace(" ", "+")
        if ctx.school:
            q = f"{q}+{ctx.school.replace(' ', '+')}"
        try:
            md = await fc.scrape_markdown(f"https://www.google.com/search?q=site:opendorse.com+{q}")
            fields = parse_opendorse_profile(md)
            if not fields.get("nil_valuation") and not fields.get("marketplace_listing"):
                md = await fc.scrape_markdown(
                    f"https://www.google.com/search?q=site:opendorse.com/athletes+{q}"
                )
                fields.update(parse_opendorse_profile(md))
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))

        if fields.get("nil_valuation"):
            sources: list[dict[str, Any]] = []
            if ctx.existing_raw.get("nil_valuation"):
                sources.append(
                    {
                        "nil_valuation": ctx.existing_raw["nil_valuation"],
                        "source": ctx.existing_raw.get("nil_valuation_source") or "existing_raw",
                        "confidence": 0.75,
                    }
                )
            sources.append(
                {
                    "nil_valuation": fields["nil_valuation"],
                    "source": "opendorse",
                    "confidence": 0.88,
                }
            )
            consensus = verify_nil_consensus(sources)
            fields.update(
                {
                    k: v
                    for k, v in consensus.items()
                    if k in ("nil_valuation", "nil_valuation_source", "nil_confidence")
                }
            )
        return self._result(scraper_key, fields=fields, confidence=0.82 if fields else 0.25)


class SportsRefHonorsScraper(BaseMicroScraper):
    KEY_SUFFIX = "sports_ref_honors"
    SOURCE_KEY = "sports_reference"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        domain = ref_domain_for_sport(ctx.sport)
        if not domain:
            return self._result(scraper_key, fields={}, error=f"no sports ref domain for {ctx.sport}")
        fc = FirecrawlClient()
        if not fc.enabled:
            return self._result(scraper_key, fields={}, error="firecrawl disabled")
        parts = [ctx.name.replace(" ", "+")]
        team = ctx.team or ctx.school
        if team:
            parts.append(team.replace(" ", "+"))
        q = "+".join(parts)
        try:
            md = await fc.scrape_markdown(
                f"https://www.google.com/search?q=site:{domain}+{q}+awards+honors"
            )
            fields = parse_sports_ref_honors(md)
        except Exception as e:
            return self._result(scraper_key, fields={}, error=str(e))
        return self._result(scraper_key, fields=fields, confidence=0.85 if fields else 0.25)


class GenericPassthroughScraper(BaseMicroScraper):
    """Fallback for registry keys not yet split into dedicated classes."""

    KEY_SUFFIX = ""

    def __init__(self, suffix: str):
        self._suffix = suffix

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        return self._result(
            scraper_key,
            fields={},
            error=f"scraper {scraper_key} registered but not yet implemented",
        )


ALL_SCRAPER_CLASSES: list[type[BaseMicroScraper]] = [
    SocialHandleDiscoveryScraper,
    SocialEngagementInstagramScraper,
    SocialEngagementTiktokScraper,
    InstagramFollowersScraper,
    TiktokFollowersScraper,
    TwitterFollowersScraper,
    NcaaOfficialRosterScraper,
    TransferPortalScraper,
    NilDealVerifiedScraper,
    GoogleTrendsAthleteScraper,
    WikipediaPageviewsScraper,
    YoutubeSubscribersScraper,
    MediaAppearancesScraper,
    IdentityConsensusScraper,
    SocialAuthenticityScraper,
    StatsFreshnessScraper,
    InjuryStructuredScraper,
    EspnRosterScraper,
    EspnStatsScraper,
    EspnAwardsScraper,
    AllAmericanScraper,
    NationalAwardsScraper,
    ConferenceHonorsScraper,
    ChampionshipResultsScraper,
    CollegeExperienceProScraper,
    ProgramContextScraper,
    CfbdStatsScraper,
    CfbdTeamRecordScraper,
    SocialGrowthDeltaScraper,
    NewsAggregateScraper,
    SpotracContractScraper,
    ForbesEarningsScraper,
    KenPomStatsScraper,
    SiteSearchScraper,
    Recruiting247Scraper,
    OpendorseProfileScraper,
    SportsRefHonorsScraper,
]

_IMPLEMENTATIONS: dict[str, BaseMicroScraper] = {}
for cls in ALL_SCRAPER_CLASSES:
    _IMPLEMENTATIONS[cls.KEY_SUFFIX] = cls()


def get_scraper_impl(scraper_key: str) -> BaseMicroScraper | None:
    if scraper_key.startswith("on3_nil"):
        return _IMPLEMENTATIONS.get("nil_deal_verified")
    if site_suffix_for_key(scraper_key):
        return _IMPLEMENTATIONS.get("")
    for suffix, impl in _IMPLEMENTATIONS.items():
        if not suffix:
            continue
        if scraper_key.startswith(f"{suffix}_") or scraper_key == suffix:
            return impl
    if scraper_key == "program_context" or scraper_key.startswith("program_context"):
        return _IMPLEMENTATIONS.get("program_context")
    if scraper_key.startswith("college_experience_pro"):
        return _IMPLEMENTATIONS.get("college_experience_pro")
    return None


async def load_program_context(conn: asyncpg.Connection, ctx: AthleteScrapeContext) -> None:
    if not ctx.school:
        return
    row = await conn.fetchrow(
        """SELECT dma_rank, nil_environment_score, conference, annual_tv_appearances,
                  collective_budget_usd
           FROM programs
           WHERE lower(trim(school)) = lower(trim($1)) AND sport = $2
           LIMIT 1""",
        ctx.school,
        normalize_sport(ctx.sport).replace("ncaab_mens", "ncaab").replace("ncaab_womens", "ncaab"),
    )
    if not row:
        return
    ctx.existing_raw.setdefault("school_market_rank", row.get("dma_rank"))
    nil_env = row.get("nil_environment_score")
    if nil_env is not None:
        nil_f = float(nil_env)
        ctx.existing_raw.setdefault("nil_environment_score", nil_f)
        ctx.existing_raw.setdefault("conference_media_index", nil_f)
