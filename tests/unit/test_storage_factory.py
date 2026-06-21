# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the artifact store factory (settings -> backend)."""

from __future__ import annotations

from seryvon.core.config import Settings
from seryvon.storage import InMemoryArtifactStore, S3ArtifactStore, make_artifact_store


def test_in_memory_when_unconfigured() -> None:
    store = make_artifact_store(Settings(_env_file=None))
    assert isinstance(store, InMemoryArtifactStore)
    assert store.bucket == "seryvon-artifacts"


def test_in_memory_honors_bucket_name() -> None:
    store = make_artifact_store(Settings(_env_file=None, S3_BUCKET="custom"))
    assert isinstance(store, InMemoryArtifactStore)
    assert store.bucket == "custom"


def test_s3_when_endpoint_and_bucket_set() -> None:
    settings = Settings(
        _env_file=None,
        S3_ENDPOINT="http://minio:9000",
        S3_BUCKET="seryvon-artifacts",
        S3_ACCESS_KEY="key",
        S3_SECRET_KEY="secret",
        S3_REGION="local",
    )
    store = make_artifact_store(settings)
    assert isinstance(store, S3ArtifactStore)
    assert store.bucket == "seryvon-artifacts"
