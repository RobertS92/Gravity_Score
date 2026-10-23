"""Gravity market-outcome label builders (SCORING_ML_FIX_SPEC §5 G1).

Builders accept point-in-time snapshot frames + event tables. They enforce
banned-source lineage via the F2 registry (never read athlete_gravity_scores /
raw_composite_score / formula helpers). Live training still needs dated deals
and coverage flags from scraper history.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from gravity_ml.labels.registry import (
    BANNED_LABEL_SOURCES,
    LabelSpec,
    get_label,
    register_label,
)


def _ensure_utc_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _as_of_ts(as_of: datetime | str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(as_of)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts


def assert_frame_sources_allowed(source_tables: tuple[str, ...]) -> None:
    bad = [s for s in source_tables if s in BANNED_LABEL_SOURCES]
    if bad:
        raise ValueError(f"Label builder invoked with banned sources: {bad}")


def build_l_deal_180(
    snapshots: pd.DataFrame,
    deals: pd.DataFrame,
    *,
    athlete_col: str = "athlete_id",
    as_of_col: str = "as_of",
    deal_date_col: str = "deal_date",
    coverage_col: str = "coverage_ok",
    horizon_days: int = 180,
) -> pd.DataFrame:
    """L_deal_180: 1 if a deal falls in (t, t+180d]; require coverage_ok when present.

    ``snapshots``: one row per (athlete_id, as_of).
    ``deals``: athlete_id + deal_date (+ optional coverage / source columns).
    """
    assert_frame_sources_allowed(("athlete_nil_deals", "verified_deal_transactions"))
    if snapshots.empty:
        return pd.DataFrame(columns=[athlete_col, as_of_col, "L_deal_180", "coverage_ok"])

    snap = snapshots.copy()
    snap[as_of_col] = _ensure_utc_ts(snap[as_of_col])
    snap[athlete_col] = snap[athlete_col].astype(str)

    deal = deals.copy() if deals is not None else pd.DataFrame()
    if deal.empty:
        out = snap[[athlete_col, as_of_col]].copy()
        out["L_deal_180"] = 0
        out["coverage_ok"] = False
        return out

    deal[athlete_col] = deal[athlete_col].astype(str)
    deal[deal_date_col] = _ensure_utc_ts(deal[deal_date_col])
    if coverage_col not in deal.columns:
        deal[coverage_col] = True

    labels: list[dict[str, Any]] = []
    horizon = timedelta(days=horizon_days)
    deals_by_athlete = {aid: g for aid, g in deal.groupby(athlete_col)}
    for _, row in snap.iterrows():
        aid = str(row[athlete_col])
        t0 = row[as_of_col]
        t1 = t0 + horizon
        g = deals_by_athlete.get(aid)
        coverage_ok = True
        if g is None:
            positive = 0
            # No deals and no coverage row → coverage unknown; mark false.
            coverage_ok = False
        else:
            # Coverage: any scrape coverage flag True for this athlete in window sources.
            coverage_ok = bool(g[coverage_col].fillna(False).any())
            in_window = (g[deal_date_col] > t0) & (g[deal_date_col] <= t1)
            positive = int(in_window.any()) if coverage_ok else 0
        labels.append(
            {
                athlete_col: aid,
                as_of_col: t0,
                "L_deal_180": positive if coverage_ok else 0,
                "coverage_ok": coverage_ok,
            }
        )
    return pd.DataFrame(labels)


def build_l_attention_90(
    snapshots: pd.DataFrame,
    future_reach: pd.DataFrame,
    *,
    athlete_col: str = "athlete_id",
    as_of_col: str = "as_of",
    reach_col: str = "trusted_social_reach",
    future_as_of_col: str = "as_of",
    horizon_days: int = 90,
    tol_days: int = 14,
) -> pd.DataFrame:
    """L_attention_90 ≈ log(reach at t+90 / reach at t) from social/metric history."""
    assert_frame_sources_allowed(("social_snapshots", "athlete_metric_history"))
    snap = snapshots.copy()
    snap[as_of_col] = _ensure_utc_ts(snap[as_of_col])
    snap[athlete_col] = snap[athlete_col].astype(str)
    fut = future_reach.copy()
    fut[future_as_of_col] = _ensure_utc_ts(fut[future_as_of_col])
    fut[athlete_col] = fut[athlete_col].astype(str)

    rows: list[dict[str, Any]] = []
    fut_by = {aid: g for aid, g in fut.groupby(athlete_col)}
    for _, row in snap.iterrows():
        aid = str(row[athlete_col])
        t0 = row[as_of_col]
        reach0 = float(row.get(reach_col) or 0.0)
        target = t0 + timedelta(days=horizon_days)
        g = fut_by.get(aid)
        label = np.nan
        if g is not None and reach0 > 0:
            deltas = (g[future_as_of_col] - target).abs()
            ok = deltas <= pd.Timedelta(days=tol_days)
            if bool(ok.any()):
                candidates = g.loc[ok]
                nearest = candidates.iloc[
                    (candidates[future_as_of_col] - target).abs().to_numpy().argmin()
                ]
                reach1 = float(nearest.get(reach_col) or 0.0)
                if reach1 > 0:
                    label = float(np.log(reach1 / reach0))
        rows.append({athlete_col: aid, as_of_col: t0, "L_attention_90": label})
    return pd.DataFrame(rows)


def build_l_dollars(
    snapshots: pd.DataFrame,
    verified_deals: pd.DataFrame,
    *,
    athlete_col: str = "athlete_id",
    as_of_col: str = "as_of",
    amount_col: str = "amount_usd",
    deal_date_col: str = "deal_date",
) -> pd.DataFrame:
    """log1p(verified deal USD) — verified_deal_transactions only (not On3)."""
    assert_frame_sources_allowed(("verified_deal_transactions",))
    # Refuse On3 / estimate columns if present under wrong names.
    banned_amount_cols = {"nil_valuation", "on3_valuation", "dollar_p50_usd"}
    overlap = banned_amount_cols & set(verified_deals.columns)
    if overlap:
        raise ValueError(
            f"L_dollars refuses non-verified amount columns: {sorted(overlap)}"
        )

    snap = snapshots.copy()
    snap[as_of_col] = _ensure_utc_ts(snap[as_of_col])
    snap[athlete_col] = snap[athlete_col].astype(str)
    deals = verified_deals.copy()
    if deals.empty:
        out = snap[[athlete_col, as_of_col]].copy()
        out["L_dollars"] = np.nan
        return out
    deals[deal_date_col] = _ensure_utc_ts(deals[deal_date_col])
    deals[athlete_col] = deals[athlete_col].astype(str)

    rows: list[dict[str, Any]] = []
    by = {aid: g for aid, g in deals.groupby(athlete_col)}
    for _, row in snap.iterrows():
        aid = str(row[athlete_col])
        t0 = row[as_of_col]
        g = by.get(aid)
        val = np.nan
        if g is not None:
            past = g.loc[g[deal_date_col] <= t0]
            if not past.empty and amount_col in past.columns:
                total = float(past[amount_col].fillna(0).sum())
                val = float(np.log1p(max(0.0, total)))
        rows.append({athlete_col: aid, as_of_col: t0, "L_dollars": val})
    return pd.DataFrame(rows)


def build_l_unavail_180(
    snapshots: pd.DataFrame,
    events: pd.DataFrame,
    *,
    athlete_col: str = "athlete_id",
    as_of_col: str = "as_of",
    event_date_col: str = "event_date",
    event_type_col: str = "event_type",
    horizon_days: int = 180,
) -> pd.DataFrame:
    """1 if portal/draft/injury/role-loss occurs in (t, t+180d]."""
    assert_frame_sources_allowed(("roster_events", "injury_feed", "athlete_team_seasons"))
    unavail_types = {
        "transfer_portal",
        "draft",
        "season_ending_injury",
        "lost_starting_role",
        "injury",
        "portal",
    }
    snap = snapshots.copy()
    snap[as_of_col] = _ensure_utc_ts(snap[as_of_col])
    snap[athlete_col] = snap[athlete_col].astype(str)
    ev = events.copy() if events is not None else pd.DataFrame()
    if ev.empty:
        out = snap[[athlete_col, as_of_col]].copy()
        out["L_unavail_180"] = 0
        return out
    ev[event_date_col] = _ensure_utc_ts(ev[event_date_col])
    ev[athlete_col] = ev[athlete_col].astype(str)

    rows: list[dict[str, Any]] = []
    by = {aid: g for aid, g in ev.groupby(athlete_col)}
    horizon = timedelta(days=horizon_days)
    for _, row in snap.iterrows():
        aid = str(row[athlete_col])
        t0 = row[as_of_col]
        t1 = t0 + horizon
        g = by.get(aid)
        positive = 0
        if g is not None:
            types = g[event_type_col].astype(str).str.lower()
            in_window = (g[event_date_col] > t0) & (g[event_date_col] <= t1)
            hit = in_window & types.isin(unavail_types)
            positive = int(hit.any())
        rows.append({athlete_col: aid, as_of_col: t0, "L_unavail_180": positive})
    return pd.DataFrame(rows)


def build_l_game_margin(games: pd.DataFrame) -> pd.Series:
    """Impact I1 label: home_score - away_score."""
    assert_frame_sources_allowed(("games",))
    if "home_score" not in games.columns or "away_score" not in games.columns:
        raise ValueError("games need home_score and away_score")
    return (games["home_score"].astype(float) - games["away_score"].astype(float)).rename(
        "L_game_margin"
    )


def register_gravity_builders(*, overwrite: bool = True) -> None:
    """Re-bind registry entries to real builders (idempotent)."""
    specs = [
        LabelSpec(
            name="L_deal_180",
            source_tables=("athlete_nil_deals", "verified_deal_transactions"),
            horizon=timedelta(days=180),
            builder=build_l_deal_180,
            description="1 if athlete has a deal with deal_date in (t, t+180d]",
            role="primary",
            objective="gravity",
        ),
        LabelSpec(
            name="L_attention_90",
            source_tables=("social_snapshots", "athlete_metric_history"),
            horizon=timedelta(days=90),
            builder=build_l_attention_90,
            description="log(reach at t+90d / reach at t) from trusted social totals",
            role="auxiliary",
            objective="gravity",
        ),
        LabelSpec(
            name="L_dollars",
            source_tables=("verified_deal_transactions",),
            horizon=None,
            builder=build_l_dollars,
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
            builder=build_l_unavail_180,
            description="1 if portal/draft/injury/role-loss in (t, t+180d]",
            role="risk",
            objective="gravity",
        ),
        LabelSpec(
            name="L_game_margin",
            source_tables=("games",),
            horizon=None,
            builder=build_l_game_margin,
            description="home_score - away_score for APM (Impact I1)",
            role="primary",
            objective="impact",
        ),
    ]
    for spec in specs:
        register_label(spec, overwrite=overwrite)


def make_deal_label_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Small fixture for unit tests (not production training)."""
    snapshots = pd.DataFrame(
        {
            "athlete_id": ["a1", "a1", "a2"],
            "as_of": pd.to_datetime(
                ["2025-01-01", "2025-06-01", "2025-01-01"], utc=True
            ),
        }
    )
    deals = pd.DataFrame(
        {
            "athlete_id": ["a1", "a2"],
            "deal_date": pd.to_datetime(["2025-03-15", "2024-06-01"], utc=True),
            "coverage_ok": [True, True],
        }
    )
    return snapshots, deals


# Bind builders at import so registry lineage points at real callables.
register_gravity_builders(overwrite=True)

# Touch get_label so static analyzers know registry is populated.
_ = get_label  # noqa: F841


__all__ = [
    "assert_frame_sources_allowed",
    "build_l_attention_90",
    "build_l_deal_180",
    "build_l_dollars",
    "build_l_game_margin",
    "build_l_unavail_180",
    "make_deal_label_fixture",
    "register_gravity_builders",
]
