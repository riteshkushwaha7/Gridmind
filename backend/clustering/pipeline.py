"""Feature extraction + clustering (KMeans for groups, DBSCAN for outliers)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import (
    CLUSTERING_DBSCAN_EPS,
    CLUSTERING_DBSCAN_MIN_SAMPLES,
    CLUSTERING_K,
    CLUSTERING_LOOKBACK_DAYS,
    INFLUXDB_BUCKET,
    ZONES,
)
from clustering.scoring import ZoneFeatures
from shared import influx_client

log = logging.getLogger("gridmind.clustering.pipeline")


# ─────────────── Feature extraction ───────────────
async def _series_for_zone(zone_id: str, *, measurement: str, field: str) -> list[tuple[datetime, float]]:
    flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -{CLUSTERING_LOOKBACK_DAYS}d)
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
  |> filter(fn: (r) => r.zone_id == "{zone_id}")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
'''
    rows = await influx_client.query(flux)
    pts = []
    for r in rows:
        if r["value"] is None:
            continue
        pts.append((r["time"], float(r["value"])))
    pts.sort()
    return pts


def _linear_growth_pct(series: list[tuple[datetime, float]]) -> float:
    """Slope of OLS line, expressed as % of mean over the period."""
    if len(series) < 3:
        return 0.0
    y = np.array([v for _, v in series], dtype=np.float64)
    x = np.arange(len(y), dtype=np.float64)
    a, _ = np.polyfit(x, y, 1)
    mean = max(1e-6, float(y.mean()))
    return float(a / mean * 100.0 * len(y))


async def extract_features() -> list[ZoneFeatures]:
    out: list[ZoneFeatures] = []
    for zone_id in ZONES:
        demand = await _series_for_zone(zone_id, measurement="ev_analytics", field="demand_kwh_15min")
        head   = await _series_for_zone(zone_id, measurement="grid_telemetry", field="headroom_pct")
        chargers = await _series_for_zone(zone_id, measurement="ev_analytics", field="total_chargers")
        utilization = await _series_for_zone(zone_id, measurement="ev_analytics", field="utilization_pct")
        queue = await _series_for_zone(zone_id, measurement="ev_analytics", field="queued_evs")

        demand_vals = np.array([v for _, v in demand], dtype=np.float64) if demand else np.array([0.0])
        head_vals   = np.array([v for _, v in head],   dtype=np.float64) if head   else np.array([100.0])
        existing = int(chargers[-1][1]) if chargers else 0
        util_avg = float(np.mean([v for _, v in utilization])) if utilization else 0.0
        queue_avg = float(np.mean([v for _, v in queue])) if queue else 0.0

        # Convert daily-mean demand to daily-total kWh
        daily_total = float(demand_vals.mean()) * 96  # 96 × 15-min slots
        out.append(ZoneFeatures(
            zone_id=zone_id,
            avg_demand_kwh_daily=daily_total,
            demand_growth_rate_pct=_linear_growth_pct(demand),
            peak_demand_kw=float(demand_vals.max() * 4),    # kW per 15-min bucket
            demand_variance=float(demand_vals.var()),
            grid_headroom_avg_pct=float(head_vals.mean()),
            grid_headroom_min_pct=float(head_vals.min()),
            existing_charger_count=existing,
            charger_utilization_pct=util_avg,
            avg_queue_length=queue_avg,
            ev_adoption_growth_rate=_linear_growth_pct(chargers),
        ))
    return out


# ─────────────── Clustering ───────────────
def cluster(features: list[ZoneFeatures]) -> dict:
    """Run K-Means + DBSCAN on the same standardised feature matrix."""
    if not features:
        return {"labels": [], "outliers": [], "silhouette": 0.0, "feature_names": []}

    matrix = np.array([
        [
            f.avg_demand_kwh_daily, f.demand_growth_rate_pct, f.peak_demand_kw,
            f.demand_variance, f.grid_headroom_avg_pct, f.grid_headroom_min_pct,
            f.existing_charger_count, f.charger_utilization_pct,
            f.avg_queue_length, f.ev_adoption_growth_rate,
        ]
        for f in features
    ], dtype=np.float64)
    feat_names = [
        "avg_demand_kwh_daily", "demand_growth_rate_pct", "peak_demand_kw", "demand_variance",
        "grid_headroom_avg_pct", "grid_headroom_min_pct", "existing_charger_count",
        "charger_utilization_pct", "avg_queue_length", "ev_adoption_growth_rate",
    ]

    scaler = StandardScaler()
    X = scaler.fit_transform(matrix)

    k = min(CLUSTERING_K, len(features))
    km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(X)
    labels = km.labels_.tolist()
    sil = float(silhouette_score(X, km.labels_)) if len(set(km.labels_)) > 1 else 0.0

    db = DBSCAN(eps=CLUSTERING_DBSCAN_EPS, min_samples=CLUSTERING_DBSCAN_MIN_SAMPLES).fit(X)
    outliers = (db.labels_ == -1).tolist()

    return {
        "labels": labels,
        "outliers": outliers,
        "silhouette": sil,
        "feature_names": feat_names,
    }
