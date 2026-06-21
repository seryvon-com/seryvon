# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Artifact store abstraction (Observe layer, SIC doc 03 §7-8).

`ArtifactStore` is the single interface the rest of the codebase depends on. The
in-memory backend (`InMemoryArtifactStore`) keeps tests and offline runs fully
deterministic; an S3/MinIO backend implements the same contract for production.
Storing is content-addressed (SHA-256) and therefore idempotent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from seryvon.models.artifact import (
    ARTIFACT_MEDIA,
    ArtifactRef,
    ArtifactType,
    Compression,
)
from seryvon.storage.keys import build_object_key, gzip_deterministic, sha256_hex


class ArtifactNotFound(KeyError):
    """Raised when an object key is absent from the store."""


class ArtifactStore(ABC):
    """Content-addressed object store for raw collection artifacts."""

    def __init__(self, bucket: str) -> None:
        self.bucket = bucket

    def put(
        self,
        data: bytes,
        *,
        project_id: str,
        run_id: str,
        artifact_type: ArtifactType,
        compress: bool = False,
        retention: timedelta | None = None,
        now: datetime | None = None,
    ) -> ArtifactRef:
        """Store `data` and return its metadata.

        The SHA-256 (hence the key) is computed over the *uncompressed* bytes, so
        re-storing the same payload always lands on the same key whatever the
        compression. Idempotent: a re-`put` overwrites with identical content.
        """
        sha256 = sha256_hex(data)
        object_key = build_object_key(project_id, run_id, artifact_type, sha256)
        payload = gzip_deterministic(data) if compress else data
        self._write(object_key, payload)

        created_at = now or datetime.now(UTC)
        mime_type, _ = ARTIFACT_MEDIA[artifact_type]
        return ArtifactRef(
            project_id=project_id,
            run_id=run_id,
            type=artifact_type,
            bucket=self.bucket,
            object_key=object_key,
            sha256=sha256,
            mime_type=mime_type,
            size_bytes=len(data),
            compression=Compression.GZIP if compress else Compression.NONE,
            retention_until=(created_at + retention) if retention else None,
            created_at=created_at,
        )

    def get(self, ref: ArtifactRef) -> bytes:
        """Fetch and return the original (decompressed) bytes for `ref`."""
        raw = self._read(ref.object_key)
        if ref.compression is Compression.GZIP:
            import gzip

            return gzip.decompress(raw)
        return raw

    def exists(self, ref: ArtifactRef) -> bool:
        """Whether the object key is present in the store."""
        return self._exists(ref.object_key)

    @abstractmethod
    def presigned_url(self, ref: ArtifactRef, expires: timedelta) -> str:
        """Short-lived signed URL for direct download (SIC doc 03 §6)."""

    @abstractmethod
    def _write(self, object_key: str, payload: bytes) -> None: ...

    @abstractmethod
    def _read(self, object_key: str) -> bytes: ...

    @abstractmethod
    def _exists(self, object_key: str) -> bool: ...
