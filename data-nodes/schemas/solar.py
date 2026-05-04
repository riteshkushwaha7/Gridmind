from __future__ import annotations
from datetime import datetime, time
from pydantic import BaseModel


class SolarSnapshot(BaseModel):
    zone_id: str
    node_id: str = "solar"
    timestamp: datetime
    pv_capacity_kw: float
    irradiance_wm2: float
    temperature_c: float
    cloud_cover_pct: float
    pv_output_kw: float
    pv_efficiency_pct: float
    battery_soc_pct: float
    battery_capacity_kwh: float
    battery_charge_kw: float
    grid_export_kw: float
    self_consumption_kw: float
    forecast_generation_kwh: float
    sunrise: time
    sunset: time
    day_length_hours: float
