"""Multi-sport scraper smoke tests (ESPN live + optional DB scheduled_full)."""

from gravity_api.scraper_smoke.athletes import SMOKE_ATHLETES

__all__ = ["SMOKE_ATHLETES", "run_smoke_suite"]


def __getattr__(name: str):
    if name == "run_smoke_suite":
        from gravity_api.scraper_smoke.runner import run_smoke_suite

        return run_smoke_suite
    raise AttributeError(name)
