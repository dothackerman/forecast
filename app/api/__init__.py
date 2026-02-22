from __future__ import annotations

from app.api.parcels import router as parcels_router
from app.api.forecasts import router as forecasts_router

__all__ = ["parcels_router", "forecasts_router"]
