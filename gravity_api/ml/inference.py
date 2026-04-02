import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from gravity_api.ml.features import FEATURE_ORDER, compute_confidence, engineer_features
from gravity_api.ml.model import COMPONENT_WEIGHTS, GravityNet, compute_gravity_score

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODEL_PATH = _MODEL_DIR / "gravity_net_v1.pt"
FEATURE_ORDER_PATH = _MODEL_DIR / "feature_order.json"

_model: Optional[GravityNet] = None
_feature_order: Optional[List[str]] = None


def load_model() -> None:
    global _model, _feature_order
    if MODEL_PATH.exists():
        checkpoint = torch.load(MODEL_PATH, map_location="cpu")
        input_dim = int(checkpoint.get("input_dim", 35))
        _model = GravityNet(input_dim=input_dim)
        _model.load_state_dict(checkpoint["model_state_dict"])
        _model.eval()
    else:
        _model = GravityNet(input_dim=35)
        _model.eval()

    if FEATURE_ORDER_PATH.exists():
        with open(FEATURE_ORDER_PATH, encoding="utf-8") as f:
            _feature_order = json.load(f)
    else:
        _feature_order = None


def score_athlete(athlete_data: Dict[str, Any]) -> Dict[str, Any]:
    global _model, _feature_order
    if _model is None:
        load_model()

    features = engineer_features(athlete_data)
    explain = {k: v for k, v in features.items() if not k.startswith("pad_")}
    confidence = compute_confidence(explain)

    order = _feature_order or FEATURE_ORDER
    in_dim = int(_model.feature_norm.num_features) if _model else 35
    feature_values = [features.get(k, 0.0) for k in order[:in_dim]]
    while len(feature_values) < in_dim:
        feature_values.append(0.0)
    feature_values = feature_values[:in_dim]

    x = torch.tensor([feature_values], dtype=torch.float32)

    assert _model is not None
    with torch.no_grad():
        outputs = _model(x)

    components = {k: round(float(v[0]) * 100, 1) for k, v in outputs.items()}
    gravity = compute_gravity_score(components)
    top_up, top_down = _compute_shap_attribution(explain, components)

    return {
        "gravity_score": gravity,
        "brand_score": components["brand"],
        "proof_score": components["proof"],
        "proximity_score": components["proximity"],
        "velocity_score": components["velocity"],
        "risk_score": components["risk"],
        "confidence": round(confidence, 3),
        "top_factors_up": top_up,
        "top_factors_down": top_down,
        "shap_values": explain,
    }


def _compute_shap_attribution(
    features: Dict[str, float], components: Dict[str, float]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    FEATURE_LABELS = {
        "log_ig_followers": "Instagram following",
        "log_tt_followers": "TikTok following",
        "ig_engagement_norm": "Instagram engagement rate",
        "tt_engagement_norm": "TikTok engagement rate",
        "log_news_mentions": "Media mentions",
        "primary_stat_norm": "Primary performance stat",
        "secondary_stat_norm": "Secondary performance stat",
        "conference_strength": "Conference strength",
        "recruiting_stars_norm": "Recruiting ranking",
        "market_size_norm": "Market size",
        "collective_budget_norm": "School NIL budget",
        "tv_exposure_norm": "TV exposure",
        "existing_deals_norm": "Existing NIL deal history",
        "social_growth_velocity": "Social following growth",
        "news_velocity_norm": "News momentum",
        "performance_trajectory": "Performance trend",
        "injury_risk_norm": "Injury history",
        "controversy_norm": "Controversy risk",
        "eligibility_remaining": "Eligibility remaining",
        "transfer_instability": "Transfer history",
    }

    weighted: Dict[str, float] = {}
    for feat, val in features.items():
        if feat in FEATURE_LABELS and val > 0:
            group = _feature_to_group(feat)
            weight = abs(COMPONENT_WEIGHTS.get(group, 0.1))
            weighted[feat] = val * weight

    sorted_feats = sorted(weighted.items(), key=lambda x: x[1], reverse=True)
    risk_feats = {"injury_risk_norm", "controversy_norm", "transfer_instability"}

    top_up = [
        {
            "factor": FEATURE_LABELS.get(k, k),
            "impact": round(v * 100, 1),
            "raw_value": round(features.get(k, 0), 3),
        }
        for k, v in sorted_feats[:5]
        if k not in risk_feats
    ]

    top_down = [
        {
            "factor": FEATURE_LABELS.get(k, k),
            "impact": round(v * 100, 1),
            "raw_value": round(features.get(k, 0), 3),
        }
        for k, v in sorted_feats
        if k in risk_feats and v > 0.1
    ][:3]

    return top_up, top_down


def _feature_to_group(feature: str) -> str:
    if any(w in feature for w in ["ig_", "tt_", "tw_", "yt_", "social", "news"]):
        return "brand"
    if any(w in feature for w in ["stat", "recruit", "conf", "award", "snap", "pff"]):
        return "proof"
    if any(w in feature for w in ["market", "collective", "tv_", "deal", "rev_share"]):
        return "proximity"
    if "velocity" in feature or "growth" in feature or "trajectory" in feature:
        return "velocity"
    return "risk"
