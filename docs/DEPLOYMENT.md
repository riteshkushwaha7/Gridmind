# GRIDMIND — Deployment

## Quick Start (Docker Compose)

```bash
cp .env.example .env
# At minimum, set INFLUXDB_TOKEN to a long random string before the first up.
docker compose pull
docker compose build
docker compose up -d
docker compose ps
```

The first run will:
1. Initialise PostgreSQL + InfluxDB (the influx token is baked in on first start — change it later by recreating the volume).
2. Build all four backend services from the shared `./backend` context.
3. Build `data-nodes` and `frontend`.
4. Start data-nodes immediately (begins backfilling 7 days into per-node SQLite).
5. Wait for redis/postgres/influxdb/mlflow to be healthy, then start the ML backends and gateway, then the frontend.

## Environment Setup (zero → running)

```bash
git clone <repo> gridmind && cd gridmind
cp .env.example .env

# Generate a real Influx token
python -c "import secrets; print(secrets.token_urlsafe(48))"  # paste into INFLUXDB_TOKEN

docker compose up -d
docker compose logs -f backend-gateway     # follow gateway boot
```

The frontend is at `http://localhost:3000`, the gateway at `http://localhost:8000`.

## Verifying Services

| Service              | Verify                                                          |
| -------------------- | --------------------------------------------------------------- |
| backend-gateway      | `curl http://localhost:8000/health`                             |
| backend-lstm         | `curl http://localhost:8010/health`                             |
| backend-ppo          | `curl http://localhost:8011/health`                             |
| backend-clustering   | `curl http://localhost:8012/health`                             |
| data-nodes           | `curl http://localhost:8001/health`                             |
| frontend             | open `http://localhost:3000`                                    |
| mlflow               | open `http://localhost:5000`                                    |
| influxdb             | `curl http://localhost:8086/health`                             |
| postgresql           | `docker compose exec postgresql pg_isready -U gridmind`         |
| redis                | `docker compose exec redis redis-cli ping`                      |
| prometheus metrics   | `curl http://localhost:8000/metrics` (any backend service)      |

A healthy gateway response shows `dependencies` for all upstreams as `"ok"`.

## Common Issues

| Symptom                                                                 | Fix                                                                                                                                  |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `backend-lstm` / `ppo` returns `503 model_not_loaded` on inference      | No model in MLflow registry yet. Run `docker compose exec backend-lstm python -m lstm.train` (and `ppo.train` for PPO) once.         |
| InfluxDB rejects writes with `unauthorized`                              | `INFLUXDB_TOKEN` in `.env` differs from the one Influx initialised with. Recreate the influxdb volume or align the token.            |
| Gateway logs `redis connection refused`                                  | Redis container not yet healthy. Wait 20 s; otherwise `docker compose logs redis`.                                                   |
| Frontend shows fallback data ([GRIDMIND API] in console)                 | `NEXT_PUBLIC_API_URL` not set in the frontend container env. Check `.env` and rebuild the frontend image.                            |
| `backend/<svc>/Dockerfile` build fails with `COPY config.py: not found` | Compose `build` block must use `context: ./backend, dockerfile: <svc>/Dockerfile`. Already configured in the committed compose file. |

## Production Notes

- **Recommended cloud:** AWS. EKS for backend services, **ElastiCache for Redis**, **RDS PostgreSQL Multi-AZ**, **InfluxDB Cloud Serverless** (or self-hosted on EBS gp3), **S3** as MLflow artifact root, CloudFront + S3 in front of a Next.js static export.
- **Scaling:** ML backends are stateless behind their `/predict|/schedule|/ranking` endpoints — scale horizontally on request rate. PPO inference is the hottest path; colocate with Redis in the same AZ. Data-nodes is a single process today; before sharding, split routers across multiple replicas keyed by `zone_id`.
- **Secrets:** Move `INFLUXDB_TOKEN`, DB passwords, and any operator JWT signing keys to AWS Secrets Manager / GCP Secret Manager — never commit `.env`.
- **Persistence:** Snapshot InfluxDB nightly to S3; PITR-enable RDS. MLflow backend store should be the same RDS instance to keep experiment metadata transactional.
- **Observability:** Each backend service exposes Prometheus metrics at `/metrics`. Ship JSON logs from stdout to CloudWatch / GCP Logging. Build Grafana dashboards over both data sources.

## Production Checklist

- [ ] All required `.env` values filled (no placeholder tokens)
- [ ] `DEBUG=false`
- [ ] `LOG_LEVEL=INFO`
- [ ] Volumes mounted for `postgres_data`, `influxdb_data`, `mlflow_artifacts`, `redis_data`, `data_nodes_db`
- [ ] Memory limits set on `backend-lstm` and `backend-ppo` (4 GB each in committed compose)
- [ ] Redis persistence enabled (`--appendonly yes` — committed)
- [ ] CORS `FRONTEND_ORIGIN` locked to your real frontend domain (not `localhost:3000`)
- [ ] Initial LSTM and PPO training run completed; models registered in MLflow
- [ ] Influx token rotated and stored in secrets manager
- [ ] All services show `restart: unless-stopped` (committed)
