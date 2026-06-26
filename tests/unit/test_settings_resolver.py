# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the settings resolver (env + DB BYOK merge, pure, no real DB)."""

from __future__ import annotations

from typing import Any

import pytest
from cryptography.fernet import Fernet

from seryvon.core import settings_resolver
from seryvon.core.config import Settings
from seryvon.core.crypto import encrypt_value
from seryvon.db import repository


class _FakeSession:
    """A no-op session — repository functions are monkeypatched directly."""


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Any:
    """get_settings() is lru_cached: clear it between tests so env changes take effect."""
    from seryvon.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_settings(
    monkeypatch: pytest.MonkeyPatch, *, secret_key: str = "", psi_api_key: str = ""
) -> None:
    """Force a fresh Settings build via env vars (fields use validation_alias).

    `Settings(psi_api_key=...)` is ignored because `psi_api_key` is exposed only
    through `validation_alias="PSI_API_KEY"`. Setting the underlying env var is
    the supported way to seed these fields.
    """
    # Strip every BYOK env var so the test starts from a known-empty baseline.
    for env_var in (
        "PSI_API_KEY",
        "OPR_API_KEY",
        "DATAFORSEO_API_KEY",
        "PERPLEXITY_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "SERP_API_KEY",
        "GSC_SERVICE_ACCOUNT",
        "SERYVON_SECRET_KEY",
    ):
        monkeypatch.delenv(env_var, raising=False)
    if secret_key:
        monkeypatch.setenv("SERYVON_SECRET_KEY", secret_key)
    if psi_api_key:
        monkeypatch.setenv("PSI_API_KEY", psi_api_key)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setattr(settings_resolver, "get_settings", lambda: settings)


def test_no_secret_key_returns_base_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_settings(monkeypatch, secret_key="")
    monkeypatch.setattr(
        repository,
        "get_key_encrypted",
        lambda _s, _c: pytest.fail("DB should not be queried when secret_key is empty"),
    )
    resolved = settings_resolver.resolve_settings(_FakeSession())  # type: ignore[arg-type]
    assert resolved.psi_api_key == ""


def test_db_key_fills_gap_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    sk = Fernet.generate_key().decode()
    _seed_settings(monkeypatch, secret_key=sk, psi_api_key="")

    stored = {"psi": encrypt_value(sk, "from-db-key")}
    monkeypatch.setattr(repository, "get_key_encrypted", lambda _s, c: stored.get(c))
    resolved = settings_resolver.resolve_settings(_FakeSession())  # type: ignore[arg-type]
    assert resolved.psi_api_key == "from-db-key"


def test_env_takes_precedence_over_db(monkeypatch: pytest.MonkeyPatch) -> None:
    sk = Fernet.generate_key().decode()
    _seed_settings(monkeypatch, secret_key=sk, psi_api_key="from-env-key")

    # Even though a DB key exists, the env value wins (the DB is not consulted
    # for fields that already have a value).
    called: list[str] = []

    def _get(_session: Any, connector: str) -> bytes | None:
        called.append(connector)
        return encrypt_value(sk, "from-db-key") if connector == "psi" else None

    monkeypatch.setattr(repository, "get_key_encrypted", _get)
    resolved = settings_resolver.resolve_settings(_FakeSession())  # type: ignore[arg-type]
    assert resolved.psi_api_key == "from-env-key"
    assert "psi" not in called  # short-circuited by the env-takes-precedence guard


def test_unreadable_db_token_is_silently_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """If a DB token cannot be decrypted (wrong key), the gap stays empty (ENF-03)."""
    sk = Fernet.generate_key().decode()
    other = Fernet.generate_key().decode()
    _seed_settings(monkeypatch, secret_key=sk)

    # Token was encrypted with a different key — decryption will fail.
    bad_token = encrypt_value(other, "irrelevant")
    monkeypatch.setattr(
        repository,
        "get_key_encrypted",
        lambda _s, c: bad_token if c == "psi" else None,
    )
    resolved = settings_resolver.resolve_settings(_FakeSession())  # type: ignore[arg-type]
    assert resolved.psi_api_key == ""


def test_no_db_keys_returns_base_object_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no DB key is found for any connector, model_copy is skipped."""
    sk = Fernet.generate_key().decode()
    _seed_settings(monkeypatch, secret_key=sk, psi_api_key="env-only")
    monkeypatch.setattr(repository, "get_key_encrypted", lambda _s, _c: None)
    resolved = settings_resolver.resolve_settings(_FakeSession())  # type: ignore[arg-type]
    assert resolved.psi_api_key == "env-only"
