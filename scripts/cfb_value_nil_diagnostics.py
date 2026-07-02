#!/usr/bin/env python3
"""CFB value_nil diagnostics: gap analysis, feature importance, aug ablation, label coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "_build_nb.py"
DATA_DIR = Path.home() / "Downloads/gravity_exports/raw"
OUT_DIR = ROOT / "artifacts" / "cfb_value_nil_diagnostics"
RANDOM_SEED = 42

SPORT_CONFIG = {
    "cfb": {
        "file": "athletes_cfb_raw.csv",
        "league": "ncaa",
        "conference_parse": "college",
        "train_objectives": ["value_nil", "value_proxy_ig", "quality"],
        "export_objectives": ["value_nil"],
        "min_rows_train": 80,
    },
}

AUG_FLAGS = {
    "cfb": {
        "bootstrap_multiplier": 2.0,
        "missingness_p": 0.35,
        "jitter_sigma": 0.05,
        "school_swap_p": 0.10,
    },
}


def _load_notebook_utils():
    """Execute notebook generator utilities inline (shared training logic)."""
    src = NB.read_text(encoding="utf-8")
    marker = "UTILS = r'''"
    start = src.index(marker) + len(marker)
    end = src.index("'''", start)
    code = src[start:end]
    import numpy as np
    import pandas as pd

    ns: dict = {
        "__builtins__": __builtins__,
        "DATA_DIR": DATA_DIR,
        "RANDOM_SEED": RANDOM_SEED,
        "np": np,
        "pd": pd,
        "Path": Path,
        "json": json,
        "re": __import__("re"),
    }
    exec(code, ns)  # noqa: S102 — local training utilities only
    ns.setdefault("SPORT_CONFIG", SPORT_CONFIG)
    ns.setdefault("AUG_FLAGS", AUG_FLAGS)
    ns.setdefault(
        "P5_CONFERENCES",
        {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "Pac-12 Conference"},
    )
    return ns


def _metrics(y_true, pred) -> dict:
    if len(y_true) == 0:
        return {}
    mae = float(mean_absolute_error(y_true, pred))
    rmse = float(mean_squared_error(y_true, pred) ** 0.5)
    spear = float(pd.Series(y_true).corr(pd.Series(pred), method="spearman")) if len(y_true) > 2 else None
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "spearman": round(spear, 4) if spear is not None and pd.notna(spear) else None,
        "n": int(len(y_true)),
    }


def _fit_predict(train_df, val_df, test_df, objective, utils, *, augment: bool):
    tcol = utils["target_column"](objective)
    rng = np.random.default_rng(RANDOM_SEED)
    aug_flags = utils["AUG_FLAGS"]["cfb"]
    if augment:
        train = utils["build_augmented_train"](train_df, "cfb", aug_flags, rng)
    else:
        train = train_df.copy()
        train["sample_weight"] = train.get("data_quality_score", pd.Series(0.7, index=train.index)).fillna(0.7).clip(0.2, 1.0)

    X_train, feat_names = utils["feature_matrix"](train, objective)
    y_train = train[tcol].astype(float).values
    w_train = train["sample_weight"].astype(float).values
    X_val, _ = utils["feature_matrix"](val_df, objective, fixed_cols=feat_names)
    X_test, _ = utils["feature_matrix"](test_df, objective, fixed_cols=feat_names)

    model = GradientBoostingRegressor(
        n_estimators=120, max_depth=4, learning_rate=0.08, subsample=0.85, random_state=RANDOM_SEED
    )
    model.fit(X_train, y_train, sample_weight=w_train)
    return model, feat_names, {
        "validation": _metrics(val_df[tcol].astype(float).values, model.predict(X_val)),
        "test": _metrics(test_df[tcol].astype(float).values, model.predict(X_test)),
    }


def _temporal_stability(work, objective, utils):
    """Rolling-origin folds on chronological labeled rows."""
    tcol = utils["target_column"](objective)
    sort_col = "scraped_at" if "scraped_at" in work.columns else work.columns[0]
    work = work.sort_values(sort_col).reset_index(drop=True)
    n = len(work)
    folds = []
    for train_frac, val_frac in ((0.55, 0.15), (0.65, 0.15), (0.70, 0.15)):
        i1 = int(n * train_frac)
        i2 = int(n * (train_frac + val_frac))
        i3 = min(n, i2 + max(int(n * 0.15), 20))
        if i3 <= i2 or i1 < 30:
            continue
        train, val, test = work.iloc[:i1], work.iloc[i1:i2], work.iloc[i2:i3]
        _, _, m = _fit_predict(train, val, test, objective, utils, augment=True)
        folds.append({
            "train_frac": train_frac,
            "val_frac": val_frac,
            "train_n": len(train),
            "val_n": len(val),
            "test_n": len(test),
            **{f"val_{k}": v for k, v in m["validation"].items()},
            **{f"test_{k}": v for k, v in m["test"].items()},
        })
    return folds


def _label_coverage(df: pd.DataFrame) -> dict:
    out: dict = {"rows_total": len(df)}
    if "nil_valuation" not in df.columns:
        return out
    nil = pd.to_numeric(df["nil_valuation"], errors="coerce")
    out["nil_nonnull_imputed"] = int(nil.notna().sum())
    out["nil_positive_imputed"] = int((nil.fillna(0) > 0).sum())
    if "nil_valuation_observed" in df.columns:
        obs = df["nil_valuation_observed"] == 1
        out["nil_observed_positive"] = int((obs & (nil > 0)).sum())
        out["nil_observed_pct"] = round(100 * out["nil_observed_positive"] / max(len(df), 1), 2)
    else:
        out["nil_observed_positive"] = int((nil > 0).sum())
        out["nil_observed_pct"] = round(100 * out["nil_observed_positive"] / max(len(df), 1), 2)
    if "position" in df.columns:
        pos = df.assign(_nil=(nil > 0).astype(int)).groupby("position")["_nil"].agg(["sum", "count"])
        pos["coverage_pct"] = (100 * pos["sum"] / pos["count"]).round(1)
        out["nil_by_position_top"] = pos.sort_values("sum", ascending=False).head(10).to_dict("index")
    if "conference" in df.columns:
        conf = df.assign(_nil=(nil > 0).astype(int)).groupby("conference")["_nil"].agg(["sum", "count"])
        conf["coverage_pct"] = (100 * conf["sum"] / conf["count"]).round(1)
        out["nil_by_conference_top"] = conf.sort_values("sum", ascending=False).head(10).to_dict("index")
    if "scraped_at" in df.columns:
        ts = pd.to_datetime(df["scraped_at"], errors="coerce")
        labeled = df.assign(_nil=(nil > 0).astype(int), _month=ts.dt.to_period("M").astype(str))
        monthly = labeled.groupby("_month")["_nil"].agg(["sum", "count"])
        monthly["coverage_pct"] = (100 * monthly["sum"] / monthly["count"]).round(1)
        out["nil_monthly"] = monthly.tail(12).to_dict("index")
    return out


def _instagram_audit(df: pd.DataFrame) -> dict:
    if "instagram_followers" not in df.columns:
        return {"status": "missing_column"}
    ig = pd.to_numeric(df["instagram_followers"], errors="coerce")
    vc = ig.value_counts().head(5)
    top_val = float(vc.index[0]) if len(vc) else None
    top_frac = float(vc.iloc[0] / ig.notna().sum()) if len(vc) and ig.notna().any() else 0.0
    log_ig = np.log1p(ig.clip(lower=0))
    observed = None
    if "instagram_followers_observed" in df.columns:
        observed = int((df["instagram_followers_observed"] == 1).sum())
    handles = int(df["instagram_handle"].notna().sum()) if "instagram_handle" in df.columns else None
    return {
        "nonnull": int(ig.notna().sum()),
        "observed_mask_1": observed,
        "unique_values": int(ig.nunique()),
        "top_value": top_val,
        "top_value_frac": round(top_frac, 4),
        "median": float(ig.median()) if ig.notna().any() else None,
        "p95": float(ig.quantile(0.95)) if ig.notna().any() else None,
        "log_ig_unique": int(log_ig.nunique()),
        "log_ig_top_frac": round(float(log_ig.value_counts(normalize=True).iloc[0]), 4) if len(log_ig) else None,
        "handles_present": handles,
        "degenerate_for_proxy_ig": bool(log_ig.nunique() < 10 or top_frac > 0.6),
    }


def main() -> int:
    if not DATA_DIR.exists():
        print(json.dumps({"error": f"Missing data dir: {DATA_DIR}"}))
        return 1

    utils = _load_notebook_utils()
    cfg = utils["SPORT_CONFIG"]["cfb"]
    raw = utils["load_sport"]("cfb", cfg)
    raw = utils["flatten_raw_json"](raw)
    clean = utils["clean_dataframe"](raw, "cfb", cfg)
    imputed = utils["apply_imputation"](clean, "cfb")
    df = utils["extract_features"](imputed, "cfb")

    objective = "value_nil"
    tcol = utils["target_column"](objective)
    work = df[df[tcol].notna()].copy()
    sort_col = "scraped_at" if "scraped_at" in work.columns else work.columns[0]
    work = work.sort_values(sort_col)
    n = len(work)
    i1, i2 = int(n * 0.70), int(n * 0.85)
    train, val, test = work.iloc[:i1], work.iloc[i1:i2], work.iloc[i2:]

    model, feat_names, metrics_aug = _fit_predict(train, val, test, objective, utils, augment=True)
    _, _, metrics_no_aug = _fit_predict(train, val, test, objective, utils, augment=False)

    imp = sorted(
        zip(feat_names, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )[:25]

    report = {
        "data_dir": str(DATA_DIR),
        "labeled_rows": n,
        "split": {"train": len(train), "val": len(val), "test": len(test)},
        "metrics_with_augmentation": metrics_aug,
        "metrics_no_augmentation": metrics_no_aug,
        "augmentation_delta": {
            "val_mae": round(metrics_no_aug["validation"]["mae"] - metrics_aug["validation"]["mae"], 4),
            "test_mae": round(metrics_no_aug["test"]["mae"] - metrics_aug["test"]["mae"], 4),
            "test_spearman": round(metrics_aug["test"]["spearman"] - metrics_no_aug["test"]["spearman"], 4),
        },
        "top_features": [{"feature": f, "importance": round(float(w), 4)} for f, w in imp],
        "temporal_stability_folds": _temporal_stability(work, objective, utils),
        "label_coverage": _label_coverage(df),
        "instagram_audit": _instagram_audit(df),
        "value_proxy_ig_skip_reason": utils["train_objective"](df, "cfb", "value_proxy_ig", np.random.default_rng(RANDOM_SEED)).get("reason"),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
