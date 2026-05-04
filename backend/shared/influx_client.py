"""Async-friendly InfluxDB v2 wrapper for backend services."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from config import INFLUXDB_BUCKET, INFLUXDB_ORG, INFLUXDB_TOKEN, INFLUXDB_URL

log = logging.getLogger("gridmind.influx")

_client: Optional[InfluxDBClient] = None


def _ensure_client() -> InfluxDBClient:
    global _client
    if _client is None:
        _client = InfluxDBClient(
            url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG, timeout=10_000,
        )
    return _client


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _build_point(
    measurement: str,
    *,
    tags: dict[str, str],
    fields: dict[str, Any],
    ts: Optional[datetime] = None,
) -> Point:
    p = Point(measurement)
    for k, v in tags.items():
        if v is not None:
            p = p.tag(k, str(v))
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, bool):
            p = p.field(k, v)
        elif isinstance(v, (int, float)):
            p = p.field(k, float(v))
        else:
            p = p.field(k, str(v))
    if ts is not None:
        p = p.time(ts, WritePrecision.NS)
    return p


def _write_sync(points: list[Point]) -> None:
    if not points:
        return
    c = _ensure_client()
    with c.write_api(write_options=SYNCHRONOUS) as w:
        w.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=points)


async def write_point(
    measurement: str,
    *,
    tags: dict[str, str],
    fields: dict[str, Any],
    ts: Optional[datetime] = None,
) -> None:
    point = _build_point(measurement, tags=tags, fields=fields, ts=ts)
    try:
        await asyncio.to_thread(_write_sync, [point])
    except Exception:
        log.exception("influx write_point failed measurement=%s", measurement)


async def write_points(points_spec: Iterable[dict[str, Any]]) -> None:
    """Bulk write. Each item: {measurement, tags, fields, ts?}."""
    pts = [
        _build_point(p["measurement"], tags=p.get("tags", {}), fields=p.get("fields", {}), ts=p.get("ts"))
        for p in points_spec
    ]
    try:
        await asyncio.to_thread(_write_sync, pts)
    except Exception:
        log.exception("influx write_points failed n=%d", len(pts))


def _query_sync(flux: str) -> list[dict[str, Any]]:
    c = _ensure_client()
    tables = c.query_api().query(flux, org=INFLUXDB_ORG)
    out: list[dict[str, Any]] = []
    for tbl in tables:
        for rec in tbl.records:
            out.append({
                "time": rec.get_time(),
                "measurement": rec.get_measurement(),
                "field": rec.get_field(),
                "value": rec.get_value(),
                **{k: v for k, v in rec.values.items() if k.startswith("zone_id") or k in ("model_version",)},
            })
    return out


async def query(flux: str) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_query_sync, flux)
    except Exception:
        log.exception("influx query failed")
        return []


async def query_zone_metric(
    *,
    measurement: str,
    field: str,
    zone_id: Optional[str] = None,
    start: timedelta = timedelta(hours=24),
    every: str = "15m",
) -> list[dict[str, Any]]:
    """Convenience: aggregate one field for one (or all) zones."""
    zone_filter = f'|> filter(fn: (r) => r.zone_id == "{zone_id}")' if zone_id else ""
    flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -{int(start.total_seconds())}s)
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => r._field == "{field}")
  {zone_filter}
  |> aggregateWindow(every: {every}, fn: mean, createEmpty: false)
  |> yield(name: "mean")
'''
    return await query(flux)


async def healthy() -> bool:
    try:
        c = _ensure_client()
        return c.ping()
    except Exception:
        return False
