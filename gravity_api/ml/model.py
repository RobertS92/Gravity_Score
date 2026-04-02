from typing import Dict

import torch
import torch.nn as nn


class GravityNet(nn.Module):
    """Neural net for college athlete commercial valuation (5 heads)."""

    def __init__(self, input_dim: int = 35, dropout: float = 0.3):
        super().__init__()
        self.feature_norm = nn.BatchNorm1d(input_dim)

        self.shared = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
        )

        self.brand_head = nn.Sequential(
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid()
        )
        self.proof_head = nn.Sequential(
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid()
        )
        self.proximity_head = nn.Sequential(
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid()
        )
        self.velocity_head = nn.Sequential(
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid()
        )
        self.risk_head = nn.Sequential(
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor):
        x = self.feature_norm(x)
        shared = self.shared(x)
        return {
            "brand": self.brand_head(shared).squeeze(-1),
            "proof": self.proof_head(shared).squeeze(-1),
            "proximity": self.proximity_head(shared).squeeze(-1),
            "velocity": self.velocity_head(shared).squeeze(-1),
            "risk": self.risk_head(shared).squeeze(-1),
        }


COMPONENT_WEIGHTS = {
    "brand": 0.30,
    "proof": 0.25,
    "proximity": 0.20,
    "velocity": 0.15,
    "risk": -0.10,
}


def compute_gravity_score(components: Dict[str, float]) -> float:
    raw = sum(
        components[k] * w for k, w in COMPONENT_WEIGHTS.items() if k != "risk"
    ) - components["risk"] * abs(COMPONENT_WEIGHTS["risk"])

    min_possible = 0 - abs(COMPONENT_WEIGHTS["risk"])
    max_possible = sum(w for k, w in COMPONENT_WEIGHTS.items() if k != "risk")
    normalized = (raw - min_possible) / (max_possible - min_possible)
    return round(float(normalized) * 100, 1)
