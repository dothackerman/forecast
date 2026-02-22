from __future__ import annotations

from datetime import datetime
from typing import Any

import pystac_client


class STACIngestionClient:
    """Client for discovering weather data assets via a STAC API."""

    def __init__(self, api_url: str) -> None:
        self.api_url = api_url
        self._client: pystac_client.Client | None = None

    def _get_client(self) -> pystac_client.Client:
        if self._client is None:
            self._client = pystac_client.Client.open(self.api_url)
        return self._client

    def search_items(
        self,
        bbox: tuple[float, float, float, float],
        datetime_range: tuple[datetime, datetime],
        collections: list[str],
    ) -> list[Any]:
        """Search the STAC catalog and return a list of matched items.

        Args:
            bbox: (lon_min, lat_min, lon_max, lat_max)
            datetime_range: (start, end) as timezone-aware datetimes
            collections: list of STAC collection IDs to search

        Returns:
            List of pystac Item objects
        """
        client = self._get_client()
        dt_str = "{}/{}".format(
            datetime_range[0].isoformat(),
            datetime_range[1].isoformat(),
        )
        search = client.search(
            collections=collections,
            bbox=list(bbox),
            datetime=dt_str,
        )
        return list(search.items())

    def fetch_item_assets(self, item: Any) -> dict[str, str]:
        """Return a mapping of asset key → href URL for a STAC item.

        Args:
            item: a pystac Item

        Returns:
            dict mapping asset role/key to download URL
        """
        return {key: asset.href for key, asset in item.assets.items()}
