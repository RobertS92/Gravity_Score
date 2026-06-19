"""Gravity NIL Intelligence API — entrypoint."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import ResponseValidationError

from gravity_api.config import get_settings
from gravity_api.database import close_db, init_db
from gravity_api.services.model_health import (
    get_model_health,
    probe_model_health,
    should_abort_startup_on_fallback,
)
from gravity_api.routers import (
    agent,
    alerts,
    athletes,
    auth,
    brands_scoring,
    cap,
    data_submissions,
    deals,
    feed,
    ingest,
    market,
    match,
    operations,
    programs,
    query,
    reports,
    roster,
    scores,
    scraper_jobs,
    team_favorites,
    user_preferences,
    watchlist,
    webhooks,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception:
        logger.exception("Gravity API startup failed while connecting to Postgres")
        raise
    # Probe the ML scorer once so /health and CSC reporting know whether the
    # production model is live. The probe is best-effort and never blocks
    # startup unless MODEL_FAIL_ON_FALLBACK=1 and the probe reports a confirmed
    # fallback scorer (not a transient bundle-missing probe during ML deploy).
    health = await probe_model_health()
    if should_abort_startup_on_fallback(health):
        logger.error(
            "ML scorer is on fallback (%s, reason=%s); MODEL_FAIL_ON_FALLBACK is set — aborting startup",
            health.model_version,
            health.reason,
        )
        raise RuntimeError(
            f"Refusing to start: ML scorer is on fallback ({health.model_version})"
        )
    if health.is_fallback:
        logger.warning(
            "ML scorer reported fallback model_version=%s reason=%s — CSC reports will return 503 unless overridden; /health will re-probe",
            health.model_version,
            health.reason,
        )
    else:
        logger.info(
            "ML scorer health: status=%s model_version=%s reason=%s",
            health.status,
            health.model_version,
            health.reason,
        )
    logger.info("Gravity API started")
    yield
    await close_db()
    logger.info("Gravity API shutdown")


settings = get_settings()
# redirect_slashes=False prevents FastAPI from returning 307 redirects when a
# request is missing a trailing slash (e.g. GET /v1/watchlist?user_id=…).
# Browsers strip the Authorization header on cross-origin redirects, so those
# 307s caused every authenticated XHR from the terminal to silently lose data.
app = FastAPI(
    title="Gravity NIL Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ResponseValidationError)
async def response_validation_handler(
    request: Request, exc: ResponseValidationError
) -> JSONResponse:
    """Return structured 500s so CORS middleware can attach headers on failures."""
    logger.error("Response validation failed on %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=500, content={"detail": "Internal response validation error"})

app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(user_preferences.router, prefix="/v1/user", tags=["user"])
app.include_router(athletes.router, prefix="/v1/athletes", tags=["athletes"])
app.include_router(scores.router, prefix="/v1/scores", tags=["scores"])
app.include_router(reports.router, prefix="/v1/reports", tags=["reports"])
app.include_router(deals.router, prefix="/v1/deals", tags=["deals"])
app.include_router(programs.router, prefix="/v1/programs", tags=["programs"])
app.include_router(query.router, prefix="/v1/query", tags=["query"])
app.include_router(market.router, prefix="/v1/market", tags=["market"])
app.include_router(agent.router, prefix="/v1/agent", tags=["agent"])
app.include_router(watchlist.router, prefix="/v1/watchlist", tags=["watchlist"])
app.include_router(alerts.router, prefix="/v1/alerts", tags=["alerts"])
app.include_router(webhooks.router, prefix="/v1/webhooks", tags=["webhooks"])
app.include_router(match.router, prefix="/v1/match", tags=["match"])
app.include_router(brands_scoring.router, prefix="/v1/brands", tags=["brands"])
app.include_router(roster.router, prefix="/v1/roster", tags=["roster"])
app.include_router(operations.router, prefix="/v1/operations", tags=["operations"])
app.include_router(cap.router, prefix="/v1/cap", tags=["cap"])
app.include_router(data_submissions.router, prefix="/v1/data", tags=["data"])
app.include_router(scraper_jobs.router, prefix="/v1/scraper", tags=["scraper-pipeline"])
app.include_router(team_favorites.router, prefix="/v1/team-favorites", tags=["team-favorites"])
app.include_router(feed.router, prefix="/v1/feed", tags=["feed"])
app.include_router(ingest.router, prefix="/v1/ingest", tags=["ingest"])


def _ml_probe_is_stale() -> bool:
    """Re-probe when the cached result is old or from before ML bundle deploy."""
    cached = get_model_health()
    if cached.reason in ("not_probed", "ml_service_reports_no_bundle"):
        return True
    age_s = (datetime.now(tz=timezone.utc) - cached.checked_at).total_seconds()
    return age_s > 60


@app.get("/health")
async def health():
    if _ml_probe_is_stale():
        await probe_model_health()
    return {
        "status": "ok",
        "service": "gravity-nil-intelligence",
        "ml_model": get_model_health().to_dict(),
    }


@app.get("/v1/health")
async def health_v1():
    """Versioned health endpoint mirroring `/health` for terminal clients."""
    return await health()
