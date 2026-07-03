"""Load champion model bundles from local path or S3-synced directory."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModelBundle:
    def __init__(self, root: Path, model_key: str, version: str) -> None:
        self.root = root
        self.model_key = model_key
        self.version = version
        self.manifest = self._read_json("training_manifest.json", {})
        self.metrics = self._read_json("metrics.json", {})
        self.objective = self.manifest.get("objective", "value")
        self.sport = self.manifest.get("sport")
        self.entity_type = self.manifest.get("entity_type", "athlete")
        self._model = None
        self._vectorizer = None

    def _read_json(self, name: str, default: Any) -> Any:
        path = self.root / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def model_path(self) -> Path:
        for name in ("model.pkl", "model.joblib", "model.pt"):
            p = self.root / name
            if p.exists():
                return p
        raise FileNotFoundError(f"No model file in {self.root}")

    def load_model(self) -> Any:
        if self._model is not None:
            return self._model
        path = self.model_path
        if path.suffix == ".pt":
            import torch

            self._model = torch.jit.load(str(path), map_location="cpu")
            self._model.eval()
        elif path.suffix in (".pkl", ".joblib"):
            import pickle

            if path.suffix == ".joblib":
                try:
                    import joblib
                    self._model = joblib.load(path)
                except ImportError:
                    with path.open("rb") as fh:
                        self._model = pickle.load(fh)
            else:
                with path.open("rb") as fh:
                    self._model = pickle.load(fh)
        else:
            raise ValueError(f"Unsupported model format: {path.suffix}")
        logger.info("Loaded model %s/%s from %s", self.model_key, self.version, path)
        return self._model

    def load_vectorizer(self):
        if self._vectorizer is not None:
            return self._vectorizer
        from gravity_ml.inference.vectorizer import FeatureVectorizer

        manifest = self.root / "feature_manifest.json"
        if not manifest.exists():
            raise FileNotFoundError(f"Missing feature_manifest.json in {self.root}")
        self._vectorizer = FeatureVectorizer.from_manifest_path(manifest)
        return self._vectorizer


class BundleLoader:
    def __init__(self, bundle_root: str | None = None) -> None:
        root = bundle_root or os.environ.get("MODEL_BUNDLE_ROOT") or os.environ.get("MODEL_BUNDLE_PATH")
        self.bundle_root = Path(root) if root else None
        self._cache: dict[str, ModelBundle] = {}
        self._index: dict[str, str] = {}
        if self.bundle_root and self.bundle_root.exists():
            self._load_index()

    def _load_index(self) -> None:
        index_path = self.bundle_root / "index.json"
        if index_path.exists():
            data = json.loads(index_path.read_text(encoding="utf-8"))
            self._index = dict(data.get("champions") or {})
            return
        # Auto-discover champion dirs: {model_key}/{version}/
        if not self.bundle_root:
            return
        for model_dir in self.bundle_root.iterdir():
            if not model_dir.is_dir():
                continue
            versions = sorted(
                (v for v in model_dir.iterdir() if v.is_dir()),
                key=lambda p: p.name,
                reverse=True,
            )
            if versions:
                self._index[model_dir.name] = versions[0].name

    def resolve(self, model_key: str, version: str | None = None) -> ModelBundle | None:
        if not self.bundle_root or not self.bundle_root.exists():
            return None
        cache_key = f"{model_key}:{version or 'champion'}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        ver = version or self._index.get(model_key)
        if not ver:
            return None
        root = self.bundle_root / model_key / ver
        if not root.exists():
            return None
        bundle = ModelBundle(root, model_key, ver)
        from gravity_ml.inference.promotion_policy import bundle_inference_allowed

        if not bundle_inference_allowed(
            model_key,
            manifest=bundle.manifest,
            metrics=bundle.metrics,
        ):
            logger.warning(
                "Skipping non-promotable bundle %s/%s (synthetic or blocked)",
                model_key,
                ver,
            )
            return None
        self._cache[cache_key] = bundle
        return bundle

    def has_model(self, model_key: str) -> bool:
        return self.resolve(model_key) is not None


_loader: BundleLoader | None = None


def get_bundle_loader() -> BundleLoader:
    global _loader
    if _loader is None:
        _loader = BundleLoader()
    return _loader
