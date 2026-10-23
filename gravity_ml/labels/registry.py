"""Label registry with lineage (SCORING_ML_FIX_SPEC §3 F2).

Each label declares name, source_tables, horizon, and builder. Labels that read
our own score tables / formula helpers are banned and fail CI via
``validate_registry``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Iterable

import pandas as pd

# Tables / helpers that must never appear in label lineage (M1–M5).
BANNED_LABEL_SOURCES: frozenset[str] = frozenset(
    {
        "athlete_gravity_scores",
        "raw_composite_score",
        "component_proxy_raw",
        "compute_win_impact_score_v0",
        "compute_target_impact_score",
    }
)

BuilderFn = Callable[..., pd.Series | pd.DataFrame]


@dataclass(frozen=True)
class LabelSpec:
    name: str
    source_tables: tuple[str, ...]
    horizon: timedelta | None
    builder: BuilderFn
    description: str = ""
    role: str = "primary"  # primary | auxiliary | risk | quantile
    disabled: bool = False
    disabled_reason: str = ""
    objective: str = ""  # impact | gravity | ...

    def assert_not_banned(self) -> None:
        bad = [s for s in self.source_tables if _is_banned_source(s)]
        if bad:
            raise ValueError(
                f"Label {self.name!r} lists banned source(s) {bad}; "
                f"banned={sorted(BANNED_LABEL_SOURCES)}"
            )


_REGISTRY: dict[str, LabelSpec] = {}


def _is_banned_source(source: str) -> bool:
    if source in BANNED_LABEL_SOURCES:
        return True
    lower = source.lower()
    if lower.startswith("athlete_") and lower.endswith("_scores"):
        return True
    if "win_impact_score" in lower:
        return True
    # Model-written score columns / helpers referenced as sources.
    model_prefixes = (
        "gravity_",
        "brand_",
        "proof_",
        "proximity_",
        "velocity_",
        "risk_",
        "quality_",
        "win_impact_",
        "target_",
    )
    if source.endswith("_score") and any(source.startswith(p) for p in model_prefixes):
        return True
    return False


def register_label(spec: LabelSpec, *, overwrite: bool = False) -> LabelSpec:
    spec.assert_not_banned()
    if spec.name in _REGISTRY and not overwrite:
        raise ValueError(f"Label already registered: {spec.name}")
    _REGISTRY[spec.name] = spec
    return spec


def get_label(name: str) -> LabelSpec:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown label {name!r}; known={sorted(_REGISTRY)}") from exc


def list_labels(*, objective: str | None = None) -> list[LabelSpec]:
    specs = list(_REGISTRY.values())
    if objective is not None:
        specs = [s for s in specs if s.objective == objective]
    return sorted(specs, key=lambda s: s.name)


def validate_registry(specs: Iterable[LabelSpec] | None = None) -> None:
    """Raise if any registered label lists a banned source. Used by CI."""
    items = list(specs) if specs is not None else list(_REGISTRY.values())
    errors: list[str] = []
    for spec in items:
        try:
            spec.assert_not_banned()
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise AssertionError("Banned label sources:\n" + "\n".join(errors))


def clear_registry_for_tests() -> None:
    """Test helper — wipe and re-seed default outcome labels."""
    _REGISTRY.clear()
    _register_defaults()


def _stub_builder(*_args: Any, **_kwargs: Any) -> pd.Series:
    raise NotImplementedError(
        "Label builder blocked until scraper WP10 / deal history is available"
    )


def _register_defaults() -> None:
    """Register Gravity (G1) and Impact outcome labels. Builders stubbed until data."""
    defaults: list[LabelSpec] = [
        LabelSpec(
            name="L_deal_180",
            source_tables=("athlete_nil_deals", "verified_deal_transactions"),
            horizon=timedelta(days=180),
            builder=_stub_builder,
            description="1 if athlete has a deal with deal_date in (t, t+180d]",
            role="primary",
            objective="gravity",
        ),
        LabelSpec(
            name="L_attention_90",
            source_tables=("social_snapshots", "athlete_metric_history"),
            horizon=timedelta(days=90),
            builder=_stub_builder,
            description="log(reach at t+90d / reach at t) from trusted social totals",
            role="auxiliary",
            objective="gravity",
        ),
        LabelSpec(
            name="L_dollars",
            source_tables=("verified_deal_transactions",),
            horizon=None,
            builder=_stub_builder,
            description="log1p(verified deal USD); disabled until ≥500 verified deals",
            role="quantile",
            objective="gravity",
            disabled=True,
            disabled_reason="Insufficient verified deals (need ≥500)",
        ),
        LabelSpec(
            name="L_unavail_180",
            source_tables=("roster_events", "injury_feed", "athlete_team_seasons"),
            horizon=timedelta(days=180),
            builder=_stub_builder,
            description="1 if portal/draft/injury/role-loss in (t, t+180d]",
            role="risk",
            objective="gravity",
        ),
        LabelSpec(
            name="L_game_margin",
            source_tables=("games",),
            horizon=None,
            builder=_stub_builder,
            description="home_score - away_score for APM (Impact I1)",
            role="primary",
            objective="impact",
        ),
        LabelSpec(
            name="L_impact_rate",
            source_tables=("games", "game_player_box", "athlete_season_stats"),
            horizon=None,
            builder=_stub_builder,
            description="Posterior margin-per-game impact from APM/RAPM fusion",
            role="primary",
            objective="impact",
        ),
    ]
    for spec in defaults:
        if spec.name not in _REGISTRY:
            register_label(spec)


_register_defaults()
