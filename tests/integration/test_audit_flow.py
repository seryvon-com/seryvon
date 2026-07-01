# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Integration test of the audit flow (discovery + crawl mocked, no network)."""

from __future__ import annotations

import pytest

from seryvon.core import audit as audit_module
from seryvon.core.audit import run_audit
from seryvon.crawler import extract_page_signals
from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
from seryvon.models.signals import PageSignals


def _fake_discovery() -> DiscoveryResult:
    return DiscoveryResult(
        home_url="https://example.com/",
        origin="https://example.com",
        domain="example.com",
        robots=RobotsTxt.allow_all(),
        robots_found=False,
        crawl_delay=None,
        declared_sitemaps=[],
        sitemap_urls=[],
        sitemap_valid=False,
        home_allowed=True,
        frontier=["https://example.com/"],
    )


@pytest.fixture
def patched_crawl(monkeypatch: pytest.MonkeyPatch, sample_html: str) -> None:
    async def fake_discover(url: str, **kwargs: object) -> DiscoveryResult:
        return _fake_discovery()

    async def fake_crawl(discovery: DiscoveryResult, **kwargs: object) -> list[PageSignals]:
        return [extract_page_signals("https://example.com/", sample_html, status_code=200)]

    monkeypatch.setattr(audit_module, "discover", fake_discover)
    monkeypatch.setattr(audit_module, "crawl_site", fake_crawl)


async def test_full_audit_produces_report(patched_crawl: None) -> None:
    report, _pages = await run_audit("https://example.com")
    assert report.domain == "example.com"
    assert report.tool_version
    assert "seo" in report.pillars
    assert report.pillars["seo"].score > 0  # title present in the sample HTML
    assert report.aso_readiness is not None  # agentic-readiness summary present


async def test_audit_is_deterministic(patched_crawl: None) -> None:
    """Two audits of the same site -> same scores (zero variance)."""
    a, _ = await run_audit("https://example.com")
    b, _ = await run_audit("https://example.com")
    assert a.score_global == b.score_global
    assert a.config_digest == b.config_digest
    assert {p: s.score for p, s in a.pillars.items()} == {p: s.score for p, s in b.pillars.items()}


async def test_audit_stores_artifacts_when_store_provided(
    monkeypatch: pytest.MonkeyPatch, sample_html: str
) -> None:
    """With an artifact store, raw HTML is captured and referenced (C-P2)."""
    from seryvon.models.artifact import ArtifactType
    from seryvon.storage import InMemoryArtifactStore

    async def fake_discover(url: str, **kwargs: object) -> DiscoveryResult:
        return _fake_discovery()

    async def fake_crawl(discovery: DiscoveryResult, **kwargs: object) -> list[PageSignals]:
        sink = kwargs.get("html_sink")
        if sink is not None:
            sink("https://example.com/", sample_html)  # type: ignore[operator]
        return [extract_page_signals("https://example.com/", sample_html, status_code=200)]

    monkeypatch.setattr(audit_module, "discover", fake_discover)
    monkeypatch.setattr(audit_module, "crawl_site", fake_crawl)

    store = InMemoryArtifactStore()
    report, _pages = await run_audit("https://example.com", artifact_store=store)

    assert len(report.artifacts) == 1
    ref = report.artifacts[0]
    assert ref.type is ArtifactType.HTML
    assert ref.compression.value == "gzip"
    assert store.get(ref).decode("utf-8") == sample_html


async def test_audit_without_store_captures_no_artifacts(patched_crawl: None) -> None:
    report, _pages = await run_audit("https://example.com")
    assert report.artifacts == []


async def test_audit_unreachable_site_is_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unreachable site: no page crawled -> report produced, no exception (ENF-03)."""

    async def fake_discover(url: str, **kwargs: object) -> DiscoveryResult:
        return _fake_discovery()

    async def empty_crawl(discovery: DiscoveryResult, **kwargs: object) -> list[PageSignals]:
        return []

    monkeypatch.setattr(audit_module, "discover", fake_discover)
    monkeypatch.setattr(audit_module, "crawl_site", empty_crawl)

    report, _pages = await run_audit("https://unreachable.example")
    assert report.domain == "example.com"
    # No signal: meta.title absent -> SEO scored 0, but the report exists.
    assert report.pillars["seo"].score == 0.0
