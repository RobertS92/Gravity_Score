"""CLI skeleton for Gravity deal-outcome training (SCORING_ML_FIX_SPEC §5 G6).

Wires label builders + promotion gates. Does not claim a trained commercial
model — live data (dated deals, PIT socials, Impact Proof features) is required
before G-G1..G-G5 can pass.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gravity_ml.gravity import BLOCKED_REASON
from gravity_ml.gravity.labels import build_l_deal_180, make_deal_label_fixture
from gravity_ml.labels.registry import get_label, validate_registry
from gravity_ml.train.promotion_gate import (
    PromotionRefused,
    assert_bundle_promotable,
    write_metrics_with_lineage,
)

logger = logging.getLogger(__name__)

LEAGUE_MODEL_KEYS = {
    "cfb": "gravity_athlete_cfb_gravity_v2",
    "ncaab_mens": "gravity_athlete_ncaab_mens_gravity_v2",
}


def run_label_smoke(*, league: str, version: str, out_root: Path, promote: bool) -> Path:
    validate_registry()
    spec = get_label("L_deal_180")
    assert spec.builder is build_l_deal_180 or spec.builder.__name__ == "build_l_deal_180"

    snapshots, deals = make_deal_label_fixture()
    labels = build_l_deal_180(snapshots, deals)
    positives = int(labels["L_deal_180"].sum())
    model_key = LEAGUE_MODEL_KEYS[league]
    metrics: dict[str, Any] = {
        "label_source": "athlete_nil_deals",
        "fixture_rows": int(len(labels)),
        "test_positives": positives,
        "test_rows": int(len(labels)),
        "circularity_holdout_r2": 0.0,
        "notes": BLOCKED_REASON,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    metrics = write_metrics_with_lineage(
        metrics, label_source="athlete_nil_deals", model_key=model_key
    )

    out_dir = out_root / model_key / version
    out_dir.mkdir(parents=True, exist_ok=True)
    labels.to_csv(out_dir / "label_smoke.csv", index=False)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (out_dir / "training_manifest.json").write_text(
        json.dumps(
            {
                "model_key": model_key,
                "version": version,
                "label_source": "athlete_nil_deals",
                "training_source": "fixture_label_smoke",
                "row_count": int(len(labels)),
                "component": "gravity_label_smoke",
                "blocked_reason": BLOCKED_REASON,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("Gravity label smoke wrote %s (positives=%d)", out_dir, positives)
    logger.warning("Not a trained Gravity model — %s", BLOCKED_REASON)

    if promote:
        try:
            assert_bundle_promotable(model_key, metrics, label_source="athlete_nil_deals")
        except PromotionRefused as exc:
            logger.error("NOT promoted: %s", exc)
            raise SystemExit(2) from exc
    else:
        try:
            assert_bundle_promotable(model_key, metrics, label_source="athlete_nil_deals")
        except PromotionRefused as exc:
            logger.info("Promotion correctly refused: %s", exc)

    return out_dir


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Gravity label/train skeleton (no live promote)")
    parser.add_argument("--league", choices=sorted(LEAGUE_MODEL_KEYS), default="cfb")
    parser.add_argument("--version", default="0.0.1-label-smoke")
    parser.add_argument("--out", default="models/bundles")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    run_label_smoke(
        league=args.league,
        version=args.version,
        out_root=Path(args.out),
        promote=bool(args.promote),
    )


if __name__ == "__main__":
    main()
