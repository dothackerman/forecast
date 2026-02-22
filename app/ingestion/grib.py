from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
import xarray as xr

from app.config import settings

# Mapping from common GRIB shortName / CF variable names to our canonical names
_VARIABLE_ALIASES: dict[str, str] = {
    # Temperature 2 m
    "t2m": "t2m",
    "2m_temperature": "t2m",
    "TMP_2maboveground": "t2m",
    # Total precipitation
    "tp": "tp",
    "total_precipitation": "tp",
    "APCP_surface": "tp",
    # 10-m wind components
    "u10": "u10",
    "10m_u_component_of_wind": "u10",
    "UGRD_10maboveground": "u10",
    "v10": "v10",
    "10m_v_component_of_wind": "v10",
    "VGRD_10maboveground": "v10",
    # Relative humidity
    "r2": "r2",
    "2m_relative_humidity": "r2",
    "RH_2maboveground": "r2",
    # Surface solar radiation downwards
    "ssrd": "ssrd",
    "surface_solar_radiation_downwards": "ssrd",
    "DSWRF_surface": "ssrd",
}


class GRIBIngestionPipeline:
    """Load, clip and export GRIB2 forecast data for Switzerland."""

    def load_grib_dataset(self, path_or_url: Union[str, Path]) -> xr.Dataset:
        """Load a GRIB2 file using cfgrib backend.

        Args:
            path_or_url: Local path or HTTP URL to the GRIB2 file.

        Returns:
            xarray Dataset with CF-convention variable names.
        """
        ds = xr.open_dataset(
            str(path_or_url),
            engine="cfgrib",
            backend_kwargs={"indexpath": ""},
        )
        return ds

    def extract_switzerland(self, ds: xr.Dataset) -> xr.Dataset:
        """Clip the dataset to the Swiss bounding box.

        Supports datasets with 'latitude'/'longitude' or 'lat'/'lon' coordinate names.
        """
        lon_min, lat_min, lon_max, lat_max = settings.CH_BOUNDS

        # Normalise coordinate names
        lon_name = "longitude" if "longitude" in ds.coords else "lon"
        lat_name = "latitude" if "latitude" in ds.coords else "lat"

        ds_ch = ds.sel(
            {
                lon_name: slice(lon_min, lon_max),
                lat_name: slice(lat_min, lat_max),
            }
        )
        # Handle descending latitude grids
        if ds_ch.sizes.get(lat_name, 1) == 0:
            ds_ch = ds.sel(
                {
                    lon_name: slice(lon_min, lon_max),
                    lat_name: slice(lat_max, lat_min),
                }
            )
        return ds_ch

    def get_variables(self, ds: xr.Dataset) -> xr.Dataset:
        """Extract and rename variables to canonical names (t2m, tp, u10, v10, r2, ssrd).

        Raises:
            KeyError: if none of the expected variables are present.
        """
        rename_map: dict[str, str] = {}
        for var in ds.data_vars:
            canonical = _VARIABLE_ALIASES.get(str(var))
            if canonical and canonical != str(var):
                rename_map[str(var)] = canonical

        if rename_map:
            ds = ds.rename(rename_map)

        desired = {"t2m", "tp", "u10", "v10", "r2", "ssrd"}
        present = desired.intersection(set(ds.data_vars))
        if not present:
            raise KeyError(
                f"No expected variables found in dataset. "
                f"Available: {list(ds.data_vars)}"
            )
        return ds[list(present)]

    def to_zarr(self, ds: xr.Dataset, s3_path: str) -> None:
        """Write an xarray Dataset to a Zarr store on S3.

        Args:
            ds: Dataset to persist.
            s3_path: S3 URI, e.g. 's3://bucket/path/to/store'.
        """
        import s3fs
        from app.config import settings

        fs = s3fs.S3FileSystem(
            key=settings.AWS_ACCESS_KEY_ID,
            secret=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_ENDPOINT_URL or None,
        )
        store = s3fs.S3Map(root=s3_path, s3=fs, check=False)
        ds.to_zarr(store, mode="w", consolidated=True)
