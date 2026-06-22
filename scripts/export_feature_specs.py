#!/usr/bin/env python3
"""Export feature engineering sport specs to config/feature_engineering/manifest.json."""

from __future__ import annotations

import json
from pathlib import Path

from gravity_api.feature_engineering.sport_specs import export_specs_json


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "config" / "feature_engineering"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = export_specs_json()
    manifest["schema_version"] = "gravity_features_bpxvr_v1"
    manifest["description"] = (
        "BPXVR feature extraction specs — all positions, college + pro target sports. "
        "Profile card: level_raw, level_pctile, level_tier, delta_yoy_pct, trajectory_class, stability_score."
    )
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    sports = manifest["sports"]
    total_positions = sum(len(s["position_groups"]) for s in sports.values())
    print(f"Wrote {path} ({len(sports)} sports, {total_positions} position groups)")


if __name__ == "__main__":
    main()
