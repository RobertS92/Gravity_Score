"""Micro-scraper implementations — quality boosters, core, achievements, pro college."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.scrapers.base import BaseMicroScraper, sport_from_any_key
from gravity_api.scrapers.clients.espn import EspnClient, normalize_sport
from gravity_api.scrapers.clients.firecrawl import FirecrawlClient
from gravity_api.scrapers.clients.wikipedia import WikipediaClient
from gravity_api.scrapers.parsers.achievements import merge_espn_awards, parse_achievements_from_text
from gravity_api.scrapers.parsers.common import parse_count, slugify_school
from gravity_api.scrapers.parsers.nil import parse_nil_from_text, verify_nil_consensus
from gravity_api.scrapers.parsers.roster import parse_roster_presence, parse_transfer_portal
from gravity_api.scrapers.parsers.social import (
    authenticity_score,
    handles_from_page,
    merge_handle_sources,
    parse_engagement_from_markdown,
)
from gravity_api.scrapers.types import AthleteScrapeContext, ScraperResult

logger = logging.getLogger(__name__)


class SocialHandleDiscoveryScraper(BaseMicroScraper):
    KEY_SUFFIX = "social_handle_discovery"
    SOURCE_KEY = "derived"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        espn = EspnClient()
        fc = FirecrawlClient()
        sources: list[dict[str, str]] = []
        espn_id = ctx.espn_id or ctx.existing_raw.get("espn_id")
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
        if fc.enabled and ctx.school:
            try:
                md = await fc.scrape_markdown(
                    f"https://www.google.com/search?q={ctx.name.replace(' ', '+')}"
                    f"+{slugify_school(ctx.school)}+instagram+twitter"
                )
                sources.append(handles_from_page(md, "firecrawl_search"))
            except Exception as e:
                logger.debug("handle discovery firecrawl: %s", e)
        merged = merge_handle_sources(*sources)
        return self._result(scraper_key, fields=merged, confidence=float(merged.get("handle_confidence") or 0.5))


class SocialEngagementInstagramScraper(BaseMicroScraper):
    KEY_SUFFIX = "social_engagement_instagram"
    SOURCE_KEY = "instagram"

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        handle = ctx.existing_raw.get("instagram_handle")
        fc = FirecrawlClient()
        if not handle or not fc.enabled:
            return self._result(scraper_key, fields={}, error="missing handle or firecrawl")
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

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        handle = ctx.existing_raw.get("instagram_handle")
        fc = FirecrawlClient()
        fields: dict[str, Any] = {"instagram_handle": handle}
        if handle and fc.enabled:
            try:
                md = await fc.scrape_markdown(f"https://www.instagram.com/{handle.lstrip('@')}/")
                count = parse_count(md)
                if count:
                    fields["instagram_followers"] = count
                eng = parse_engagement_from_markdown(md)
                if eng.get("instagram_engagement_rate"):
                    fields["instagram_engagement_rate"] = eng["instagram_engagement_rate"]
            except Exception as e:
                return self._result(scraper_key, fields=fields, error=str(e))
        return self._result(scraper_key, fields=fields, confidence=0.8 if fields.get("instagram_followers") else 0.3)


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

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        fc = FirecrawlClient()
        sources: list[dict[str, Any]] = []
        if ctx.existing_raw.get("nil_valuation"):
            sources.append(
                {
                    "nil_valuation": ctx.existing_raw["nil_valuation"],
                    "source": "existing_raw",
                    "confidence": 0.6,
                }
            )
        if fc.enabled:
            try:
                md = await fc.scrape_markdown(
                    f"https://www.on3.com/nil/{ctx.name.replace(' ', '-').lower()}/"
                )
                val = parse_nil_from_text(md)
                if val:
                    sources.append({"nil_valuation": val, "source": "on3", "confidence": 0.92})
            except Exception:
                pass
        verified = verify_nil_consensus(sources)
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
        auth = authenticity_score(
            handle=ctx.existing_raw.get("instagram_handle"),
            followers=ctx.existing_raw.get("instagram_followers"),
            linked_from_roster=bool(ctx.existing_raw.get("is_on_roster")),
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

    async def run(self, ctx: AthleteScrapeContext, scraper_key: str) -> ScraperResult:
        espn = EspnClient()
        espn_id = ctx.espn_id or ctx.existing_raw.get("espn_id")
        if not espn_id:
            espn_id = await espn.search_athlete(ctx.name, ctx.sport, team=ctx.school)
        if not espn_id:
            return self._result(scraper_key, fields={}, error="espn id missing")
        stats = await espn.get_season_stats(str(espn_id), ctx.sport)
        return self._result(scraper_key, fields=stats, confidence=0.9)


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
        text = json.dumps(ctx.existing_raw)
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
]

_IMPLEMENTATIONS: dict[str, BaseMicroScraper] = {}
for cls in ALL_SCRAPER_CLASSES:
    _IMPLEMENTATIONS[cls.KEY_SUFFIX] = cls()


def get_scraper_impl(scraper_key: str) -> BaseMicroScraper | None:
    for suffix, impl in _IMPLEMENTATIONS.items():
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
    ctx.existing_raw.setdefault("nil_environment_score", row.get("nil_environment_score"))
    ctx.existing_raw.setdefault("conference_media_index", row.get("nil_environment_score"))
