"""Shared promotion gate wiring for train scripts (SCORING_ML_FIX_SPEC F5 / §4 / §5).

Trainers call ``assert_bundle_promotable`` before writing champions/index.json.
Formula / self-score label sources are always refused.
"""

from __future__ import annotations

from typing import Any

from gravity_ml.inference.promotion_policy import (
    load_promotion_policy,
    metrics_satisfy_gates,
)
from gravity_ml.labels.registry import BANNED_LABEL_SOURCES


class PromotionRefused(RuntimeError):
    """Bundle must not be loaded or written to champions."""


def banned_training_label_sources() -> frozenset[str]:
    policy = load_promotion_policy()
    blocked = set((policy.get("blocked_training_labels") or {}).get("sources") or [])
    return frozenset(blocked | set(BANNED_LABEL_SOURCES))


def assert_label_source_allowed(label_source: str | None) -> None:
    if not label_source:
        raise PromotionRefused("missing label_source in metrics/training manifest")
    banned = banned_training_label_sources()
    if label_source in banned:
        raise PromotionRefused(
            f"banned training label_source={label_source!r}; "
            f"banned={sorted(banned)}"
        )


def assert_bundle_promotable(
    model_key: str,
    metrics: dict[str, Any] | None,
    *,
    label_source: str | None = None,
) -> None:
    """Raise PromotionRefused if metrics fail production_gates or label is banned."""
    src = label_source or (metrics or {}).get("label_source") or (metrics or {}).get(
        "training_source"
    )
    if src:
        assert_label_source_allowed(str(src))
    ok, failures = metrics_satisfy_gates(model_key, metrics)
    if not ok:
        raise PromotionRefused(
            f"promotion gates failed for {model_key}: " + "; ".join(failures)
        )


def write_metrics_with_lineage(
    metrics: dict[str, Any],
    *,
    label_source: str,
    model_key: str,
) -> dict[str, Any]:
    """Stamp label lineage onto metrics.json payload before save."""
    out = dict(metrics)
    out["label_source"] = label_source
    out["model_key"] = model_key
    assert_label_source_allowed(label_source)
    return out


__all__ = [
    "PromotionRefused",
    "assert_bundle_promotable",
    "assert_label_source_allowed",
    "banned_training_label_sources",
    "write_metrics_with_lineage",
]
