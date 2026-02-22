"""Initial schema: parcels and weather_forecasts

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS extension must exist before geometry columns can be created
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "parcels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column(
            "geometry",
            sa.NullType(),  # GeoAlchemy2 type rendered by native DDL
            nullable=False,
        ),
        sa.Column("area_ha", sa.Float(), nullable=False, server_default="0"),
        sa.Column("elevation_m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("slope_deg", sa.Float(), nullable=False, server_default="0"),
        sa.Column("aspect_deg", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Create the geometry column properly via AddGeometryColumn
    op.execute(
        "SELECT AddGeometryColumn('parcels', 'geom_col', 4326, 'POLYGON', 2)"
    )
    # Drop the placeholder NullType column and use the PostGIS-created one
    # Actually: drop the null geometry column and re-add via PostGIS helper
    op.execute("ALTER TABLE parcels DROP COLUMN geometry")
    op.execute(
        "ALTER TABLE parcels ADD COLUMN geometry geometry(POLYGON, 4326) NOT NULL"
        " DEFAULT ST_GeomFromText('POLYGON EMPTY', 4326)"
    )
    op.execute("ALTER TABLE parcels ALTER COLUMN geometry DROP DEFAULT")
    op.execute("DROP TABLE IF EXISTS geometry_columns_temp")  # cleanup helper artefact

    op.create_index("ix_parcels_parcel_id", "parcels", ["parcel_id"], unique=True)
    op.create_index(
        "ix_parcels_geometry",
        "parcels",
        ["geometry"],
        postgresql_using="gist",
    )

    op.create_table(
        "weather_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_2m", sa.Float(), nullable=False),
        sa.Column("precipitation_mm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("wind_speed_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("wind_direction_deg", sa.Float(), nullable=False, server_default="0"),
        sa.Column("relative_humidity_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("solar_radiation_wm2", sa.Float(), nullable=False, server_default="0"),
        sa.Column("raw_temperature_2m", sa.Float(), nullable=False),
        sa.Column("correction_delta_t", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(64), nullable=False, server_default="unknown"),
        sa.Column("zarr_path", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parcel_id"], ["parcels.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_weather_forecasts_parcel_id", "weather_forecasts", ["parcel_id"]
    )
    op.create_index(
        "ix_weather_forecasts_valid_time", "weather_forecasts", ["valid_time"]
    )


def downgrade() -> None:
    op.drop_table("weather_forecasts")
    op.drop_table("parcels")
