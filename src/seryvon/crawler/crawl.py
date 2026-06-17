# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""M2 Crawler async multi-pages.

Parcours en largeur (BFS) par vagues à partir de la frontière fournie par M1.
Couche de collecte : les I/O (fetch) sont injectables pour des tests sans réseau.

Déterminisme : la sortie ne dépend jamais de l'ordre d'arrivée des réponses
concurrentes. Chaque vague est filtrée puis traitée par URL triée, les pages sont
dédupliquées par URL finale (après redirections) et la liste finale est triée par
URL. Concurrence bornée par un sémaphore ; si un `crawl-delay` est déclaré, la
concurrence retombe à 1 avec une pause entre requêtes (politesse, ENF-04).

Détection SSR/CSR : heuristique sans navigateur (décision D2). La mesure fiable
par rendu Playwright arrive en Phase 2 pour le critère geo.ssr.
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

#: Récupère une page par URL (injectable pour les tests).
PageFetcher = Callable[[str], Awaitable[FetchResult]]
#: Pause asynchrone (injectable : no-op en test, asyncio.sleep en prod).
Sleeper = Callable[[float], Awaitable[None]]

DEFAULT_MAX_CONCURRENCY = 5

# Heuristique SSR/CSR (D2) — remplacée par une mesure Playwright en Phase 2.
_SSR_MIN_WORDS = 50
_CSR_MOUNT_SELECTORS = ("#root", "#app", "[data-reactroot]", "[ng-version]")


def detect_render_mode(html: str) -> str:
    """Devine `"ssr"` ou `"csr"` sans navigateur (heuristique, décision D2).

    Un corps riche en texte indique un rendu serveur ; un corps quasi vide avec
    un nœud de montage SPA ou de nombreux scripts indique un rendu client. La
    mesure fiable (HTML brut vs DOM rendu) viendra avec Playwright (Phase 2).
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
    """Récupère une vague d'URLs en concurrence bornée ; les échecs sont ignorés."""
    fetched: dict[str, FetchResult] = {}

    async def _one(url: str) -> None:
        async with semaphore:
            if delay > 0:
                await sleep(delay)
            # Page injoignable : ignorée (ENF-03), l'audit continue.
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
) -> list[PageSignals]:
    """Boucle de crawl BFS déterministe à partir d'un fetcher (réel ou injecté)."""
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
) -> list[PageSignals]:
    """Crawle un site à partir de la frontière de M1 et renvoie les signaux par page.

    Si `fetch` est fourni (tests), il est utilisé tel quel ; sinon `fetch_page`
    (httpx) est employé. La liste renvoyée est triée par URL (déterminisme).
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
    )
