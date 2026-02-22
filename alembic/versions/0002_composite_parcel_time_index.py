"""Add composite index on weather_forecasts(parcel_id, valid_time)

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-22 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_weather_forecasts_parcel_time",
        "weather_forecasts",
        ["parcel_id", "valid_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_weather_forecasts_parcel_time", table_name="weather_forecasts")
