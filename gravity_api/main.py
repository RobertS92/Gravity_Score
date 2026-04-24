"""Gravity NIL Intelligence API — entrypoint."""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gravity_api.config import get_settings
from gravity_api.database import close_db, init_db
from gravity_api.routers import (
    agent,
    alerts,
    athletes,
    auth,
    brands_scoring,
    cap,
    data_submissions,
    deals,
    market,
    match,
    operations,
    programs,
    query,
    reports,
    roster,
    scores,
    scraper_jobs,
    user_preferences,
    watchlist,
    webhooks,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Gravity API started")
    yield
    await close_db()
    logger.info("Gravity API shutdown")


settings = get_settings()
app = FastAPI(
    title="Gravity NIL Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gravity-nil-intelligence"}
