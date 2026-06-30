# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Playwright-based page rendering for SSR/CSR detection and signal extraction.

The `PlaywrightRenderer` callable is the injectable interface used by `crawl_site`.
`renderer_session` builds a persistent browser session (one Chromium process for the
whole crawl) with bounded concurrency; `make_renderer` is kept for unit tests that
need a one-shot callable without a context manager.

All pages are rendered when Playwright is available so that JS-injected content
(images, text, links) is accurately captured.  Concurrency is bounded by
`max_concurrent` (default 3) to avoid overloading the target server.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)

#: CSR classification threshold: rendered words >= raw words × this factor.
CSR_RATIO_THRESHOLD = 1.5
#: Minimum rendered-word surplus (absolute) to call CSR, avoiding false positives
#: when both raw and rendered are near-empty (e.g. error pages).
CSR_MIN_SURPLUS = 100


@dataclass(slots=True)
class RenderedPage:
    """Result of a Playwright render."""

    html: str
    word_count: int
    render_time_ms: int


#: Injectable renderer: URL -> RenderedPage | None (None on timeout/failure).
PlaywrightRenderer = Callable[[str], Awaitable[RenderedPage | None]]


def _word_count(html: str) -> int:
    tree = HTMLParser(html)
    body = tree.body
    if body is None:
        return 0
    return len(body.text(separator=" ", strip=True).split())


def classify_render_mode(raw_html: str, rendered_html: str) -> str:
    """Compare raw HTTP HTML with Playwright-rendered DOM to detect CSR.

    Returns `"csr"` when the rendered DOM has significantly more textual content
    than the raw HTML (suggesting the page relies on JavaScript to populate it),
    `"ssr"` otherwise.
    """
    raw_words = _word_count(raw_html)
    rendered_words = _word_count(rendered_html)
    surplus = rendered_words - raw_words
    ratio = rendered_words / max(raw_words, 1)
    if ratio >= CSR_RATIO_THRESHOLD and surplus >= CSR_MIN_SURPLUS:
        return "csr"
    return "ssr"


@contextlib.asynccontextmanager
async def renderer_session(
    *,
    user_agent: str,
    timeout: float,
    max_concurrent: int = 3,
) -> AsyncIterator[PlaywrightRenderer | None]:
    """Async context manager that keeps one Chromium browser alive for the crawl.

    Yields a `PlaywrightRenderer` bounded by `max_concurrent` simultaneous renders,
    or `None` when the `playwright` package is not installed (graceful degradation).
    Using a single browser avoids the per-URL launch/close overhead of
    `make_renderer` and makes full-site rendering practical.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        yield None
        return

    semaphore = asyncio.Semaphore(max_concurrent)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            async def _render(url: str) -> RenderedPage | None:
                from seryvon.crawler.safety import assert_url_safe

                async with semaphore:
                    t0 = time.monotonic()
                    try:
                        await assert_url_safe(url)
                        context = await browser.new_context(user_agent=user_agent)
                        try:
                            page = await context.new_page()
                            await page.goto(
                                url,
                                timeout=timeout * 1000,
                                wait_until="load",
                            )
                            await page.wait_for_timeout(1500)
                            html = await page.content()
                        finally:
                            await context.close()
                    except Exception as exc:
                        log.warning("playwright render failed url=%s err=%r", url, exc)
                        return None
                    elapsed = int((time.monotonic() - t0) * 1000)
                    return RenderedPage(
                        html=html,
                        word_count=_word_count(html),
                        render_time_ms=elapsed,
                    )

            yield _render
        finally:
            await browser.close()


def make_renderer(*, user_agent: str, timeout: float) -> PlaywrightRenderer | None:
    """One-shot renderer — kept for unit tests.

    Launches and closes a browser per call. Use `renderer_session` for production
    crawls where performance matters.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    async def _render(url: str) -> RenderedPage | None:
        from seryvon.crawler.safety import assert_url_safe

        t0 = time.monotonic()
        try:
            await assert_url_safe(url)
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(user_agent=user_agent)
                    await page.goto(url, timeout=timeout * 1000, wait_until="load")
                    await page.wait_for_timeout(1500)
                    html = await page.content()
                finally:
                    await browser.close()
        except Exception as exc:
            log.warning("playwright render failed url=%s err=%r", url, exc)
            return None
        elapsed = int((time.monotonic() - t0) * 1000)
        return RenderedPage(html=html, word_count=_word_count(html), render_time_ms=elapsed)

    return _render
