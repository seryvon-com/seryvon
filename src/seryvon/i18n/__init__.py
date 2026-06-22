# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Backend message catalog (produced text: recommendations, explanations…).

English is the base locale; French is a fully translated second locale. The
locale is an *audit-time* parameter, not a runtime toggle: produced text is baked
into the report when the audit runs. It is carried through a `ContextVar` so the
pure `Criterion.evaluate(signals, thresholds)` signature stays untouched and
determinism holds (the locale is set deterministically from the audit config).

Looking a key up is pure (a dict access) — safe to call inside `evaluate`. A key
missing from the active locale falls back to English, then to the key itself.
"""

from __future__ import annotations

from contextvars import ContextVar

from seryvon.i18n.catalog import CATALOG

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "fr")

_current_locale: ContextVar[str] = ContextVar("seryvon_locale", default=DEFAULT_LOCALE)


def normalize_locale(locale: str | None) -> str:
    """Coerce an arbitrary locale string to a supported one (default English)."""
    if not locale:
        return DEFAULT_LOCALE
    base = locale.strip().lower().split("-")[0]
    return base if base in SUPPORTED_LOCALES else DEFAULT_LOCALE


def set_locale(locale: str | None) -> str:
    """Set the active locale for produced text; returns the normalized value."""
    normalized = normalize_locale(locale)
    _current_locale.set(normalized)
    return normalized


def get_locale() -> str:
    """The active locale for produced text."""
    return _current_locale.get()


def has_message(key: str) -> bool:
    """Whether `key` exists in the active locale or the English fallback."""
    locale = get_locale()
    return key in CATALOG.get(locale, {}) or key in CATALOG[DEFAULT_LOCALE]


def t(key: str, /, **params: object) -> str:
    """Translate `key` in the active locale, formatting with `params`.

    Falls back to English, then to the key string itself if unknown.
    """
    locale = get_locale()
    table = CATALOG.get(locale, CATALOG[DEFAULT_LOCALE])
    template = table.get(key)
    if template is None:
        template = CATALOG[DEFAULT_LOCALE].get(key, key)
    return template.format(**params) if params else template


__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "get_locale",
    "has_message",
    "normalize_locale",
    "set_locale",
    "t",
]
