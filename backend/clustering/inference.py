"""Clustering inference server (port 8012).

* GET /clustering/zones/ranking — returns latest ranking from cache or recomputes.
* POST /clustering/replan — fires an immediate recompute, returns job_id.
* APScheduler runs a recompute every CLUSTERING_REPLAN_DAYS days.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import BackgroundTasks, FastAPI

from config import CLUSTERING_REGISTRY_NAME, CLUSTERING_REPLAN_DAYS
from clustering import pipeline as clustering_pipeline
from clustering import scoring as scoring_mod
from shared import influx_client, mlflow_client, postgres_client, redis_consumer
from shared.observability import install_observability, uptime_seconds
from shared.schemas import (
    HealthResponse,
    RankingResponse,
    ReplanResponse,
    ZoneMetrics,
    ZoneRanking,
    ZoneRecommendation,
)

log = logging.getLogger("gridmind.clustering.inference")
SERVICE = "backend-clustering"

CACHE_KEY = "clustering:latest_ranking"

STATE: dict[str, Any] = {
    "model_version": "v0",
    "last_run": None,
    "next_run": None,
    "in_flight_jobs": {},
}


# ─────────────── Pipeline ───────────────
async def _compute_ranking() -> RankingResponse:
    log.info("clustering recompute starting")
    features = await clustering_pipeline.extract_features()
    cluster_out = clustering_pipeline.cluster(features)
    scored = scoring_mod.score_zones(features)

    rankings: list[ZoneRanking] = []
    for i, base in enumerate(scored):
        rec_dict = scoring_mod.recommend(base)
        rankings.append(ZoneRanking(
            zone_id=base["zone_id"],
            score=base["score"],
            priority=base["priority"],
            cluster_label=int(cluster_out["labels"][i]) if cluster_out["labels"] else 0,
            is_outlier=bool(cluster_out["outliers"][i]) if cluster_out["outliers"] else False,
            metrics=ZoneMetrics(**base["metrics"]),
            recommendation=ZoneRecommendation(**rec_dict),
        ))
    rankings.sort(key=lambda r: r.score, reverse=True)

    now = datetime.now(timezone.utc)
    next_replan = now + timedelta(days=CLUSTERING_REPLAN_DAYS)

    response = RankingResponse(
        computed_at=now,
        next_replan=next_replan,
        zones=rankings,
        silhouette_score=round(float(cluster_out["silhouette"]), 4),
        model_version=STATE["model_version"],
    )
    STATE["last_run"] = now
    STATE["next_run"] = next_replan
    await _persist(response)
    return response


async def _persist(resp: RankingResponse) -> None:
    payload = resp.model_dump(mode="json")
    await redis_consumer.cache_set(CACHE_KEY, payload, ttl_seconds=CLUSTERING_REPLAN_DAYS * 24 * 3600)
    await postgres_client.insert_recommendations(resp.model_version, payload)
    points = [
        {
            "measurement": "zone_score",
            "tags": {"zone_id": z.zone_id, "model_version": resp.model_version, "priority": z.priority.value},
            "fields": {
                "score": z.score,
                "cluster_label": z.cluster_label,
                "is_outlier": int(z.is_outlier),
                "new_chargers_suggested": z.recommendation.new_chargers_suggested,
            },
            "ts": resp.computed_at,
        }
        for z in resp.zones
    ]
    await influx_client.write_points(points)
    await postgres_client.insert_audit(
        service=SERVICE, action="recompute", actor=None, correlation_id=None,
        payload={"silhouette": resp.silhouette_score, "n_zones": len(resp.zones)},
    )


# ─────────────── App ───────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_consumer.connect()
    await postgres_client.connect()

    async def _scheduled_compute() -> None:
        try:
            await _compute_ranking()
        except Exception:
            log.exception("scheduled clustering compute failed")

    sched = AsyncIOScheduler()
    sched.add_job(
        _scheduled_compute,
        IntervalTrigger(days=CLUSTERING_REPLAN_DAYS),
        id="clustering_replan", replace_existing=True,
    )
    sched.start()
    log.info("clustering scheduler started cadence=%dd", CLUSTERING_REPLAN_DAYS)

    # Run an initial pass so the cache is warm.
    try:
        await _compute_ranking()
    except Exception:
        log.exception("initial clustering compute failed")

    yield
    sched.shutdown(wait=False)
    await redis_consumer.close()
    await postgres_client.close()
    influx_client.close()


app = FastAPI(title="GRIDMIND clustering", version="1.0.0", lifespan=lifespan)
install_observability(app, service=SERVICE)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    deps = {
        "redis":    "ok" if await redis_consumer.healthy() else "down",
        "postgres": "ok" if await postgres_client.healthy() else "down",
        "influx":   "ok" if await influx_client.healthy() else "down",
    }
    return HealthResponse(
        status="ok",
        service=SERVICE,
        uptime_seconds=uptime_seconds(),
        model_version=STATE["model_version"],
        dependencies=deps,
    )


@app.get("/clustering/zones/ranking", response_model=RankingResponse)
async def ranking() -> RankingResponse:
    cached = await redis_consumer.cache_get(CACHE_KEY)
    if cached:
        return RankingResponse.model_validate(cached)
    latest = await postgres_client.latest_recommendations()
    if latest:
        return RankingResponse.model_validate(latest)
    return await _compute_ranking()


@app.post("/clustering/replan", response_model=ReplanResponse)
async def replan(bg: BackgroundTasks) -> ReplanResponse:
    job_id = uuid.uuid4().hex
    STATE["in_flight_jobs"][job_id] = datetime.now(timezone.utc).isoformat()

    async def _run():
        try:
            await _compute_ranking()
        finally:
            STATE["in_flight_jobs"].pop(job_id, None)

    bg.add_task(_run)
    return ReplanResponse(job_id=job_id, accepted_at=datetime.now(timezone.utc))
