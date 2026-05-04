"""Train the LSTM load forecaster, log to MLflow, register a new version.

Run standalone (`python -m lstm.train`) or via APScheduler (lstm.scheduler).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import pickle
import tempfile
from typing import Any

import mlflow
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from config import (
    LSTM_BATCH,
    LSTM_LR,
    LSTM_MAX_EPOCHS,
    LSTM_PATIENCE,
    LSTM_REGISTRY_NAME,
    LSTM_TRAIN_DAYS,
    ZONES,
)
from lstm.features import training_dataset
from lstm.model import LoadForecastLSTM, build_optimizer_scheduler, huber_loss
from shared import mlflow_client

log = logging.getLogger("gridmind.lstm.train")


def _split_chronological(X, Z, Y, *, train_frac: float = 0.8):
    n = X.shape[0]
    cut = int(n * train_frac)
    return (X[:cut], Z[:cut], Y[:cut]), (X[cut:], Z[cut:], Y[cut:])


def _per_zone_metrics(model: torch.nn.Module, X, Z, Y, device) -> dict[str, dict[str, float]]:
    model.eval()
    with torch.no_grad():
        pred = model(X.to(device), Z.to(device)).cpu().numpy()
    y = Y.numpy()
    z = Z.numpy()
    out: dict[str, dict[str, float]] = {}
    for idx, zone_id in enumerate(ZONES):
        mask = z == idx
        if not mask.any():
            continue
        diff = pred[mask] - y[mask]
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        mae = float(np.mean(np.abs(diff)))
        out[zone_id] = {"rmse": rmse, "mae": mae}
    return out


async def run() -> dict[str, Any]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info("training device=%s", device)

    X, Z, Y, scaler = await training_dataset(days=LSTM_TRAIN_DAYS)
    (Xtr, Ztr, Ytr), (Xva, Zva, Yva) = _split_chronological(X, Z, Y)
    log.info("samples train=%d val=%d", Xtr.shape[0], Xva.shape[0])

    train_loader = DataLoader(TensorDataset(Xtr, Ztr, Ytr), batch_size=LSTM_BATCH, shuffle=True)
    val_loader = DataLoader(TensorDataset(Xva, Zva, Yva), batch_size=LSTM_BATCH)

    model = LoadForecastLSTM().to(device)
    optim, lr_sched = build_optimizer_scheduler(model, LSTM_LR)
    loss_fn = huber_loss()

    best_val = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    patience = 0

    with mlflow_client.start_run(experiment="gridmind-lstm-load-forecast") as run_:
        mlflow_client.log_params({
            "seq_len": Xtr.shape[1], "horizon": Ytr.shape[1], "batch": LSTM_BATCH,
            "lr": LSTM_LR, "patience": LSTM_PATIENCE, "max_epochs": LSTM_MAX_EPOCHS,
            "n_train": Xtr.shape[0], "n_val": Xva.shape[0],
        })
        for epoch in range(LSTM_MAX_EPOCHS):
            model.train()
            tr_loss_sum = 0.0
            for xb, zb, yb in train_loader:
                xb, zb, yb = xb.to(device), zb.to(device), yb.to(device)
                optim.zero_grad()
                pred = model(xb, zb)
                loss = loss_fn(pred, yb)
                loss.backward()
                optim.step()
                tr_loss_sum += float(loss.item()) * xb.size(0)
            train_loss = tr_loss_sum / max(1, len(train_loader.dataset))

            model.eval()
            val_loss_sum = 0.0
            with torch.no_grad():
                for xb, zb, yb in val_loader:
                    xb, zb, yb = xb.to(device), zb.to(device), yb.to(device)
                    pred = model(xb, zb)
                    val_loss_sum += float(loss_fn(pred, yb).item()) * xb.size(0)
            val_loss = val_loss_sum / max(1, len(val_loader.dataset))
            lr_sched.step(val_loss)

            mlflow_client.log_metrics({"train_loss": train_loss, "val_loss": val_loss}, step=epoch)
            log.info("epoch=%d train=%.4f val=%.4f", epoch, train_loss, val_loss)

            if val_loss < best_val - 1e-4:
                best_val = val_loss
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
                patience = 0
            else:
                patience += 1
                if patience >= LSTM_PATIENCE:
                    log.info("early stop epoch=%d", epoch)
                    break

        if best_state is not None:
            model.load_state_dict(best_state)

        # Per-zone validation metrics
        per_zone = _per_zone_metrics(model, Xva, Zva, Yva, device)
        for zone_id, m in per_zone.items():
            mlflow_client.log_metrics(
                {f"rmse_{zone_id}": m["rmse"], f"mae_{zone_id}": m["mae"]},
            )
        all_rmse = float(np.mean([m["rmse"] for m in per_zone.values()] or [0.0]))
        residuals = []
        with torch.no_grad():
            pred = model(Xva.to(device), Zva.to(device)).cpu().numpy()
            residuals = (pred - Yva.numpy()).reshape(-1)
        residual_std = float(np.std(residuals)) if residuals.size else 1.0
        mlflow_client.log_metrics({"rmse_overall": all_rmse, "residual_std": residual_std})

        # Persist scaler + metadata as artifacts
        with tempfile.TemporaryDirectory() as tmp:
            scaler_path = os.path.join(tmp, "scaler.pkl")
            with open(scaler_path, "wb") as f:
                pickle.dump(scaler, f)
            mlflow_client.log_artifact(scaler_path)
            meta_path = os.path.join(tmp, "metadata.json")
            with open(meta_path, "w") as f:
                json.dump({
                    "rmse_overall": all_rmse,
                    "residual_std": residual_std,
                    "per_zone": per_zone,
                }, f)
            mlflow_client.log_artifact(meta_path)

        # Register the model
        model_uri = mlflow_client.register_pytorch(model.cpu(), LSTM_REGISTRY_NAME)
        log.info("registered model uri=%s", model_uri)

        # Promote to Production
        latest = mlflow_client.latest_any_version(LSTM_REGISTRY_NAME)
        if latest:
            mlflow_client.transition_to_production(LSTM_REGISTRY_NAME, latest)

        return {
            "run_id": run_.info.run_id,
            "rmse_overall": all_rmse,
            "residual_std": residual_std,
            "version": latest,
            "per_zone": per_zone,
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    res = asyncio.run(run())
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
