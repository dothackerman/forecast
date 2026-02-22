"""Reusable test factories and synthetic data builders.

Import these in any test module instead of redefining helpers locally:

    from tests.factories import make_mock_parcel, make_synthetic_ds, make_grid_ds
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import xarray as xr

from app.models.forecast import WeatherForecast
from app.models.parcel import Parcel

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SAMPLE_POLYGON_GEOJSON: dict = {
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
# Mock ORM objects
# ---------------------------------------------------------------------------

def make_mock_parcel(
    parcel_id: uuid.UUID | None = None,
    external_id: str = "CH-001",
    elevation_m: float = 550.0,
    slope_deg: float = 5.0,
    aspect_deg: float = 180.0,
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
    mock.elevation_m = elevation_m
    mock.slope_deg = slope_deg
    mock.aspect_deg = aspect_deg
    mock.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return mock


def make_mock_forecast(
    forecast_id: uuid.UUID | None = None,
    parcel_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock WeatherForecast ORM object."""
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
# Synthetic xarray datasets
# ---------------------------------------------------------------------------

def make_synthetic_ds(shape: tuple[int, int] = (10, 10), seed: int = 42) -> xr.Dataset:
    """Create a small synthetic NWP-like dataset over Switzerland."""
    lat = np.linspace(45.82, 47.81, shape[0])
    lon = np.linspace(5.96, 10.49, shape[1])
    rng = np.random.default_rng(seed)

    return xr.Dataset(
        {
            "t2m": (["latitude", "longitude"], 285.0 + rng.normal(0, 2, shape)),
            "tp": (["latitude", "longitude"], rng.uniform(0, 5, shape)),
            "u10": (["latitude", "longitude"], rng.normal(0, 3, shape)),
            "v10": (["latitude", "longitude"], rng.normal(0, 3, shape)),
            "r2": (["latitude", "longitude"], rng.uniform(40, 95, shape)),
            "ssrd": (["latitude", "longitude"], rng.uniform(0, 800, shape)),
        },
        coords={"latitude": lat, "longitude": lon},
    )


def make_grid_ds(shape: tuple[int, int] = (20, 20), seed: int = 0) -> xr.Dataset:
    """Create a synthetic NWP grid dataset for spatial correction tests."""
    lat = np.linspace(45.82, 47.81, shape[0])
    lon = np.linspace(5.96, 10.49, shape[1])
    rng = np.random.default_rng(seed)

    return xr.Dataset(
        {
            "t2m": (["latitude", "longitude"], 285.0 + rng.normal(0, 1, shape)),
            "tp": (["latitude", "longitude"], rng.uniform(0, 2, shape)),
            "u10": (["latitude", "longitude"], rng.normal(2, 1, shape)),
            "v10": (["latitude", "longitude"], rng.normal(-1, 1, shape)),
            "r2": (["latitude", "longitude"], rng.uniform(50, 90, shape)),
            "ssrd": (["latitude", "longitude"], rng.uniform(100, 600, shape)),
        },
        coords={"latitude": lat, "longitude": lon},
    )


def make_dem_da(rows: int = 20, cols: int = 20) -> xr.DataArray:
    """Create a synthetic DEM DataArray over a small Swiss area."""
    lat = np.linspace(46.9, 47.1, rows)
    lon = np.linspace(7.4, 7.6, cols)
    elev = np.outer(np.linspace(400, 600, rows), np.linspace(1, 1.2, cols))
    return xr.DataArray(
        elev,
        dims=["latitude", "longitude"],
        coords={"latitude": lat, "longitude": lon},
    )
