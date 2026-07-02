"""Evaluate production gates against diagnostics report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts" / "cfb_value_nil_diagnostics" / "report.json"


def main() -> int:
    from gravity_ml.inference.promotion_policy import production_gates

    if not REPORT.exists():
        print(json.dumps({"error": f"Missing report: {REPORT}"}))
        return 1

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    gates = production_gates("gravity_athlete_cfb_value_v1")
    required = gates.get("required") or {}

    test = (report.get("metrics_with_augmentation") or {}).get("test") or {}
    val = (report.get("metrics_with_augmentation") or {}).get("validation") or {}
    folds = report.get("temporal_stability_folds") or []
    fold_spear = [f["test_spearman"] for f in folds if f.get("test_spearman") is not None]

    val_test_ratio = (test.get("mae") or 0) / max(val.get("mae") or 1e-9, 1e-9)
    observed = (report.get("label_coverage") or {}).get("nil_observed_positive") or 0
    total = (report.get("label_coverage") or {}).get("rows_total") or 1
    ig_obs = (report.get("instagram_audit") or {}).get("observed_mask_1") or 0

    checks = {
        "labeled_rows_min": {
            "required": required.get("labeled_rows_min"),
            "actual": report.get("labeled_rows"),
            "pass": report.get("labeled_rows", 0) >= required.get("labeled_rows_min", 0),
        },
        "test_rows_min": {
            "required": required.get("test_rows_min"),
            "actual": test.get("n"),
            "pass": (test.get("n") or 0) >= required.get("test_rows_min", 0),
        },
        "test_spearman_min": {
            "required": required.get("test_spearman_min"),
            "actual": test.get("spearman"),
            "pass": (test.get("spearman") or 0) >= required.get("test_spearman_min", 0),
        },
        "test_mae_max": {
            "required": required.get("test_mae_max"),
            "actual": test.get("mae"),
            "pass": (test.get("mae") or 999) <= required.get("test_mae_max", 999),
        },
        "val_test_mae_ratio_max": {
            "required": required.get("val_test_mae_ratio_max"),
            "actual": round(val_test_ratio, 3),
            "pass": val_test_ratio <= required.get("val_test_mae_ratio_max", 999),
        },
        "temporal_fold_test_spearman_min": {
            "required": required.get("temporal_fold_test_spearman_min"),
            "actual": min(fold_spear) if fold_spear else None,
            "pass": (min(fold_spear) if fold_spear else 0) >= required.get("temporal_fold_test_spearman_min", 0),
        },
        "temporal_fold_spearman_std_max": {
            "required": required.get("temporal_fold_spearman_std_max"),
            "actual": round(float(__import__("numpy").std(fold_spear)), 4) if len(fold_spear) > 1 else None,
            "pass": (
                float(__import__("numpy").std(fold_spear)) <= required.get("temporal_fold_spearman_std_max", 999)
                if len(fold_spear) > 1
                else False
            ),
        },
        "nil_label_coverage_pct": {
            "recommended": (gates.get("recommended") or {}).get("nil_label_coverage_pct_min"),
            "actual": round(100 * observed / total, 2),
            "pass": (100 * observed / total) >= (gates.get("recommended") or {}).get("nil_label_coverage_pct_min", 0),
        },
        "instagram_observed_pct": {
            "recommended": (gates.get("recommended") or {}).get("instagram_observed_pct_min"),
            "actual": round(100 * ig_obs / total, 2),
            "pass": (100 * ig_obs / total) >= (gates.get("recommended") or {}).get("instagram_observed_pct_min", 0),
        },
    }

    required_pass = all(v["pass"] for k, v in checks.items() if k in required or k.endswith("_max") or k.endswith("_min"))
    all_required = all(
        checks[k]["pass"]
        for k in (
            "labeled_rows_min",
            "test_rows_min",
            "test_spearman_min",
            "test_mae_max",
            "val_test_mae_ratio_max",
            "temporal_fold_test_spearman_min",
            "temporal_fold_spearman_std_max",
        )
    )

    out = {
        "model_key": "gravity_athlete_cfb_value_v1",
        "stage_recommendation": "champion" if all_required else "beta_rank_only",
        "all_required_gates_pass": all_required,
        "checks": checks,
    }
    print(json.dumps(out, indent=2))
    return 0 if all_required else 2


if __name__ == "__main__":
    sys.exit(main())
