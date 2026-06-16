# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests de l'extraction de signaux internes."""

from __future__ import annotations

from seryvon.crawler.extract import extract_page_signals


def test_extract_basic_fields(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html, status_code=200)
    assert signals.title is not None
    assert "Seryvon" in signals.title
    assert signals.meta_description is not None
    assert signals.canonical == "https://example.com/"
    assert signals.status_code == 200


def test_extract_headings(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html)
    assert signals.h1_count == 1
    assert signals.headings["h1"] == 1
    assert signals.headings["h2"] == 1


def test_extract_structured_data_types(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html)
    assert "Organization" in signals.structured_data_types


def test_extract_links_and_images(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html)
    assert signals.internal_links == 1
    assert signals.external_links == 1
    assert signals.images_total == 2
    assert signals.images_with_alt == 1


def test_extract_is_deterministic(sample_html: str) -> None:
    """Même HTML -> mêmes signaux (propriété de reproductibilité)."""
    a = extract_page_signals("https://example.com/", sample_html)
    b = extract_page_signals("https://example.com/", sample_html)
    assert a.model_dump() == b.model_dump()


def test_extract_handles_empty_html() -> None:
    signals = extract_page_signals("https://example.com/", "")
    assert signals.title is None
    assert signals.word_count == 0
    assert signals.structured_data_types == []


def test_extract_ignores_malformed_jsonld() -> None:
    html = '<html><head><script type="application/ld+json">{not valid json}</script></head></html>'
    signals = extract_page_signals("https://example.com/", html)
    assert signals.structured_data_types == []
