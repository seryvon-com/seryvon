# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the artifact store (Observe layer, SIC C-P2)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from seryvon.models.artifact import ArtifactType, Compression
from seryvon.storage import (
    ArtifactNotFound,
    InMemoryArtifactStore,
    build_object_key,
    sha256_hex,
)
from seryvon.storage.keys import gzip_deterministic


def _store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore(bucket="test-bucket")


def test_object_key_follows_convention() -> None:
    key = build_object_key("p1", "r1", ArtifactType.HTML, "abc123")
    assert key == "projects/p1/runs/r1/html/abc123.html"


def test_put_is_content_addressed_and_idempotent() -> None:
    store = _store()
    data = b"<html><body>hello</body></html>"
    ref1 = store.put(data, project_id="p1", run_id="r1", artifact_type=ArtifactType.HTML)
    ref2 = store.put(data, project_id="p1", run_id="r1", artifact_type=ArtifactType.HTML)

    assert ref1.sha256 == sha256_hex(data)
    assert ref1.object_key == ref2.object_key
    assert ref1.object_key.endswith(f"{ref1.sha256}.html")
    assert ref1.mime_type == "text/html"
    assert ref1.size_bytes == len(data)
    assert ref1.bucket == "test-bucket"


def test_roundtrip_uncompressed() -> None:
    store = _store()
    data = b'{"k": "v"}'
    ref = store.put(data, project_id="p", run_id="r", artifact_type=ArtifactType.LLM_RESPONSE)
    assert ref.compression is Compression.NONE
    assert store.get(ref) == data
    assert store.exists(ref)


def test_roundtrip_compressed_keeps_same_key() -> None:
    store = _store()
    data = b"x" * 5000
    plain = store.put(data, project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    store_c = _store()
    comp = store_c.put(
        data, project_id="p", run_id="r", artifact_type=ArtifactType.HTML, compress=True
    )
    # Key is over uncompressed content -> identical regardless of compression.
    assert comp.object_key == plain.object_key
    assert comp.compression is Compression.GZIP
    assert comp.size_bytes == len(data)
    assert store_c.get(comp) == data


def test_gzip_is_deterministic() -> None:
    assert gzip_deterministic(b"payload") == gzip_deterministic(b"payload")


def test_get_missing_raises() -> None:
    store = _store()
    ref = store.put(b"data", project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    other = ref.model_copy(update={"object_key": "projects/p/runs/r/html/deadbeef.html"})
    assert not store.exists(other)
    with pytest.raises(ArtifactNotFound):
        store.get(other)


def test_retention_sets_expiry() -> None:
    store = _store()
    ref = store.put(
        b"data",
        project_id="p",
        run_id="r",
        artifact_type=ArtifactType.HTML,
        retention=timedelta(days=30),
    )
    assert ref.retention_until is not None
    assert ref.created_at is not None
    assert (ref.retention_until - ref.created_at) == timedelta(days=30)


def test_presigned_url_is_stable() -> None:
    store = _store()
    ref = store.put(b"data", project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    url = store.presigned_url(ref, expires=timedelta(minutes=5))
    assert url == f"memory://test-bucket/{ref.object_key}"


def test_presigned_url_missing_raises() -> None:
    store = _store()
    ref = store.put(b"data", project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    other = ref.model_copy(update={"object_key": "projects/p/runs/r/html/missing.html"})
    with pytest.raises(ArtifactNotFound):
        store.presigned_url(other, expires=timedelta(minutes=5))


@pytest.mark.parametrize("bad", ["", "  ", "a/b", "..", "a\\b"])
def test_invalid_segments_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        build_object_key(bad, "r", ArtifactType.HTML, "abc")
