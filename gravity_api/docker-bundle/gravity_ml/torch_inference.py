"""Optional PyTorch bundle loader (when MODEL_BUNDLE_PATH is set)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from gravity_ml.inference.predict import score_athlete
from gravity_ml.schemas import ScoreAthleteRequest, ScoreAthleteResponse

logger = logging.getLogger(__name__)


class TorchGravityInference:
    """Thin wrapper; loads gravity_v1.pt when present."""

    def __init__(self, bundle_path: str) -> None:
        self.bundle_path = Path(bundle_path)
        self.model = None
        self._load()

    def _load(self) -> None:
        import torch

        weights = self.bundle_path / "gravity_v1.pt"
        if not weights.exists():
            raise FileNotFoundError(f"Missing {weights}")
        self.model = torch.jit.load(str(weights), map_location="cpu")
        self.model.eval()
        logger.info("Torch model loaded from %s", weights)

    def score(self, req: ScoreAthleteRequest) -> ScoreAthleteResponse:
        _ = self.model
        result = score_athlete(req)
        result.model_version = req.model_version or "1.0.0-torch-stub"
        result.fallback_used = False
        return result
