"""Feature engineering: pull from Redis / InfluxDB → aligned 15-min matrices.

Two entry points:
  * `live_window(zone_id)` — build a single (1, T, F) tensor for inference,
    pulling the most-recent T 15-min buckets from InfluxDB + Redis fallback.
  * `training_dataset(days)` — build (samples, T, F) train + (samples, H) target
    tensors for `train.py`, using `LSTM_TRAIN_DAYS` of history per zone.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

from config import (
    INFLUXDB_BUCKET,
    LSTM_FEATURE_NAMES,
    LSTM_HORIZON,
    LSTM_NUM_FEATURES,
    LSTM_SEQ_LEN,
    STREAMS,
    ZONES,
)
from shared import influx_client, redis_consumer

log = logging.getLogger("gridmind.lstm.features")

ZONE_INDEX: dict[str, int] = {z: i for i, z in enumerate(ZONES)}
RES_MIN = 15  # 15-minute buckets


def _calendar(ts: datetime) -> tuple[float, float, float, float, float]:
    h = ts.hour + ts.minute / 60.0
    dow = ts.weekday()
    return (
        math.sin(2 * math.pi * h / 24.0),
        math.cos(2 * math.pi * h / 24.0),
        math.sin(2 * math.pi * dow / 7.0),
        math.cos(2 * math.pi * dow / 7.0),
        1.0 if dow >= 5 else 0.0,
    )


def _bucket_floor(ts: datetime) -> datetime:
    minute = (ts.minute // RES_MIN) * RES_MIN
    return ts.replace(minute=minute, second=0, microsecond=0)


# ─────────────── Influx pull ───────────────
async def _zone_history(zone_id: str, *, hours: int) -> dict[datetime, dict[str, float]]:
    """Pull aligned 15-min series for one zone over `hours` lookback."""
    flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) =>
        r._measurement == "ev_analytics" or
        r._measurement == "grid_telemetry" or
        r._measurement == "solar_generation" or
        r._measurement == "tariff_signals" or
        r._measurement == "weather_data")
  |> filter(fn: (r) => not exists r.zone_id or r.zone_id == "{zone_id}" or r.zone_id == "ALL")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
'''
    rows = await influx_client.query(flux)
    out: dict[datetime, dict[str, float]] = {}
    for r in rows:
        t = _bucket_floor(r["time"].replace(tzinfo=timezone.utc) if r["time"].tzinfo is None else r["time"])
        out.setdefault(t, {})
        out[t][r["field"]] = float(r["value"]) if r["value"] is not None else 0.0
    return out


# ─────────────── Vectorisation ───────────────
def _row(zone_id: str, ts: datetime, src: dict[str, float]) -> list[float]:
    cs, cc, ds, dc, wknd = _calendar(ts)
    return [
        float(src.get("demand_kwh_15min", 0.0)),
        float(src.get("base_load_kw", 0.0)),
        float(src.get("ev_load_kw", 0.0)),
        float(src.get("active_sessions", 0.0)),
        float(src.get("rate_inr_per_kwh", 0.0)),
        float(src.get("pv_output_kw", 0.0)),
        float(src.get("battery_soc_pct", 0.0)),
        float(src.get("temperature_c", 0.0)),
        float(src.get("cloud_cover_pct", 0.0)),
        cs, cc, ds, dc, wknd,
    ]


def _ffill_zone_mean(matrix: np.ndarray, max_steps: int = 3) -> np.ndarray:
    """Forward-fill NaNs up to `max_steps`, then fall back to per-feature mean."""
    M = matrix.copy()
    for col in range(M.shape[1]):
        last = None
        run = 0
        for row in range(M.shape[0]):
            if np.isnan(M[row, col]):
                if last is not None and run < max_steps:
                    M[row, col] = last
                    run += 1
            else:
                last = M[row, col]
                run = 0
        col_mean = np.nanmean(M[:, col])
        if np.isnan(col_mean):
            col_mean = 0.0
        np.nan_to_num(M[:, col], copy=False, nan=col_mean)
    return M


# ─────────────── Public API ───────────────
async def live_window(zone_id: str) -> tuple[torch.Tensor, torch.Tensor, list[datetime], "StandardScaler | None"]:
    """Return (x, zone_idx, timestamps, scaler-placeholder) for inference.

    Caller is expected to apply a scaler loaded from the MLflow run; if none
    is available, raw values are returned and the model still infers (degraded).
    """
    hours = (LSTM_SEQ_LEN * RES_MIN) // 60 + 2
    history = await _zone_history(zone_id, hours=hours)
    # Fallback: enrich with most-recent values from Redis if Influx empty.
    if not history:
        latest = {
            "ev_analytics":      await redis_consumer.get_latest(STREAMS["ev_session"]),
            "grid_telemetry":    await redis_consumer.get_latest(STREAMS["grid"]),
            "solar_generation":  await redis_consumer.get_latest(STREAMS["solar"]),
            "tariff_signals":    await redis_consumer.get_latest(STREAMS["tariff"]),
            "weather_data":      await redis_consumer.get_latest(STREAMS["weather"]),
        }
        flat: dict[str, float] = {}
        for blob in latest.values():
            if isinstance(blob, dict):
                for k, v in blob.items():
                    if isinstance(v, (int, float)):
                        flat[k] = float(v)
        now = _bucket_floor(datetime.now(timezone.utc))
        history = {now - timedelta(minutes=RES_MIN * i): flat for i in range(LSTM_SEQ_LEN)}

    keys = sorted(history.keys())[-LSTM_SEQ_LEN:]
    if len(keys) < LSTM_SEQ_LEN:
        # Pad with the earliest available.
        first = keys[0] if keys else _bucket_floor(datetime.now(timezone.utc))
        pad = [first - timedelta(minutes=RES_MIN * (i + 1)) for i in range(LSTM_SEQ_LEN - len(keys))]
        keys = list(reversed(pad)) + keys
        for p in pad:
            history.setdefault(p, history.get(first, {}))

    matrix = np.array([_row(zone_id, t, history.get(t, {})) for t in keys], dtype=np.float32)
    matrix = _ffill_zone_mean(matrix)
    x = torch.from_numpy(matrix).unsqueeze(0)  # (1, T, F)
    zone_idx = torch.tensor([ZONE_INDEX[zone_id]], dtype=torch.long)
    return x, zone_idx, keys, None


async def training_dataset(days: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, StandardScaler]:
    """Return (X, zone_idx, Y, scaler) over `days` of history for all zones."""
    horizon = LSTM_HORIZON
    seq = LSTM_SEQ_LEN
    all_X: list[np.ndarray] = []
    all_Y: list[np.ndarray] = []
    all_Z: list[int] = []

    for zone_id in ZONES:
        hist = await _zone_history(zone_id, hours=days * 24)
        keys = sorted(hist.keys())
        if len(keys) < seq + horizon:
            log.warning("zone=%s insufficient history len=%d", zone_id, len(keys))
            continue
        matrix = np.array([_row(zone_id, t, hist[t]) for t in keys], dtype=np.float32)
        matrix = _ffill_zone_mean(matrix)
        demand = matrix[:, 0]  # demand_kwh column
        for start in range(0, len(keys) - seq - horizon, horizon):  # stride = horizon
            all_X.append(matrix[start:start + seq])
            all_Y.append(demand[start + seq:start + seq + horizon])
            all_Z.append(ZONE_INDEX[zone_id])

    if not all_X:
        # Degenerate case — return tiny synthetic batch so trainer can still smoke-test.
        log.warning("training_dataset empty; emitting synthetic batch")
        all_X = [np.zeros((seq, LSTM_NUM_FEATURES), dtype=np.float32) for _ in range(8)]
        all_Y = [np.zeros((horizon,), dtype=np.float32) for _ in range(8)]
        all_Z = [0] * 8

    X = np.stack(all_X)
    Y = np.stack(all_Y)
    Z = np.array(all_Z, dtype=np.int64)

    # Per-feature scaler fit on the train split (caller will split chronologically).
    scaler = StandardScaler()
    flat = X.reshape(-1, X.shape[-1])
    scaler.fit(flat)
    Xs = scaler.transform(flat).reshape(X.shape)
    return torch.from_numpy(Xs).float(), torch.from_numpy(Z), torch.from_numpy(Y).float(), scaler


def apply_scaler(x: torch.Tensor, scaler: Optional[StandardScaler]) -> torch.Tensor:
    if scaler is None:
        return x
    arr = x.numpy()
    flat = arr.reshape(-1, arr.shape[-1])
    return torch.from_numpy(scaler.transform(flat).reshape(arr.shape)).float()


def feature_index(name: str) -> int:
    return LSTM_FEATURE_NAMES.index(name)
