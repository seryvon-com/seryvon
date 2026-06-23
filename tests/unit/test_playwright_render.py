# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for Playwright SSR/CSR detection logic (playwright_render.py).

All tests are pure (no real browser, no network). The `classify_render_mode`
function and the crawler integration are tested with injected mock renderers.
"""

from __future__ import annotations

import pytest

from seryvon.crawler.playwright_render import (
    CSR_MIN_SURPLUS,
    CSR_RATIO_THRESHOLD,
    RenderedPage,
    classify_render_mode,
    make_renderer,
)

# ---------------------------------------------------------------------------
# classify_render_mode — unit tests
# ---------------------------------------------------------------------------


def _html(words: int) -> str:
    """Minimal HTML body with the given number of words."""
    body = " ".join(f"word{i}" for i in range(words))
    return f"<html><body><p>{body}</p></body></html>"


def test_classify_ssr_when_similar_word_counts() -> None:
    raw = _html(200)
    rendered = _html(220)  # +10% — well below 1.5× threshold
    assert classify_render_mode(raw, rendered) == "ssr"


def test_classify_csr_when_rendered_much_richer() -> None:
    raw = _html(10)
    rendered = _html(500)  # ratio >> 1.5, surplus >> 100
    assert classify_render_mode(raw, rendered) == "csr"


def test_classify_ssr_when_surplus_below_minimum() -> None:
    # Ratio >= threshold but absolute surplus is tiny (e.g. near-empty error pages).
    raw = _html(0)
    rendered = _html(CSR_MIN_SURPLUS - 1)  # ratio = inf but surplus too small
    assert classify_render_mode(raw, rendered) == "ssr"


def test_classify_csr_exactly_at_threshold() -> None:
    # Exactly at both threshold and minimum surplus.
    raw_words = 200
    # rendered_words must satisfy: rendered/raw >= 1.5 AND rendered - raw >= 100
    rendered_words = int(raw_words * CSR_RATIO_THRESHOLD)  # 300, surplus = 100
    raw = _html(raw_words)
    rendered = _html(rendered_words)
    assert classify_render_mode(raw, rendered) == "csr"


def test_classify_handles_empty_raw() -> None:
    raw = "<html><body></body></html>"
    rendered = _html(50)  # surplus = 50 < 100 → SSR despite high ratio
    assert classify_render_mode(raw, rendered) == "ssr"


# ---------------------------------------------------------------------------
# make_renderer — graceful degradation when playwright not installed
# ---------------------------------------------------------------------------


def test_make_renderer_returns_none_when_playwright_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """When playwright is not importable, make_renderer returns None."""
    import builtins

    real_import = builtins.__import__

    def _no_playwright(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("playwright"):
            raise ImportError("no module named playwright")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _no_playwright)
    result = make_renderer(user_agent="TestBot/1.0", timeout=5.0)
    assert result is None


# ---------------------------------------------------------------------------
# Crawler integration — mock PlaywrightRenderer
# ---------------------------------------------------------------------------


def _make_mock_renderer(rendered_html: str | None) -> object:
    """Build a mock PlaywrightRenderer that returns a fixed RenderedPage (or None)."""

    async def _renderer(_url: str) -> RenderedPage | None:
        if rendered_html is None:
            return None
        from seryvon.crawler.playwright_render import _word_count

        return RenderedPage(
            html=rendered_html,
            word_count=_word_count(rendered_html),
            render_time_ms=42,
        )

    return _renderer


@pytest.mark.asyncio
async def test_crawl_uses_playwright_for_home_page() -> None:
    """When a mock renderer is injected, home page gets render_source='playwright'."""
    from seryvon.crawler.crawl import crawl_site
    from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
    from seryvon.crawler.fetch import FetchResult

    raw_html = "<html><body><p>Tiny CSR shell</p></body></html>"
    # Rich rendered DOM → CSR detected
    rendered_html = (
        "<html><body>" + "<p>" + " ".join(f"word{i}" for i in range(500)) + "</p></body></html>"
    )

    discovery = DiscoveryResult(
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

    async def _fetch(_url: str) -> FetchResult:
        return FetchResult(
            url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            html=raw_html,
            redirects=0,
        )

    pages = await crawl_site(
        discovery,
        user_agent="TestBot/1.0",
        fetch=_fetch,
        sleep=lambda _: __import__("asyncio").sleep(0),
        playwright_renderer=_make_mock_renderer(rendered_html),  # type: ignore[arg-type]
    )

    assert len(pages) == 1
    assert pages[0].render_source == "playwright"
    assert pages[0].render_mode == "csr"


@pytest.mark.asyncio
async def test_crawl_falls_back_to_heuristic_when_renderer_returns_none() -> None:
    """When the renderer fails (returns None), heuristic is used instead."""
    from seryvon.crawler.crawl import crawl_site
    from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
    from seryvon.crawler.fetch import FetchResult

    rich_html = (
        "<html><body>" + "<p>" + " ".join(f"word{i}" for i in range(200)) + "</p></body></html>"
    )

    discovery = DiscoveryResult(
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

    async def _fetch(_url: str) -> FetchResult:
        return FetchResult(
            url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            html=rich_html,
            redirects=0,
        )

    pages = await crawl_site(
        discovery,
        user_agent="TestBot/1.0",
        fetch=_fetch,
        sleep=lambda _: __import__("asyncio").sleep(0),
        playwright_renderer=_make_mock_renderer(None),  # type: ignore[arg-type]
    )

    assert len(pages) == 1
    assert pages[0].render_source == "heuristic"
    assert pages[0].render_mode == "ssr"  # heuristic: 200 words → SSR


@pytest.mark.asyncio
async def test_crawl_reextracts_signals_for_csr_home_page() -> None:
    """For a CSR home page, signals are extracted from the rendered DOM, not raw HTML."""
    from seryvon.crawler.crawl import crawl_site
    from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
    from seryvon.crawler.fetch import FetchResult

    # Raw HTML has no title; rendered DOM has a title.
    raw_html = "<html><body><div id='root'></div></body></html>"
    rendered_html = (
        "<html><head><title>Rendered Title</title></head>"
        "<body><p>" + " ".join(f"word{i}" for i in range(500)) + "</p></body></html>"
    )

    discovery = DiscoveryResult(
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

    async def _fetch(_url: str) -> FetchResult:
        return FetchResult(
            url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            html=raw_html,
            redirects=0,
        )

    pages = await crawl_site(
        discovery,
        user_agent="TestBot/1.0",
        fetch=_fetch,
        sleep=lambda _: __import__("asyncio").sleep(0),
        playwright_renderer=_make_mock_renderer(rendered_html),  # type: ignore[arg-type]
    )

    assert len(pages) == 1
    home = pages[0]
    assert home.render_mode == "csr"
    assert home.render_source == "playwright"
    # Signals should come from the rendered DOM (title visible in rendered HTML)
    assert home.title == "Rendered Title"
    assert home.word_count > 100  # rich rendered content
