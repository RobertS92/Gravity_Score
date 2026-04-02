"""Gravity MLP: 250 → 512 → 256 → 128 → 64 → 1 (sigmoid × 100)."""

from __future__ import annotations

import torch
import torch.nn as nn

from gravity.ml.feature_engineer import N_FEATURE_COLUMNS


class GravityNet(nn.Module):
    def __init__(self, in_dim: int = N_FEATURE_COLUMNS) -> None:
        super().__init__()
        self.in_dim = in_dim
        self.blocks = nn.Sequential(
            nn.Linear(in_dim, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.blocks(x) * 100.0


__all__ = ["GravityNet"]
