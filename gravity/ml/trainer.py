"""
Train GravityNet with MSE on composite labels, early stopping, optional CV.
Train/test split by ``class_year`` buckets (not random rows).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import KFold
from torch.utils.data import DataLoader, TensorDataset

from gravity.ml.feature_engineer import (
    CohortStats,
    N_FEATURE_COLUMNS,
    build_cohort_stats,
    engineer_dataframe,
)
from gravity.ml.network import GravityNet
from gravity.ml.normalizer import GravityNormalizer
from gravity.ml.training_labels import raw_composite_score

logger = logging.getLogger(__name__)


def _class_year_split_mask(
    df: pd.DataFrame, test_fraction: float = 0.2, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """Return train_bool, test_bool masks; whole class_year values go to one side."""
    cy = df.get("class_year")
    if cy is None:
        n = len(df)
        rng = np.random.RandomState(seed)
        idx = np.arange(n)
        rng.shuffle(idx)
        cut = int(n * (1 - test_fraction))
        train = np.zeros(n, dtype=bool)
        test = np.zeros(n, dtype=bool)
        train[idx[:cut]] = True
        test[idx[cut:]] = True
        return train, test

    labels = cy.fillna("unknown").astype(str).values
    uniq = np.unique(labels)
    rng = np.random.RandomState(seed)
    rng.shuffle(uniq)
    n_test_classes = max(1, int(len(uniq) * test_fraction))
    test_set = set(uniq[:n_test_classes])
    test_mask = np.array([str(x) in test_set for x in labels], dtype=bool)
    train_mask = ~test_mask
    return train_mask, test_mask


def train_one_fold(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 200,
    patience: int = 15,
    batch_size: int = 64,
    lr: float = 1e-3,
    device: str = "cpu",
) -> tuple[GravityNet, dict[str, Any]]:
    model = GravityNet(N_FEATURE_COLUMNS).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    Xt = torch.tensor(X_train, dtype=torch.float32, device=device)
    yt = torch.tensor(y_train, dtype=torch.float32, device=device).view(-1, 1)
    ds = TensorDataset(Xt, yt)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True)

    Xv = torch.tensor(X_val, dtype=torch.float32, device=device)
    yv = torch.tensor(y_val, dtype=torch.float32, device=device).view(-1, 1)

    best_val = float("inf")
    best_state: dict[str, Any] | None = None
    bad_epochs = 0

    for ep in range(epochs):
        model.train()
        for xb, yb in dl:
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()

        model.eval()
        with torch.no_grad():
            pv = model(Xv)
            vloss = float(loss_fn(pv, yv).item())

        if vloss < best_val - 1e-6:
            best_val = vloss
            bad_epochs = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                logger.info("Early stop epoch %s val_loss=%.6f", ep + 1, best_val)
                break

    if best_state:
        model.load_state_dict(best_state)

    history_tail = {"best_val_mse": best_val}
    return model, history_tail


def _labels_scaled(
    rows: list[dict[str, Any]], lo: float, hi: float
) -> np.ndarray:
    out = []
    for r in rows:
        v = raw_composite_score(r)
        if hi - lo < 1e-9:
            out.append(50.0)
        else:
            out.append(float(max(0.0, min(100.0, (v - lo) / (hi - lo) * 100.0))))
    return np.asarray(out, dtype=np.float32).reshape(-1, 1)


def train_from_dataframe(
    df: pd.DataFrame,
    output_dir: Path,
    cv_folds: int = 0,
    epochs: int = 200,
    seed: int = 42,
    device: str | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    train_m, test_m = _class_year_split_mask(df, test_fraction=0.2, seed=seed)
    train_df = df[train_m].reset_index(drop=True)
    test_df = df[test_m].reset_index(drop=True)

    y_train_raw = np.array([raw_composite_score(r) for r in train_df.to_dict("records")])
    lo, hi = float(y_train_raw.min()), float(y_train_raw.max())

    cohort: CohortStats = build_cohort_stats(train_df.to_dict("records"))
    X_train = engineer_dataframe(train_df, cohort)
    X_test = engineer_dataframe(test_df, cohort)

    normalizer = GravityNormalizer()
    X_tr = normalizer.fit_transform(X_train)
    X_te = normalizer.transform(X_test)

    y_tr = _labels_scaled(train_df.to_dict("records"), lo, hi)
    y_te = _labels_scaled(test_df.to_dict("records"), lo, hi)

    if cv_folds and cv_folds > 1:
        # CV on training portion only (by row chunks)
        kf = KFold(n_splits=cv_folds, shuffle=True, random_state=seed)
        cv_losses: list[float] = []
        for fold, (fit_idx, val_idx) in enumerate(kf.split(X_tr)):
            model, h = train_one_fold(
                X_tr[fit_idx],
                y_tr[fit_idx],
                X_tr[val_idx],
                y_tr[val_idx],
                epochs=epochs,
                device=device,
            )
            cv_losses.append(h["best_val_mse"])
            logger.info("CV fold %s val MSE %.6f", fold, h["best_val_mse"])
        logger.info("CV mean MSE %.6f", float(np.mean(cv_losses)))

    model, _ = train_one_fold(
        X_tr, y_tr, X_te, y_te, epochs=epochs, device=device
    )
    model.eval()
    with torch.no_grad():
        Xte_t = torch.tensor(X_te, dtype=torch.float32, device=device)
        preds = model(Xte_t).cpu().numpy().ravel()
        test_mse = float(np.mean((preds - y_te.ravel()) ** 2))

    meta = {
        "n_rows": len(df),
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "test_mse": test_mse,
        "label_raw_lo": lo,
        "label_raw_hi": hi,
        "device": device,
    }

    torch.save(
        {
            "state_dict": model.state_dict(),
            "in_dim": N_FEATURE_COLUMNS,
            "meta": meta,
        },
        output_dir / "gravity_v1.pt",
    )
    normalizer.save(output_dir / "normalizer_v1.pkl")
    joblib.dump(cohort, output_dir / "cohort_v1.pkl")
    (output_dir / "training_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    logger.info("Saved bundle to %s test_mse=%.6f", output_dir, test_mse)
    return meta


def load_training_table(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return pd.DataFrame(raw)
        raise ValueError("JSON must be a list of objects")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported format {path.suffix}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Train Gravity Stage-1 MLP")
    ap.add_argument("data", type=Path, help="CSV or JSON list of scraper rows")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("gravity/models"),
        help="Directory for gravity_v1.pt, normalizer_v1.pkl, cohort_v1.pkl",
    )
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--cv", type=int, default=0, help="If >1, run K-fold on train split")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = load_training_table(args.data)
    if "sport" not in df.columns:
        df["sport"] = "cfb"

    train_from_dataframe(df, args.out, cv_folds=args.cv, epochs=args.epochs, seed=args.seed)


if __name__ == "__main__":
    main()
