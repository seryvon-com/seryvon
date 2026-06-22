# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""M2 multi-page async crawler.

Breadth-first traversal (BFS) by waves from the frontier provided by M1.
Collection layer: the I/O (fetch) is injectable for network-free tests.

Determinism: the output never depends on the arrival order of concurrent
responses. Each wave is filtered then processed by sorted URL, pages are
deduplicated by final URL (after redirects) and the final list is sorted by URL.
Concurrency is bounded by a semaphore; if a `crawl-delay` is declared,
concurrency drops to 1 with a pause between requests (politeness, ENF-04).

SSR/CSR detection: browser-free heuristic (decision D2). The reliable
Playwright-rendering measurement arrives in Phase 2 for the geo.ssr criterion.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

import httpx
from selectolax.parser import HTMLParser

from seryvon.crawler.discovery import DiscoveryResult, same_host
from seryvon.crawler.extract import extract_links, extract_page_signals
from seryvon.crawler.fetch import FetchResult, fetch_page
from seryvon.models.signals import PageSignals

#: Fetch a page by URL (injectable for tests).
PageFetcher = Callable[[str], Awaitable[FetchResult]]
#: Async pause (injectable: no-op in tests, asyncio.sleep in prod).
Sleeper = Callable[[float], Awaitable[None]]
#: Optional sink for raw HTML (final_url, html) — collection-side artifact capture.
HtmlSink = Callable[[str, str], None]

DEFAULT_MAX_CONCURRENCY = 5

# SSR/CSR heuristic (D2) — replaced by a Playwright measurement in Phase 2.
_SSR_MIN_WORDS = 50
_CSR_MOUNT_SELECTORS = ("#root", "#app", "[data-reactroot]", "[ng-version]")


def detect_render_mode(html: str) -> str:
    """Guess `"ssr"` or `"csr"` without a browser (heuristic, decision D2).

    A text-rich body indicates server rendering; a near-empty body with an SPA
    mount node or many scripts indicates client rendering. The reliable
    measurement (raw HTML vs rendered DOM) will come with Playwright (Phase 2).
    """
    tree = HTMLParser(html)
    body = tree.body
    word_count = len(body.text(separator=" ", strip=True).split()) if body else 0
    if word_count >= _SSR_MIN_WORDS:
        return "ssr"
    has_mount = any(tree.css_first(sel) is not None for sel in _CSR_MOUNT_SELECTORS)
    if has_mount or len(tree.css("script")) > 5:
        return "csr"
    return "ssr"


async def _fetch_wave(
    urls: list[str],
    fetch: PageFetcher,
    semaphore: asyncio.Semaphore,
    delay: float,
    sleep: Sleeper,
) -> dict[str, FetchResult]:
    """Fetch a wave of URLs with bounded concurrency; failures are ignored."""
    fetched: dict[str, FetchResult] = {}

    async def _one(url: str) -> None:
        async with semaphore:
            if delay > 0:
                await sleep(delay)
            # Unreachable page: ignored (ENF-03), the audit continues.
            with contextlib.suppress(httpx.HTTPError):
                fetched[url] = await fetch(url)

    await asyncio.gather(*(_one(url) for url in urls))
    return fetched


async def _run_crawl(
    discovery: DiscoveryResult,
    fetch: PageFetcher,
    sleep: Sleeper,
    *,
    user_agent: str,
    max_pages: int,
    max_depth: int,
    max_concurrency: int,
    respect_robots: bool,
    html_sink: HtmlSink | None = None,
) -> list[PageSignals]:
    """Deterministic BFS crawl loop from a fetcher (real or injected)."""
    robots = discovery.robots
    host = discovery.domain
    delay = discovery.crawl_delay or 0.0
    concurrency = 1 if delay > 0 else max(1, max_concurrency)
    semaphore = asyncio.Semaphore(concurrency)

    seen: set[str] = set()
    results: dict[str, PageSignals] = {}
    current = sorted(set(discovery.frontier))
    depth = 0

    while current and len(results) < max_pages and depth <= max_depth:
        wave = [
            url
            for url in current
            if url not in seen
            and same_host(url, host)
            and (not respect_robots or robots.can_fetch(url, user_agent))
        ]
        wave = wave[: max_pages - len(results)]
        if not wave:
            break

        fetched = await _fetch_wave(wave, fetch, semaphore, delay, sleep)

        next_frontier: set[str] = set()
        for url in wave:
            seen.add(url)
            result = fetched.get(url)
            if result is None:
                continue
            seen.add(result.final_url)
            if result.final_url in results:
                continue
            signals = extract_page_signals(
                result.final_url,
                result.html,
                status_code=result.status_code,
                redirects=result.redirects,
            )
            signals.render_mode = detect_render_mode(result.html)
            results[result.final_url] = signals
            if html_sink is not None:
                html_sink(result.final_url, result.html)
            if depth < max_depth:
                for link in extract_links(result.html, result.final_url):
                    if link not in seen and same_host(link, host):
                        next_frontier.add(link)

        current = sorted(next_frontier)
        depth += 1

    return [results[url] for url in sorted(results)]


async def crawl_site(
    discovery: DiscoveryResult,
    *,
    user_agent: str,
    max_pages: int = 200,
    max_depth: int = 3,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    respect_robots: bool = True,
    timeout: float = 15.0,
    fetch: PageFetcher | None = None,
    sleep: Sleeper | None = None,
    html_sink: HtmlSink | None = None,
) -> list[PageSignals]:
    """Crawl a site from the M1 frontier and return the per-page signals.

    If `fetch` is provided (tests), it is used as-is; otherwise `fetch_page`
    (httpx) is used. The returned list is sorted by URL (determinism).
    """
    page_fetch = fetch
    if page_fetch is None:

        async def _default_fetch(url: str) -> FetchResult:
            return await fetch_page(url, user_agent=user_agent, timeout=timeout)

        page_fetch = _default_fetch

    return await _run_crawl(
        discovery,
        page_fetch,
        sleep or asyncio.sleep,
        user_agent=user_agent,
        max_pages=max_pages,
        max_depth=max_depth,
        max_concurrency=max_concurrency,
        respect_robots=respect_robots,
        html_sink=html_sink,
    )
