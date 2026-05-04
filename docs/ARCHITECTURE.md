# GRIDMIND — Architecture

## System Overview

```
                        ┌────────────────────────────────────┐
                        │         FRONTEND  (Next.js 14)      │
                        │     Operator dashboard / planner    │
                        │              :3000                  │
                        └──────────────────┬─────────────────┘
                                           │ REST + TanStack Query
                                           ▼
                        ┌────────────────────────────────────┐
                        │   BACKEND-GATEWAY (FastAPI)  :8000  │
                        │  Aggregates ML services + cache     │
                        └──┬──────────────┬──────────────┬───┘
                           │              │              │
              ┌────────────▼─┐  ┌─────────▼────┐  ┌──────▼──────────┐
              │ LSTM   :8010 │  │ PPO   :8011  │  │ Clustering :8012│
              │  Forecast    │  │  Schedule    │  │  Site scoring   │
              └────────┬─────┘  └──────┬───────┘  └────────┬────────┘
                       │               │                   │
                       ▼               ▼                   ▼
                  ┌─────────────────────────────────────────────┐
                  │             INFLUXDB :8086                   │
                  │  predictions / schedules / zone_score        │
                  └─────────────────────────────────────────────┘
                                      ▲
                                      │ writes (features / outputs)
                  ┌───────────────────┴─────────────────────────┐
                  │              REDIS :6379                     │
                  │   pub/sub bus + latest:<stream> hot cache    │
                  └───────────────────▲─────────────────────────┘
                                      │ XADD per tick
                            ┌─────────┴──────────┐
                            │  DATA-NODES :8001  │
                            │  single FastAPI    │
                            │  6 routers:        │
                            │  ocpp / grid /     │
                            │  solar / tariff /  │
                            │  ev / weather      │
                            └────────────────────┘

         POSTGRESQL :5432  ──── relational metadata + MLflow backend store
         MLFLOW     :5000  ──── experiment tracking + model registry
```

## Data Flow

`data-nodes → Redis (pub/sub + latest:* cache) → ML backends → InfluxDB (history) → Gateway → Frontend`

1. **data-nodes** simulates six telemetry sources (OCPP chargers, grid feeders, rooftop PV, BESCOM ToU tariff, EV session aggregates, Open-Meteo weather) and publishes to Redis Streams (`ocpp_events`, `grid_telemetry`, `solar_generation`, `tariff_signals`, `ev_analytics`, `weather_data`). Each publish also updates `latest:<stream>` for cheap hot reads.
2. **ML backends** read live state from Redis and historical state from InfluxDB. Each writes its outputs (predictions, schedules, zone scores) back to InfluxDB with proper tags (`zone_id`, `model_version`).
3. **backend-gateway** is the only service the browser talks to. It fans out to LSTM/PPO/Clustering and to data-nodes, and caches responses in Redis (5min forecast / 1min schedule / 1h zones / 30s dashboard).
4. **Frontend** consumes the gateway via TanStack Query hooks; falls back to in-memory mock shapes if the gateway is unreachable so the UI never breaks.

## Layer Responsibilities

**Data Nodes.** One FastAPI process exposing six routers (`/ocpp`, `/grid`, `/solar`, `/tariff`, `/ev`, `/weather`) and a single `/health`. Every router owns its own SQLite DB at `/data/<node>.db` for the 7-day backfill; live ticks publish to Redis on per-node cadences (OCPP event-driven; grid/solar/ev/tariff every 15 min; weather every 30 min).

**Streaming Bus (Redis Stack).** Acts as both the pub/sub fanout and the hot-cache (`latest:<stream>`). Persistence enabled via `--appendonly yes` so a restart does not lose the most recent tick.

**ML Backends.** Three model services. All three load their model from the MLflow registry on startup, expose an inference endpoint, persist outputs to InfluxDB, and write Postgres audit rows. APScheduler jobs retrain the LSTM every 24 h, online-update PPO every 6 h, and recompute clustering every 7 d.

**Persistence.** PostgreSQL 16 holds `schedules`, `schedule_overrides`, `zone_recommendations`, `audit_log`, plus the MLflow tracking-server backend store. InfluxDB 2.7 holds time-series telemetry, features, predictions, schedules, scores, and `safety_events`.

**Gateway.** Thin FastAPI aggregator: CORS, `/metrics` (Prometheus), correlation-ID middleware, JSON logs, tenacity-backed retries on inter-service calls.

**Frontend.** Next.js 14 App Router; Tailwind + Recharts UI; TanStack Query for data fetching; Zustand for client state.

## Tech Stack

| Service              | Technology                       | Purpose                                          |
| -------------------- | -------------------------------- | ------------------------------------------------ |
| frontend             | Next.js 14 + React 18 + Tailwind | Operator dashboard, planner, forecasting view    |
|                      | TanStack Query 5, Zustand 5      | Server-state caching + client state              |
|                      | Recharts, Framer Motion          | Charts + animations                              |
| backend-gateway      | FastAPI + httpx + tenacity       | Single REST surface for the frontend             |
| backend-lstm         | PyTorch 2.4 + FastAPI            | Short-horizon load / demand forecast             |
| backend-ppo          | Stable-Baselines3 2.3 + Gymnasium| Charger schedule control via RL                  |
| backend-clustering   | scikit-learn 1.5 + FastAPI       | Candidate site scoring (KMeans + DBSCAN)         |
| data-nodes           | FastAPI + aiosqlite + httpx      | Six simulators in one process                    |
| redis                | Redis Stack 7                    | Pub/sub bus + hot feature cache (appendonly on)  |
| influxdb             | InfluxDB 2.7                     | Time-series telemetry, features, predictions     |
| postgresql           | PostgreSQL 16                    | Relational metadata + MLflow backend             |
| mlflow               | MLflow 2.16                      | Experiment tracking + model registry             |
| observability        | Prometheus client + JSON logs    | `/metrics` + structured logs across all services |
