from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class EventType(str, Enum):
    StartTransaction = "StartTransaction"
    StopTransaction = "StopTransaction"
    StatusNotification = "StatusNotification"
    MeterValues = "MeterValues"


class ConnectorStatus(str, Enum):
    Available = "Available"
    Occupied = "Occupied"
    Faulted = "Faulted"
    Unavailable = "Unavailable"


class ChargerType(str, Enum):
    L2_AC_7kW = "L2_AC_7kW"
    L2_AC_22kW = "L2_AC_22kW"
    DC_Fast_50kW = "DC_Fast_50kW"
    DC_Fast_100kW = "DC_Fast_100kW"


class OCPPVersion(str, Enum):
    v1_6J = "1.6J"
    v2_0_1 = "2.0.1"


class OCPPEvent(BaseModel):
    charger_id: str
    zone_id: str
    node_id: str = "ocpp"
    event_type: EventType
    connector_id: int
    id_tag: str
    meter_start_wh: float
    meter_stop_wh: Optional[float] = None
    timestamp: datetime
    timestamp_start: datetime
    timestamp_stop: Optional[datetime] = None
    duration_minutes: float
    energy_delivered_kwh: Optional[float] = None
    power_kw: float
    connector_status: ConnectorStatus
    soc_start_pct: float
    soc_end_pct: float
    charger_type: ChargerType
    ocpp_version: OCPPVersion
    error_code: Optional[str] = None
