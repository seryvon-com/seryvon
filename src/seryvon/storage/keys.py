# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Content addressing and object-key convention (SIC doc 03 §8).

Key convention:

    projects/{project_id}/runs/{run_id}/{artifact_type}/{sha256}.{ext}

Keys are derived purely from content + identifiers (no clock, no randomness), so
storing the same payload twice produces the same key — writes are idempotent and
the provenance is reproducible.
"""

from __future__ import annotations

import gzip
import hashlib

from seryvon.models.artifact import ARTIFACT_MEDIA, ArtifactType

# Single path segments only — guards against traversal / injection in keys.
_FORBIDDEN = ("/", "\\", "..")


def sha256_hex(data: bytes) -> str:
    """SHA-256 of the raw (uncompressed) content, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def _safe_segment(value: str, label: str) -> str:
    value = value.strip()
    if not value or any(token in value for token in _FORBIDDEN):
        raise ValueError(f"invalid {label} for object key: {value!r}")
    return value


def build_object_key(
    project_id: str,
    run_id: str,
    artifact_type: ArtifactType,
    sha256: str,
) -> str:
    """Assemble the canonical object key for an artifact."""
    project = _safe_segment(project_id, "project_id")
    run = _safe_segment(run_id, "run_id")
    _, ext = ARTIFACT_MEDIA[artifact_type]
    return f"projects/{project}/runs/{run}/{artifact_type.value}/{sha256}.{ext}"


def gzip_deterministic(data: bytes) -> bytes:
    """Gzip with a fixed mtime so identical input yields identical bytes."""
    return gzip.compress(data, mtime=0)
