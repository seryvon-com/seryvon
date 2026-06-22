# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""S3/MinIO artifact store backend (SIC docs 03 §7-8 + 11).

Same `ArtifactStore` contract as the in-memory backend, backed by any
S3-compatible object store (MinIO in the reference docker-compose, AWS S3 in
production). `boto3` is an optional dependency (extra `[storage]`); importing
this module without it raises a clear error rather than failing elsewhere.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from seryvon.models.artifact import ArtifactRef
from seryvon.storage.base import ArtifactNotFound, ArtifactStore

if TYPE_CHECKING:
    from collections.abc import Mapping


def _require_boto3() -> Any:
    try:
        import boto3
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised via message
        raise RuntimeError(
            "S3ArtifactStore requires the optional 'storage' extra: pip install 'seryvon[storage]'"
        ) from exc
    return boto3


class S3ArtifactStore(ArtifactStore):
    """Artifact store backed by an S3-compatible service (boto3 client)."""

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(bucket)
        self._config = {
            "endpoint_url": endpoint_url,
            "region_name": region_name,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        self.__client: Any | None = client

    @property
    def _client(self) -> Any:
        """Lazily built boto3 client — config alone never requires boto3."""
        if self.__client is None:
            boto3 = _require_boto3()
            self.__client = boto3.client("s3", **self._config)
        return self.__client

    def presigned_url(self, ref: ArtifactRef, expires: timedelta) -> str:
        if not self._exists(ref.object_key):
            raise ArtifactNotFound(ref.object_key)
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": ref.object_key},
            ExpiresIn=int(expires.total_seconds()),
        )
        return url

    def _write(self, object_key: str, payload: bytes) -> None:
        self._client.put_object(Bucket=self.bucket, Key=object_key, Body=payload)

    def _read(self, object_key: str) -> bytes:
        try:
            response: Mapping[str, Any] = self._client.get_object(
                Bucket=self.bucket, Key=object_key
            )
        except Exception as exc:  # normalize backend "missing key" errors
            if _is_missing_key(exc):
                raise ArtifactNotFound(object_key) from exc
            raise
        body: bytes = response["Body"].read()
        return body

    def _exists(self, object_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=object_key)
        except Exception as exc:
            if _is_missing_key(exc):
                return False
            raise
        return True


def _is_missing_key(exc: Exception) -> bool:
    """Whether a boto3 error denotes an absent key (404 / NoSuchKey)."""
    code = (
        getattr(exc, "response", {}).get("Error", {}).get("Code")
        if hasattr(exc, "response")
        else None
    )
    return code in {"404", "NoSuchKey", "NotFound"}
