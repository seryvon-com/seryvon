# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
"""Tests for SignalBundle convenience accessors."""

from seryvon.models.signals import PageSignals, SignalBundle


def test_signal_bundle_home_is_first_page() -> None:
    first = PageSignals(url="https://example.com/")
    bundle = SignalBundle(
        domain="example.com", pages=[first, PageSignals(url="https://example.com/a")]
    )
    assert bundle.home is first


def test_signal_bundle_home_is_none_without_pages() -> None:
    assert SignalBundle(domain="example.com").home is None
