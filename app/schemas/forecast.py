from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ForecastCreate(BaseModel):
    parcel_id: uuid.UUID
    valid_time: datetime
    issued_at: datetime
    temperature_2m: float
    precipitation_mm: float = 0.0
    wind_speed_ms: float = 0.0
    wind_direction_deg: float = 0.0
    relative_humidity_pct: float = 0.0
    solar_radiation_wm2: float = 0.0
    raw_temperature_2m: float
    correction_delta_t: float = 0.0
    source: str = "unknown"
    zarr_path: str | None = None


class ForecastRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parcel_id: uuid.UUID
    valid_time: datetime
    issued_at: datetime
    temperature_2m: float
    precipitation_mm: float
    wind_speed_ms: float
    wind_direction_deg: float = Field(description="Wind direction in degrees (0–360)")
    relative_humidity_pct: float
    solar_radiation_wm2: float
    raw_temperature_2m: float
    correction_delta_t: float
    source: str
    zarr_path: str | None
    created_at: datetime
