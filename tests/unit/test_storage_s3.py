# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the S3/MinIO backend via an injected fake client (no boto3/network)."""

from __future__ import annotations

import io
from datetime import timedelta
from typing import Any

import pytest

from seryvon.models.artifact import ArtifactType, Compression
from seryvon.storage import ArtifactNotFound, S3ArtifactStore


class _MissingKey(Exception):
    """Mimics botocore's ClientError shape for an absent key."""

    def __init__(self, code: str = "NoSuchKey") -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3Client:
    """Minimal in-memory stand-in for a boto3 S3 client."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        try:
            data = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise _MissingKey() from exc
        return {"Body": io.BytesIO(data)}

    def head_object(self, *, Bucket: str, Key: str) -> None:
        if (Bucket, Key) not in self.objects:
            raise _MissingKey("404")

    def generate_presigned_url(self, op: str, *, Params: dict[str, str], ExpiresIn: int) -> str:
        return f"https://minio.example/{Params['Bucket']}/{Params['Key']}?exp={ExpiresIn}"


def _store() -> S3ArtifactStore:
    return S3ArtifactStore("seryvon", client=FakeS3Client())


def test_put_get_roundtrip() -> None:
    store = _store()
    data = b"<html>x</html>"
    ref = store.put(data, project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    assert ref.object_key.endswith(f"{ref.sha256}.html")
    assert store.exists(ref)
    assert store.get(ref) == data


def test_compressed_roundtrip() -> None:
    store = _store()
    data = b"y" * 4096
    ref = store.put(
        data, project_id="p", run_id="r", artifact_type=ArtifactType.HTML, compress=True
    )
    assert ref.compression is Compression.GZIP
    assert store.get(ref) == data


def test_missing_key_normalized() -> None:
    store = _store()
    ref = store.put(b"d", project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    other = ref.model_copy(update={"object_key": "projects/p/runs/r/html/missing.html"})
    assert not store.exists(other)
    with pytest.raises(ArtifactNotFound):
        store.get(other)


def test_presigned_url_delegates_to_client() -> None:
    store = _store()
    ref = store.put(b"d", project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    url = store.presigned_url(ref, expires=timedelta(minutes=10))
    assert url == f"https://minio.example/seryvon/{ref.object_key}?exp=600"


def test_presigned_url_missing_raises() -> None:
    store = _store()
    ref = store.put(b"d", project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
    other = ref.model_copy(update={"object_key": "projects/p/runs/r/html/gone.html"})
    with pytest.raises(ArtifactNotFound):
        store.presigned_url(other, expires=timedelta(minutes=10))


def test_missing_boto3_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _no_boto3(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "boto3":
            raise ModuleNotFoundError("No module named 'boto3'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_boto3)
    store = S3ArtifactStore("seryvon", endpoint_url="http://localhost:9000")
    # Config alone is fine (lazy); the error surfaces on first I/O.
    with pytest.raises(RuntimeError, match="seryvon\\[storage\\]"):
        store.put(b"d", project_id="p", run_id="r", artifact_type=ArtifactType.HTML)
