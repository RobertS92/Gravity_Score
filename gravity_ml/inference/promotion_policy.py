"""Load model promotion / beta-ranker policy from config.

SCORING_ML_FIX_SPEC §3 F5: refuse to load a bundle whose metrics.json does not
satisfy production_gates. Formula-label min_spearman gates are removed from
policy; circularity and outcome gates are required instead.
"""

from __future__ import annotations

import json
import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_POLICY: dict[str, Any] = {
    "inference": {
        "allow_ml_quality_models": False,
        "require_metrics_gates": True,
        "quality_fallback": "heuristic_components",
        "beta_ranker_models": {},
    },
    "blocked_inference_models": {"pattern": "*_quality_v1", "reason": ""},
    "production_gates": {},
}

# Boolean gate flags that must be present and true in metrics.json when listed
# under production_gates.required.
_BOOLEAN_GATE_KEYS = frozenset(
    {
        "game_margin_rmse_beats_team_baseline",
        "game_margin_rmse_delta_ci_excludes_zero",
        "next_season_winpct_beats_prior_winpct",
        "yoy_impact_rate_corr_beats_raw_box",
        "beats_v0_on_G_I1_and_G_I2",
        "ap_beats_best_baseline_ci_excludes_zero",
        "precision_at_50_beats_best_baseline",
        "attention_spearman_beats_reach_baselines",
        "unavail_auc_beats_transfer_history",
    }
)


def _policy_path() -> Path:
    here = Path(__file__).resolve()
    for base in (here.parents[1], here.parents[2]):
        candidate = base / "config" / "model_promotion_policy.json"
        if candidate.exists():
            return candidate
    return here.parents[1] / "config" / "model_promotion_policy.json"


@lru_cache(maxsize=1)
def load_promotion_policy() -> dict[str, Any]:
    path = _policy_path()
    if not path.exists():
        return dict(_DEFAULT_POLICY)
    return json.loads(path.read_text(encoding="utf-8"))


def clear_policy_cache() -> None:
    load_promotion_policy.cache_clear()


def beta_ranker_config(model_key: str) -> dict[str, Any] | None:
    policy = load_promotion_policy()
    cfg = (policy.get("inference") or {}).get("beta_ranker_models") or {}
    entry = cfg.get(model_key)
    return dict(entry) if isinstance(entry, dict) else None


def is_beta_ranker(model_key: str) -> bool:
    cfg = beta_ranker_config(model_key)
    return bool(cfg and cfg.get("output_mode") == "rank_only")


def allow_ml_quality_models() -> bool:
    policy = load_promotion_policy()
    return bool((policy.get("inference") or {}).get("allow_ml_quality_models", False))


def require_metrics_gates() -> bool:
    policy = load_promotion_policy()
    return bool((policy.get("inference") or {}).get("require_metrics_gates", True))


def is_blocked_inference_model(model_key: str) -> bool:
    policy = load_promotion_policy()
    blocked = policy.get("blocked_inference_models") or {}
    pattern = blocked.get("pattern")
    if not pattern:
        return False
    return fnmatch.fnmatch(model_key, pattern)


def production_gates(model_key: str) -> dict[str, Any]:
    policy = load_promotion_policy()
    gates = dict((policy.get("production_gates") or {}).get(model_key) or {})
    inherits = gates.get("inherits")
    if inherits:
        parent = dict((policy.get("production_gates") or {}).get(inherits) or {})
        merged = {**parent, **gates}
        # Child required overrides parent required keys.
        parent_req = dict(parent.get("required") or {})
        child_req = dict(gates.get("required") or {})
        merged["required"] = {**parent_req, **child_req}
        merged.pop("inherits", None)
        return merged
    return gates


def is_synthetic_training_manifest(manifest: dict[str, Any]) -> bool:
    """Detect bootstrap/synthetic bundles that must not serve inference."""
    if not manifest:
        return True
    source = str(manifest.get("training_source") or "").lower()
    if source in ("synthetic", "synthetic_bootstrap", "bootstrap"):
        return True
    row_count = int(manifest.get("row_count") or 0)
    if row_count == 200 and source != "observed_nil_valuation":
        return True
    return False


def _metric_value(metrics: dict[str, Any], key: str) -> Any:
    """Resolve a gate key from flat or nested metrics.json."""
    if key in metrics:
        return metrics[key]
    test = metrics.get("test") or {}
    if isinstance(test, dict) and key in test:
        return test[key]
    # Common aliases written by the eval harness / trainers.
    aliases = {
        "test_spearman_min": ("test_spearman", "spearman"),
        "test_mae_max": ("test_mae", "mae"),
        "test_rows_min": ("test_rows", "n_test", "n"),
        "labeled_rows_min": ("labeled_rows", "n_train", "row_count"),
        "circularity_holdout_r2_max": ("circularity_holdout_r2", "circularity_r2"),
        "calibration_ece_max": ("calibration_ece", "ece"),
        "verified_deals_min": ("verified_deals",),
        "test_positives_min": ("test_positives",),
        "test_games_min": ("test_games",),
    }
    for alt in aliases.get(key, ()):
        if alt in metrics:
            return metrics[alt]
        if isinstance(test, dict) and alt in test:
            return test[alt]
    nested = metrics.get("gates") or {}
    if isinstance(nested, dict) and key in nested:
        return nested[key]
    return None


def metrics_satisfy_gates(
    model_key: str,
    metrics: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    """Return (ok, failures) comparing metrics.json to production_gates.required."""
    gates = production_gates(model_key)
    required = gates.get("required") or {}
    if not required:
        return True, []
    if not metrics:
        return False, ["missing_metrics_json"]

    # Hard ban: training on formula / self-score labels.
    label_source = str(metrics.get("label_source") or metrics.get("training_source") or "")
    policy = load_promotion_policy()
    banned = set((policy.get("blocked_training_labels") or {}).get("sources") or [])
    banned |= set(gates.get("banned_label_sources") or [])
    if label_source and label_source in banned:
        return False, [f"banned_label_source:{label_source}"]

    failures: list[str] = []
    for key, threshold in required.items():
        actual = _metric_value(metrics, key)
        if key in _BOOLEAN_GATE_KEYS or (
            isinstance(threshold, bool) and not str(key).endswith("_max") and not str(key).endswith("_min")
        ):
            if actual is not True:
                failures.append(f"{key}: required true, got {actual!r}")
            continue
        if actual is None:
            failures.append(f"{key}: missing (required {threshold})")
            continue
        try:
            actual_f = float(actual)
            thresh_f = float(threshold)
        except (TypeError, ValueError):
            failures.append(f"{key}: non-numeric actual={actual!r} threshold={threshold!r}")
            continue
        if key.endswith("_max") or key.endswith("_ratio_max"):
            if actual_f > thresh_f:
                failures.append(f"{key}: {actual_f} > max {thresh_f}")
        else:
            # *_min and related lower bounds
            if actual_f < thresh_f:
                failures.append(f"{key}: {actual_f} < min {thresh_f}")
    return (len(failures) == 0), failures


def _is_v2_model_key(model_key: str) -> bool:
    return model_key.endswith("_v2") or "_impact_v2" in model_key or "_gravity_v2" in model_key


def bundle_inference_allowed(
    model_key: str,
    *,
    manifest: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> bool:
    """Return False for blocked patterns, synthetic bundles, or failed gates."""
    if is_blocked_inference_model(model_key):
        return False
    if manifest and is_synthetic_training_manifest(manifest):
        return False
    if metrics:
        source = str(metrics.get("training_source") or "").lower()
        if source in ("synthetic", "synthetic_bootstrap"):
            return False

    gates = production_gates(model_key)
    required = gates.get("required") or {}
    if not require_metrics_gates() or not required:
        return True

    # Outcome models (v2): metrics.json must fully satisfy required gates.
    if _is_v2_model_key(model_key):
        ok, _failures = metrics_satisfy_gates(model_key, metrics)
        return ok

    # Legacy keys: keep prior allow behavior, but refuse when provided metrics
    # fail any required threshold that is present (esp. circularity).
    if not metrics:
        return True
    for key, threshold in required.items():
        actual = _metric_value(metrics, key)
        if actual is None:
            continue
        if key in _BOOLEAN_GATE_KEYS or isinstance(threshold, bool):
            if actual is not True:
                return False
            continue
        try:
            actual_f = float(actual)
            thresh_f = float(threshold)
        except (TypeError, ValueError):
            return False
        if key.endswith("_max") or key.endswith("_ratio_max"):
            if actual_f > thresh_f:
                return False
        elif actual_f < thresh_f:
            return False
    return True
