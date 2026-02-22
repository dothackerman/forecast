from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, String, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"
    __table_args__ = (
        Index("ix_weather_forecasts_parcel_time", "parcel_id", "valid_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    valid_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Terrain-corrected values
    temperature_2m: Mapped[float] = mapped_column(Float, nullable=False)
    precipitation_mm: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wind_speed_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wind_direction_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relative_humidity_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    solar_radiation_wm2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Raw values and correction metadata
    raw_temperature_2m: Mapped[float] = mapped_column(Float, nullable=False)
    correction_delta_t: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    source: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    zarr_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    parcel: Mapped["app.models.parcel.Parcel"] = relationship(  # type: ignore[name-defined]
        "Parcel", lazy="select"
    )
