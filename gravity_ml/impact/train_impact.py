"""CLI: train Impact APM (I1) with promotion gates (SCORING_ML_FIX_SPEC §4 I7).

Default path uses fixtures for skeleton dry-runs. Live promotion requires WP10
``games`` / ``game_player_box`` and §4 G-I1..G-I5 metrics — this script never
promotes on formula labels (M4/M5).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gravity_ml.impact import BLOCKED_REASON
from gravity_ml.impact.apm import (
    ImpactDataBlocked,
    assert_live_games_available,
    fit_apm,
    make_fixture_games,
)
from gravity_ml.train.promotion_gate import (
    PromotionRefused,
    assert_bundle_promotable,
    write_metrics_with_lineage,
)

logger = logging.getLogger(__name__)

LEAGUE_MODEL_KEYS = {
    "ncaab_mens": "gravity_athlete_ncaab_mens_impact_v2",
    "ncaab_womens": "gravity_athlete_ncaab_womens_impact_v2",
    "cfb": "gravity_athlete_cfb_impact_v2",
}

LEAGUE_MODE = {
    "ncaab_mens": "basketball_minutes",
    "ncaab_womens": "basketball_minutes",
    "cfb": "football_snaps",
}


def _load_frames_from_csv(games_path: Path, box_path: Path):
    import pandas as pd

    return pd.read_csv(games_path), pd.read_csv(box_path)


def run_skeleton(
    *,
    league: str,
    version: str,
    out_root: Path,
    promote: bool,
    use_fixture: bool,
    games_csv: Path | None,
    box_csv: Path | None,
) -> Path:
    model_key = LEAGUE_MODEL_KEYS[league]
    mode = LEAGUE_MODE[league]

    if use_fixture:
        games, box = make_fixture_games(n_games=12, n_players_per_team=5, seed=7)
        label_source = "fixture_game_margins"
        logger.warning(
            "Running APM skeleton on synthetic fixtures — NOT eligible for promotion"
        )
    else:
        if not games_csv or not box_csv:
            raise ImpactDataBlocked(
                "Provide --games-csv and --box-csv, or --fixture for skeleton. "
                + BLOCKED_REASON
            )
        games, box = _load_frames_from_csv(games_csv, box_csv)
        assert_live_games_available(games, box)
        label_source = "games_margins"

    result = fit_apm(games, box, mode=mode)  # type: ignore[arg-type]
    metrics: dict[str, Any] = {
        "n_games": result.n_games,
        "n_players": result.n_players,
        "alpha": result.alpha,
        "participation_observed_frac": result.participation_observed_frac,
        "cv_rmse_by_alpha": dict(zip(result.lambda_path, result.cv_rmse)),
        "label_source": label_source,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        # Gate fields left unset until real holdout eval — promotion must fail.
        "test_rows": result.n_games,
        "test_games": result.n_games,
        "circularity_holdout_r2": 0.0,
        "notes": BLOCKED_REASON if use_fixture else "APM fit only; run G-I1..G-I5 before promote",
    }
    metrics = write_metrics_with_lineage(
        metrics, label_source=label_source, model_key=model_key
    )

    out_dir = out_root / model_key / version
    out_dir.mkdir(parents=True, exist_ok=True)
    betas_path = out_dir / "apm_betas.csv"
    result.betas.rename("impact_rate").to_frame().join(
        result.se.rename("impact_rate_se")
    ).to_csv(betas_path)
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "model_key": model_key,
        "league": league,
        "version": version,
        "label_source": label_source,
        "training_source": label_source,
        "row_count": result.n_games,
        "component": "apm_i1_skeleton",
        "blocked_reason": BLOCKED_REASON if use_fixture else None,
    }
    (out_dir / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("Wrote APM skeleton bundle %s (n_games=%d)", out_dir, result.n_games)

    if promote:
        try:
            assert_bundle_promotable(model_key, metrics, label_source=label_source)
        except PromotionRefused as exc:
            logger.error("NOT promoted: %s", exc)
            raise SystemExit(2) from exc
        # Unreachable until G-I gates are filled with real outcomes.
        index_path = out_root / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"champions": {}}
        index.setdefault("champions", {})[model_key] = version
        index["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        logger.info("PROMOTED %s -> %s", model_key, version)
    else:
        # Still verify gates would refuse fixtures / incomplete metrics.
        try:
            assert_bundle_promotable(model_key, metrics, label_source=label_source)
            logger.warning("Unexpected: gates passed without --promote")
        except PromotionRefused as exc:
            logger.info("Promotion correctly refused (expected until WP10+gates): %s", exc)

    return out_dir


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Train Impact APM (I1). Fixture skeleton by default; live WP10 required to promote."
    )
    parser.add_argument("--league", choices=sorted(LEAGUE_MODEL_KEYS), default="ncaab_mens")
    parser.add_argument("--version", default="0.0.1-skeleton")
    parser.add_argument("--out", default="models/bundles")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Fit APM on synthetic games (unit/skeleton only; cannot promote)",
    )
    parser.add_argument("--games-csv", type=Path, default=None)
    parser.add_argument("--box-csv", type=Path, default=None)
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Attempt champion write (refused until G-I gates pass on live data)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    if not args.fixture and not (args.games_csv and args.box_csv):
        # Default: refuse silent live train without data; print blocker.
        logger.error("Impact train blocked: %s", BLOCKED_REASON)
        logger.error("Pass --fixture for skeleton dry-run, or --games-csv/--box-csv.")
        raise SystemExit(1)

    try:
        run_skeleton(
            league=args.league,
            version=args.version,
            out_root=Path(args.out),
            promote=args.promote,
            use_fixture=bool(args.fixture),
            games_csv=args.games_csv,
            box_csv=args.box_csv,
        )
    except ImpactDataBlocked as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
