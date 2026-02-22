from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np
import xarray as xr

if TYPE_CHECKING:
    from app.models.parcel import Parcel

# Standard environmental lapse rate (K/m) — temperature decreases with altitude
STANDARD_LAPSE_RATE: float = -0.0065


class PhysicsLiteCorrection:
    """Apply terrain-based physics-lite corrections to gridded NWP forecasts.

    The correction pipeline:
    1. Bilinearly interpolate the grid to the parcel centroid.
    2. Apply lapse-rate temperature correction based on elevation difference between
       the model grid cell and the actual parcel elevation.
    3. Optionally adjust solar radiation for slope and aspect.
    """

    # ------------------------------------------------------------------ #
    # Core interpolation                                                   #
    # ------------------------------------------------------------------ #

    def interpolate_to_point(
        self, ds: xr.Dataset, lon: float, lat: float
    ) -> dict[str, float]:
        """Bilinearly interpolate all variables in *ds* to (lon, lat).

        Args:
            ds: xarray Dataset with 'latitude'/'lat' and 'longitude'/'lon' coords.
            lon: Target longitude (WGS84).
            lat: Target latitude (WGS84).

        Returns:
            Dict mapping variable name → scalar float value.
        """
        lon_dim = "longitude" if "longitude" in ds.coords else "lon"
        lat_dim = "latitude" if "latitude" in ds.coords else "lat"

        point = ds.interp(
            {lon_dim: lon, lat_dim: lat},
            method="linear",
        )
        return {var: float(point[var].values) for var in ds.data_vars}

    # ------------------------------------------------------------------ #
    # Lapse-rate temperature correction                                    #
    # ------------------------------------------------------------------ #

    def lapse_rate_correction(
        self,
        t_grid: float,
        elev_grid: float,
        elev_target: float,
        lapse_rate: float = STANDARD_LAPSE_RATE,
    ) -> float:
        """Compute terrain-corrected temperature using the environmental lapse rate.

        T_corrected = T_grid + lapse_rate × (elev_target − elev_grid)

        Args:
            t_grid: Temperature at the model grid-cell elevation (°C or K).
            elev_grid: Model grid-cell elevation (m).
            elev_target: Target parcel mean elevation (m).
            lapse_rate: Lapse rate in K/m (default −0.0065 K/m).

        Returns:
            Corrected temperature in the same unit as *t_grid*.
        """
        delta_elev = elev_target - elev_grid
        return t_grid + lapse_rate * delta_elev

    # ------------------------------------------------------------------ #
    # Solar radiation slope/aspect correction                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _solar_correction_factor(
        slope_deg: float,
        aspect_deg: float,
        solar_zenith_deg: float = 40.0,
        solar_azimuth_deg: float = 180.0,
    ) -> float:
        """Compute ratio of incident radiation on a tilted surface vs flat terrain.

        Uses the standard cosine-of-incidence formula:

            cos θ_i = cos(slope) · cos(zenith)
                    + sin(slope) · sin(zenith) · cos(azimuth − aspect)

        Args:
            slope_deg: Surface slope in degrees.
            aspect_deg: Surface aspect (0 = North, 90 = East, …).
            solar_zenith_deg: Solar zenith angle in degrees (default: 40° ≈ midday CH).
            solar_azimuth_deg: Solar azimuth in degrees (default: 180° = South, midday).

        Returns:
            Correction factor ≥ 0.  A value of 1.0 means the tilted surface receives
            the same radiation as flat terrain.
        """
        slope_rad = math.radians(slope_deg)
        aspect_rad = math.radians(aspect_deg)
        zenith_rad = math.radians(solar_zenith_deg)
        azimuth_rad = math.radians(solar_azimuth_deg)

        # Flat surface incidence
        cos_flat = math.cos(zenith_rad)

        # Tilted surface incidence
        cos_tilt = math.cos(slope_rad) * math.cos(zenith_rad) + math.sin(
            slope_rad
        ) * math.sin(zenith_rad) * math.cos(azimuth_rad - aspect_rad)

        if cos_flat <= 0:
            return 0.0
        return max(0.0, cos_tilt / cos_flat)

    # ------------------------------------------------------------------ #
    # Full correction pipeline                                             #
    # ------------------------------------------------------------------ #

    def correct_forecast(
        self,
        ds: xr.Dataset,
        parcel: "Parcel",
        model_grid_elevation: float = 0.0,
    ) -> dict[str, Any]:
        """Run the full correction pipeline for a single parcel.

        Args:
            ds: NWP Dataset containing at minimum 't2m'.  Other variables
                (tp, u10, v10, r2, ssrd) are passed through unchanged.
            parcel: ORM Parcel instance with geometry, elevation_m, slope_deg,
                    aspect_deg.
            model_grid_elevation: Elevation of the NWP grid cell closest to the
                parcel centroid (metres).  Defaults to 0 (sea level).

        Returns:
            Dict with corrected forecast values and correction metadata.
        """
        from geoalchemy2.shape import to_shape

        geom = to_shape(parcel.geometry)
        centroid = geom.centroid
        lon, lat = centroid.x, centroid.y

        # 1. Interpolate to parcel centroid
        raw = self.interpolate_to_point(ds, lon, lat)

        raw_t2m = raw.get("t2m", float("nan"))
        # Convert from Kelvin if value looks like it's in Kelvin
        if raw_t2m > 200:
            raw_t2m_c = raw_t2m - 273.15
        else:
            raw_t2m_c = raw_t2m

        # 2. Lapse-rate temperature correction
        corrected_t2m = self.lapse_rate_correction(
            raw_t2m_c, model_grid_elevation, parcel.elevation_m
        )
        delta_t = corrected_t2m - raw_t2m_c

        # 3. Derive wind speed and direction from components
        u10 = raw.get("u10", 0.0)
        v10 = raw.get("v10", 0.0)
        wind_speed = math.sqrt(u10**2 + v10**2)
        # Meteorological wind direction (FROM direction)
        wind_dir = (270 - math.degrees(math.atan2(v10, u10))) % 360

        # 4. Solar radiation slope/aspect correction
        raw_ssrd = raw.get("ssrd", 0.0)
        solar_factor = self._solar_correction_factor(parcel.slope_deg, parcel.aspect_deg)
        corrected_ssrd = raw_ssrd * solar_factor

        return {
            "temperature_2m": round(corrected_t2m, 4),
            "raw_temperature_2m": round(raw_t2m_c, 4),
            "correction_delta_t": round(delta_t, 4),
            "precipitation_mm": round(raw.get("tp", 0.0), 4),
            "wind_speed_ms": round(wind_speed, 4),
            "wind_direction_deg": round(wind_dir, 2),
            "relative_humidity_pct": round(raw.get("r2", 0.0), 4),
            "solar_radiation_wm2": round(corrected_ssrd, 4),
        }
