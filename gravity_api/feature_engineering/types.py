"""Types for BPXVR feature engineering (profile cards, cohorts, trajectories)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class TrajectoryClass(str, Enum):
    ASCENDING = "ascending"
    IMPROVING = "improving"
    IMPROVING_STABLE = "improving_stable"
    IMPROVING_UNSTABLE = "improving_unstable"
    STABLE = "stable"
    DECLINING = "declining"
    DECLINING_FROM_ELITE = "declining_from_elite"
    DESCENDING = "descending"
    UNSTABLE = "unstable"
    BREAKOUT = "breakout"
    INSUFFICIENT_DATA = "insufficient_data"
    WORSENING = "worsening"
    ON_FIELD_UP_OFF_FIELD_FLAT = "on_field_up_off_field_flat"
    LATE_BLOOMER = "late_bloomer"


class TierLabel(str, Enum):
    GENERATIONAL = "generational"
    ELITE = "elite"
    HIGH = "high"
    UPPER_MID = "upper_mid"
    MID = "mid"
    LOWER_MID = "lower_mid"
    LOW = "low"
    UNKNOWN = "unknown"


class CohortConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


StatDirection = Literal["higher", "lower"]


@dataclass(frozen=True)
class StatWeight:
    stat_key: str
    weight: float
    direction: StatDirection = "higher"


@dataclass(frozen=True)
class MetricProfileSpec:
    """Blueprint for profile-card extraction on a single metric."""

    metric_key: str
    component: Literal["brand", "proof", "proximity", "velocity", "risk", "identity"]
    level_raw_key: str | None = None
    yoy: bool = True
    deltas: tuple[str, ...] = ("7d", "30d", "90d")
    trajectory: bool = True
    invert_for_risk: bool = False
    log_transform: bool = False
    mask_below_confidence: float = 0.0


@dataclass(frozen=True)
class PositionProofSpec:
    position_group: str
    aliases: tuple[str, ...]
    performance_stats: tuple[StatWeight, ...]
    expected_games: int = 1
    recruiting_stats: tuple[str, ...] = ()
    achievement_weights: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SportFeatureSpec:
    sport: str
    league: str
    display_name: str
    terminal_visible: bool
    position_groups: tuple[PositionProofSpec, ...]
    brand_metrics: tuple[MetricProfileSpec, ...]
    proximity_metrics: tuple[MetricProfileSpec, ...]
    velocity_metrics: tuple[MetricProfileSpec, ...]
    risk_metrics: tuple[MetricProfileSpec, ...]
    platform_weights: dict[str, float] = field(default_factory=dict)
    min_games_for_proof_pctile: int = 4
    college_pro_bridge: bool = False


@dataclass
class CohortBaseline:
    league: str
    sport: str
    position_group: str
    season_year: int | None
    window_key: str
    metric_key: str
    cohort_level: str
    n: int
    mean: float | None
    std: float | None
    p50: float | None
    p75: float | None
    p80: float | None
    p90: float | None
    p95: float | None
    p99: float | None


@dataclass
class ProfileCard:
    metric_key: str
    level_raw: float | None = None
    level_pctile: float | None = None
    level_tier: TierLabel = TierLabel.UNKNOWN
    delta_yoy_pct: float | None = None
    delta_7d_pct: float | None = None
    delta_30d_pct: float | None = None
    delta_90d_pct: float | None = None
    yoy_percentile_change: float | None = None
    trajectory_class: TrajectoryClass = TrajectoryClass.INSUFFICIENT_DATA
    stability_score: float | None = None
    cohort_confidence: CohortConfidence = CohortConfidence.LOW
    masked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_key": self.metric_key,
            "level_raw": self.level_raw,
            "level_pctile": self.level_pctile,
            "level_tier": self.level_tier.value,
            "delta_yoy_pct": self.delta_yoy_pct,
            "delta_7d_pct": self.delta_7d_pct,
            "delta_30d_pct": self.delta_30d_pct,
            "delta_90d_pct": self.delta_90d_pct,
            "yoy_percentile_change": self.yoy_percentile_change,
            "trajectory_class": self.trajectory_class.value,
            "stability_score": self.stability_score,
            "cohort_confidence": self.cohort_confidence.value,
            "masked": self.masked,
        }


@dataclass
class ComponentFeatureBlock:
    component: str
    profile_cards: dict[str, ProfileCard] = field(default_factory=dict)
    composite_index: float | None = None
    composite_pctile: float | None = None
    composite_tier: TierLabel = TierLabel.UNKNOWN
    trajectory_class: TrajectoryClass = TrajectoryClass.INSUFFICIENT_DATA
    volatility_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "composite_index": self.composite_index,
            "composite_pctile": self.composite_pctile,
            "composite_tier": self.composite_tier.value,
            "trajectory_class": self.trajectory_class.value,
            "volatility_score": self.volatility_score,
            "metrics": {k: v.to_dict() for k, v in self.profile_cards.items()},
        }


@dataclass
class AthleteFeatureSnapshot:
    entity_id: str
    sport: str
    league: str
    position_group: str
    season_year: int
    cohort_key: str
    as_of: str
    brand: ComponentFeatureBlock
    proof: ComponentFeatureBlock
    proximity: ComponentFeatureBlock
    velocity: ComponentFeatureBlock
    risk: ComponentFeatureBlock
    college_proof: dict[str, Any] | None = None
    missingness: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "entity": {
                "sport": self.sport,
                "league": self.league,
                "position_group": self.position_group,
                "season_year": self.season_year,
                "cohort_key": self.cohort_key,
            },
            "as_of": self.as_of,
            "brand": self.brand.to_dict(),
            "proof": self.proof.to_dict(),
            "proximity": self.proximity.to_dict(),
            "velocity": self.velocity.to_dict(),
            "risk": self.risk.to_dict(),
            "missingness": self.missingness,
        }
        if self.college_proof:
            out["college_proof"] = self.college_proof
        return out
