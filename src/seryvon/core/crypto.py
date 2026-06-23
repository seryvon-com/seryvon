# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""BYOK key encryption helpers (Fernet symmetric encryption).

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Set it as SERYVON_SECRET_KEY. Empty => encryption disabled, /keys endpoints return 503.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(ValueError):
    """Raised when decryption fails (wrong key or corrupted data)."""


def encrypt_value(secret_key: str, plaintext: str) -> bytes:
    """Encrypt a plaintext string with Fernet."""
    return Fernet(secret_key.encode()).encrypt(plaintext.encode("utf-8"))


def decrypt_value(secret_key: str, token: bytes) -> str:
    """Decrypt a Fernet token back to plaintext."""
    try:
        return Fernet(secret_key.encode()).decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise EncryptionError("Decryption failed — wrong key or corrupted token") from exc


def mask_value(value: str) -> str:
    """Return a display-safe masked version: first 4 + '...' + last 4 chars."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
