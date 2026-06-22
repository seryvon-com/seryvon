# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Shared settings resolver: env + DB BYOK keys.

Used by both the API layer and Celery workers so that BYOK keys stored in the
database are available wherever an audit or citation task is executed.
"""

from __future__ import annotations

import contextlib

from sqlalchemy.orm import Session

from seryvon.core.config import Settings, get_settings
from seryvon.core.crypto import EncryptionError, decrypt_value
from seryvon.db import repository


def resolve_settings(session: Session) -> Settings:
    """Return a Settings instance with DB BYOK keys merged in.

    Environment variables always take precedence; DB-stored keys fill gaps.
    When ``SERYVON_SECRET_KEY`` is absent, the base env settings are returned
    unchanged (BYOK features are disabled).
    """
    base = get_settings()
    sk = base.secret_key
    if not sk:
        return base
    overrides: dict[str, str] = {}
    for connector, field in repository.CONNECTOR_FIELD.items():
        if not getattr(base, field, ""):
            encrypted = repository.get_key_encrypted(session, connector)
            if encrypted:
                with contextlib.suppress(EncryptionError):
                    overrides[field] = decrypt_value(sk, encrypted)
    return base.model_copy(update=overrides) if overrides else base
