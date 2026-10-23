"""F2 — label registry lineage + banned sources."""

from __future__ import annotations

from datetime import timedelta

import pytest

from gravity_ml.features.manifest import assert_features_allowed, is_banned_feature
from gravity_ml.inference.vectorizer import build_feature_manifest
from gravity_ml.labels.registry import (
    BANNED_LABEL_SOURCES,
    LabelSpec,
    list_labels,
    register_label,
    validate_registry,
)


def _noop_builder(*_a, **_k):
    raise NotImplementedError


def test_registered_labels_pass_banned_source_check():
    validate_registry()
    names = {s.name for s in list_labels()}
    assert "L_deal_180" in names
    assert "L_game_margin" in names
    assert "athlete_gravity_scores" in BANNED_LABEL_SOURCES


def test_banned_source_rejected_at_registration():
    with pytest.raises(ValueError, match="banned"):
        register_label(
            LabelSpec(
                name="L_bad_self_score",
                source_tables=("athlete_gravity_scores",),
                horizon=timedelta(days=1),
                builder=_noop_builder,
                objective="gravity",
            ),
            overwrite=True,
        )


def test_formula_helpers_are_banned_sources():
    for src in (
        "raw_composite_score",
        "component_proxy_raw",
        "compute_win_impact_score_v0",
    ):
        with pytest.raises(ValueError, match="banned"):
            register_label(
                LabelSpec(
                    name=f"L_bad_{src}",
                    source_tables=(src,),
                    horizon=None,
                    builder=_noop_builder,
                ),
                overwrite=True,
            )


def test_validate_registry_fails_on_injected_banned_spec():
    bad = LabelSpec(
        name="L_injected",
        source_tables=("athlete_gravity_scores",),
        horizon=None,
        builder=_noop_builder,
    )
    # Bypass register_label's assert to simulate a corrupt registry entry.
    with pytest.raises(AssertionError, match="Banned label sources"):
        validate_registry([bad])


def test_banned_features_stripped_from_manifests():
    for objective in ("value", "impact", "quality", "gravity"):
        keys = build_feature_manifest(objective, sport="cfb")
        for banned in (
            "gravity_score_prior",
            "proof_score_prior",
            "quality_score_prior",
            "dollar_p50_usd",
            "win_impact_score",
            "target_impact_score",
            "proof_composite_pctile",
        ):
            assert banned not in keys
            assert is_banned_feature(banned)


def test_assert_features_allowed_raises():
    with pytest.raises(ValueError, match="Banned features"):
        assert_features_allowed(["instagram_followers", "gravity_score_prior"])
