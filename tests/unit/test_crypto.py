# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the BYOK Fernet encryption helpers."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from seryvon.core.crypto import EncryptionError, decrypt_value, encrypt_value, mask_value


@pytest.fixture
def secret_key() -> str:
    return Fernet.generate_key().decode()


def test_encrypt_decrypt_roundtrip(secret_key: str) -> None:
    token = encrypt_value(secret_key, "sk-live-abcdef123456")
    assert isinstance(token, bytes)
    assert decrypt_value(secret_key, token) == "sk-live-abcdef123456"


def test_encrypt_handles_unicode(secret_key: str) -> None:
    plaintext = "clé-byok-émoji-🔑"
    token = encrypt_value(secret_key, plaintext)
    assert decrypt_value(secret_key, token) == plaintext


def test_decrypt_with_wrong_key_raises(secret_key: str) -> None:
    other = Fernet.generate_key().decode()
    token = encrypt_value(secret_key, "secret")
    with pytest.raises(EncryptionError):
        decrypt_value(other, token)


def test_decrypt_corrupted_token_raises(secret_key: str) -> None:
    with pytest.raises(EncryptionError):
        decrypt_value(secret_key, b"not-a-valid-fernet-token")


def test_decrypt_malformed_secret_key_raises() -> None:
    # An invalid Fernet key string (not 32 url-safe base64 bytes) makes Fernet()
    # itself raise ValueError — caught and re-raised as EncryptionError.
    token = encrypt_value(Fernet.generate_key().decode(), "x")
    with pytest.raises(EncryptionError):
        decrypt_value("not-a-fernet-key", token)


def test_mask_value_short_string() -> None:
    assert mask_value("") == ""
    assert mask_value("abc") == "***"
    assert mask_value("abcdefgh") == "********"  # exactly 8 chars => fully masked


def test_mask_value_long_string() -> None:
    assert mask_value("abcdef123456789") == "abcd...6789"


def test_mask_value_never_exposes_middle() -> None:
    secret = "sk-live-abcdefghijklmnop"
    masked = mask_value(secret)
    # The middle (8 chars from the start, last 4 chars from the end) must be hidden.
    assert "efghijkl" not in masked
    assert masked.startswith("sk-l")
    assert masked.endswith("mnop")
