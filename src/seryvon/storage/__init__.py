# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Object storage for raw collection artifacts (Observe layer, SIC C-P2)."""

from seryvon.storage.base import ArtifactNotFound, ArtifactStore
from seryvon.storage.keys import build_object_key, sha256_hex
from seryvon.storage.memory import InMemoryArtifactStore
from seryvon.storage.s3 import S3ArtifactStore

__all__ = [
    "ArtifactNotFound",
    "ArtifactStore",
    "InMemoryArtifactStore",
    "S3ArtifactStore",
    "build_object_key",
    "sha256_hex",
]
