"""Backend-wide configuration. Read once at import."""
from __future__ import annotations
import os

# ───── Service identity ─────
SERVICE_NAME = os.getenv("SERVICE_NAME", "backend")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ───── Infrastructure URLs ─────
REDIS_URL          = os.getenv("REDIS_URL", "redis://redis:6379/0")
POSTGRES_URL       = os.getenv("POSTGRES_URL", "postgresql://gridmind:gridmind@postgresql:5432/gridmind")
INFLUXDB_URL       = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN     = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG       = os.getenv("INFLUXDB_ORG", "bescom")
INFLUXDB_BUCKET    = os.getenv("INFLUXDB_BUCKET", "gridmind")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

# ───── Inter-service URLs ─────
DATA_NODES_URL = os.getenv("DATA_NODES_URL", "http://data-nodes:8001")
LSTM_URL       = os.getenv("LSTM_URL", "http://backend-lstm:8010")
PPO_URL        = os.getenv("PPO_URL", "http://backend-ppo:8011")
CLUSTERING_URL = os.getenv("CLUSTERING_URL", "http://backend-clustering:8012")
GATEWAY_URL    = os.getenv("GATEWAY_URL", "http://backend-gateway:8000")

# ───── CORS ─────
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# ───── Zones (must match data-nodes/config.py) ─────
ZONES: list[str] = [f"Z{i:02d}" for i in range(1, 11)]

# ───── Redis stream names ─────
STREAMS = {
    "ocpp":       "ocpp_events",
    "grid":       "grid_telemetry",
    "solar":      "solar_generation",
    "tariff":     "tariff_signals",
    "ev_session": "ev_analytics",
    "weather":    "weather_data",
}

# ───── LSTM ─────
LSTM_SEQ_LEN     = 192        # 48h × 4 (15-min res)
LSTM_HORIZON     = 16         # 4h ×  4
LSTM_HIDDEN      = 128
LSTM_DROPOUT     = 0.2
LSTM_LAYERS      = 2
LSTM_LR          = 1e-3
LSTM_BATCH       = 64
LSTM_MAX_EPOCHS  = 100
LSTM_PATIENCE    = 10
LSTM_TRAIN_DAYS  = 30
LSTM_REGISTRY_NAME = "gridmind-lstm-load-forecast"
LSTM_FEATURE_NAMES = [
    "demand_kwh", "base_load_kw", "ev_load_kw", "active_sessions",
    "tariff_rate", "solar_output_kw", "battery_soc",
    "temperature_c", "cloud_cover_pct",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend",
]
LSTM_NUM_FEATURES = len(LSTM_FEATURE_NAMES)
LSTM_ZONE_EMB_DIM = 8

# ───── PPO ─────
PPO_OBS_DIM = 16 + 1 + 10 + 10 + 10 + 10 + 10 + 3   # = 70 (forecast 16, tariff 1, headroom 10, evs 10, soc 10, batt 10, solar 10, calendar 3)
PPO_ACTION_DIM   = len(ZONES)
PPO_EPISODE_LEN  = 96
PPO_TOTAL_TIMESTEPS  = 500_000
PPO_ONLINE_TIMESTEPS = 50_000
PPO_REGISTRY_NAME    = "gridmind-ppo-scheduler"

# Reward weights — tuned empirically on synthetic data;
# raise α for cost-sensitive deployments, β for grid-stressed zones.
PPO_REWARD_ALPHA = float(os.getenv("PPO_REWARD_ALPHA", "0.5"))   # cost
PPO_REWARD_BETA  = float(os.getenv("PPO_REWARD_BETA",  "0.3"))   # peak-load penalty
PPO_REWARD_GAMMA = float(os.getenv("PPO_REWARD_GAMMA", "0.2"))   # energy delivered

# Safety
SAFETY_HEADROOM_FLOOR_PCT = 10.0   # below this → fairness fallback engaged

# ───── Clustering ─────
CLUSTERING_REGISTRY_NAME = "gridmind-zone-scoring"
CLUSTERING_K = 3            # K-Means clusters (HIGH/MEDIUM/LOW priority)
CLUSTERING_DBSCAN_EPS = 0.8
CLUSTERING_DBSCAN_MIN_SAMPLES = 2
CLUSTERING_LOOKBACK_DAYS = 30
SCORE_ALPHA = 0.4   # demand
SCORE_BETA  = 0.3   # grid headroom (inverse — low headroom → high score)
SCORE_GAMMA = 0.3   # existing infra penalty

CHARGER_COST_INR_LAKHS = {
    "L2_AC_22kW":  3.5,
    "DC_Fast_50kW": 12.0,
}

# ───── Gateway cache TTLs (seconds) ─────
CACHE_TTL = {
    "forecast": 300,
    "schedule": 60,
    "zones":    3600,
    "dashboard": 30,
}

# ───── Schedules ─────
LSTM_RETRAIN_HOURS    = 24
PPO_ONLINE_HOURS      = 6
CLUSTERING_REPLAN_DAYS = 7
