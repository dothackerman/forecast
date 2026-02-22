from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.forecast import WeatherForecast
from app.schemas.forecast import ForecastRead

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/{parcel_id}/latest", response_model=ForecastRead)
async def get_latest_forecast(parcel_id: uuid.UUID, db: DBSession) -> ForecastRead:
    result = await db.execute(
        select(WeatherForecast)
        .where(WeatherForecast.parcel_id == parcel_id)
        .order_by(WeatherForecast.valid_time.desc())
        .limit(1)
    )
    forecast = result.scalar_one_or_none()
    if forecast is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast found for this parcel",
        )
    return ForecastRead.model_validate(forecast)


@router.get("/{parcel_id}/", response_model=list[ForecastRead])
async def list_forecasts(
    parcel_id: uuid.UUID,
    db: DBSession,
    limit: int = Query(48, ge=1, le=500),
    offset: int = Query(0, ge=0),
    from_time: datetime | None = Query(None, description="ISO-8601 start time filter"),
    to_time: datetime | None = Query(None, description="ISO-8601 end time filter"),
) -> list[ForecastRead]:
    stmt = (
        select(WeatherForecast)
        .where(WeatherForecast.parcel_id == parcel_id)
        .order_by(WeatherForecast.valid_time.asc())
        .offset(offset)
        .limit(limit)
    )
    if from_time:
        stmt = stmt.where(WeatherForecast.valid_time >= from_time)
    if to_time:
        stmt = stmt.where(WeatherForecast.valid_time <= to_time)

    result = await db.execute(stmt)
    forecasts = result.scalars().all()
    return [ForecastRead.model_validate(f) for f in forecasts]


@router.post("/trigger-ingestion", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(
    source: str = Query("cosmo", description="NWP source name"),
    bbox: str = Query(
        "5.96,45.82,10.49,47.81",
        description="Bounding box as lon_min,lat_min,lon_max,lat_max",
    ),
    valid_time: datetime = Query(..., description="Forecast valid time (ISO-8601)"),
) -> dict[str, str]:
    """Enqueue a background ingestion job via arq."""
    try:
        import arq
        from app.config import settings

        redis = await arq.create_pool(
            arq.connections.RedisSettings.from_dsn(settings.REDIS_URL)
        )
        await redis.enqueue_job(
            "ingest_forecast_data",
            source,
            bbox,
            valid_time.isoformat(),
        )
        await redis.aclose()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not enqueue ingestion job: {exc}",
        ) from exc

    return {"status": "accepted", "source": source, "valid_time": valid_time.isoformat()}
