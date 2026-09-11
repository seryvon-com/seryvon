# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Integration test of the audit flow (discovery + crawl mocked, no network)."""

from __future__ import annotations

from types import SimpleNamespace

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


def test_brand_name_resolution_prefers_site_name_then_title_then_host() -> None:
    assert (
        audit_module._brand_name(
            PageSignals(url="https://example.com/", open_graph={"og:site_name": " Acme "})
        )
        == "Acme"
    )
    assert (
        audit_module._brand_name(PageSignals(url="https://example.com/", title="Acme | Docs"))
        == "Acme"
    )
    assert (
        audit_module._brand_name(PageSignals(url="https://example.com/", title="Acme Docs"))
        == "Acme Docs"
    )
    assert audit_module._brand_name(PageSignals(url="https://www.example.com/")) == "example"


@pytest.mark.asyncio
async def test_collect_brand_handles_disabled_missing_and_found_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled = SimpleNamespace(wikidata_enabled=False, request_timeout=1)
    assert await audit_module._collect_brand(None, disabled) == (None, None)
    enabled = SimpleNamespace(wikidata_enabled=True, request_timeout=1)
    assert await audit_module._collect_brand(PageSignals(url="https:///"), enabled) == (None, None)

    async def missing(*_: object, **__: object) -> object:
        return SimpleNamespace(found=False)

    monkeypatch.setattr(audit_module, "fetch_wikidata", missing)
    assert await audit_module._collect_brand(
        PageSignals(url="https://example.com/", title="Example"), enabled
    ) == (False, None)

    async def found(*_: object, **__: object) -> object:
        return SimpleNamespace(found=True)

    monkeypatch.setattr(audit_module, "fetch_wikidata", found)
    monkeypatch.setattr(audit_module, "brand_coherence", lambda *_: {"name": 1.0})
    assert await audit_module._collect_brand(
        PageSignals(url="https://example.com/", title="Example"), enabled
    ) == (True, {"name": 1.0})


@pytest.mark.asyncio
async def test_run_audit_exercises_configured_connector_paths(
    monkeypatch: pytest.MonkeyPatch, sample_html: str
) -> None:
    async def fake_discover(*_: object, **__: object) -> DiscoveryResult:
        return _fake_discovery()

    async def fake_crawl(*_: object, **kwargs: object) -> list[PageSignals]:
        page = extract_page_signals("https://example.com/", sample_html, status_code=200)
        page.render_source = "playwright"
        callback = kwargs.get("on_progress")
        if callback is not None:
            callback(0, 1, 1)
        return [page]

    monkeypatch.setattr(audit_module, "discover", fake_discover)
    monkeypatch.setattr(audit_module, "crawl_site", fake_crawl)
    monkeypatch.setattr(
        audit_module, "renderer_session", lambda **_: audit_module.contextlib.nullcontext(object())
    )

    async def psi(*_: object, **__: object) -> object:
        return SimpleNamespace(
            core_web_vitals={"lcp": 1}, lighthouse_performance=90.0, error_reason=None
        )

    monkeypatch.setattr(audit_module, "fetch_pagespeed", psi)

    async def dfs(*_: object, **__: object) -> object:
        return SimpleNamespace(
            open_page_rank_equivalent=7.5, referring_domains=4, domain_rank=3, organic_etv=12
        )

    monkeypatch.setattr(audit_module, "fetch_dataforseo", dfs)

    async def gsc(*_: object, **__: object) -> object:
        return SimpleNamespace(
            avg_position=2.0,
            total_clicks=10,
            total_impressions=100,
            avg_ctr=0.1,
            date_range_days=28,
            queries=[],
            pages=[],
            comparison=None,
        )

    monkeypatch.setattr(audit_module, "fetch_gsc", gsc)

    async def aio(*_: object, **__: object) -> object:
        return SimpleNamespace(
            presence_rate=0.5, trigger_rate=0.4, avg_position=2.0, query_count=1, provider="test"
        )

    monkeypatch.setattr(audit_module, "fetch_serp_aio", aio)

    async def probes(*_: object, **__: object) -> dict[str, object]:
        return {"ai.txt": True}

    monkeypatch.setattr(audit_module, "probe_ai_discovery", probes)

    async def nlweb(*_: object, **__: object) -> str:
        return "ok"

    monkeypatch.setattr(audit_module, "probe_nlweb", nlweb)
    monkeypatch.setattr(
        audit_module,
        "generate_prompt_set",
        lambda *_: (_ for _ in ()).throw(RuntimeError("disabled")),
    )
    settings = SimpleNamespace(
        user_agent="test",
        request_timeout=1,
        playwright_enabled=True,
        playwright_timeout=1,
        psi_api_key="psi",
        pagespeed_strategy="mobile",
        psi_timeout=1,
        dataforseo_api_key="dfs",
        opr_api_key=None,
        gsc_service_account="gsc",
        serp_api_key="serp",
        serp_provider="test",
        wikidata_enabled=False,
    )
    progress: list[str] = []
    report, _ = await run_audit(
        "https://example.com", settings=settings, on_progress=progress.append
    )
    assert report.measurement_profile is not None
    assert any("Connectors done" in msg for msg in progress)


@pytest.mark.asyncio
async def test_run_audit_reports_missing_external_connector_data(
    monkeypatch: pytest.MonkeyPatch, sample_html: str
) -> None:
    async def discover(*_: object, **__: object) -> DiscoveryResult:
        return _fake_discovery()

    monkeypatch.setattr(audit_module, "discover", discover)

    async def crawl(*_: object, **__: object) -> list[PageSignals]:
        return [extract_page_signals("https://example.com/", sample_html, status_code=200)]

    monkeypatch.setattr(audit_module, "crawl_site", crawl)
    from seryvon.models.signals import ExternalSignals

    monkeypatch.setattr(audit_module, "_collect_external", lambda *a, **k: None)
    # Keep the audit's warning branches independent from network implementations.
    external = ExternalSignals(psi_error_reason=None, dataforseo_active=True)

    async def collect(*_: object, **__: object) -> ExternalSignals:
        return external

    monkeypatch.setattr(audit_module, "_collect_external", collect)
    settings = SimpleNamespace(
        user_agent="test",
        request_timeout=1,
        playwright_enabled=False,
        playwright_timeout=1,
        psi_api_key="psi",
        pagespeed_strategy="mobile",
        psi_timeout=1,
        dataforseo_api_key=None,
        opr_api_key="opr",
        gsc_service_account=None,
        serp_api_key=None,
        serp_provider="test",
        wikidata_enabled=False,
    )
    progress: list[str] = []
    await run_audit("https://example.com", settings=settings, on_progress=progress.append)
    assert any("PSI" in item for item in progress)
    assert any("OPR" in item for item in progress)


@pytest.mark.asyncio
async def test_collect_external_uses_configured_connectors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def psi(*_: object, **__: object) -> object:
        return SimpleNamespace(
            core_web_vitals={"lcp": 1}, lighthouse_performance=92.0, error_reason=None
        )

    async def dataforseo(*_: object, **__: object) -> object:
        return SimpleNamespace(
            domain_rank=4, organic_etv=10, open_page_rank_equivalent=7.5, referring_domains=12
        )

    async def gsc(*_: object, **__: object) -> object:
        return SimpleNamespace(avg_position=3.0)

    monkeypatch.setattr(audit_module, "fetch_pagespeed", psi)
    monkeypatch.setattr(audit_module, "fetch_dataforseo", dataforseo)
    monkeypatch.setattr(audit_module, "fetch_gsc", gsc)
    settings = SimpleNamespace(
        psi_api_key="psi",
        pagespeed_strategy="mobile",
        psi_timeout=2,
        dataforseo_api_key="dfs",
        opr_api_key=None,
        gsc_service_account="gsc",
        request_timeout=1,
    )
    result = await audit_module._collect_external(
        "example.com", [PageSignals(url="https://example.com/")], settings
    )
    assert result.lighthouse_performance == 92.0
    assert result.dataforseo_active is True
    assert result.open_page_rank == 7.5
    assert result.referring_domains == 12
    assert result.gsc_data.avg_position == 3.0


@pytest.mark.asyncio
async def test_collect_external_falls_back_to_openpagerank(monkeypatch: pytest.MonkeyPatch) -> None:
    async def opr(*_: object, **__: object) -> object:
        return SimpleNamespace(page_rank=5.0)

    monkeypatch.setattr(audit_module, "fetch_openpagerank", opr)
    settings = SimpleNamespace(
        psi_api_key=None,
        dataforseo_api_key=None,
        opr_api_key="opr",
        gsc_service_account=None,
        request_timeout=1,
    )
    result = await audit_module._collect_external("example.com", [], settings)
    assert result.open_page_rank == 5.0
