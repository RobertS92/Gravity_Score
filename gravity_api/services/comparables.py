"""FAISS / similarity index rebuild — placeholder until Week 3."""

import logging

import asyncpg

logger = logging.getLogger(__name__)


async def rebuild_comparables_index(db: asyncpg.Connection) -> None:
    """Populate comparable_sets from similarity model (stub)."""
    logger.info(
        "rebuild_comparables_index: stub — implement FAISS similarity in services/comparables.py"
    )
