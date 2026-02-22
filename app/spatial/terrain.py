from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
import xarray as xr


class TerrainAnalyzer:
    """Analyze DEM rasters to extract elevation, slope, and aspect for parcels."""

    def load_dem(self, path_or_url: Union[str, Path]) -> xr.DataArray:
        """Load a DEM raster as an xarray DataArray using rioxarray.

        Args:
            path_or_url: Local path or HTTP URL to a GeoTIFF/COG DEM.

        Returns:
            DataArray with spatial reference information attached.
        """
        import rioxarray  # noqa: F401  # activates rio accessor

        da = xr.open_dataarray(str(path_or_url), engine="rasterio")
        return da

    def get_elevation(self, lon: float, lat: float, dem: xr.DataArray) -> float:
        """Sample the DEM at a single (lon, lat) point.

        Args:
            lon: Longitude in the CRS of *dem* (usually WGS84 decimal degrees).
            lat: Latitude in the CRS of *dem*.
            dem: DataArray returned by :meth:`load_dem`.

        Returns:
            Elevation value at the requested point (metres).
        """
        x_dim = "x" if "x" in dem.dims else "longitude"
        y_dim = "y" if "y" in dem.dims else "latitude"

        val = dem.sel(
            {x_dim: lon, y_dim: lat},
            method="nearest",
        )
        return float(val.values.squeeze())

    def compute_slope(self, dem: xr.DataArray) -> xr.DataArray:
        """Compute terrain slope in degrees from a DEM.

        Uses central-difference gradients in x and y directions.
        Cell spacing is estimated from coordinate differences (degrees → metres
        via a simple approximation for Swiss latitudes).

        Args:
            dem: 2-D DataArray (y, x) or (latitude, longitude).

        Returns:
            DataArray of slope values in degrees, same shape as *dem*.
        """
        data = dem.values.squeeze()
        if data.ndim == 3:
            data = data[0]

        x_dim = "x" if "x" in dem.dims else "longitude"
        y_dim = "y" if "y" in dem.dims else "latitude"

        x_coords = dem[x_dim].values
        y_coords = dem[y_dim].values

        # Approximate cell spacing in metres (Swiss latitudes ~47°)
        dx_deg = float(np.abs(np.diff(x_coords).mean())) if len(x_coords) > 1 else 1e-4
        dy_deg = float(np.abs(np.diff(y_coords).mean())) if len(y_coords) > 1 else 1e-4
        dx_m = dx_deg * 111_320 * np.cos(np.radians(47.0))
        dy_m = dy_deg * 111_320

        dz_dy, dz_dx = np.gradient(data, dy_m, dx_m)
        slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
        slope_deg = np.degrees(slope_rad)

        result = xr.DataArray(slope_deg, coords=dem.squeeze().coords, dims=dem.squeeze().dims)
        return result

    def compute_aspect(self, dem: xr.DataArray) -> xr.DataArray:
        """Compute terrain aspect in degrees (0 = North, clockwise) from a DEM.

        Args:
            dem: 2-D DataArray (y, x) or (latitude, longitude).

        Returns:
            DataArray of aspect values in degrees [0, 360), same shape as *dem*.
        """
        data = dem.values.squeeze()
        if data.ndim == 3:
            data = data[0]

        x_dim = "x" if "x" in dem.dims else "longitude"
        y_dim = "y" if "y" in dem.dims else "latitude"

        x_coords = dem[x_dim].values
        y_coords = dem[y_dim].values

        dx_deg = float(np.abs(np.diff(x_coords).mean())) if len(x_coords) > 1 else 1e-4
        dy_deg = float(np.abs(np.diff(y_coords).mean())) if len(y_coords) > 1 else 1e-4
        dx_m = dx_deg * 111_320 * np.cos(np.radians(47.0))
        dy_m = dy_deg * 111_320

        dz_dy, dz_dx = np.gradient(data, dy_m, dx_m)

        # Aspect: 0° = North, increasing clockwise
        aspect_deg = (np.degrees(np.arctan2(dz_dx, dz_dy)) + 360) % 360

        result = xr.DataArray(aspect_deg, coords=dem.squeeze().coords, dims=dem.squeeze().dims)
        return result

    def analyze_parcel(self, geometry: object, dem: xr.DataArray) -> dict[str, float]:
        """Compute mean elevation, slope, and aspect for a polygon geometry.

        Args:
            geometry: A shapely Polygon or any object with a ``__geo_interface__``.
            dem: DEM DataArray as returned by :meth:`load_dem`.

        Returns:
            Dict with keys 'elevation_m', 'slope_deg', 'aspect_deg'.
        """
        import rioxarray  # noqa: F401
        from shapely.geometry import mapping

        # Clip DEM to parcel bounding box first, then mask
        dem_clipped = dem.squeeze().rio.clip([mapping(geometry)], crs="EPSG:4326", all_touched=True)

        elev_vals = dem_clipped.values.flatten()
        elev_vals = elev_vals[~np.isnan(elev_vals)]

        slope_da = self.compute_slope(dem_clipped)
        aspect_da = self.compute_aspect(dem_clipped)

        slope_vals = slope_da.values.flatten()
        slope_vals = slope_vals[~np.isnan(slope_vals)]

        aspect_vals = aspect_da.values.flatten()
        aspect_vals = aspect_vals[~np.isnan(aspect_vals)]

        return {
            "elevation_m": float(np.mean(elev_vals)) if len(elev_vals) else 0.0,
            "slope_deg": float(np.mean(slope_vals)) if len(slope_vals) else 0.0,
            "aspect_deg": float(np.mean(aspect_vals)) if len(aspect_vals) else 0.0,
        }
