from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parcel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=False
    )
    area_ha: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    elevation_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    slope_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    aspect_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
