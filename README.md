# Forecast

`forecast` is a backend service for **Swiss parcel-level weather forecasts**.

It combines:
- a FastAPI API for parcel CRUD and forecast retrieval,
- an `arq` worker for ingestion/correction jobs,
- PostGIS for parcel/forecast persistence,
- S3-compatible Zarr storage for intermediate gridded datasets.

The system takes gridded NWP fields (via STAC + GRIB), clips them to Switzerland, interpolates to each parcel centroid, and applies lightweight terrain corrections before storing parcel-level outputs.

## Why this exists

The project aims to deliver practical parcel-level weather estimates from operational NWP data with a relatively small and understandable processing stack.

It is intentionally **physics-lite** and operationally simple.

## What it does today

1. Discover NWP assets through STAC.
2. Load GRIB, clip to CH bounds, normalize variables (`t2m`, `tp`, `u10`, `v10`, `r2`, `ssrd`).
3. Persist clipped data to S3 as Zarr.
4. For each parcel:
   - bilinear interpolation at the parcel centroid,
   - lapse-rate temperature correction from parcel elevation,
   - slope/aspect adjustment of solar radiation,
   - wind speed/direction derived from `u10/v10`.
5. Save corrected values in PostgreSQL.

## Scope and key limitations (important)

This service **does not perform**:
- dynamical downscaling (no nested mesoscale model runs),
- statistical downscaling (no ML/regression bias-correction trained on station history),
- full microclimate or canopy/process simulation.

Because of that, forecast quality is constrained by the parent NWP grid and simplified corrections:
- parcel estimates are point-sampled at centroids, not full parcel-area integrations,
- sub-grid topographic effects are approximated through a constant lapse rate and a simple solar geometry factor,
- precipitation/humidity/wind are largely inherited from the source field (with wind transformed, not dynamically re-simulated),
- no calibrated local bias model is applied per region/season.

Treat outputs as **terrain-adjusted parcel guidance**, not true high-resolution downscaled weather analyses.

## Architecture

- **API process**: `app/main.py` with routers in `app/api/`.
- **Worker process**: `app/worker/tasks.py` (`ingest_forecast_data`, `correct_parcel_forecasts`).
- **Storage**:
  - PostgreSQL/PostGIS for parcels and parcel forecasts,
  - object storage for Zarr datasets.

See `docs/current-state.md`, `docs/api.md`, and `docs/limitations.md` for details.

## Local development

```bash
make setup
make infra
make migrate
make serve
# in another terminal
make worker
```

API docs are then available at `http://localhost:8000/docs`.

## Quality checks

```bash
make lint
make test
```
