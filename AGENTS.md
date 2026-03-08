# AGENTS.md — forecast

## Overview

Swiss parcel-level weather forecasting backend. FastAPI + arq worker, PostGIS, S3 Zarr storage.

## Quick Reference

A `Makefile` provides all common targets:

```bash
make setup          # cp .env.example .env + install dev deps
make infra          # docker compose up -d postgres redis
make migrate        # alembic upgrade head
make serve          # uvicorn app.main:app --reload
make worker         # python -m arq app.worker.tasks.WorkerSettings
make test           # pytest
make lint           # ruff check + ruff format --check
make fix            # ruff check --fix + ruff format
```

## Architecture

Two async processes, one codebase:

1. **API** (`app/main.py`) — FastAPI, routes under `/api/v1`. Routers: `app/api/parcels.py` (CRUD), `app/api/forecasts.py` (read + trigger ingestion).
2. **Worker** (`app/worker/tasks.py`) — arq Redis queue. Tasks: `ingest_forecast_data`, `correct_parcel_forecasts`.

**Data flow**: STAC catalog → GRIB → clip to CH bounds → Zarr on S3 → bilinear interpolation to parcel centroid → lapse-rate & solar corrections → `WeatherForecast` rows in PostgreSQL/PostGIS.

## Critical Conventions

- **`from __future__ import annotations`** at the top of every Python file.
- **Pydantic v2 only**: `ConfigDict(from_attributes=True)`, `model_validate()`. Never use v1 patterns (`from_orm`, `class Config`).
- **DB sessions**: use `DBSession` alias from `app/api/deps.py` (`Annotated[AsyncSession, Depends(get_db)]`). Never instantiate sessions manually in routes.
- **Dual DB URLs**: async `postgresql+asyncpg` for app; sync `postgresql+psycopg2` for Alembic. Configured in `app/config.py`.
- **Geometry handling**: store as WKB via GeoAlchemy2. Convert with `from_shape()` / `to_shape()` (see `app/api/parcels.py`).
- **Area computation**: always server-side in EPSG:3035, never from client input.
- **NWP variable names**: canonical set is `t2m`, `tp`, `u10`, `v10`, `r2`, `ssrd`. Alias mapping in `app/ingestion/grib._VARIABLE_ALIASES`.

## Project Structure

| Path | Role |
|---|---|
| `app/models/` | SQLAlchemy 2.0 models (`Parcel`, `WeatherForecast`). Re-exported in `__init__.py`. |
| `app/schemas/` | Pydantic v2 schemas (`*Create`, `*Read`, `*Update`). |
| `app/api/` | FastAPI routers + `deps.py` (dependency injection). |
| `app/ingestion/` | `GRIBIngestionPipeline`, `STACIngestionClient`, `ZarrStore`. |
| `app/spatial/` | `PhysicsLiteCorrection` (lapse-rate, solar), `TerrainAnalyzer` (DEM slope/aspect). |
| `app/worker/` | arq task functions + `WorkerSettings`. |
| `alembic/` | Migrations. First migration enables PostGIS via raw DDL. |
| `tests/` | Structured by domain: `tests/api/`, `tests/ingestion/`, `tests/spatial/`, `tests/worker/`. |
| `tests/factories.py` | Shared mock builders and synthetic dataset helpers. Import from here instead of redefining locally. |

## Testing Rules

- `pytest-asyncio` with `asyncio_mode = "auto"` — async tests auto-detected.
- Tests organised by domain: `tests/api/`, `tests/ingestion/`, `tests/spatial/`, `tests/worker/`.
- Shared factories in `tests/factories.py` — never redefine helpers locally.
- API tests: override `get_db` with `app.dependency_overrides[get_db]`, yield a `MagicMock` session, always call `app.dependency_overrides.clear()` after.
- HTTP client: `httpx.AsyncClient` with `ASGITransport(app=app)`, no live server.
- Spatial/ingestion: use `make_synthetic_ds()`, `make_grid_ds()`, `make_dem_da()` from `tests.factories`.
- S3: mock by setting `store._fs = MagicMock()`.

## Linting

- **ruff** for linting + formatting. Config in `pyproject.toml` (`[tool.ruff]`).
- Run `make lint` / `make fix`.

## Adding a New Endpoint

1. Schema in `app/schemas/`.
2. Model in `app/models/`, re-export in `__init__.py`.
3. Route in `app/api/` using `DBSession`.
4. Register router in `app/main.py`: `app.include_router(router, prefix="/api/v1")`.
5. Migration: `alembic revision --autogenerate -m "description"`.
6. Tests with mocked DB via dependency overrides.

## Git Discipline (Non-Negotiable)

- Git is the backup. Treat uncommitted local work as at-risk work.
- Commit related changes together as soon as lint/tests are green.
- Push after each clean, meaningful commit (avoid local commit pileups).
- Never mix unrelated changes in one commit.
- Never end a task with relevant local-only commits not pushed.
