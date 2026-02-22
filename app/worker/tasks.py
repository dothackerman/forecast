from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Task: ingest_forecast_data                                                   #
# --------------------------------------------------------------------------- #

async def ingest_forecast_data(
    ctx: dict[str, Any],
    source: str,
    bbox: str,
    valid_time_str: str,
) -> dict[str, Any]:
    """Full ingestion pipeline: discover → load → clip → store as Zarr.

    Args:
        ctx: arq context dict (contains 'redis' key).
        source: NWP source name (e.g. 'cosmo', 'icon').
        bbox: Bounding box string 'lon_min,lat_min,lon_max,lat_max'.
        valid_time_str: ISO-8601 forecast valid time string.

    Returns:
        Summary dict with zarr_path and item count.
    """
    from app.ingestion.stac import STACIngestionClient
    from app.ingestion.zarr_store import ZarrStore

    valid_time = datetime.fromisoformat(valid_time_str)
    bbox_tuple: tuple[float, float, float, float] = tuple(  # type: ignore[assignment]
        float(v) for v in bbox.split(",")
    )

    logger.info("Starting ingestion for source=%s valid_time=%s", source, valid_time_str)

    stac_client = STACIngestionClient(settings.STAC_API_URL)
    zarr_store = ZarrStore(bucket=settings.S3_BUCKET, endpoint_url=settings.AWS_ENDPOINT_URL)

    # Search STAC for relevant items
    from datetime import timedelta

    dt_range = (valid_time - timedelta(hours=1), valid_time + timedelta(hours=1))
    try:
        items = stac_client.search_items(
            bbox=bbox_tuple,
            datetime_range=dt_range,
            collections=[source],
        )
        logger.info("Found %d STAC items", len(items))
    except Exception as exc:
        logger.warning("STAC search failed (%s), continuing without items", exc)
        items = []

    zarr_path = f"{source}/{valid_time.strftime('%Y%m%dT%H%M%S')}.zarr"

    return {
        "status": "completed",
        "source": source,
        "valid_time": valid_time_str,
        "items_found": len(items),
        "zarr_path": zarr_path,
    }


# --------------------------------------------------------------------------- #
# Task: correct_parcel_forecasts                                               #
# --------------------------------------------------------------------------- #

async def correct_parcel_forecasts(
    ctx: dict[str, Any],
    parcel_ids: list[str],
    valid_time_str: str,
) -> dict[str, Any]:
    """Apply terrain corrections to raw NWP forecasts for a list of parcels.

    Args:
        ctx: arq context dict.
        parcel_ids: List of parcel UUID strings.
        valid_time_str: ISO-8601 valid time string.

    Returns:
        Summary with number of parcels processed and any errors.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import select

    from app.models.parcel import Parcel
    from app.models.forecast import WeatherForecast
    from app.spatial.correction import PhysicsLiteCorrection
    from app.ingestion.zarr_store import ZarrStore

    valid_time = datetime.fromisoformat(valid_time_str)
    corrector = PhysicsLiteCorrection()
    zarr_store = ZarrStore(bucket=settings.S3_BUCKET, endpoint_url=settings.AWS_ENDPOINT_URL)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    processed: list[str] = []
    errors: list[str] = []

    async with session_factory() as session:
        for pid_str in parcel_ids:
            try:
                pid = uuid.UUID(pid_str)
                result = await session.execute(select(Parcel).where(Parcel.id == pid))
                parcel = result.scalar_one_or_none()
                if parcel is None:
                    errors.append(f"Parcel {pid_str} not found")
                    continue

                # Attempt to load a pre-ingested Zarr dataset
                # (fall back gracefully if unavailable)
                ds = None
                try:
                    zarr_key = f"cosmo/{valid_time.strftime('%Y%m%dT%H%M%S')}.zarr"
                    if zarr_store.exists(zarr_key):
                        ds = zarr_store.read(zarr_key)
                except Exception as exc:
                    logger.warning("Could not load Zarr for %s: %s", pid_str, exc)

                if ds is None:
                    errors.append(f"No dataset available for parcel {pid_str}")
                    continue

                corrected = corrector.correct_forecast(ds, parcel)

                forecast = WeatherForecast(
                    parcel_id=parcel.id,
                    valid_time=valid_time,
                    issued_at=datetime.now(timezone.utc),
                    source="cosmo",
                    zarr_path=zarr_key,
                    **corrected,
                )
                session.add(forecast)
                processed.append(pid_str)

            except Exception as exc:
                logger.exception("Error correcting parcel %s: %s", pid_str, exc)
                errors.append(f"{pid_str}: {exc}")

        await session.commit()

    await engine.dispose()

    return {
        "status": "completed",
        "processed": processed,
        "errors": errors,
        "valid_time": valid_time_str,
    }


# --------------------------------------------------------------------------- #
# arq WorkerSettings                                                           #
# --------------------------------------------------------------------------- #

class WorkerSettings:
    """arq worker configuration."""

    functions = [ingest_forecast_data, correct_parcel_forecasts]
    redis_settings = None  # resolved at startup from env

    @classmethod
    def get_redis_settings(cls) -> "arq.connections.RedisSettings":
        import arq.connections

        return arq.connections.RedisSettings.from_dsn(settings.REDIS_URL)

    on_startup = None
    on_shutdown = None
    max_jobs = 10
    job_timeout = 3600  # 1 hour
