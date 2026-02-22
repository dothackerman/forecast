from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.factories import make_mock_parcel, make_synthetic_ds


# ---------------------------------------------------------------------------
# correct_parcel_forecasts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correct_parcel_forecasts_success():
    """correct_parcel_forecasts should correct and persist forecasts for valid parcels."""
    from app.worker.tasks import correct_parcel_forecasts

    parcel_id = str(uuid.uuid4())
    mock_parcel = make_mock_parcel(parcel_id=uuid.UUID(parcel_id))
    ds = make_synthetic_ds()

    corrected_values = {
        "temperature_2m": 15.0,
        "raw_temperature_2m": 16.5,
        "correction_delta_t": -1.5,
        "precipitation_mm": 0.5,
        "wind_speed_ms": 3.0,
        "wind_direction_deg": 220.0,
        "relative_humidity_pct": 65.0,
        "solar_radiation_wm2": 400.0,
    }

    # Mock the DB session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_parcel
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    # Mock ZarrStore
    mock_zarr = MagicMock()
    mock_zarr.return_value.exists.return_value = True
    mock_zarr.return_value.read.return_value = ds

    # Mock corrector
    mock_corrector = MagicMock()
    mock_corrector.return_value.correct_forecast.return_value = corrected_values

    with patch("app.worker.tasks.AsyncSessionLocal", return_value=mock_session_ctx), \
         patch("app.worker.tasks.ZarrStore", mock_zarr), \
         patch("app.worker.tasks.PhysicsLiteCorrection", mock_corrector), \
         patch("anyio.to_thread.run_sync", new_callable=lambda: _make_passthrough_run_sync):
        result = await correct_parcel_forecasts(
            ctx={},
            parcel_ids=[parcel_id],
            valid_time_str="2024-06-01T12:00:00+00:00",
            source="cosmo",
        )

    assert result["status"] == "completed"
    assert parcel_id in result["processed"]
    assert result["errors"] == []
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_correct_parcel_forecasts_parcel_not_found():
    """correct_parcel_forecasts reports error for missing parcels."""
    from app.worker.tasks import correct_parcel_forecasts

    parcel_id = str(uuid.uuid4())

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.worker.tasks.AsyncSessionLocal", return_value=mock_session_ctx), \
         patch("app.worker.tasks.ZarrStore"), \
         patch("app.worker.tasks.PhysicsLiteCorrection"):
        result = await correct_parcel_forecasts(
            ctx={},
            parcel_ids=[parcel_id],
            valid_time_str="2024-06-01T12:00:00+00:00",
        )

    assert result["status"] == "completed"
    assert result["processed"] == []
    assert any("not found" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_correct_parcel_forecasts_no_dataset():
    """correct_parcel_forecasts reports error when Zarr dataset is unavailable."""
    from app.worker.tasks import correct_parcel_forecasts

    parcel_id = str(uuid.uuid4())
    mock_parcel = make_mock_parcel(parcel_id=uuid.UUID(parcel_id))

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_parcel
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_zarr = MagicMock()
    mock_zarr.return_value.exists.return_value = False

    with patch("app.worker.tasks.AsyncSessionLocal", return_value=mock_session_ctx), \
         patch("app.worker.tasks.ZarrStore", mock_zarr), \
         patch("app.worker.tasks.PhysicsLiteCorrection"), \
         patch("anyio.to_thread.run_sync", new_callable=lambda: _make_passthrough_run_sync):
        result = await correct_parcel_forecasts(
            ctx={},
            parcel_ids=[parcel_id],
            valid_time_str="2024-06-01T12:00:00+00:00",
        )

    assert result["status"] == "completed"
    assert result["processed"] == []
    assert any("No dataset" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_correct_parcel_forecasts_custom_source():
    """correct_parcel_forecasts uses provided source for zarr key and persistence."""
    from app.worker.tasks import correct_parcel_forecasts

    parcel_id = str(uuid.uuid4())
    mock_parcel = make_mock_parcel(parcel_id=uuid.UUID(parcel_id))

    corrected_values = {
        "temperature_2m": 15.0,
        "raw_temperature_2m": 16.5,
        "correction_delta_t": -1.5,
        "precipitation_mm": 0.5,
        "wind_speed_ms": 3.0,
        "wind_direction_deg": 220.0,
        "relative_humidity_pct": 65.0,
        "solar_radiation_wm2": 400.0,
    }

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_parcel
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_zarr = MagicMock()
    mock_zarr.return_value.exists.return_value = True
    mock_zarr.return_value.read.return_value = make_synthetic_ds()

    mock_corrector = MagicMock()
    mock_corrector.return_value.correct_forecast.return_value = corrected_values

    with patch("app.worker.tasks.AsyncSessionLocal", return_value=mock_session_ctx), \
         patch("app.worker.tasks.ZarrStore", mock_zarr), \
         patch("app.worker.tasks.PhysicsLiteCorrection", mock_corrector), \
         patch("anyio.to_thread.run_sync", new_callable=lambda: _make_passthrough_run_sync):
        result = await correct_parcel_forecasts(
            ctx={},
            parcel_ids=[parcel_id],
            valid_time_str="2024-06-01T12:00:00+00:00",
            source="icon",
        )

    assert result["status"] == "completed"
    assert parcel_id in result["processed"]
    # Verify the forecast was created with the right source
    added_forecast = mock_session.add.call_args[0][0]
    assert added_forecast.source == "icon"
    assert "icon/" in added_forecast.zarr_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_passthrough_run_sync():
    """Create an async mock that calls the function directly (bypassing threads)."""
    async def _run_sync(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    mock = AsyncMock(side_effect=_run_sync)
    return mock
