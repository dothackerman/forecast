from __future__ import annotations

import xarray as xr


class ZarrStore:
    """Read/write xarray Datasets as Zarr on S3-compatible object storage."""

    def __init__(self, bucket: str, endpoint_url: str = "") -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url or None
        self._fs = None

    def _get_fs(self) -> "s3fs.S3FileSystem":
        """Lazy-initialise the S3 filesystem."""
        if self._fs is None:
            import s3fs
            from app.config import settings

            self._fs = s3fs.S3FileSystem(
                key=settings.AWS_ACCESS_KEY_ID,
                secret=settings.AWS_SECRET_ACCESS_KEY,
                endpoint_url=self.endpoint_url,
            )
        return self._fs

    def _s3_path(self, key: str) -> str:
        return f"s3://{self.bucket}/{key.lstrip('/')}"

    def write(self, ds: xr.Dataset, key: str) -> None:
        """Write *ds* to a Zarr store at *key* inside the configured bucket.

        Args:
            ds: Dataset to persist.
            key: Key (path) within the bucket, e.g. 'cosmo/2024-01-01T00.zarr'.
        """
        import s3fs

        fs = self._get_fs()
        store = s3fs.S3Map(root=self._s3_path(key), s3=fs, check=False)
        ds.to_zarr(store, mode="w", consolidated=True)

    def read(self, key: str) -> xr.Dataset:
        """Read a Zarr store from S3 and return an xarray Dataset.

        Args:
            key: Key within the bucket.
        """
        import s3fs

        fs = self._get_fs()
        store = s3fs.S3Map(root=self._s3_path(key), s3=fs, check=False)
        return xr.open_zarr(store, consolidated=True)

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all Zarr store keys under *prefix* in the bucket.

        Returns:
            List of keys (relative to bucket root), stripped of the bucket prefix.
        """
        fs = self._get_fs()
        full_prefix = f"{self.bucket}/{prefix.lstrip('/')}"
        try:
            paths = fs.ls(full_prefix, detail=False)
        except FileNotFoundError:
            return []
        # Strip 'bucket/' prefix so callers get bucket-relative keys
        return [p.removeprefix(f"{self.bucket}/") for p in paths]

    def exists(self, key: str) -> bool:
        """Return True if *key* exists in the bucket."""
        fs = self._get_fs()
        return fs.exists(self._s3_path(key))
