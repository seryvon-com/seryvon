# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""In-memory artifact store — deterministic, offline default.

Backs tests and any run without a configured object store. The presigned URL is a
stable fake (`memory://bucket/key`) so callers can be exercised without network.
"""

from __future__ import annotations

from datetime import timedelta

from seryvon.models.artifact import ArtifactRef
from seryvon.storage.base import ArtifactNotFound, ArtifactStore


class InMemoryArtifactStore(ArtifactStore):
    """Dictionary-backed store keyed by object key."""

    def __init__(self, bucket: str = "seryvon-artifacts") -> None:
        super().__init__(bucket)
        self._objects: dict[str, bytes] = {}

    def presigned_url(self, ref: ArtifactRef, expires: timedelta) -> str:
        if not self._exists(ref.object_key):
            raise ArtifactNotFound(ref.object_key)
        return f"memory://{self.bucket}/{ref.object_key}"

    def _write(self, object_key: str, payload: bytes) -> None:
        self._objects[object_key] = payload

    def _read(self, object_key: str) -> bytes:
        try:
            return self._objects[object_key]
        except KeyError as exc:
            raise ArtifactNotFound(object_key) from exc

    def _exists(self, object_key: str) -> bool:
        return object_key in self._objects
