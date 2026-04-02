"""NIL deal ingestion from gravity.nil connectors."""

import logging

import asyncpg

logger = logging.getLogger(__name__)


async def ingest_nil_deals_from_connectors(db: asyncpg.Connection) -> None:
    """Pull verified / estimated deals (stub)."""
    logger.info(
        "ingest_nil_deals_from_connectors: stub — orchestrate gravity.nil pipeline"
    )
