from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParcelCreate(BaseModel):
    parcel_id: str = Field(..., description="External cadastre or farm identifier")
    name: str | None = Field(None, description="Human-readable name")
    geometry: dict[str, Any] = Field(..., description="GeoJSON polygon geometry")
    elevation_m: float = Field(0.0, ge=0.0, description="Mean elevation in metres")
    slope_deg: float = Field(0.0, ge=0.0, le=90.0, description="Mean slope in degrees")
    aspect_deg: float = Field(0.0, ge=0.0, lt=360.0, description="Aspect / facing direction in degrees")


class ParcelUpdate(BaseModel):
    name: str | None = None
    elevation_m: float | None = Field(None, ge=0.0)
    slope_deg: float | None = Field(None, ge=0.0, le=90.0)
    aspect_deg: float | None = Field(None, ge=0.0, lt=360.0)


class ParcelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parcel_id: str
    name: str | None
    geometry: dict[str, Any]
    area_ha: float
    elevation_m: float
    slope_deg: float
    aspect_deg: float
    created_at: datetime
    updated_at: datetime
