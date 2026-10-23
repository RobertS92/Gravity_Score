"""DEPRECATED wrapper — career is derived from per-season rows (WP7).

Redirects to ``gravity_api.jobs.backfill_season_stats``. Career totals must never
be scraped into season GP fields; use the season backfill and the
``athlete_career_stats`` view.
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.warning(
        "backfill_career_stats is deprecated; forwarding to backfill_season_stats"
    )
    from gravity_api.jobs.backfill_season_stats import main as season_main

    # Preserve argv; season backfill CLI is the canonical entrypoint.
    season_main()


if __name__ == "__main__":
    main()
