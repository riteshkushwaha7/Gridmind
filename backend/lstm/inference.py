"""LSTM inference server (port 8010).

Loads the latest Production model from MLflow on startup, exposes
POST /lstm/forecast and a hot-reload endpoint POST /lstm/reload.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import pickle
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from sklearn.preprocessing import StandardScaler

from config import (
    LSTM_FEATURE_NAMES,
    LSTM_HORIZON,
    LSTM_REGISTRY_NAME,
)
from lstm.features import (
    ZONE_INDEX,
    apply_scaler,
    feature_index,
    live_window,
)
from shared import influx_client, mlflow_client, postgres_client, redis_consumer
from shared.observability import install_observability, uptime_seconds
from shared.schemas import (
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
)

log = logging.getLogger("gridmind.lstm.inference")
SERVICE = "backend-lstm"

STATE: dict[str, Any] = {
    "model": None,
    "scaler": None,
    "model_version": None,
    "rmse_last_eval": 0.0,
    "residual_std": 1.0,
    "loaded_at": None,
}


# ─────────────── Model load ───────────────
async def _load_model() -> None:
    log.info("loading model from registry name=%s", LSTM_REGISTRY_NAME)
    model = await mlflow_client.aload_pytorch(LSTM_REGISTRY_NAME)
    if model is None:
        log.warning("no registered LSTM model — service will return 503 until trained")
        return
    model.eval()
    STATE["model"] = model
    STATE["model_version"] = mlflow_client.latest_production_version(LSTM_REGISTRY_NAME) or mlflow_client.latest_any_version(LSTM_REGISTRY_NAME)

    # Pull scaler + metadata from artifacts of the model's run.
    with tempfile.TemporaryDirectory() as tmp:
        path = await mlflow_client.adownload_artifact(LSTM_REGISTRY_NAME, tmp)
        if path:
            sp = os.path.join(path, "scaler.pkl")
            mp = os.path.join(path, "metadata.json")
            if os.path.exists(sp):
                with open(sp, "rb") as f:
                    STATE["scaler"] = pickle.load(f)
            if os.path.exists(mp):
                with open(mp) as f:
                    meta = json.load(f)
                STATE["rmse_last_eval"] = float(meta.get("rmse_overall", 0.0))
                STATE["residual_std"] = float(meta.get("residual_std", 1.0))
    STATE["loaded_at"] = datetime.now(timezone.utc).isoformat()


# ─────────────── Inference ───────────────
async def _forecast(zone_id: str, horizon_hours: int) -> ForecastResponse:
    if zone_id not in ZONE_INDEX:
        raise HTTPException(status_code=404, detail=f"unknown zone {zone_id}")
    model = STATE["model"]
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded; train via lstm.train first")

    horizon_steps = min(LSTM_HORIZON, horizon_hours * 4)
    x, zone_idx, ts_keys, _ = await live_window(zone_id)
    x_scaled = apply_scaler(x, STATE["scaler"])
    with torch.no_grad():
        pred = model(x_scaled, zone_idx).squeeze(0).cpu().numpy()
    pred = pred[:horizon_steps]

    sigma = STATE["residual_std"]
    band = 1.96 * sigma
    last_ts = ts_keys[-1] if ts_keys else datetime.now(timezone.utc)
    points = [
        ForecastPoint(
            timestamp=last_ts + timedelta(minutes=15 * (i + 1)),
            demand_kwh=float(pred[i]),
            confidence_lower=float(pred[i] - band),
            confidence_upper=float(pred[i] + band),
        )
        for i in range(horizon_steps)
    ]

    importance = await _permutation_importance(model, x_scaled, zone_idx)

    response = ForecastResponse(
        zone_id=zone_id,
        model_version=str(STATE["model_version"] or "unregistered"),
        generated_at=datetime.now(timezone.utc),
        forecast=points,
        rmse_last_eval=float(STATE["rmse_last_eval"]),
        feature_importance=importance,
    )
    asyncio.create_task(_persist(zone_id, response))
    return response


async def _permutation_importance(model: torch.nn.Module, x: torch.Tensor, zone_idx: torch.Tensor, *, repeats: int = 2) -> dict[str, float]:
    """Light permutation importance — shuffle each feature column, measure ΔMSE."""
    model.eval()
    with torch.no_grad():
        base = model(x, zone_idx).cpu().numpy()
    out: dict[str, float] = {}
    rng = np.random.default_rng(0)
    arr = x.numpy()
    for name in LSTM_FEATURE_NAMES:
        col = feature_index(name)
        delta_total = 0.0
        for _ in range(repeats):
            permuted = arr.copy()
            perm = rng.permutation(permuted.shape[1])
            permuted[:, :, col] = permuted[:, perm, col]
            with torch.no_grad():
                p = model(torch.from_numpy(permuted).float(), zone_idx).cpu().numpy()
            delta_total += float(np.mean((p - base) ** 2))
        out[name] = round(delta_total / repeats, 6)
    total = sum(out.values()) or 1.0
    return {k: round(v / total, 4) for k, v in out.items()}


async def _persist(zone_id: str, resp: ForecastResponse) -> None:
    points = [
        {
            "measurement": "lstm_forecast",
            "tags": {"zone_id": zone_id, "model_version": resp.model_version},
            "fields": {
                "demand_kwh": p.demand_kwh,
                "lower": p.confidence_lower,
                "upper": p.confidence_upper,
            },
            "ts": p.timestamp,
        }
        for p in resp.forecast
    ]
    await influx_client.write_points(points)
    await postgres_client.insert_audit(
        service=SERVICE, action="forecast", actor=None,
        correlation_id=None,
        payload={"zone_id": zone_id, "horizon": len(points), "model_version": resp.model_version},
    )


# ─────────────── App ───────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_consumer.connect()
    await postgres_client.connect()
    await _load_model()
    yield
    await redis_consumer.close()
    await postgres_client.close()
    influx_client.close()


app = FastAPI(title="GRIDMIND LSTM forecast", version="1.0.0", lifespan=lifespan)
install_observability(app, service=SERVICE)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    deps = {
        "redis":  "ok" if await redis_consumer.healthy() else "down",
        "postgres": "ok" if await postgres_client.healthy() else "down",
        "mlflow": "ok" if await mlflow_client.healthy() else "down",
        "influx": "ok" if await influx_client.healthy() else "down",
    }
    return HealthResponse(
        status="ok" if STATE["model"] is not None else "model_not_loaded",
        service=SERVICE,
        uptime_seconds=uptime_seconds(),
        model_version=str(STATE["model_version"] or ""),
        dependencies=deps,
    )


@app.post("/lstm/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest) -> ForecastResponse:
    return await _forecast(req.zone_id, req.horizon_hours)


@app.post("/lstm/reload")
async def reload_model() -> dict[str, Any]:
    await _load_model()
    return {"status": "reloaded", "model_version": STATE["model_version"], "loaded_at": STATE["loaded_at"]}
