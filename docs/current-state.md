# Current state of the project

This document summarizes what is implemented in the repository right now.

## Runtime components

- FastAPI application with health endpoint and versioned API routes under `/api/v1`.
- `arq` worker with two production tasks:
  - `ingest_forecast_data`
  - `correct_parcel_forecasts`
- Async SQLAlchemy integration with Postgres/PostGIS.
- Alembic migrations for schema and index management.

## Implemented domain model

### Parcel
- UUID primary key
- external `parcel_id` (unique)
- geometry (`POLYGON`, SRID 4326)
- computed/stored `area_ha`
- terrain metadata (`elevation_m`, `slope_deg`, `aspect_deg`)
- timestamps

### WeatherForecast
- UUID primary key
- foreign key to parcel
- `valid_time`, `issued_at`
- corrected outputs (`temperature_2m`, precipitation, wind, humidity, solar)
- correction metadata (`raw_temperature_2m`, `correction_delta_t`)
- source + optional zarr path
- composite index on (`parcel_id`, `valid_time`)

## Ingestion and correction pipeline status

### Ingestion
Implemented flow:
1. STAC search by source/temporal window/bbox.
2. Asset scan for GRIB-like URLs.
3. GRIB open through `cfgrib` backend.
4. Swiss bounding-box extraction.
5. Variable alias normalization to canonical set.
6. Zarr write to S3-compatible object storage.

### Parcel correction
Implemented flow:
1. Load parcel and locate matching ingested Zarr key.
2. Bilinear interpolation at parcel centroid.
3. Lapse-rate temperature correction.
4. Wind speed/direction derivation from U/V components.
5. Slope/aspect solar correction.
6. Persist `WeatherForecast` row.

## Testing status

Automated tests exist across:
- API routes (`tests/api`)
- ingestion components (`tests/ingestion`)
- spatial correction/terrain logic (`tests/spatial`)
- worker tasks (`tests/worker`)

The tests heavily use mocks/factories and validate core behavior without requiring live external services.
