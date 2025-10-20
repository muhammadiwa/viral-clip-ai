"""Storage service abstractions for interacting with MinIO."""

from __future__ import annotations

from datetime import timedelta
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

from minio import Minio
from minio.error import S3Error

from ..core.config import get_settings


class StorageConfigurationError(RuntimeError):
    """Raised when storage configuration is invalid."""


class MinioStorageService:
    """Lightweight wrapper around MinIO for presigned upload workflows."""

    def __init__(
        self,
        *,
        client: Minio,
        bucket: str,
        upload_expiry_seconds: int,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._upload_expiry = upload_expiry_seconds
        self._ensure_bucket()

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def upload_expiry_seconds(self) -> int:
        return self._upload_expiry

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except S3Error as exc:  # pragma: no cover - network side effect
            raise StorageConfigurationError(
                f"Unable to ensure bucket '{self._bucket}': {exc}"
            ) from exc

    def ensure_bucket(self) -> None:
        """Idempotently create the backing bucket if it does not yet exist."""

        self._ensure_bucket()

    def generate_object_key(
        self,
        *,
        org_id: UUID,
        project_id: UUID,
        suffix: str | None = None,
    ) -> str:
        """Return a deterministic object key for new uploads."""

        suffix_fragment = f"-{suffix}" if suffix else ""
        return f"orgs/{org_id}/projects/{project_id}/{uuid4()}{suffix_fragment}"

    def generate_presigned_put(self, object_key: str) -> str:
        """Generate a presigned PUT URL for direct uploads."""

        self._ensure_bucket()
        return self._client.presigned_put_object(
            self._bucket, object_key, expires=timedelta(seconds=self._upload_expiry)
        )

    def generate_brand_asset_key(
        self, *, org_id: UUID, brand_kit_id: UUID, filename: str | None = None
    ) -> str:
        suffix = Path(filename or "").suffix
        return f"orgs/{org_id}/brand-kits/{brand_kit_id}/{uuid4()}{suffix}"

    def default_upload_headers(self) -> dict[str, str]:
        """Headers clients should send when uploading via the presigned URL."""

        return {"Content-Type": "application/octet-stream"}

    def object_exists(self, object_key: str) -> bool:
        """Return True when the object key exists in storage."""

        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error as exc:  # pragma: no cover - remote dependency
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                return False
            raise

    def download_to_path(self, object_key: str, destination: Path | str) -> Path:
        """Download an object to a local path and return the resulting file path."""

        self._ensure_bucket()
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._client.fget_object(self._bucket, object_key, str(target))
        return target

    def upload_file(
        self,
        object_key: str,
        file_path: Path | str,
        *,
        content_type: str | None = None,
    ) -> None:
        """Upload a local file to the configured bucket."""

        path = Path(file_path)
        if content_type is None:
            content_type = guess_type(path.name)[0] or "application/octet-stream"
        self._ensure_bucket()
        self._client.fput_object(
            self._bucket,
            object_key,
            str(path),
            content_type=content_type,
        )

    def object_uri(self, object_key: str) -> str:
        """Return an s3:// style URI for the provided object key."""

        return f"s3://{self._bucket}/{object_key}"


def build_storage_service() -> MinioStorageService:
    """Instantiate a storage service from application settings."""

    settings = get_settings()
    if not all(
        [
            settings.s3_endpoint_url,
            settings.s3_bucket,
            settings.s3_access_key,
            settings.s3_secret_key,
        ]
    ):
        raise StorageConfigurationError("S3/MinIO environment variables are not fully set")

    parsed = urlparse(str(settings.s3_endpoint_url))
    secure = (
        settings.s3_secure
        if settings.s3_secure is not None
        else parsed.scheme == "https"
    )
    endpoint = parsed.netloc
    client = Minio(
        endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=secure,
        region=settings.s3_region,
    )
    return MinioStorageService(
        client=client,
        bucket=str(settings.s3_bucket),
        upload_expiry_seconds=settings.storage_upload_expiry_seconds,
    )
