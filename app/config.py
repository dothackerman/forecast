from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://forecast:forecast@localhost:5432/forecast"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://forecast:forecast@localhost:5432/forecast"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # S3 / Object storage
    S3_BUCKET: str = "forecast-zarr"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL: str = ""

    # STAC
    STAC_API_URL: str = "https://planetarycomputer.microsoft.com/api/stac/v1"

    # Switzerland bounding box: lon_min, lat_min, lon_max, lat_max
    CH_BOUNDS: tuple[float, float, float, float] = (5.96, 45.82, 10.49, 47.81)


settings = Settings()
