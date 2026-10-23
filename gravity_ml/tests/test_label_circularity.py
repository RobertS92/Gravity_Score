"""F3 — circularity CI gate (would have caught M1, M3, M4)."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

from gravity_ml.eval.circularity import assert_not_circular, circularity_holdout_r2
from gravity_ml.features.manifest import allowed_features
from gravity_ml.labels.registry import list_labels


CIRCULARITY_R2_MAX = 0.95


def _fit_holdout_r2(X: np.ndarray, y: np.ndarray, seed: int = 0) -> float:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed
    )
    model = HistGradientBoostingRegressor(
        max_depth=4, max_iter=80, learning_rate=0.08, random_state=seed
    )
    model.fit(X_train, y_train)
    return float(r2_score(y_test, model.predict(X_test)))


def test_m1_style_formula_label_fails_circularity_gate():
    """M1: label = weighted sum of the same inputs → R² ≈ 1."""
    rng = np.random.default_rng(1)
    n, p = 800, 6
    X = rng.uniform(0, 100, size=(n, p))
    # raw_composite_score-style hand formula over features (exact, noiseless).
    weights = np.array([0.28, 0.22, 0.20, 0.12, 0.10, 0.08])
    y = X @ weights
    r2 = circularity_holdout_r2(X, y, max_iter=200)
    assert r2 >= CIRCULARITY_R2_MAX
    with pytest.raises(AssertionError, match="Circularity gate failed"):
        assert_not_circular(X, y, label="M1_raw_composite", max_iter=200)


def test_m3_style_self_score_prior_fails_circularity_gate():
    """M3: target ≈ gravity_score_prior / dollar prior present as a feature."""
    rng = np.random.default_rng(2)
    n = 400
    gravity_prior = rng.uniform(20, 90, size=n)
    noise_feats = rng.normal(size=(n, 5))
    X = np.column_stack([gravity_prior, noise_feats])
    y = gravity_prior + rng.normal(0, 0.2, size=n)  # near-copy of prior
    r2 = circularity_holdout_r2(X, y)
    assert r2 >= CIRCULARITY_R2_MAX


def test_m4_style_impact_formula_fails_circularity_gate():
    """M4: target_impact_score = 0.72·proof + 0.14·avail + …"""
    rng = np.random.default_rng(3)
    n = 400
    proof = rng.uniform(0, 100, size=n)
    availability = rng.uniform(0, 100, size=n)
    starter = rng.uniform(0, 100, size=n)
    team = rng.uniform(0, 100, size=n)
    X = np.column_stack([proof, availability, starter, team, rng.normal(size=(n, 3))])
    y = 0.72 * proof + 0.14 * availability + 0.08 * starter + 0.06 * team
    assert _fit_holdout_r2(X, y) >= CIRCULARITY_R2_MAX


@pytest.mark.parametrize("objective", ["gravity", "impact"])
def test_registered_objectives_pass_circularity_on_outcome_fixture(objective: str):
    """Outcome-style labels must not be a near-copy of the feature set."""
    feature_set = "gravity_v1" if objective == "gravity" else "impact_v1"
    cols = allowed_features(feature_set)
    rng = np.random.default_rng(10 + len(objective))
    n = 300
    X = rng.normal(size=(n, len(cols)))
    # Binary-ish market / margin outcome largely independent of X.
    y = (rng.normal(size=n) > 0.3).astype(float) * 10.0 + rng.normal(0, 3.0, size=n)
    r2 = assert_not_circular(X, y, label=objective, max_r2=CIRCULARITY_R2_MAX)
    assert r2 < CIRCULARITY_R2_MAX
    # Ensure we actually have labels registered for the objective.
    assert list_labels(objective=objective)
