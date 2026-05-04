"""PPO scheduler inference server (port 8011).

* Loads SB3 model from MLflow registry on startup.
* POST /ppo/schedule → safety-filtered per-zone power setpoint.
* APScheduler runs an online-update job every PPO_ONLINE_HOURS.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException

from config import (
    PPO_ONLINE_HOURS,
    PPO_REGISTRY_NAME,
    SAFETY_HEADROOM_FLOOR_PCT,
    ZONES,
)
from ppo import agent as ppo_agent
from ppo import safety as safety_mod
from ppo import train as ppo_train
from shared import influx_client, mlflow_client, postgres_client, redis_consumer
from shared.observability import install_observability, uptime_seconds
from shared.schemas import (
    HealthResponse,
    ScheduleRequest,
    ScheduleResponse,
    ZoneSchedule,
)

log = logging.getLogger("gridmind.ppo.inference")
SERVICE = "backend-ppo"

STATE: dict[str, Any] = {
    "model": None,
    "model_version": None,
    "model_path": None,
    "loaded_at": None,
    "loop": None,
}


# ─────────────── Model loading ───────────────
async def _download_and_load() -> None:
    log.info("downloading PPO model from MLflow registry=%s", PPO_REGISTRY_NAME)
    dst = tempfile.mkdtemp(prefix="ppo_")
    path = await mlflow_client.adownload_artifact(PPO_REGISTRY_NAME, dst)
    if not path:
        log.warning("no PPO model registered yet; service will return 503 until trained")
        return
    zip_candidate = None
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".zip"):
                zip_candidate = os.path.join(root, f)
                break
    if not zip_candidate:
        log.warning("no .zip in artifact path %s", path)
        return
    STATE["model"] = ppo_agent.load(zip_candidate)
    STATE["model_path"] = zip_candidate
    STATE["model_version"] = mlflow_client.latest_production_version(PPO_REGISTRY_NAME) or mlflow_client.latest_any_version(PPO_REGISTRY_NAME)
    STATE["loaded_at"] = datetime.now(timezone.utc).isoformat()
    log.info("ppo model loaded version=%s", STATE["model_version"])


# ─────────────── Inference helpers ───────────────
def _build_observation(req: ScheduleRequest) -> tuple[np.ndarray, dict[str, dict]]:
    """Pack the scheduler request into the env observation vector."""
    by_id = {z.zone_id: z for z in req.zones}
    headroom = np.array([by_id[z].feeder_headroom_pct if z in by_id else 100.0 for z in ZONES], dtype=np.float32)
    evs      = np.array([by_id[z].active_evs        if z in by_id else 0     for z in ZONES], dtype=np.float32)
    soc      = np.array([by_id[z].avg_soc           if z in by_id else 50.0  for z in ZONES], dtype=np.float32)
    batt     = np.array([by_id[z].battery_soc       if z in by_id else 50.0  for z in ZONES], dtype=np.float32)
    solar    = np.array([by_id[z].solar_output_kw   if z in by_id else 0.0   for z in ZONES], dtype=np.float32)
    forecast = np.asarray(req.demand_forecast, dtype=np.float32)
    now = datetime.now(timezone.utc)
    cs = math.sin(2 * math.pi * now.hour / 24)
    cc = math.cos(2 * math.pi * now.hour / 24)
    weekend = 1.0 if now.weekday() >= 5 else 0.0
    obs = np.concatenate([
        forecast, np.array([req.tariff_current], dtype=np.float32),
        headroom, evs, soc, batt, solar,
        np.array([cs, cc, weekend], dtype=np.float32),
    ])
    return obs, {z.zone_id: z.model_dump() for z in req.zones}


def _reasoning(*, headroom_pct: float, fallback: bool, capped: bool, tariff: float, kw: float) -> str:
    parts = []
    if fallback:
        parts.append(f"Headroom {headroom_pct:.1f}% below safety floor → proportional fallback")
    elif capped:
        parts.append("PPO setpoint exceeded feeder headroom → capped")
    if tariff >= 9.0:
        parts.append("High tariff window → throttled")
    elif tariff <= 5.0:
        parts.append("Off-peak window → boosted")
    if not parts:
        parts.append("Normal operating envelope")
    return f"Recommend {kw:.1f} kW — " + "; ".join(parts)


# ─────────────── App ───────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_consumer.connect()
    await postgres_client.connect()
    await _download_and_load()

    sched = AsyncIOScheduler()
    sched.add_job(
        _online_update_job,
        IntervalTrigger(hours=PPO_ONLINE_HOURS),
        id="ppo_online_update", replace_existing=True,
    )
    sched.start()
    STATE["loop"] = sched
    log.info("ppo online-update scheduler started cadence=%dh", PPO_ONLINE_HOURS)
    yield
    sched.shutdown(wait=False)
    await redis_consumer.close()
    await postgres_client.close()
    influx_client.close()


async def _online_update_job() -> None:
    log.info("online PPO update starting")
    try:
        result = await ppo_train.run(online=True, model_path=STATE.get("model_path"))
        log.info("online update done version=%s", result.get("version"))
        await _download_and_load()
    except Exception:
        log.exception("online PPO update failed")


app = FastAPI(title="GRIDMIND PPO scheduler", version="1.0.0", lifespan=lifespan)
install_observability(app, service=SERVICE)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    deps = {
        "redis":    "ok" if await redis_consumer.healthy() else "down",
        "postgres": "ok" if await postgres_client.healthy() else "down",
        "mlflow":   "ok" if await mlflow_client.healthy() else "down",
        "influx":   "ok" if await influx_client.healthy() else "down",
    }
    return HealthResponse(
        status="ok" if STATE["model"] is not None else "model_not_loaded",
        service=SERVICE,
        uptime_seconds=uptime_seconds(),
        model_version=str(STATE["model_version"] or ""),
        dependencies=deps,
    )


@app.post("/ppo/schedule", response_model=ScheduleResponse)
async def schedule(req: ScheduleRequest) -> ScheduleResponse:
    model = STATE["model"]
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded; train via ppo.train first")

    obs, _ = _build_observation(req)
    action = ppo_agent.predict(model, obs)
    zone_states = safety_mod.state_from_request([z.model_dump() for z in req.zones])
    safety = safety_mod.apply(pai_normalized=action, zone_states=zone_states, log_to_influx=True)

    # Estimated unmanaged total: assume each EV draws ~7 kW continuously.
    unmanaged_total = float(sum(z.active_evs * 7.0 for z in req.zones))
    managed_total = float(safety.final_kw.sum())
    peak_red = max(0.0, (unmanaged_total - managed_total) / unmanaged_total * 100.0) if unmanaged_total else 0.0

    schedules: list[ZoneSchedule] = []
    for i, zid in enumerate(ZONES):
        st = next((z for z in req.zones if z.zone_id == zid), None)
        kw = float(safety.final_kw[i])
        schedules.append(ZoneSchedule(
            zone_id=zid,
            recommended_power_kw=round(kw, 2),
            safety_capped=bool(safety.capped_mask[i]),
            fallback_active=bool(safety.fallback_mask[i]),
            charging_cost_inr_per_kwh=round(req.tariff_current, 2),
            estimated_sessions_served=int(min(st.active_evs if st else 0, max(1, kw // 7))) if st else 0,
            reasoning=_reasoning(
                headroom_pct=st.feeder_headroom_pct if st else 100.0,
                fallback=bool(safety.fallback_mask[i]),
                capped=bool(safety.capped_mask[i]),
                tariff=req.tariff_current,
                kw=kw,
            ),
        ))

    response = ScheduleResponse(
        schedule_id=uuid.uuid4().hex,
        generated_at=datetime.now(timezone.utc),
        valid_for_minutes=15,
        schedules=schedules,
        total_grid_load_kw=round(managed_total, 2),
        peak_reduction_vs_unmanaged_pct=round(peak_red, 2),
    )
    asyncio.create_task(_persist(response))
    return response


async def _persist(resp: ScheduleResponse) -> None:
    await postgres_client.insert_schedule(resp.schedule_id, resp.valid_for_minutes, resp.model_dump(mode="json"))
    points = [
        {
            "measurement": "ppo_schedule",
            "tags": {"zone_id": s.zone_id, "schedule_id": resp.schedule_id, "model_version": str(STATE["model_version"] or "")},
            "fields": {
                "power_kw": s.recommended_power_kw,
                "safety_capped": int(s.safety_capped),
                "fallback_active": int(s.fallback_active),
                "tariff_inr": s.charging_cost_inr_per_kwh,
            },
            "ts": resp.generated_at,
        }
        for s in resp.schedules
    ]
    await influx_client.write_points(points)


@app.post("/ppo/reload")
async def reload_model() -> dict[str, Any]:
    await _download_and_load()
    return {"status": "reloaded", "model_version": STATE["model_version"], "loaded_at": STATE["loaded_at"]}
