from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import SAMPLE_PARCEL_ID, make_mock_forecast


# ---------------------------------------------------------------------------
# GET /forecasts/{parcel_id}/latest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latest_forecast_found(async_client):
    """GET /api/v1/forecasts/{id}/latest should return 200 with forecast data."""
    mock_forecast = make_mock_forecast(parcel_id=SAMPLE_PARCEL_ID)

    async def _override_db():
        session = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_forecast
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app
    from app.schemas.forecast import ForecastRead

    app.dependency_overrides[get_db] = _override_db

    with patch("app.api.forecasts.ForecastRead") as MockRead:
        MockRead.model_validate.return_value = ForecastRead(
            id=mock_forecast.id,
            parcel_id=SAMPLE_PARCEL_ID,
            valid_time=datetime(2024, 6, 1, 12, tzinfo=timezone.utc),
            issued_at=datetime(2024, 6, 1, 0, tzinfo=timezone.utc),
            temperature_2m=18.5,
            precipitation_mm=0.0,
            wind_speed_ms=3.2,
            wind_direction_deg=220.0,
            relative_humidity_pct=65.0,
            solar_radiation_wm2=450.0,
            raw_temperature_2m=20.0,
            correction_delta_t=-1.5,
            source="cosmo",
            zarr_path="cosmo/20240601T120000.zarr",
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        response = await async_client.get(f"/api/v1/forecasts/{SAMPLE_PARCEL_ID}/latest")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "cosmo"
    assert data["temperature_2m"] == 18.5


@pytest.mark.asyncio
async def test_get_latest_forecast_not_found(async_client):
    """GET /api/v1/forecasts/{id}/latest should return 404 when no forecast exists."""

    async def _override_db():
        session = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_db
    response = await async_client.get(f"/api/v1/forecasts/{SAMPLE_PARCEL_ID}/latest")
    app.dependency_overrides.clear()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /forecasts/{parcel_id}/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_forecasts(async_client):
    """GET /api/v1/forecasts/{id}/ should return a list of forecasts."""
    mock_forecast = make_mock_forecast(parcel_id=SAMPLE_PARCEL_ID)

    async def _override_db():
        session = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_forecast]
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app
    from app.schemas.forecast import ForecastRead

    app.dependency_overrides[get_db] = _override_db

    with patch("app.api.forecasts.ForecastRead") as MockRead:
        MockRead.model_validate.return_value = ForecastRead(
            id=mock_forecast.id,
            parcel_id=SAMPLE_PARCEL_ID,
            valid_time=datetime(2024, 6, 1, 12, tzinfo=timezone.utc),
            issued_at=datetime(2024, 6, 1, 0, tzinfo=timezone.utc),
            temperature_2m=18.5,
            precipitation_mm=0.0,
            wind_speed_ms=3.2,
            wind_direction_deg=220.0,
            relative_humidity_pct=65.0,
            solar_radiation_wm2=450.0,
            raw_temperature_2m=20.0,
            correction_delta_t=-1.5,
            source="cosmo",
            zarr_path="cosmo/20240601T120000.zarr",
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        response = await async_client.get(f"/api/v1/forecasts/{SAMPLE_PARCEL_ID}/")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_forecasts_empty(async_client):
    """GET /api/v1/forecasts/{id}/ returns empty list when no forecasts exist."""

    async def _override_db():
        session = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_db
    response = await async_client.get(f"/api/v1/forecasts/{SAMPLE_PARCEL_ID}/")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []
