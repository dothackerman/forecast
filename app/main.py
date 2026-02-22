from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.parcels import router as parcels_router
from app.api.forecasts import router as forecasts_router


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Startup: nothing blocking here; Alembic handles migrations separately
    yield
    # Shutdown: dispose the async engine
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="Parcel-Level Weather Forecasting API",
    description=(
        "Physics-lite terrain-corrected weather forecasts for Swiss agricultural parcels."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# TODO: replace wildcard with explicit origin allowlist for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parcels_router, prefix="/api/v1")
app.include_router(forecasts_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
