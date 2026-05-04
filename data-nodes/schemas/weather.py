from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class WeatherCondition(str, Enum):
    CLEAR = "CLEAR"
    PARTLY_CLOUDY = "PARTLY_CLOUDY"
    OVERCAST = "OVERCAST"
    RAINY = "RAINY"
    STORMY = "STORMY"


class GridStressWeather(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WeatherSnapshot(BaseModel):
    zone_id: str
    node_id: str = "weather"
    timestamp: datetime
    temperature_c: float
    feels_like_c: float
    humidity_pct: float
    wind_speed_kmh: float
    precipitation_mm: float
    cloud_cover_pct: float
    visibility_km: float
    uv_index: float
    direct_radiation_wm2: float
    diffuse_radiation_wm2: float
    global_radiation_wm2: float
    is_monsoon: bool
    weather_condition: WeatherCondition
    ev_demand_modifier: float
    solar_generation_modifier: float
    grid_stress_weather: GridStressWeather
