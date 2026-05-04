# GRIDMIND

GRIDMIND is an AI-driven EV charging optimisation and infrastructure planning system built for **BESCOM**, the Bengaluru electricity utility.
It forecasts feeder load, schedules chargers under live tariff and grid-headroom constraints, and ranks candidate sites for new infrastructure.
A single data-nodes simulator (six routers) feeds three ML services (LSTM, PPO, k-means) behind a FastAPI gateway and a Next.js operator dashboard.

## Architecture

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
                                      │ writes
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

## Quick Start

You need **Docker Desktop** running. From the repo root:

```bash
# 1. Create your .env from the template
cp .env.example .env

# 2. IMPORTANT — set INFLUXDB_TOKEN to a real long random string.
#    Generate one with:
python -c "import secrets; print(secrets.token_urlsafe(48))"
#    Paste into the INFLUXDB_TOKEN= line in .env.

# 3. Build + start everything (first run takes 5–10 min — it builds PyTorch)
docker compose up -d --build

# 4. Watch the gateway come up
docker compose ps
docker compose logs -f backend-gateway
```

Then open:

- Dashboard       → http://localhost:3000
- Roadmap page    → http://localhost:3000/roadmap
- Gateway health  → http://localhost:8000/health
- MLflow UI       → http://localhost:5000
- InfluxDB UI     → http://localhost:8086

### One-time: train the models

LSTM and PPO inference return `503 model_not_loaded` until they have a model in the MLflow registry. Run once after the stack is healthy:

```bash
docker compose exec backend-lstm python -m lstm.train
docker compose exec backend-ppo  python -m ppo.train
```

Clustering self-runs on startup, so no manual step there. Until LSTM and PPO are trained, the frontend silently falls back to mock data — you'll see `[GRIDMIND API]` warnings in the browser console, but the UI keeps working.

### Frontend dev (hot-reload, no Docker rebuild)

```bash
cd frontend
cp .env.example .env.local
npm install        # installs @tanstack/react-query + zustand
npm run dev        # http://localhost:3000
```

Still needs the backend stack running (or the UI uses mock fallback). Easiest combo: `docker compose up -d` for the backend, then `npm run dev` separately for the frontend.

## Repository Layout

```
gridmind/
├── frontend/                # Next.js 14 + Tailwind dashboard + roadmap
├── data-nodes/              # Single FastAPI app with 6 simulator routers
├── backend/                 # ML services (LSTM, PPO, clustering) + gateway + shared
├── docs/                    # Developer docs (lean, current)
├── docker-compose.yml       # Root orchestration
├── .env.example             # Single source of truth for env vars
├── CONNECTION_GUIDE.md      # Frontend ⇆ backend wiring guide
└── README.md
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system overview, data flow, tech stack
- [Data Contracts](docs/DATA_CONTRACTS.md) — node endpoints, response schemas, Redis stream names
- [ML Models](docs/ML_MODELS.md) — LSTM, PPO (with safety fallback), clustering specs
- [API Reference](docs/API_REFERENCE.md) — gateway endpoints consumed by the frontend, with examples
- [Deployment](docs/DEPLOYMENT.md) — local + production, verifying services, common issues, prod checklist
- [Connection Guide](CONNECTION_GUIDE.md) — page → hook → endpoint table for the frontend

## Status

Research prototype. Recommendations are advisory only — no commands flow to BESCOM infrastructure today. See [/roadmap](http://localhost:3000/roadmap) for what's shipped, what's coming for the pilot, and what scales beyond.
