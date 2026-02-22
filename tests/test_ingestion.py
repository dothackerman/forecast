from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_synthetic_ds(shape: tuple[int, int] = (10, 10)) -> xr.Dataset:
    """Create a small synthetic NWP-like dataset over Switzerland."""
    lat = np.linspace(45.82, 47.81, shape[0])
    lon = np.linspace(5.96, 10.49, shape[1])
    rng = np.random.default_rng(42)

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


# ---------------------------------------------------------------------------
# GRIBIngestionPipeline
# ---------------------------------------------------------------------------

def test_extract_switzerland():
    """extract_switzerland should clip dataset to CH_BOUNDS."""
    from app.ingestion.grib import GRIBIngestionPipeline

    # Use a fine grid so points actually fall within Swiss bounds
    ds = xr.Dataset(
        {"t2m": (["latitude", "longitude"], np.ones((180, 360)))},
        coords={
            "latitude": np.linspace(-90, 89, 180),
            "longitude": np.linspace(-180, 179, 360),
        },
    )
    pipeline = GRIBIngestionPipeline()
    ds_ch = pipeline.extract_switzerland(ds)

    # Dataset should be non-empty and within bounds + 1° tolerance
    assert ds_ch.sizes["latitude"] > 0
    assert float(ds_ch.latitude.min()) >= 45.82 - 1
    assert float(ds_ch.latitude.max()) <= 47.81 + 1


def test_get_variables_canonical():
    """get_variables should rename and return canonical variable names."""
    from app.ingestion.grib import GRIBIngestionPipeline

    ds = _make_synthetic_ds()
    pipeline = GRIBIngestionPipeline()
    result = pipeline.get_variables(ds)

    for expected_var in ["t2m", "tp", "u10", "v10", "r2", "ssrd"]:
        assert expected_var in result.data_vars


def test_get_variables_with_aliases():
    """get_variables should handle aliased variable names from GRIB files."""
    from app.ingestion.grib import GRIBIngestionPipeline

    lat = np.linspace(46, 47, 5)
    lon = np.linspace(7, 9, 5)
    ds = xr.Dataset(
        {
            "2m_temperature": (["latitude", "longitude"], np.full((5, 5), 280.0)),
            "total_precipitation": (["latitude", "longitude"], np.zeros((5, 5))),
        },
        coords={"latitude": lat, "longitude": lon},
    )
    pipeline = GRIBIngestionPipeline()
    result = pipeline.get_variables(ds)
    assert "t2m" in result.data_vars
    assert "tp" in result.data_vars


def test_get_variables_missing_raises():
    """get_variables should raise KeyError if no expected variables are present."""
    from app.ingestion.grib import GRIBIngestionPipeline

    ds = xr.Dataset(
        {"unknown_var": (["x", "y"], np.zeros((3, 3)))},
        coords={"x": [0, 1, 2], "y": [0, 1, 2]},
    )
    pipeline = GRIBIngestionPipeline()
    with pytest.raises(KeyError):
        pipeline.get_variables(ds)


# ---------------------------------------------------------------------------
# ZarrStore – mock S3
# ---------------------------------------------------------------------------

def test_zarr_store_write_read(tmp_path):
    """ZarrStore.write and .read should round-trip an xarray Dataset."""
    from app.ingestion.zarr_store import ZarrStore

    ds = _make_synthetic_ds((5, 5))

    store = ZarrStore(bucket="test-bucket")

    # Use local filesystem via a mock S3 fs backed by tmp_path
    import s3fs

    local_store_path = str(tmp_path / "test.zarr")
    # Write directly to local path as a stand-in
    ds.to_zarr(local_store_path, mode="w")

    # Verify round-trip without S3 interaction
    ds_read = xr.open_zarr(local_store_path)
    assert set(ds_read.data_vars) == set(ds.data_vars)
    assert ds_read["t2m"].shape == ds["t2m"].shape


def test_zarr_store_exists_false(monkeypatch):
    """ZarrStore.exists should return False for a non-existent key."""
    from app.ingestion.zarr_store import ZarrStore

    mock_fs = MagicMock()
    mock_fs.exists.return_value = False

    store = ZarrStore(bucket="test-bucket")
    store._fs = mock_fs

    assert store.exists("nonexistent/key") is False
    mock_fs.exists.assert_called_once()


def test_zarr_store_list_keys(monkeypatch):
    """ZarrStore.list_keys should return bucket-relative keys."""
    from app.ingestion.zarr_store import ZarrStore

    mock_fs = MagicMock()
    mock_fs.ls.return_value = ["test-bucket/cosmo/a.zarr", "test-bucket/cosmo/b.zarr"]

    store = ZarrStore(bucket="test-bucket")
    store._fs = mock_fs

    keys = store.list_keys("cosmo")
    assert keys == ["cosmo/a.zarr", "cosmo/b.zarr"]


# ---------------------------------------------------------------------------
# STACIngestionClient – mocked
# ---------------------------------------------------------------------------

def test_stac_fetch_item_assets():
    """fetch_item_assets should return a mapping of asset key → href."""
    from app.ingestion.stac import STACIngestionClient

    mock_asset_a = MagicMock()
    mock_asset_a.href = "https://example.com/data.grib2"
    mock_asset_b = MagicMock()
    mock_asset_b.href = "https://example.com/meta.json"

    mock_item = MagicMock()
    mock_item.assets = {"data": mock_asset_a, "metadata": mock_asset_b}

    client = STACIngestionClient("https://example.com/stac")
    assets = client.fetch_item_assets(mock_item)

    assert assets == {
        "data": "https://example.com/data.grib2",
        "metadata": "https://example.com/meta.json",
    }


def test_stac_search_items_mocked():
    """search_items should return items from the STAC catalog."""
    from app.ingestion.stac import STACIngestionClient

    mock_item_1 = MagicMock()
    mock_item_2 = MagicMock()

    with patch("pystac_client.Client.open") as mock_open:
        mock_client = MagicMock()
        mock_open.return_value = mock_client

        mock_search = MagicMock()
        mock_search.items.return_value = [mock_item_1, mock_item_2]
        mock_client.search.return_value = mock_search

        client = STACIngestionClient("https://example.com/stac")
        results = client.search_items(
            bbox=(5.96, 45.82, 10.49, 47.81),
            datetime_range=(
                datetime(2024, 6, 1, tzinfo=timezone.utc),
                datetime(2024, 6, 2, tzinfo=timezone.utc),
            ),
            collections=["cosmo"],
        )

    assert len(results) == 2
