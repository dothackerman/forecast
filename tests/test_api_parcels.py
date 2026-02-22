from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    SAMPLE_PARCEL_ID,
    SAMPLE_POLYGON_GEOJSON,
    make_mock_parcel,
)


# ---------------------------------------------------------------------------
# POST /parcels/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_parcel(async_client, mock_db_session):
    """POST /api/v1/parcels/ should return 201 with the created parcel."""
    mock_parcel = make_mock_parcel()

    async def _mock_get_db():
        mock_db_session.refresh.side_effect = lambda obj: setattr(obj, "id", mock_parcel.id) or None
        yield mock_db_session

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _mock_get_db

    payload = {
        "parcel_id": "CH-TEST-001",
        "name": "Test Parcel",
        "geometry": SAMPLE_POLYGON_GEOJSON,
        "elevation_m": 550.0,
        "slope_deg": 5.0,
        "aspect_deg": 180.0,
    }

    with patch("app.api.parcels.Parcel") as MockParcel:
        MockParcel.return_value = mock_parcel
        with patch("app.api.parcels._parcel_to_schema") as mock_schema:
            from app.schemas.parcel import ParcelRead
            from datetime import datetime, timezone

            mock_schema.return_value = ParcelRead(
                id=mock_parcel.id,
                parcel_id="CH-TEST-001",
                name="Test Parcel",
                geometry=SAMPLE_POLYGON_GEOJSON,
                area_ha=1.23,
                elevation_m=550.0,
                slope_deg=5.0,
                aspect_deg=180.0,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
            response = await async_client.post("/api/v1/parcels/", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["parcel_id"] == "CH-TEST-001"
    assert data["elevation_m"] == 550.0


# ---------------------------------------------------------------------------
# GET /parcels/{parcel_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_parcel_found(async_client):
    """GET /api/v1/parcels/{id} should return 200 for an existing parcel."""
    mock_parcel = make_mock_parcel()

    async def _override_db():
        session = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_parcel
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_db

    with patch("app.api.parcels._parcel_to_schema") as mock_schema:
        from app.schemas.parcel import ParcelRead
        from datetime import datetime, timezone

        mock_schema.return_value = ParcelRead(
            id=mock_parcel.id,
            parcel_id="CH-001",
            name="Test Parcel",
            geometry=SAMPLE_POLYGON_GEOJSON,
            area_ha=1.23,
            elevation_m=550.0,
            slope_deg=5.0,
            aspect_deg=180.0,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        response = await async_client.get(f"/api/v1/parcels/{SAMPLE_PARCEL_ID}")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["parcel_id"] == "CH-001"


@pytest.mark.asyncio
async def test_get_parcel_not_found(async_client):
    """GET /api/v1/parcels/{id} should return 404 when parcel does not exist."""

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
    response = await async_client.get(f"/api/v1/parcels/{uuid.uuid4()}")
    app.dependency_overrides.clear()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /parcels/ with bbox filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_parcels_with_bbox(async_client):
    """GET /api/v1/parcels/?bbox=... should return a list."""
    mock_parcel = make_mock_parcel()

    async def _override_db():
        session = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_parcel]
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_db

    with patch("app.api.parcels._parcel_to_schema") as mock_schema:
        from app.schemas.parcel import ParcelRead
        from datetime import datetime, timezone

        mock_schema.return_value = ParcelRead(
            id=mock_parcel.id,
            parcel_id="CH-001",
            name="Test Parcel",
            geometry=SAMPLE_POLYGON_GEOJSON,
            area_ha=1.23,
            elevation_m=550.0,
            slope_deg=5.0,
            aspect_deg=180.0,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        response = await async_client.get(
            "/api/v1/parcels/", params={"bbox": "5.96,45.82,10.49,47.81"}
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_parcels_invalid_bbox(async_client):
    """GET /api/v1/parcels/?bbox=bad should return 422."""

    async def _override_db():
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_db
    response = await async_client.get("/api/v1/parcels/", params={"bbox": "bad"})
    app.dependency_overrides.clear()

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /parcels/{parcel_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_parcel(async_client):
    """DELETE /api/v1/parcels/{id} should return 204."""
    mock_parcel = make_mock_parcel()

    async def _override_db():
        session = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_parcel
        session.execute = AsyncMock(return_value=result)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        yield session

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_db
    response = await async_client.delete(f"/api/v1/parcels/{SAMPLE_PARCEL_ID}")
    app.dependency_overrides.clear()

    assert response.status_code == 204
