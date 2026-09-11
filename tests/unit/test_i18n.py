# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for locale normalization and catalog fallback behavior."""

from __future__ import annotations

from seryvon.i18n import get_locale, has_message, normalize_locale, set_locale, t


def test_normalize_locale_handles_missing_regions_and_unknown_values() -> None:
    assert normalize_locale(None) == "en"
    assert normalize_locale(" fr-FR ") == "fr"
    assert normalize_locale("de-DE") == "en"


def test_catalog_lookup_falls_back_to_key_and_english() -> None:
    set_locale("fr")
    assert get_locale() == "fr"
    assert has_message("rec.seo.avg_position")
    assert not has_message("missing.key")
    assert t("missing.key") == "missing.key"


def test_set_locale_defaults_to_english() -> None:
    assert set_locale("") == "en"
    assert get_locale() == "en"
