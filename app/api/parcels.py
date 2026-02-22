from __future__ import annotations

import uuid
from typing import Any

import geopandas as gpd
from fastapi import APIRouter, HTTPException, Query, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping, shape

from app.api.deps import DBSession
from app.models.parcel import Parcel
from app.schemas.parcel import ParcelCreate, ParcelRead, ParcelUpdate
from sqlalchemy import select

router = APIRouter(prefix="/parcels", tags=["parcels"])


def _geometry_to_wkb(geojson: dict[str, Any]) -> Any:
    """Convert GeoJSON geometry dict to GeoAlchemy2-compatible WKB element.

    Raises:
        HTTPException(422): if the geometry type is not Polygon or MultiPolygon.
    """
    geom = shape(geojson)
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geometry must be Polygon or MultiPolygon, got {geom.geom_type}",
        )
    return from_shape(geom, srid=4326)


def _compute_area_ha(geojson: dict[str, Any]) -> float:
    """Compute area in hectares using an equal-area projection."""
    gdf = gpd.GeoDataFrame(geometry=[shape(geojson)], crs="EPSG:4326")
    gdf_ea = gdf.to_crs("EPSG:3035")  # ETRS89-LAEA Europe
    return float(gdf_ea.geometry.area.iloc[0] / 10_000)


def _parcel_to_schema(parcel: Parcel) -> ParcelRead:
    geom_shape = to_shape(parcel.geometry)
    return ParcelRead(
        id=parcel.id,
        parcel_id=parcel.parcel_id,
        name=parcel.name,
        geometry=mapping(geom_shape),
        area_ha=parcel.area_ha,
        elevation_m=parcel.elevation_m,
        slope_deg=parcel.slope_deg,
        aspect_deg=parcel.aspect_deg,
        created_at=parcel.created_at,
        updated_at=parcel.updated_at,
    )


@router.post("/", response_model=ParcelRead, status_code=status.HTTP_201_CREATED)
async def create_parcel(body: ParcelCreate, db: DBSession) -> ParcelRead:
    area_ha = _compute_area_ha(body.geometry)
    parcel = Parcel(
        parcel_id=body.parcel_id,
        name=body.name,
        geometry=_geometry_to_wkb(body.geometry),
        area_ha=area_ha,
        elevation_m=body.elevation_m,
        slope_deg=body.slope_deg,
        aspect_deg=body.aspect_deg,
    )
    db.add(parcel)
    await db.flush()
    await db.refresh(parcel)
    return _parcel_to_schema(parcel)


@router.get("/{parcel_id}", response_model=ParcelRead)
async def get_parcel(parcel_id: uuid.UUID, db: DBSession) -> ParcelRead:
    result = await db.execute(select(Parcel).where(Parcel.id == parcel_id))
    parcel = result.scalar_one_or_none()
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
    return _parcel_to_schema(parcel)


@router.get("/", response_model=list[ParcelRead])
async def list_parcels(
    db: DBSession,
    bbox: str | None = Query(
        None,
        description="Bounding box filter as 'lon_min,lat_min,lon_max,lat_max'",
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[ParcelRead]:
    stmt = select(Parcel).offset(offset).limit(limit)

    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="bbox must be 'lon_min,lat_min,lon_max,lat_max'",
            )
        try:
            lon_min, lat_min, lon_max, lat_max = (float(v) for v in parts)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="bbox must be 'lon_min,lat_min,lon_max,lat_max'",
            )
        if not (-180 <= lon_min < lon_max <= 180 and -90 <= lat_min < lat_max <= 90):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "bbox coordinates out of range or inverted "
                    "(need lon_min<lon_max, lat_min<lat_max, "
                    "lon in [-180,180], lat in [-90,90])"
                ),
            )
        from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope
        envelope = ST_MakeEnvelope(lon_min, lat_min, lon_max, lat_max, 4326)
        stmt = stmt.where(ST_Intersects(Parcel.geometry, envelope))

    result = await db.execute(stmt)
    parcels = result.scalars().all()
    return [_parcel_to_schema(p) for p in parcels]


@router.patch("/{parcel_id}", response_model=ParcelRead)
async def update_parcel(
    parcel_id: uuid.UUID, body: ParcelUpdate, db: DBSession
) -> ParcelRead:
    result = await db.execute(select(Parcel).where(Parcel.id == parcel_id))
    parcel = result.scalar_one_or_none()
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(parcel, field, value)

    await db.flush()
    await db.refresh(parcel)
    return _parcel_to_schema(parcel)


@router.delete("/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parcel(parcel_id: uuid.UUID, db: DBSession) -> None:
    result = await db.execute(select(Parcel).where(Parcel.id == parcel_id))
    parcel = result.scalar_one_or_none()
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")
    await db.delete(parcel)
