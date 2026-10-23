"""Game-level Adjusted Plus-Minus (SCORING_ML_FIX_SPEC §4 I1).

Fits ridge on game margins with participation-share design rows. Works against
in-memory fixtures (DataFrames) without a live DB. Live training is blocked until
scraper WP10 populates ``games`` / ``game_player_box``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from gravity_ml.impact import BLOCKED_REASON

ParticipationMode = Literal["basketball_minutes", "football_snaps", "appeared"]

REQUIRED_GAME_COLS = ("game_id", "home_team_id", "away_team_id", "home_score", "away_score")
REQUIRED_BOX_COLS = ("game_id", "athlete_id", "team_id")


class ImpactDataBlocked(RuntimeError):
    """Raised when live WP10 game tables are missing or empty."""


@dataclass
class APMResult:
    """Per-player APM coefficients from a ridge fit."""

    betas: pd.Series  # athlete_id -> margin points per full-game participation
    se: pd.Series  # approximate posterior standard errors
    intercept: float
    alpha: float
    n_games: int
    n_players: int
    participation_observed_frac: float
    lambda_path: list[float] = field(default_factory=list)
    cv_rmse: list[float] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def participation_share(
    box_row: pd.Series,
    *,
    mode: ParticipationMode,
    team_minutes: float | None = None,
    team_snaps: float | None = None,
) -> tuple[float, bool]:
    """Return (share, participation_observed).

    Basketball: minutes_p / (team_minutes / 5). Football: snaps_p / team_snaps
    when present; else 1.0 if appeared with participation_observed=False.
    """
    if mode == "basketball_minutes":
        minutes = float(box_row.get("minutes") or 0.0)
        tm = float(team_minutes or 0.0)
        if minutes <= 0 or tm <= 0:
            return 0.0, False
        share = minutes / (tm / 5.0)
        return float(share), True
    if mode == "football_snaps":
        snaps = float(box_row.get("snaps") or 0.0)
        ts = float(team_snaps or 0.0)
        if snaps > 0 and ts > 0:
            return float(snaps / ts), True
        # Appeared but snaps missing — unit weight, flag unobserved.
        if bool(box_row.get("appeared", True)):
            return 1.0, False
        return 0.0, False
    # appeared
    if bool(box_row.get("appeared", True)) or float(box_row.get("minutes") or 0) > 0:
        return 1.0, False
    return 0.0, False


def _team_totals(box: pd.DataFrame, game_id: Any, team_id: Any, col: str) -> float:
    mask = (box["game_id"] == game_id) & (box["team_id"] == team_id)
    return float(box.loc[mask, col].fillna(0).sum()) if col in box.columns else 0.0


def build_apm_design(
    games: pd.DataFrame,
    box: pd.DataFrame,
    *,
    mode: ParticipationMode = "basketball_minutes",
    include_home: bool = True,
) -> tuple[np.ndarray, np.ndarray, list[str], pd.DataFrame]:
    """Build sparse-friendly dense design matrix X, margin y, player column names.

    For each completed game g: y = home_score - away_score.
    For each player who appeared: x = +s if home, -s if away.
    Extra column: home_court indicator (0 for neutral).
    """
    for col in REQUIRED_GAME_COLS:
        if col not in games.columns:
            raise ValueError(f"games missing required column {col!r}")
    for col in REQUIRED_BOX_COLS:
        if col not in box.columns:
            raise ValueError(f"game_player_box missing required column {col!r}")

    completed = games.dropna(subset=["home_score", "away_score"]).copy()
    if completed.empty:
        raise ValueError("No completed games with scores")

    player_ids = sorted({str(a) for a in box["athlete_id"].astype(str).unique()})
    player_index = {pid: i for i, pid in enumerate(player_ids)}
    n_extra = 1 if include_home else 0
    X = np.zeros((len(completed), len(player_ids) + n_extra), dtype=np.float64)
    y = np.zeros(len(completed), dtype=np.float64)
    game_meta_rows: list[dict[str, Any]] = []
    observed_flags: list[bool] = []

    for row_i, (_, g) in enumerate(completed.iterrows()):
        gid = g["game_id"]
        home = g["home_team_id"]
        away = g["away_team_id"]
        y[row_i] = float(g["home_score"]) - float(g["away_score"])
        is_neutral = bool(g.get("neutral_site", False)) if "neutral_site" in completed.columns else False
        if include_home:
            X[row_i, -1] = 0.0 if is_neutral else 1.0

        gbox = box.loc[box["game_id"] == gid]
        home_minutes = _team_totals(box, gid, home, "minutes")
        away_minutes = _team_totals(box, gid, away, "minutes")
        home_snaps = _team_totals(box, gid, home, "snaps")
        away_snaps = _team_totals(box, gid, away, "snaps")

        for _, prow in gbox.iterrows():
            pid = str(prow["athlete_id"])
            if pid not in player_index:
                continue
            team_id = prow["team_id"]
            if team_id == home:
                sign = 1.0
                tm, ts = home_minutes, home_snaps
            elif team_id == away:
                sign = -1.0
                tm, ts = away_minutes, away_snaps
            else:
                continue
            share, observed = participation_share(
                prow, mode=mode, team_minutes=tm, team_snaps=ts
            )
            observed_flags.append(observed)
            if share == 0.0:
                continue
            X[row_i, player_index[pid]] = sign * share

        game_meta_rows.append(
            {
                "game_id": gid,
                "as_of": g.get("played_at") or g.get("as_of"),
                "season_year": g.get("season_year"),
            }
        )

    feature_names = list(player_ids) + (["home_court"] if include_home else [])
    meta = pd.DataFrame(game_meta_rows)
    meta.attrs["participation_observed_frac"] = (
        float(np.mean(observed_flags)) if observed_flags else 0.0
    )
    return X, y, feature_names, meta


def _forward_chain_folds(
    meta: pd.DataFrame,
    n_folds: int = 3,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Time-ordered folds: train on earlier games, validate on later."""
    n = len(meta)
    if n < 4:
        idx = np.arange(n)
        split = max(1, n // 2)
        return [(idx[:split], idx[split:])] if split < n else [(idx, idx)]

    order = np.arange(n)
    if "as_of" in meta.columns and meta["as_of"].notna().any():
        order = np.argsort(pd.to_datetime(meta["as_of"], utc=True, errors="coerce").fillna(pd.Timestamp.min.tz_localize("UTC")).to_numpy())
    elif "season_year" in meta.columns and meta["season_year"].notna().any():
        order = np.argsort(meta["season_year"].fillna(-1).to_numpy())

    folds: list[tuple[np.ndarray, np.ndarray]] = []
    # Expanding window: validate on successive trailing chunks.
    chunk = max(1, n // (n_folds + 1))
    for k in range(1, n_folds + 1):
        val_end = min(n, chunk * (k + 1))
        val_start = chunk * k
        if val_start >= n:
            break
        train_idx = order[:val_start]
        val_idx = order[val_start:val_end]
        if len(train_idx) == 0 or len(val_idx) == 0:
            continue
        folds.append((train_idx, val_idx))
    if not folds:
        split = n // 2
        folds = [(order[:split], order[split:])]
    return folds


def select_ridge_alpha(
    X: np.ndarray,
    y: np.ndarray,
    meta: pd.DataFrame,
    *,
    alphas: Sequence[float] | None = None,
    n_folds: int = 3,
) -> tuple[float, list[float], list[float]]:
    """Choose λ by forward-chaining time CV (RMSE)."""
    alphas = list(alphas) if alphas is not None else [0.1, 1.0, 10.0, 100.0, 1000.0]
    folds = _forward_chain_folds(meta, n_folds=n_folds)
    cv_rmse: list[float] = []
    for alpha in alphas:
        rmses: list[float] = []
        for train_idx, val_idx in folds:
            model = Ridge(alpha=float(alpha), fit_intercept=True)
            model.fit(X[train_idx], y[train_idx])
            pred = model.predict(X[val_idx])
            rmses.append(float(np.sqrt(np.mean((y[val_idx] - pred) ** 2))))
        cv_rmse.append(float(np.mean(rmses)) if rmses else float("inf"))
    best_i = int(np.argmin(cv_rmse))
    return float(alphas[best_i]), list(alphas), cv_rmse


def _ridge_posterior_se(
    X: np.ndarray,
    y: np.ndarray,
    coef: np.ndarray,
    intercept: float,
    alpha: float,
) -> np.ndarray:
    """Approximate SE from σ² (XᵀX + λI)⁻¹ diagonal (dense; fine for fixtures)."""
    n, p = X.shape
    resid = y - (X @ coef + intercept)
    dof = max(1, n - p)
    sigma2 = float(np.sum(resid**2) / dof)
    xtx = X.T @ X
    # Add λ on player columns; home_court (last) gets small ridge too.
    xtx = xtx + alpha * np.eye(p)
    try:
        cov = sigma2 * np.linalg.pinv(xtx)
        se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    except np.linalg.LinAlgError:
        se = np.full(p, np.nan)
    return se


def fit_apm(
    games: pd.DataFrame,
    box: pd.DataFrame,
    *,
    mode: ParticipationMode = "basketball_minutes",
    alphas: Sequence[float] | None = None,
    include_home: bool = True,
) -> APMResult:
    """Fit I1 APM ridge on fixture or live game/box frames."""
    X, y, feature_names, meta = build_apm_design(
        games, box, mode=mode, include_home=include_home
    )
    alpha, lambda_path, cv_rmse = select_ridge_alpha(X, y, meta, alphas=alphas)
    model = Ridge(alpha=alpha, fit_intercept=True)
    model.fit(X, y)
    coef = np.asarray(model.coef_, dtype=np.float64)
    se_all = _ridge_posterior_se(X, y, coef, float(model.intercept_), alpha)

    player_names = [n for n in feature_names if n != "home_court"]
    n_players = len(player_names)
    betas = pd.Series(coef[:n_players], index=player_names, name="impact_rate")
    se = pd.Series(se_all[:n_players], index=player_names, name="impact_rate_se")
    return APMResult(
        betas=betas,
        se=se,
        intercept=float(model.intercept_),
        alpha=alpha,
        n_games=int(X.shape[0]),
        n_players=n_players,
        participation_observed_frac=float(meta.attrs.get("participation_observed_frac") or 0.0),
        lambda_path=lambda_path,
        cv_rmse=cv_rmse,
        meta={
            "home_court_coef": float(coef[-1]) if include_home and len(coef) else None,
            "mode": mode,
        },
    )


def assert_live_games_available(games: pd.DataFrame | None, box: pd.DataFrame | None) -> None:
    """Raise ImpactDataBlocked when WP10 tables are missing/empty (no silent train)."""
    if games is None or box is None or games.empty or box.empty:
        raise ImpactDataBlocked(BLOCKED_REASON)


def make_fixture_games(
    n_games: int = 6,
    n_players_per_team: int = 5,
    *,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Synthetic completed games + box for unit tests (not for promotion)."""
    rng = np.random.default_rng(seed)
    games_rows: list[dict[str, Any]] = []
    box_rows: list[dict[str, Any]] = []
    player_ids = [f"p{i}" for i in range(n_players_per_team * 4)]
    for g in range(n_games):
        gid = f"g{g}"
        home_team, away_team = f"t{g % 2}", f"t{(g % 2) + 2}"
        home_score = int(70 + rng.integers(-15, 16))
        away_score = int(70 + rng.integers(-15, 16))
        games_rows.append(
            {
                "game_id": gid,
                "home_team_id": home_team,
                "away_team_id": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "neutral_site": False,
                "played_at": f"2025-11-{(g % 28) + 1:02d}T00:00:00Z",
                "season_year": 2025,
            }
        )
        home_players = player_ids[0:n_players_per_team]
        away_players = player_ids[n_players_per_team : 2 * n_players_per_team]
        if g % 2 == 1:
            home_players = player_ids[2 * n_players_per_team : 3 * n_players_per_team]
            away_players = player_ids[3 * n_players_per_team : 4 * n_players_per_team]
        for pid in home_players:
            box_rows.append(
                {
                    "game_id": gid,
                    "athlete_id": pid,
                    "team_id": home_team,
                    "minutes": float(rng.uniform(12, 36)),
                    "appeared": True,
                }
            )
        for pid in away_players:
            box_rows.append(
                {
                    "game_id": gid,
                    "athlete_id": pid,
                    "team_id": away_team,
                    "minutes": float(rng.uniform(12, 36)),
                    "appeared": True,
                }
            )
    return pd.DataFrame(games_rows), pd.DataFrame(box_rows)


__all__ = [
    "APMResult",
    "ImpactDataBlocked",
    "assert_live_games_available",
    "build_apm_design",
    "fit_apm",
    "make_fixture_games",
    "participation_share",
    "select_ridge_alpha",
]
