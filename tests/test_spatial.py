from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grid_ds(shape: tuple[int, int] = (20, 20)) -> xr.Dataset:
    lat = np.linspace(45.82, 47.81, shape[0])
    lon = np.linspace(5.96, 10.49, shape[1])
    rng = np.random.default_rng(0)

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


def _make_mock_parcel(elevation_m: float = 1000.0, slope_deg: float = 10.0, aspect_deg: float = 180.0) -> MagicMock:
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Polygon

    poly = Polygon([(7.4, 46.9), (7.5, 46.9), (7.5, 47.0), (7.4, 47.0), (7.4, 46.9)])
    geom = from_shape(poly, srid=4326)

    mock = MagicMock()
    mock.geometry = geom
    mock.elevation_m = elevation_m
    mock.slope_deg = slope_deg
    mock.aspect_deg = aspect_deg
    return mock


# ---------------------------------------------------------------------------
# Lapse-rate correction
# ---------------------------------------------------------------------------

def test_lapse_rate_correction_zero_delta():
    """No elevation difference → no temperature correction."""
    from app.spatial.correction import PhysicsLiteCorrection

    c = PhysicsLiteCorrection()
    assert c.lapse_rate_correction(15.0, 500.0, 500.0) == pytest.approx(15.0)


def test_lapse_rate_correction_higher_elevation():
    """Higher target elevation → lower temperature."""
    from app.spatial.correction import PhysicsLiteCorrection

    c = PhysicsLiteCorrection()
    # +1000 m: −0.0065 × 1000 = −6.5 °C
    result = c.lapse_rate_correction(20.0, 0.0, 1000.0)
    assert result == pytest.approx(20.0 - 6.5, abs=1e-6)


def test_lapse_rate_correction_lower_elevation():
    """Lower target elevation → higher temperature."""
    from app.spatial.correction import PhysicsLiteCorrection

    c = PhysicsLiteCorrection()
    result = c.lapse_rate_correction(5.0, 2000.0, 500.0)
    assert result == pytest.approx(5.0 + 0.0065 * 1500, abs=1e-6)


def test_lapse_rate_correction_custom_rate():
    """Custom lapse rate is applied correctly."""
    from app.spatial.correction import PhysicsLiteCorrection

    c = PhysicsLiteCorrection()
    result = c.lapse_rate_correction(10.0, 0.0, 1000.0, lapse_rate=-0.010)
    assert result == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# interpolate_to_point
# ---------------------------------------------------------------------------

def test_interpolate_to_point_inside_grid():
    """Interpolation inside the grid should return finite values for all variables."""
    from app.spatial.correction import PhysicsLiteCorrection

    ds = _make_grid_ds()
    c = PhysicsLiteCorrection()

    # Central Switzerland
    result = c.interpolate_to_point(ds, lon=8.0, lat=46.8)

    for var in ["t2m", "tp", "u10", "v10", "r2", "ssrd"]:
        assert var in result
        assert math.isfinite(result[var]), f"{var} is not finite"


def test_interpolate_to_point_returns_float():
    """interpolate_to_point values should be plain Python floats."""
    from app.spatial.correction import PhysicsLiteCorrection

    ds = _make_grid_ds()
    c = PhysicsLiteCorrection()
    result = c.interpolate_to_point(ds, lon=7.5, lat=46.5)

    for val in result.values():
        assert isinstance(val, float)


# ---------------------------------------------------------------------------
# Solar correction factor
# ---------------------------------------------------------------------------

def test_solar_correction_flat_surface():
    """Flat surface (slope=0) should yield factor ≈ 1.0."""
    from app.spatial.correction import PhysicsLiteCorrection

    factor = PhysicsLiteCorrection._solar_correction_factor(slope_deg=0.0, aspect_deg=0.0)
    assert factor == pytest.approx(1.0, abs=1e-6)


def test_solar_correction_south_facing():
    """South-facing slope with solar azimuth 180° should be ≥ flat factor."""
    from app.spatial.correction import PhysicsLiteCorrection

    flat = PhysicsLiteCorrection._solar_correction_factor(0.0, 0.0, 40.0, 180.0)
    south = PhysicsLiteCorrection._solar_correction_factor(20.0, 180.0, 40.0, 180.0)
    assert south >= flat - 1e-6  # south-facing gets at least as much radiation


def test_solar_correction_non_negative():
    """Solar correction factor should never be negative."""
    from app.spatial.correction import PhysicsLiteCorrection

    for slope in range(0, 91, 10):
        for aspect in range(0, 360, 45):
            factor = PhysicsLiteCorrection._solar_correction_factor(
                float(slope), float(aspect)
            )
            assert factor >= 0.0


# ---------------------------------------------------------------------------
# correct_forecast – end-to-end
# ---------------------------------------------------------------------------

def test_correct_forecast_returns_expected_keys():
    """correct_forecast should return all expected output fields."""
    from app.spatial.correction import PhysicsLiteCorrection

    ds = _make_grid_ds()
    parcel = _make_mock_parcel(elevation_m=1200.0)

    c = PhysicsLiteCorrection()
    result = c.correct_forecast(ds, parcel, model_grid_elevation=400.0)

    expected_keys = {
        "temperature_2m",
        "raw_temperature_2m",
        "correction_delta_t",
        "precipitation_mm",
        "wind_speed_ms",
        "wind_direction_deg",
        "solar_radiation_wm2",
        "relative_humidity_pct",
    }
    assert expected_keys.issubset(result.keys())


def test_correct_forecast_temperature_is_lower_at_higher_elevation():
    """Temperature should be lower for a high-elevation parcel vs grid elevation."""
    from app.spatial.correction import PhysicsLiteCorrection

    ds = _make_grid_ds()

    c = PhysicsLiteCorrection()
    result_low = c.correct_forecast(ds, _make_mock_parcel(elevation_m=200.0), model_grid_elevation=200.0)
    result_high = c.correct_forecast(ds, _make_mock_parcel(elevation_m=2000.0), model_grid_elevation=200.0)

    assert result_high["temperature_2m"] < result_low["temperature_2m"]


def test_correct_forecast_delta_t_sign():
    """correction_delta_t should be negative when target is higher than grid."""
    from app.spatial.correction import PhysicsLiteCorrection

    ds = _make_grid_ds()
    parcel = _make_mock_parcel(elevation_m=2000.0)

    c = PhysicsLiteCorrection()
    result = c.correct_forecast(ds, parcel, model_grid_elevation=500.0)

    assert result["correction_delta_t"] < 0.0


def test_correct_forecast_wind_speed_non_negative():
    """Wind speed derived from u/v components should always be ≥ 0."""
    from app.spatial.correction import PhysicsLiteCorrection

    ds = _make_grid_ds()
    parcel = _make_mock_parcel()

    c = PhysicsLiteCorrection()
    result = c.correct_forecast(ds, parcel)

    assert result["wind_speed_ms"] >= 0.0


# ---------------------------------------------------------------------------
# TerrainAnalyzer
# ---------------------------------------------------------------------------

def _make_dem_da(rows: int = 20, cols: int = 20) -> xr.DataArray:
    """Create a synthetic DEM DataArray over a small Swiss area."""
    lat = np.linspace(46.9, 47.1, rows)
    lon = np.linspace(7.4, 7.6, cols)
    # Simple elevation: increases north-east (gradient in both dims)
    elev = np.outer(np.linspace(400, 600, rows), np.linspace(1, 1.2, cols))
    return xr.DataArray(
        elev,
        dims=["latitude", "longitude"],
        coords={"latitude": lat, "longitude": lon},
    )


def test_compute_slope_non_negative():
    """Slope values should be ≥ 0 everywhere."""
    from app.spatial.terrain import TerrainAnalyzer

    dem = _make_dem_da()
    ta = TerrainAnalyzer()
    slope = ta.compute_slope(dem)

    assert float(slope.min()) >= 0.0
    assert float(slope.max()) <= 90.0


def test_compute_slope_flat_is_zero():
    """A perfectly flat DEM should produce zero slope."""
    from app.spatial.terrain import TerrainAnalyzer

    lat = np.linspace(46.9, 47.0, 10)
    lon = np.linspace(7.4, 7.5, 10)
    flat_dem = xr.DataArray(
        np.full((10, 10), 500.0),
        dims=["latitude", "longitude"],
        coords={"latitude": lat, "longitude": lon},
    )
    ta = TerrainAnalyzer()
    slope = ta.compute_slope(flat_dem)

    np.testing.assert_allclose(slope.values, 0.0, atol=1e-9)


def test_compute_aspect_range():
    """Aspect values should be in [0, 360)."""
    from app.spatial.terrain import TerrainAnalyzer

    dem = _make_dem_da()
    ta = TerrainAnalyzer()
    aspect = ta.compute_aspect(dem)

    assert float(aspect.min()) >= 0.0
    assert float(aspect.max()) < 360.0


def test_get_elevation_returns_float():
    """get_elevation should return a scalar float."""
    from app.spatial.terrain import TerrainAnalyzer

    dem = _make_dem_da()
    ta = TerrainAnalyzer()
    elev = ta.get_elevation(7.5, 47.0, dem)

    assert isinstance(elev, float)
    assert elev > 0.0
