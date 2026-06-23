# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Playwright-based page rendering for SSR/CSR detection (geo.ssr, Phase 2 D2).

The `PlaywrightRenderer` callable is the injectable interface used by `crawl_site`.
`make_renderer` builds a real Playwright instance when the optional `playwright`
package is installed; it returns `None` when it is not, allowing the audit to
degrade gracefully to the heuristic.

Only the home page is rendered (performance trade-off): comparing raw HTTP HTML
with the Playwright-rendered DOM reveals whether the site relies on client-side
JavaScript to populate its content. A ratio of rendered / raw word-count >= 1.5
indicates CSR; otherwise the page is classified as SSR.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from selectolax.parser import HTMLParser

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


def make_renderer(*, user_agent: str, timeout: float) -> PlaywrightRenderer | None:
    """Return a `PlaywrightRenderer` if the optional `playwright` package is installed.

    Returns `None` when Playwright is absent — the caller falls back to the
    heuristic (decision D2). The browser is launched and closed per call so that
    the renderer is safe to use from asyncio without a shared event loop.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    async def _render(url: str) -> RenderedPage | None:
        t0 = time.monotonic()
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(user_agent=user_agent)
                    await page.goto(
                        url,
                        timeout=timeout * 1000,
                        wait_until="networkidle",
                    )
                    html = await page.content()
                finally:
                    await browser.close()
        except Exception:
            return None
        elapsed = int((time.monotonic() - t0) * 1000)
        return RenderedPage(
            html=html,
            word_count=_word_count(html),
            render_time_ms=elapsed,
        )

    return _render
