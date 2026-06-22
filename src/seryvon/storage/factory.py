# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Artifact store selection from settings.

A configured S3/MinIO endpoint + bucket yields an `S3ArtifactStore`; otherwise the
deterministic `InMemoryArtifactStore` is returned (offline default, no artifact
persistence). The rest of the code depends only on the `ArtifactStore` ABC.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from seryvon.storage.base import ArtifactStore
from seryvon.storage.memory import InMemoryArtifactStore
from seryvon.storage.s3 import S3ArtifactStore

if TYPE_CHECKING:
    from seryvon.core.config import Settings


def make_artifact_store(settings: Settings) -> ArtifactStore:
    """Build the artifact store backend implied by `settings`."""
    if settings.s3_endpoint_url and settings.s3_bucket:
        return S3ArtifactStore(
            settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region or None,
            access_key=settings.s3_access_key or None,
            secret_key=settings.s3_secret_key or None,
        )
    bucket = settings.s3_bucket or "seryvon-artifacts"
    return InMemoryArtifactStore(bucket=bucket)
