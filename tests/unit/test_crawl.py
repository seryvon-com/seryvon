# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests M2 Crawler : BFS multi-pages, limites, robots, déterminisme, SSR/CSR."""

from __future__ import annotations

import httpx

from seryvon.crawler.crawl import PageFetcher, crawl_site, detect_render_mode
from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
from seryvon.crawler.extract import extract_links
from seryvon.crawler.fetch import FetchResult

UA = "Seryvon/0.1 (+https://seryvon.com/bot)"
HOME = "https://example.com/"


def page(*links: str, body: str = "Contenu de la page de démonstration.") -> str:
    anchors = "".join(f'<a href="{href}">lien</a>' for href in links)
    return f"<html><body><p>{body}</p>{anchors}</body></html>"


def make_fetcher(pages: dict[str, str], *, status: int = 200) -> PageFetcher:
    """Fetcher en mémoire : URL connue -> page ; URL inconnue -> erreur réseau."""

    async def _fetch(url: str) -> FetchResult:
        if url not in pages:
            raise httpx.ConnectError(f"injoignable: {url}")
        return FetchResult(url=url, final_url=url, status_code=status, html=pages[url], redirects=0)

    return _fetch


async def _no_sleep(_seconds: float) -> None:
    return None


def discovery_for(
    frontier: list[str],
    *,
    robots: RobotsTxt | None = None,
    crawl_delay: float | None = None,
) -> DiscoveryResult:
    return DiscoveryResult(
        home_url=HOME,
        origin="https://example.com",
        domain="example.com",
        robots=robots or RobotsTxt.allow_all(),
        robots_found=robots is not None,
        crawl_delay=crawl_delay,
        declared_sitemaps=[],
        sitemap_urls=[],
        sitemap_valid=False,
        home_allowed=True,
        frontier=frontier,
    )


async def _crawl(pages: dict[str, str], **kwargs: object) -> list[str]:
    """Crawl utilitaire -> liste des URLs des pages obtenues."""
    discovery = discovery_for([HOME], **kwargs)  # type: ignore[arg-type]
    result = await crawl_site(discovery, user_agent=UA, fetch=make_fetcher(pages), sleep=_no_sleep)
    return [p.url for p in result]


# --------------------------------------------------------------------------- #
# extract_links                                                               #
# --------------------------------------------------------------------------- #
def test_extract_links_resolves_and_filters() -> None:
    html = (
        '<a href="/a">a</a>'
        '<a href="page?x=1#frag">b</a>'
        '<a href="https://other.com/x">ext</a>'
        '<a href="mailto:hi@example.com">mail</a>'
        '<a href="#top">anchor</a>'
    )
    links = extract_links(html, "https://example.com/dir/")
    assert links == [
        "https://example.com/a",
        "https://example.com/dir/page?x=1",
        "https://other.com/x",
    ]


# --------------------------------------------------------------------------- #
# detect_render_mode                                                          #
# --------------------------------------------------------------------------- #
def test_detect_render_mode_ssr() -> None:
    html = "<html><body><p>" + ("mot " * 80) + "</p></body></html>"
    assert detect_render_mode(html) == "ssr"


def test_detect_render_mode_csr_mount_node() -> None:
    html = '<html><body><div id="root"></div></body></html>'
    assert detect_render_mode(html) == "csr"


def test_detect_render_mode_csr_script_heavy() -> None:
    scripts = "".join(f"<script>var x{i}=1;</script>" for i in range(8))
    html = f"<html><body><span>peu de texte</span>{scripts}</body></html>"
    assert detect_render_mode(html) == "csr"


# --------------------------------------------------------------------------- #
# crawl_site                                                                  #
# --------------------------------------------------------------------------- #
async def test_crawl_follows_internal_links() -> None:
    pages = {
        HOME: page("/a", "/b"),
        "https://example.com/a": page("/c"),
        "https://example.com/b": page(),
        "https://example.com/c": page(),
    }
    urls = await _crawl(pages)
    assert urls == [
        HOME,
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


async def test_crawl_respects_max_pages() -> None:
    pages = {
        HOME: page("/a", "/b", "/c", "/d"),
        "https://example.com/a": page(),
        "https://example.com/b": page(),
        "https://example.com/c": page(),
        "https://example.com/d": page(),
    }
    discovery = discovery_for([HOME])
    result = await crawl_site(
        discovery, user_agent=UA, max_pages=2, fetch=make_fetcher(pages), sleep=_no_sleep
    )
    assert len(result) == 2
    assert [p.url for p in result] == [HOME, "https://example.com/a"]


async def test_crawl_respects_max_depth() -> None:
    pages = {
        HOME: page("/a"),
        "https://example.com/a": page("/deep"),
        "https://example.com/deep": page(),
    }
    discovery = discovery_for([HOME])
    result = await crawl_site(
        discovery, user_agent=UA, max_depth=1, fetch=make_fetcher(pages), sleep=_no_sleep
    )
    urls = [p.url for p in result]
    assert urls == [HOME, "https://example.com/a"]
    assert "https://example.com/deep" not in urls


async def test_crawl_stays_on_same_host() -> None:
    pages = {
        HOME: page("/a", "https://other.com/x"),
        "https://example.com/a": page(),
    }
    urls = await _crawl(pages)
    assert urls == [HOME, "https://example.com/a"]


async def test_crawl_dedupes_pages() -> None:
    pages = {
        HOME: page("/a", "/a", "/b"),
        "https://example.com/a": page("/b"),  # /b référencée deux fois
        "https://example.com/b": page("/a"),  # cycle
    }
    urls = await _crawl(pages)
    assert urls == [HOME, "https://example.com/a", "https://example.com/b"]


async def test_crawl_respects_robots_disallow() -> None:
    robots = RobotsTxt.parse("User-agent: *\nDisallow: /private/\n")
    pages = {
        HOME: page("/ok", "/private/secret"),
        "https://example.com/ok": page(),
        "https://example.com/private/secret": page(),
    }
    urls = await _crawl(pages, robots=robots)
    assert urls == [HOME, "https://example.com/ok"]


async def test_crawl_handles_fetch_errors_gracefully() -> None:
    pages = {
        HOME: page("/a", "/missing"),
        "https://example.com/a": page(),
        # /missing absent du dict -> le fetcher lève -> page ignorée
    }
    urls = await _crawl(pages)
    assert urls == [HOME, "https://example.com/a"]


async def test_crawl_is_deterministic() -> None:
    pages = {
        HOME: page("/c", "/a", "/b"),  # ordre des liens volontairement désordonné
        "https://example.com/a": page(),
        "https://example.com/b": page(),
        "https://example.com/c": page(),
    }
    first = await _crawl(pages)
    second = await _crawl(pages)
    assert first == second
    assert first == [
        HOME,
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


async def test_crawl_sets_render_mode() -> None:
    pages = {HOME: page(body="texte court")}
    discovery = discovery_for([HOME])
    result = await crawl_site(discovery, user_agent=UA, fetch=make_fetcher(pages), sleep=_no_sleep)
    assert result[0].render_mode in {"ssr", "csr"}


async def test_crawl_applies_crawl_delay() -> None:
    calls: list[float] = []

    async def spy_sleep(seconds: float) -> None:
        calls.append(seconds)

    pages = {HOME: page("/a"), "https://example.com/a": page()}
    discovery = discovery_for([HOME], crawl_delay=2.0)
    await crawl_site(discovery, user_agent=UA, fetch=make_fetcher(pages), sleep=spy_sleep)
    assert calls and all(c == 2.0 for c in calls)
