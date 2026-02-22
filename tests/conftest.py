from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.parcel import Parcel
from app.models.forecast import WeatherForecast

# ---------------------------------------------------------------------------
# Shared GeoJSON fixture
# ---------------------------------------------------------------------------

SAMPLE_POLYGON_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [
            [7.4, 46.9],
            [7.5, 46.9],
            [7.5, 47.0],
            [7.4, 47.0],
            [7.4, 46.9],
        ]
    ],
}

SAMPLE_PARCEL_ID = uuid.uuid4()
SAMPLE_FORECAST_ID = uuid.uuid4()

# ---------------------------------------------------------------------------
# Mock parcel helper
# ---------------------------------------------------------------------------

def make_mock_parcel(
    parcel_id: uuid.UUID | None = None,
    external_id: str = "CH-001",
) -> MagicMock:
    """Create a mock Parcel ORM object with realistic attributes."""
    from geoalchemy2.shape import from_shape
    from shapely.geometry import shape

    parcel_id = parcel_id or SAMPLE_PARCEL_ID
    geom = from_shape(shape(SAMPLE_POLYGON_GEOJSON), srid=4326)

    mock = MagicMock(spec=Parcel)
    mock.id = parcel_id
    mock.parcel_id = external_id
    mock.name = "Test Parcel"
    mock.geometry = geom
    mock.area_ha = 1.23
    mock.elevation_m = 550.0
    mock.slope_deg = 5.0
    mock.aspect_deg = 180.0
    mock.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return mock


def make_mock_forecast(
    forecast_id: uuid.UUID | None = None,
    parcel_id: uuid.UUID | None = None,
) -> MagicMock:
    mock = MagicMock(spec=WeatherForecast)
    mock.id = forecast_id or SAMPLE_FORECAST_ID
    mock.parcel_id = parcel_id or SAMPLE_PARCEL_ID
    mock.valid_time = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)
    mock.issued_at = datetime(2024, 6, 1, 0, tzinfo=timezone.utc)
    mock.temperature_2m = 18.5
    mock.precipitation_mm = 0.0
    mock.wind_speed_ms = 3.2
    mock.wind_direction_deg = 220.0
    mock.relative_humidity_pct = 65.0
    mock.solar_radiation_wm2 = 450.0
    mock.raw_temperature_2m = 20.0
    mock.correction_delta_t = -1.5
    mock.source = "cosmo"
    mock.zarr_path = "cosmo/20240601T120000.zarr"
    mock.created_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return mock


# ---------------------------------------------------------------------------
# Async test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Mock DB session fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session
