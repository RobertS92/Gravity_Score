"""Precision-weighted fusion of prior + observation (SCORING_ML_FIX_SPEC §4 I5).

Skeleton operates on arrays/Series for unit tests; live season writes wait on WP10.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FusedImpact:
    posterior_mean: pd.Series
    posterior_se: pd.Series
    impact_wins_added: pd.Series | None = None
    impact_score: pd.Series | None = None
    impact_status: pd.Series | None = None


def precision_weighted_fuse(
    prior_mean: pd.Series,
    prior_sd: pd.Series,
    obs_mean: pd.Series,
    obs_sd: pd.Series,
) -> FusedImpact:
    """Posterior = (prior/σp² + obs/σo²) / (1/σp² + 1/σo²). No hand floors."""
    idx = prior_mean.index.union(obs_mean.index)
    pm = prior_mean.reindex(idx).astype(float)
    ps = prior_sd.reindex(idx).astype(float).clip(lower=1e-6)
    om = obs_mean.reindex(idx).astype(float)
    os_ = obs_sd.reindex(idx).astype(float).clip(lower=1e-6)

    # Where observation missing, keep prior; where prior missing, keep obs.
    w_p = 1.0 / (ps**2)
    w_o = 1.0 / (os_**2)
    both = pm.notna() & om.notna()
    post = pd.Series(index=idx, dtype=float)
    post_se = pd.Series(index=idx, dtype=float)
    post.loc[both] = (pm[both] * w_p[both] + om[both] * w_o[both]) / (w_p[both] + w_o[both])
    post_se.loc[both] = np.sqrt(1.0 / (w_p[both] + w_o[both]))
    prior_only = pm.notna() & om.isna()
    post.loc[prior_only] = pm[prior_only]
    post_se.loc[prior_only] = ps[prior_only]
    obs_only = om.notna() & pm.isna()
    post.loc[obs_only] = om[obs_only]
    post_se.loc[obs_only] = os_[obs_only]
    return FusedImpact(posterior_mean=post, posterior_se=post_se)


def impact_score_percentile(
    wins_added: pd.Series,
    *,
    min_participation_mask: pd.Series,
    replacement_percentile: float = 0.20,
) -> tuple[pd.Series, pd.Series]:
    """Map wins-added to 0–100 within cohort; below min participation → NULL / insufficient_sample."""
    eligible = wins_added.loc[min_participation_mask.fillna(False)]
    scores = pd.Series(index=wins_added.index, dtype=float)
    status = pd.Series("insufficient_sample", index=wins_added.index, dtype=object)
    if eligible.empty:
        return scores, status
    # Percentile among eligible only.
    ranks = eligible.rank(pct=True) * 100.0
    scores.loc[eligible.index] = ranks
    status.loc[eligible.index] = "ok"
    _ = replacement_percentile  # documented tunable; applied by caller when computing wins_added
    return scores, status


__all__ = ["FusedImpact", "impact_score_percentile", "precision_weighted_fuse"]
