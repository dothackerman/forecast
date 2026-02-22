# Copilot Instructions — forecast

## Architecture Overview

Parcel-level weather forecasting backend for Swiss agriculture. Two async processes share the same codebase:

- **API** (`app/main.py`) — FastAPI served by uvicorn, all endpoints under `/api/v1`. Routes in `app/api/parcels.py` (CRUD) and `app/api/forecasts.py` (read + trigger ingestion).
- **Worker** (`app/worker/tasks.py`) — arq (async Redis queue) runs two tasks: `ingest_forecast_data` (STAC discovery → GRIB load → Zarr write) and `correct_parcel_forecasts` (read Zarr → terrain-correct → persist `WeatherForecast` rows).

Data flow: **STAC catalog → GRIB file → clip to CH bounds → Zarr on S3 → bilinear interpolation to parcel centroid → lapse-rate & solar corrections → PostgreSQL/PostGIS**.

## Key Conventions

- **Dual DB URLs**: async (`postgresql+asyncpg`) for the API; sync (`postgresql+psycopg2`) for Alembic migrations. Both configured via `app/config.py` (`Settings`).
- **Dependency injection**: DB sessions are injected via `DBSession = Annotated[AsyncSession, Depends(get_db)]` (see `app/api/deps.py`). Always use this alias in route signatures.
- **GeoAlchemy2 ↔ Shapely**: Parcel geometries are stored as WKB (`geoalchemy2.Geometry`). Convert with `from_shape()`/`to_shape()`. See `_geometry_to_wkb()` and `_parcel_to_schema()` in `app/api/parcels.py`.
- **Pydantic v2**: Schemas use `model_config = ConfigDict(from_attributes=True)` and `model_validate()`. No Pydantic v1 patterns (`from_orm`, `class Config`).
- **`from __future__ import annotations`**: Every module uses this — keep it at the top of new files.
- **Canonical NWP variable names**: `t2m`, `tp`, `u10`, `v10`, `r2`, `ssrd`. GRIB aliases are mapped in `app/ingestion/grib._VARIABLE_ALIASES`.
- **Area computation**: Parcel area is computed on the server in EPSG:3035 (ETRS89-LAEA), not accepted from the client.

## Project Layout

| Directory | Purpose |
|---|---|
| `app/models/` | SQLAlchemy 2.0 mapped classes (`Parcel`, `WeatherForecast`). Always import via `app.models`. |
| `app/schemas/` | Pydantic v2 request/response schemas (`*Create`, `*Read`, `*Update`). |
| `app/ingestion/` | GRIB loading (`GRIBIngestionPipeline`), STAC discovery (`STACIngestionClient`), S3 Zarr I/O (`ZarrStore`). |
| `app/spatial/` | `PhysicsLiteCorrection` (lapse-rate, solar, wind derivation) and `TerrainAnalyzer` (DEM slope/aspect). |
| `app/worker/` | arq task definitions and `WorkerSettings`. |
| `alembic/` | Migrations use the sync URL. First migration enables PostGIS and adds geometry columns via raw DDL. |

## Dev Workflow

```bash
# Start infra (PostGIS 16 + Redis 7)
docker compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start API (hot-reload)
uvicorn app.main:app --reload

# Start worker
python -m arq app.worker.tasks.WorkerSettings

# Run tests (no live DB required — tests mock the DB session)
pytest
```

## Testing Patterns

- Tests use **`pytest-asyncio` with `asyncio_mode = "auto"`** — async test functions are detected automatically, no `@pytest.mark.asyncio` decorator needed (though it's used for clarity).
- API tests override `get_db` via `app.dependency_overrides[get_db]` with an async generator yielding a `MagicMock` session. Always clear overrides after: `app.dependency_overrides.clear()`.
- HTTP calls use `httpx.AsyncClient` with `ASGITransport(app=app)` (no live server).
- Spatial/ingestion tests create synthetic `xr.Dataset` grids (see helpers like `_make_synthetic_ds()`, `_make_grid_ds()`) — no real GRIB files needed.
- S3 interactions are mocked by injecting `store._fs = MagicMock()`.

## Adding a New Endpoint

1. Add the Pydantic schema(s) in `app/schemas/`.
2. Add or extend the SQLAlchemy model in `app/models/` and re-export in `__init__.py`.
3. Create the route in `app/api/`, using `DBSession` for the session parameter.
4. Register the router in `app/main.py` with `app.include_router(router, prefix="/api/v1")`.
5. Write a migration: `alembic revision --autogenerate -m "description"`.
6. Add tests mocking the DB session via dependency overrides.
