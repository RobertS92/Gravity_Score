"""Load model promotion / beta-ranker policy from config."""

from __future__ import annotations

import json
import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_POLICY: dict[str, Any] = {
    "inference": {
        "allow_ml_quality_models": False,
        "quality_fallback": "heuristic_components",
        "beta_ranker_models": {},
    },
    "blocked_inference_models": {"pattern": "*_quality_v1", "reason": ""},
}


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


def is_blocked_inference_model(model_key: str) -> bool:
    policy = load_promotion_policy()
    blocked = policy.get("blocked_inference_models") or {}
    pattern = blocked.get("pattern")
    if not pattern:
        return False
    return fnmatch.fnmatch(model_key, pattern)


def production_gates(model_key: str) -> dict[str, Any]:
    policy = load_promotion_policy()
    return dict((policy.get("production_gates") or {}).get(model_key) or {})
