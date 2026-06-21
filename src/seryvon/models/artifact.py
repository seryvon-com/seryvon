# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Artifact metadata model (Observe layer, SIC docs 03 §8 + 05).

An artifact is a heavy, immutable object (raw HTML, HTTP headers, LLM request/
response payloads, render snapshots) stored in an S3/MinIO bucket. PostgreSQL
keeps only the queryable metadata; the object store keeps the bytes. Every
artifact is content-addressed by SHA-256, which makes writes idempotent and the
provenance chain verifiable.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ArtifactType(StrEnum):
    """Kind of raw object captured during collection (SIC doc 05)."""

    HTML = "html"  # raw crawled HTML body
    HTTP_HEADERS = "http_headers"  # response headers (JSON)
    DOM_SNAPSHOT = "dom_snapshot"  # rendered DOM (Playwright)
    SCREENSHOT = "screenshot"  # rendered page screenshot
    LLM_REQUEST = "llm_request"  # provider request payload (citation tracking)
    LLM_RESPONSE = "llm_response"  # provider response payload
    REPORT_JSON = "report_json"  # exported audit report (source of truth)


class Compression(StrEnum):
    """Compression applied to the stored bytes."""

    NONE = "none"
    GZIP = "gzip"


# Canonical MIME type + file extension per artifact type. Centralized so object
# keys stay stable across the codebase (determinism).
ARTIFACT_MEDIA: dict[ArtifactType, tuple[str, str]] = {
    ArtifactType.HTML: ("text/html", "html"),
    ArtifactType.HTTP_HEADERS: ("application/json", "json"),
    ArtifactType.DOM_SNAPSHOT: ("text/html", "html"),
    ArtifactType.SCREENSHOT: ("image/png", "png"),
    ArtifactType.LLM_REQUEST: ("application/json", "json"),
    ArtifactType.LLM_RESPONSE: ("application/json", "json"),
    ArtifactType.REPORT_JSON: ("application/json", "json"),
}


class ArtifactRef(BaseModel):
    """Queryable metadata for one stored artifact (maps to the `artifact` table).

    The bytes live in the object store under `object_key`; this row is the
    PostgreSQL-side handle. `sha256` is over the *uncompressed* content, so the
    same logical payload yields the same key regardless of compression.
    """

    project_id: str
    run_id: str
    type: ArtifactType
    bucket: str
    object_key: str
    sha256: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    compression: Compression = Compression.NONE
    encryption: bool = False
    retention_until: datetime | None = None
    created_at: datetime | None = None
