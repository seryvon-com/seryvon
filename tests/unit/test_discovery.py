# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests M1 Discovery : normalisation, robots.txt, sitemaps, frontière de crawl."""

from __future__ import annotations

import gzip

import pytest

from seryvon.crawler.discovery import (
    ResourceFetcher,
    RobotsTxt,
    discover,
    normalize_url,
    parse_sitemap,
)
from seryvon.crawler.fetch import FetchedResource

UA = "Seryvon/0.1 (+https://seryvon.com/bot)"
NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


# --------------------------------------------------------------------------- #
# normalize_url                                                               #
# --------------------------------------------------------------------------- #
def test_normalize_bare_domain_defaults_to_https() -> None:
    norm = normalize_url("example.com")
    assert norm.scheme == "https"
    assert norm.host == "example.com"
    assert norm.origin == "https://example.com"
    assert norm.url == "https://example.com/"


def test_normalize_lowercases_scheme_and_host() -> None:
    norm = normalize_url("HTTP://Example.COM/Path")
    assert norm.scheme == "http"
    assert norm.host == "example.com"
    assert norm.url == "http://example.com/Path"  # le chemin garde sa casse


def test_normalize_strips_default_port_but_keeps_custom() -> None:
    assert normalize_url("https://example.com:443/").origin == "https://example.com"
    assert normalize_url("http://example.com:80/").origin == "http://example.com"
    assert normalize_url("https://example.com:8443/").origin == "https://example.com:8443"


def test_normalize_strips_trailing_dot_and_fragment_keeps_query() -> None:
    norm = normalize_url("https://example.com./page?q=1#section")
    assert norm.host == "example.com"
    assert norm.url == "https://example.com/page?q=1"


def test_normalize_without_host_raises() -> None:
    with pytest.raises(ValueError, match="host"):
        normalize_url("https:///")


# --------------------------------------------------------------------------- #
# RobotsTxt                                                                   #
# --------------------------------------------------------------------------- #
def test_robots_disallow_and_allow_precedence() -> None:
    robots = RobotsTxt.parse(
        "User-agent: *\nDisallow: /private/\nAllow: /private/ok\nDisallow: /*.pdf$\n"
    )
    assert robots.found is True
    assert robots.can_fetch("https://example.com/public", UA) is True
    assert robots.can_fetch("https://example.com/private/x", UA) is False
    assert robots.can_fetch("https://example.com/private/ok", UA) is True
    assert robots.can_fetch("https://example.com/file.pdf", UA) is False


def test_robots_crawl_delay_and_sitemaps() -> None:
    robots = RobotsTxt.parse("User-agent: *\nCrawl-delay: 3\nSitemap: https://example.com/sm.xml\n")
    assert robots.crawl_delay(UA) == 3.0
    assert robots.sitemaps == ["https://example.com/sm.xml"]


def test_robots_absent_allows_everything() -> None:
    robots = RobotsTxt.allow_all()
    assert robots.found is False
    assert robots.can_fetch("https://example.com/anything", UA) is True
    assert robots.crawl_delay(UA) is None
    assert robots.sitemaps == []


# --------------------------------------------------------------------------- #
# parse_sitemap                                                               #
# --------------------------------------------------------------------------- #
def _urlset(*locs: str) -> bytes:
    body = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return f'<?xml version="1.0"?><urlset {NS}>{body}</urlset>'.encode()


def _index(*locs: str) -> bytes:
    body = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in locs)
    return f'<?xml version="1.0"?><sitemapindex {NS}>{body}</sitemapindex>'.encode()


def test_parse_urlset_namespaced() -> None:
    result = parse_sitemap(_urlset("https://example.com/a", "https://example.com/b"))
    assert result.valid is True
    assert result.is_index is False
    assert result.urls == ["https://example.com/a", "https://example.com/b"]


def test_parse_urlset_without_namespace() -> None:
    raw = b"<urlset><url><loc>https://example.com/x</loc></url></urlset>"
    result = parse_sitemap(raw)
    assert result.valid is True
    assert result.urls == ["https://example.com/x"]


def test_parse_sitemapindex() -> None:
    result = parse_sitemap(_index("https://example.com/sm1.xml", "https://example.com/sm2.xml"))
    assert result.is_index is True
    assert result.sitemaps == ["https://example.com/sm1.xml", "https://example.com/sm2.xml"]
    assert result.urls == []


def test_parse_gzipped_sitemap() -> None:
    raw = gzip.compress(_urlset("https://example.com/g"))
    result = parse_sitemap(raw, source_url="https://example.com/sitemap.xml.gz")
    assert result.valid is True
    assert result.urls == ["https://example.com/g"]


def test_parse_invalid_xml_is_not_valid() -> None:
    assert parse_sitemap(b"<not xml").valid is False
    assert parse_sitemap(b"").valid is False
    assert parse_sitemap(b'<?xml version="1.0"?><rss></rss>').valid is False


def test_parse_rejects_doctype_entities() -> None:
    malicious = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE urlset [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b"<urlset><url><loc>&xxe;</loc></url></urlset>"
    )
    assert parse_sitemap(malicious).valid is False


def test_parse_mislabeled_gzip_is_invalid() -> None:
    # content-type prétend gzip mais le corps ne l'est pas : invalide, sans exception.
    assert parse_sitemap(b"<urlset></urlset>", content_type="application/gzip").valid is False


# --------------------------------------------------------------------------- #
# discover (orchestration, fetcher injecté)                                   #
# --------------------------------------------------------------------------- #
def make_fetcher(responses: dict[str, tuple[int, bytes, str | None]]) -> ResourceFetcher:
    """Fetcher en mémoire : URL -> (status, contenu, content-type). Défaut 404."""

    async def _fetch(url: str) -> FetchedResource:
        status, content, ctype = responses.get(url, (404, b"", None))
        return FetchedResource(
            url=url, final_url=url, status_code=status, content=content, content_type=ctype
        )

    return _fetch


async def test_discover_with_robots_and_sitemap() -> None:
    fetch = make_fetcher(
        {
            "https://example.com/robots.txt": (
                200,
                b"User-agent: *\nCrawl-delay: 1\nDisallow: /private/\n"
                b"Sitemap: https://example.com/sitemap.xml\n",
                "text/plain",
            ),
            "https://example.com/sitemap.xml": (
                200,
                _urlset(
                    "https://example.com/",
                    "https://example.com/about",
                    "https://other.com/external",  # autre hôte -> exclu
                ),
                "application/xml",
            ),
        }
    )
    result = await discover("https://example.com", user_agent=UA, fetch=fetch)

    assert result.robots_found is True
    assert result.crawl_delay == 1.0
    assert result.sitemap_valid is True
    assert result.home_allowed is True
    # Le candidat par défaut est dédupliqué avec celui déclaré dans robots.
    assert result.declared_sitemaps == ["https://example.com/sitemap.xml"]
    # URLs externes exclues ; tri déterministe.
    assert result.sitemap_urls == ["https://example.com/", "https://example.com/about"]
    # Frontière : home en tête, pas de doublon, même hôte uniquement.
    assert result.frontier == ["https://example.com/", "https://example.com/about"]


async def test_discover_without_robots_uses_default_sitemap() -> None:
    fetch = make_fetcher(
        {
            "https://example.com/sitemap.xml": (
                200,
                _urlset("https://example.com/page"),
                "application/xml",
            ),
        }
    )
    result = await discover("https://example.com", user_agent=UA, fetch=fetch)

    assert result.robots_found is False
    assert result.crawl_delay is None
    assert result.home_allowed is True
    assert result.declared_sitemaps == ["https://example.com/sitemap.xml"]
    assert result.frontier == ["https://example.com/", "https://example.com/page"]


async def test_discover_follows_sitemap_index() -> None:
    fetch = make_fetcher(
        {
            "https://example.com/sitemap.xml": (
                200,
                _index("https://example.com/sm-pages.xml"),
                "application/xml",
            ),
            "https://example.com/sm-pages.xml": (
                200,
                _urlset("https://example.com/p1", "https://example.com/p2"),
                "application/xml",
            ),
        }
    )
    result = await discover("https://example.com", user_agent=UA, fetch=fetch)

    assert result.sitemap_valid is True
    assert result.sitemap_urls == ["https://example.com/p1", "https://example.com/p2"]


async def test_discover_respects_robots_disallow_in_frontier() -> None:
    responses: dict[str, tuple[int, bytes, str | None]] = {
        "https://example.com/robots.txt": (
            200,
            b"User-agent: *\nDisallow: /private/\n",
            "text/plain",
        ),
        "https://example.com/sitemap.xml": (
            200,
            _urlset("https://example.com/ok", "https://example.com/private/secret"),
            "application/xml",
        ),
    }
    blocked = await discover("https://example.com", user_agent=UA, fetch=make_fetcher(responses))
    # La page interdite est dans le sitemap mais pas dans la frontière.
    assert "https://example.com/private/secret" in blocked.sitemap_urls
    assert blocked.frontier == ["https://example.com/", "https://example.com/ok"]

    allowed = await discover(
        "https://example.com", user_agent=UA, fetch=make_fetcher(responses), respect_robots=False
    )
    assert "https://example.com/private/secret" in allowed.frontier


async def test_discover_excludes_disallowed_home() -> None:
    fetch = make_fetcher(
        {
            "https://example.com/robots.txt": (200, b"User-agent: *\nDisallow: /\n", "text/plain"),
        }
    )
    result = await discover("https://example.com", user_agent=UA, fetch=fetch)
    assert result.home_allowed is False
    assert result.frontier == []


async def test_discover_is_deterministic() -> None:
    responses: dict[str, tuple[int, bytes, str | None]] = {
        "https://example.com/robots.txt": (
            200,
            b"User-agent: *\nSitemap: https://example.com/sitemap.xml\n",
            "text/plain",
        ),
        "https://example.com/sitemap.xml": (
            200,
            _urlset("https://example.com/b", "https://example.com/a", "https://example.com/c"),
            "application/xml",
        ),
    }
    first = await discover("https://example.com", user_agent=UA, fetch=make_fetcher(responses))
    second = await discover("https://example.com", user_agent=UA, fetch=make_fetcher(responses))
    assert first.frontier == second.frontier
    # Tri stable indépendant de l'ordre du sitemap.
    assert first.frontier == [
        "https://example.com/",
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
