# GRIDMIND — Gateway API Reference

Base URL: `http://localhost:8000` (or whatever `NEXT_PUBLIC_API_URL` points to).
All responses are JSON; errors follow `{ "error", "detail", "timestamp", "correlation_id" }`.
Every response includes the response header `X-Correlation-ID` (echoed from request, or generated).

| Method | Path                              | Request                                                       | Response                                                                                                                              |
| ------ | --------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/health`                         | —                                                             | `{status, service, uptime_seconds, dependencies:{redis,postgres,lstm,ppo,clustering,data-nodes}}`                                     |
| GET    | `/metrics`                        | —                                                             | Prometheus exposition text                                                                                                            |
| GET    | `/dashboard/overview`             | —                                                             | `DashboardOverview` — see example below                                                                                                |
| GET    | `/dashboard/zone/{zone_id}`       | path: `Z01..Z10`                                              | `{zone_id, timestamp, grid, solar, ev, ocpp}` — fan-out to data-nodes                                                                  |
| GET    | `/dashboard/alerts`               | —                                                             | `{timestamp, count, alerts:[{zone_id,severity,message,timestamp}]}`                                                                    |
| GET    | `/forecast/{zone_id}`             | query: `hours=1..24` (default 4)                              | `ForecastResponse` (LSTM)                                                                                                              |
| GET    | `/forecast/all`                   | query: `hours=1..24`                                          | `{horizon_hours, forecasts:[ForecastResponse], errors:[]}`                                                                             |
| GET    | `/schedule/current`               | —                                                             | `ScheduleResponse` — see example below                                                                                                 |
| POST   | `/schedule/override`              | `{zone_id, power_kw, operator_id, reason}`                    | `{override_id, schedule_id, applied_at, status:"accepted"}`                                                                            |
| GET    | `/zones/ranking`                  | —                                                             | `RankingResponse` — see example below                                                                                                  |
| GET    | `/zones/{zone_id}/history`        | query: `metric=demand\|grid\|solar`, `hours=1..720`           | Pass-through to data-nodes (shape depends on metric)                                                                                   |

> Note: clustering replan is not exposed on the gateway directly. Hit the clustering service via `POST :8012/clustering/replan` (or proxy server-side) for on-demand recompute.

## Examples

### `GET /dashboard/overview`

```json
{
  "timestamp": "2026-05-04T10:15:00Z",
  "system_status": "HEALTHY",
  "zones_summary": [
    { "zone_id": "Z01", "status": "NORMAL", "load_pct": 41.2, "active_evs": 6, "score": 0.74 }
  ],
  "grid_total": { "total_load_kw": 6840, "total_capacity_kw": 11050, "system_headroom_pct": 38.1 },
  "current_tariff": { "tier": "MID_PEAK", "rate_inr": 7.0, "next_change_minutes": 142 },
  "solar_total": { "generation_kw": 412, "battery_soc_avg": 64.5, "self_consumption_pct": 71.2 },
  "active_sessions_total": 58,
  "peak_reduction_today_pct": 18.6,
  "cost_savings_today_inr": 4320,
  "alerts": [
    { "zone_id": "Z05", "severity": "WARNING", "message": "Feeder BESCOM-F-Z05 status=WARNING (headroom 14.8%)", "timestamp": "2026-05-04T10:15:00Z" }
  ]
}
```

### `POST /ppo/schedule` (proxied behind `GET /schedule/current`)

```jsonc
// request body — built by the gateway from live data-nodes state
{
  "zones": [
    { "zone_id": "Z01", "active_evs": 6, "avg_soc": 38.4, "feeder_headroom_pct": 24.6, "solar_output_kw": 12.1, "battery_soc": 58.0 }
  ],
  "tariff_current": 9.5,
  "demand_forecast": [310, 318, 326, 332, 340, 345, 348, 350, 352, 350, 346, 340, 332, 322, 314, 306]
}
```

```jsonc
// response — ScheduleResponse
{
  "schedule_id": "f9e3b4...",
  "generated_at": "2026-05-04T10:15:00Z",
  "valid_for_minutes": 15,
  "schedules": [
    {
      "zone_id": "Z01",
      "recommended_power_kw": 22.0,
      "safety_capped": false,
      "fallback_active": false,
      "charging_cost_inr_per_kwh": 9.5,
      "estimated_sessions_served": 3,
      "reasoning": "Recommend 22.0 kW — High tariff window → throttled"
    }
  ],
  "total_grid_load_kw": 612.5,
  "peak_reduction_vs_unmanaged_pct": 22.4
}
```

### `GET /zones/ranking`

```jsonc
{
  "computed_at": "2026-05-04T10:00:00Z",
  "next_replan": "2026-05-11T10:00:00Z",
  "silhouette_score": 0.62,
  "model_version": "v0",
  "zones": [
    {
      "zone_id": "Z04",
      "score": 0.91,
      "priority": "HIGH",
      "cluster_label": 0,
      "is_outlier": false,
      "metrics": { "avg_demand": 412.3, "growth_rate": 11.4, "headroom": 18.0, "existing_chargers": 3 },
      "recommendation": {
        "action": "EXPAND",
        "new_chargers_suggested": 4,
        "charger_type_suggested": "DC_Fast_50kW",
        "estimated_cost_inr_lakhs": 48.0,
        "priority_reason": "High score (0.91); growth 11.4%/30d; headroom 18%"
      }
    }
  ]
}
```
