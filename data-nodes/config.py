"""Static configuration for the data-nodes service."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Literal

# ───── Paths ─────
DATA_DIR = os.getenv("DATA_NODES_DIR", "/data")

# ───── Network ─────
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8001"))
SERVICE_NAME = "data-nodes"

# ───── Redis ─────
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STREAM_MAXLEN = 10_000

STREAMS: dict[str, str] = {
    "ocpp":       "ocpp_events",
    "grid":       "grid_telemetry",
    "solar":      "solar_generation",
    "tariff":     "tariff_signals",
    "ev_session": "ev_analytics",
    "weather":    "weather_data",
}

# ───── Geography ─────
BENGALURU_LAT = 12.9716
BENGALURU_LON = 77.5946
TIMEZONE_OFFSET_HOURS = 5.5  # IST

# ───── External APIs ─────
OPENMETEO_BASE_URL = os.getenv("OPENMETEO_BASE_URL", "https://api.open-meteo.com/v1")

# ───── Backfill ─────
BACKFILL_DAYS = 7

# ───── Tariff (BESCOM-style ToU) ─────
# Tier order matters for next-tier lookup.
TARIFF_SCHEDULE = [
    {"tier": "OFF_PEAK",   "start": "23:00", "end": "06:00", "rate_inr_per_kwh": 4.50},
    {"tier": "MID_PEAK",   "start": "06:00", "end": "17:00", "rate_inr_per_kwh": 7.00},
    {"tier": "PEAK",       "start": "17:00", "end": "21:00", "rate_inr_per_kwh": 9.50},
    {"tier": "SUPER_PEAK", "start": "21:00", "end": "23:00", "rate_inr_per_kwh": 11.00},
]
DEMAND_CHARGE_INR_PER_KW = 250.00
EV_INCENTIVE_OFFPEAK_RATE_INR = 3.50

# ───── Zones ─────
ZoneType = Literal["residential", "commercial", "highway", "mixed"]

@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    type: ZoneType
    chargers: int
    feeder_capacity_kw: float
    transformer_kva: float
    pv_capacity_kw: float
    battery_kwh: float

ZONES: list[Zone] = [
    Zone("Z01", "Indiranagar",     "residential", 32,  900.0, 1200.0, 45.0,  90.0),
    Zone("Z02", "Koramangala",     "residential", 38, 1100.0, 1400.0, 60.0, 120.0),
    Zone("Z03", "HSR Layout",      "residential", 28,  800.0, 1100.0, 40.0,  80.0),
    Zone("Z04", "MG Road",         "commercial",  45, 1800.0, 2200.0, 90.0, 180.0),
    Zone("Z05", "Whitefield",      "commercial",  50, 2000.0, 2500.0, 100.0,200.0),
    Zone("Z06", "Electronic City", "commercial",  42, 1700.0, 2100.0, 85.0, 170.0),
    Zone("Z07", "NICE Road",       "highway",     22,  600.0,  800.0, 30.0,  60.0),
    Zone("Z08", "Tumkur Road",     "highway",     25,  650.0,  850.0, 35.0,  70.0),
    Zone("Z09", "Hosur Road",      "highway",     24,  600.0,  800.0, 30.0,  60.0),
    Zone("Z10", "Yeshwanthpur",    "mixed",       35, 1300.0, 1600.0, 70.0, 140.0),
]
ZONES_BY_ID: dict[str, Zone] = {z.id: z for z in ZONES}

def transformer_limit_kw(zone: Zone) -> float:
    """0.85 of transformer kVA rating, conservative thermal limit."""
    return round(zone.transformer_kva * 0.85, 2)

# ───── OCPP simulation parameters ─────
# (type, rated_kw, weight_in_fleet)
CHARGER_TYPES: list[tuple[str, float, float]] = [
    ("L2_AC_7kW",     7.0,  0.45),
    ("L2_AC_22kW",   22.0,  0.30),
    ("DC_Fast_50kW", 50.0,  0.18),
    ("DC_Fast_100kW",100.0, 0.07),
]
CONNECTOR_FAULT_RATE = 0.03
SESSION_DURATION_MIN: dict[str, tuple[int, int]] = {
    "L2_AC_7kW":     (60, 240),
    "L2_AC_22kW":    (60, 180),
    "DC_Fast_50kW":  (20,  45),
    "DC_Fast_100kW": (20,  35),
}
OCPP_VERSIONS = ["1.6J", "2.0.1"]

# Hourly arrival weights — index = hour of day (0..23)
# Tuned so peak residential evening ≈ 7, commercial midday ≈ 7, highway flat ≈ 1.5
HOURLY_PROFILES: dict[tuple[str, str], list[float]] = {
    ("residential", "weekday"): [
        0.5, 0.3, 0.3, 0.3, 0.3, 0.5, 1.0, 2.0, 4.0, 4.0,
        2.0, 1.5, 1.0, 1.0, 1.0, 1.5, 2.0, 3.0, 6.0, 7.0,
        7.0, 6.0, 3.0, 1.5,
    ],
    ("residential", "weekend"): [
        0.5, 0.3, 0.3, 0.3, 0.3, 0.5, 1.0, 1.5, 2.5, 4.0,
        4.5, 4.5, 4.0, 3.0, 2.0, 2.0, 3.0, 4.5, 5.5, 5.5,
        5.0, 3.0, 2.0, 1.0,
    ],
    ("commercial", "weekday"): [
        0.3, 0.2, 0.2, 0.2, 0.3, 0.5, 1.0, 2.0, 4.0, 6.5,
        7.0, 7.0, 6.5, 6.0, 6.0, 5.5, 4.5, 3.0, 2.5, 2.0,
        1.5, 1.0, 0.5, 0.3,
    ],
    ("commercial", "weekend"): [
        0.3, 0.2, 0.2, 0.2, 0.3, 0.5, 0.8, 1.2, 2.0, 3.5,
        4.0, 4.0, 4.0, 3.5, 3.0, 2.5, 2.0, 2.0, 2.0, 1.5,
        1.0, 0.8, 0.5, 0.3,
    ],
    ("highway", "weekday"): [1.5] * 24,
    ("highway", "weekend"): [2.0] * 24,
    ("mixed", "weekday"): [
        0.5, 0.3, 0.3, 0.3, 0.3, 0.5, 1.0, 2.0, 3.0, 3.5,
        3.5, 3.5, 3.0, 2.5, 2.5, 2.5, 3.0, 4.0, 5.0, 5.5,
        5.0, 3.5, 2.0, 1.0,
    ],
    ("mixed", "weekend"): [
        0.5, 0.3, 0.3, 0.3, 0.3, 0.5, 1.0, 1.5, 2.5, 3.5,
        4.0, 4.0, 4.0, 3.5, 3.0, 2.5, 3.0, 4.0, 4.5, 4.0,
        3.5, 2.5, 1.5, 0.8,
    ],
}
# Multiplier applied to hourly weight → expected arrivals/hour for that zone.
ARRIVAL_SCALE = 2.0

# ───── Grid base load curves (kW, hourly) ─────
BASE_LOAD_PROFILES: dict[str, list[float]] = {
    "residential": [
        40, 40, 40, 40, 45, 55, 70, 90, 100, 95,
        85, 80, 80, 80, 85, 95, 110, 130, 160, 180,
        170, 140, 100, 60,
    ],
    "commercial": [
        50, 45, 45, 45, 50, 60, 80, 110, 140, 155,
        160, 165, 165, 160, 155, 145, 130, 110, 90, 75,
        65, 60, 55, 50,
    ],
    "highway": [
        60, 60, 60, 65, 70, 75, 80, 85, 90, 90,
        90, 90, 90, 90, 90, 95, 100, 100, 95, 90,
        85, 80, 75, 65,
    ],
    "mixed": [
        50, 45, 45, 45, 50, 60, 80, 100, 115, 115,
        110, 110, 110, 110, 110, 115, 125, 135, 145, 145,
        135, 110, 85, 65,
    ],
}

# ───── Tick cadences (seconds) ─────
TICK_OCPP = 30
TICK_GRID = 15 * 60
TICK_SOLAR = 15 * 60
TICK_TARIFF = 15 * 60
TICK_EV = 15 * 60
TICK_WEATHER = 30 * 60
