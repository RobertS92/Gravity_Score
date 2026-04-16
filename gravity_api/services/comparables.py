"""Rebuild comparable_sets from latest Gravity score vectors (cosine similarity)."""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

import asyncpg
import numpy as np

logger = logging.getLogger(__name__)


def _score_matrix(rows: List[asyncpg.Record]) -> Tuple[np.ndarray, List[str], List[str]]:
    ids: List[str] = []
    sports: List[str] = []
    mat: List[List[float]] = []
    for r in rows:
        ids.append(str(r["id"]))
        sports.append(str(r["sport"] or ""))
        mat.append(
            [
                float(r["brand_score"] or 0),
                float(r["proof_score"] or 0),
                float(r["proximity_score"] or 0),
                float(r["velocity_score"] or 0),
                float(r["gravity_score"] or 0),
                100.0 - float(r["risk_score"] or 0),
            ]
        )
    m = np.array(mat, dtype=np.float64)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    m_norm = m / norms
    return m_norm, ids, sports


async def rebuild_comparables_index(db: asyncpg.Connection, top_k: int = 15) -> int:
    """Replace comparable_sets rows using cosine similarity on latest score vectors."""
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (a.id)
            a.id, a.sport,
            s.brand_score, s.proof_score, s.proximity_score, s.velocity_score,
            s.risk_score, s.gravity_score
        FROM athletes a
        INNER JOIN athlete_gravity_scores s ON s.athlete_id = a.id
        ORDER BY a.id, s.calculated_at DESC
        """
    )
    if len(rows) < 2:
        logger.info("rebuild_comparables_index: fewer than 2 scored athletes; skipping")
        return 0

    m_norm, ids, sports = _score_matrix(rows)
    sim = m_norm @ m_norm.T
    pairs: List[Tuple[str, str, float]] = []
    n = len(ids)
    for i in range(n):
        scores = sim[i].copy()
        scores[i] = -1.0
        for j in range(n):
            if i != j and sports[j] == sports[i]:
                scores[j] = min(1.0, scores[j] + 0.05)
        order = np.argsort(scores)[::-1]
        added = 0
        for j in order:
            if added >= top_k:
                break
            if i == j or scores[j] <= 0:
                continue
            pairs.append((ids[i], ids[j], float(scores[j])))
            added += 1

    await db.execute("DELETE FROM comparable_sets")
    if not pairs:
        return 0
    await db.executemany(
        """INSERT INTO comparable_sets (subject_athlete_id, comparable_athlete_id, similarity_score, matching_dimensions)
           VALUES ($1::uuid, $2::uuid, $3, '{}'::jsonb)
           ON CONFLICT (subject_athlete_id, comparable_athlete_id)
           DO UPDATE SET similarity_score = EXCLUDED.similarity_score, created_at = NOW()""",
        pairs,
    )
    logger.info("rebuild_comparables_index: wrote %d pairs", len(pairs))
    return len(pairs)


__all__ = ["rebuild_comparables_index"]
