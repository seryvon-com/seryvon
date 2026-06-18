# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""M1 Discovery: domain normalization, robots.txt, sitemaps, crawl frontier.

A *collection*-layer module: it performs I/O (fetch robots.txt + sitemaps),
strictly separate from scoring. The parsing logic (`normalize_url`,
`parse_sitemap`, `RobotsTxt`) is pure and testable without a network; only
`discover()` orchestrates the fetches, via an injectable `fetch` (test
determinism, document 03 §9).

robots.txt compliance (ENF-04, acceptance criterion §8) is delegated to `protego`
(RFC 9309: `*`/`$` wildcards, longest-match, crawl-delay, Sitemap). A missing
robots.txt => everything allowed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx
from protego import Protego

from seryvon.crawler.fetch import FetchedResource

# Sitemap size limit (sitemaps.org spec: 50 MiB uncompressed).
_MAX_SITEMAP_BYTES = 52_428_800
_GZIP_MAGIC = b"\x1f\x8b"
_DEFAULT_PORTS = {"http": "80", "https": "443"}

DEFAULT_MAX_SITEMAP_URLS = 5000
DEFAULT_MAX_INDEX_DEPTH = 3

# User-agents of known AI agent bots (aso.agent_access criterion).
AGENT_BOTS = (
    "OAI-SearchBot",
    "ChatGPT-User",
    "GPTBot",
    "PerplexityBot",
    "ClaudeBot",
    "Claude-Web",
    "Google-Extended",
    "CCBot",
    "Amazonbot",
)

#: Fetch a raw resource by URL (injectable for tests).
ResourceFetcher = Callable[[str], Awaitable[FetchedResource]]


@dataclass(frozen=True, slots=True)
class NormalizedUrl:
    """Canonical URL: lowercased host, default port removed, fragment stripped."""

    url: str  # full canonical URL (seed/home)
    origin: str  # scheme://host[:port]
    scheme: str
    host: str  # lowercased host, no trailing dot


def normalize_url(raw: str) -> NormalizedUrl:
    """Normalize a URL or bare domain into a deterministic canonical form.

    - Missing scheme => `https`.
    - Host and scheme lowercased; trailing dot of the host removed.
    - Default port (80/443) removed; empty path => `/`; fragment stripped.
    """
    candidate = raw.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError(f"URL without a usable host: {raw!r}")

    netloc = host
    port = parts.port
    if port is not None and _DEFAULT_PORTS.get(scheme) != str(port):
        netloc = f"{host}:{port}"

    origin = f"{scheme}://{netloc}"
    path = parts.path or "/"
    url = urlunsplit((scheme, netloc, path, parts.query, ""))
    return NormalizedUrl(url=url, origin=origin, scheme=scheme, host=host)


class RobotsTxt:
    """Parsed robots.txt (protego), with RFC 9309 semantics.

    A missing or unreadable robots.txt => everything allowed (`found=False`).
    """

    def __init__(self, *, parser: Protego | None, found: bool) -> None:
        self._parser = parser
        self.found = found

    @classmethod
    def parse(cls, text: str) -> RobotsTxt:
        """Build from the text of a fetched robots.txt."""
        return cls(parser=Protego.parse(text), found=True)

    @classmethod
    def allow_all(cls) -> RobotsTxt:
        """Missing robots.txt: no restriction (RFC 9309)."""
        return cls(parser=None, found=False)

    def can_fetch(self, url: str, user_agent: str) -> bool:
        """Whether `user_agent` may fetch `url`."""
        if self._parser is None:
            return True
        return bool(self._parser.can_fetch(url, user_agent))

    def crawl_delay(self, user_agent: str) -> float | None:
        """Politeness delay declared for `user_agent`, or None."""
        if self._parser is None:
            return None
        delay = self._parser.crawl_delay(user_agent)
        return float(delay) if delay is not None else None

    @property
    def sitemaps(self) -> list[str]:
        """Sitemaps declared via `Sitemap:` lines."""
        if self._parser is None:
            return []
        return list(self._parser.sitemaps)


@dataclass(slots=True)
class SitemapParseResult:
    """Result of parsing a sitemap: URLs (urlset) or sub-sitemaps (index)."""

    urls: list[str]
    sitemaps: list[str]
    is_index: bool
    valid: bool


def _localname(tag: str) -> str:
    """Local name of an XML tag, namespace removed, lowercased."""
    return tag.rsplit("}", 1)[-1].lower()


def _collect_locs(root: ET.Element, child_tag: str) -> list[str]:
    """Collect the `<loc>` values of `child_tag` children (`url` or `sitemap`)."""
    locs: list[str] = []
    for child in root:
        if _localname(child.tag) != child_tag:
            continue
        for sub in child:
            if _localname(sub.tag) == "loc" and sub.text:
                loc = sub.text.strip()
                if loc:
                    locs.append(loc)
    return locs


def _gunzip_bounded(data: bytes, max_size: int) -> bytes:
    """Decompress gzip with a strict bound (gzip-bomb protection)."""
    decompressor = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    out = decompressor.decompress(data, max_size + 1)
    if len(out) > max_size or decompressor.unconsumed_tail:
        raise OSError("decompressed sitemap too large")
    out += decompressor.flush()
    if len(out) > max_size:
        raise OSError("decompressed sitemap too large")
    return out


def _maybe_gunzip(
    content: bytes, *, content_type: str | None, source_url: str | None
) -> bytes | None:
    """Decompress if the content is gzipped (magic bytes / content-type / extension)."""
    is_gzip = content[:2] == _GZIP_MAGIC
    if not is_gzip and content_type and "gzip" in content_type.lower():
        is_gzip = True
    if not is_gzip and source_url and source_url.lower().endswith(".gz"):
        is_gzip = True
    if not is_gzip:
        return content
    try:
        return _gunzip_bounded(content, _MAX_SITEMAP_BYTES)
    except (OSError, zlib.error, EOFError):
        return None


def parse_sitemap(
    content: bytes,
    *,
    content_type: str | None = None,
    source_url: str | None = None,
) -> SitemapParseResult:
    """Parse a sitemap (urlset or sitemapindex), gzip handled. Pure and deterministic.

    Security: any DTD/entity is rejected before parsing (XXE / billion-laughs guard) —
    a conformant sitemap never contains one. The size is bounded.
    """
    invalid = SitemapParseResult(urls=[], sitemaps=[], is_index=False, valid=False)

    raw = _maybe_gunzip(content, content_type=content_type, source_url=source_url)
    if raw is None or len(raw) > _MAX_SITEMAP_BYTES:
        return invalid

    prologue = raw[:4096].lower()
    if b"<!doctype" in prologue or b"<!entity" in prologue:
        return invalid

    try:
        # DTD/entities already rejected above: no entity expansion is possible.
        root = ET.fromstring(raw)
    except ET.ParseError:
        return invalid

    tag = _localname(root.tag)
    if tag == "sitemapindex":
        return SitemapParseResult(
            urls=[], sitemaps=_collect_locs(root, "sitemap"), is_index=True, valid=True
        )
    if tag == "urlset":
        return SitemapParseResult(
            urls=_collect_locs(root, "url"), sitemaps=[], is_index=False, valid=True
        )
    return invalid


def same_host(url: str, host: str) -> bool:
    """True if `url` is on the same host (case-insensitive comparison)."""
    try:
        parsed_host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return parsed_host == host


def blocked_agent_bots(robots: RobotsTxt, url: str) -> list[str]:
    """AI agent bots (`AGENT_BOTS`) denied access to `url` by robots.txt."""
    return sorted(bot for bot in AGENT_BOTS if not robots.can_fetch(url, bot))


@dataclass(slots=True)
class DiscoveryResult:
    """M1 output: everything the crawler (M2) needs to start.

    `robots` is kept so the crawler can check `can_fetch` on URLs discovered along
    the way without re-fetching robots.txt.
    """

    home_url: str
    origin: str
    domain: str
    robots: RobotsTxt
    robots_found: bool
    crawl_delay: float | None
    declared_sitemaps: list[str]  # declared (robots) + /sitemap.xml candidate
    sitemap_urls: list[str]  # same-host URLs extracted from the sitemaps, sorted
    sitemap_valid: bool  # at least one sitemap parsed successfully
    home_allowed: bool
    frontier: list[str]  # deterministic crawl seeds: home then allowed sitemap_urls


async def _run_discovery(
    norm: NormalizedUrl,
    fetch: ResourceFetcher,
    *,
    user_agent: str,
    respect_robots: bool,
    max_sitemap_urls: int,
    max_index_depth: int,
) -> DiscoveryResult:
    """Discovery orchestration from a fetcher (real or injected)."""
    # 1. robots.txt
    robots = RobotsTxt.allow_all()
    try:
        resp = await fetch(f"{norm.origin}/robots.txt")
    except httpx.HTTPError:
        resp = None
    if resp is not None and resp.status_code == 200 and resp.content:
        robots = RobotsTxt.parse(resp.content.decode("utf-8", errors="replace"))

    crawl_delay = robots.crawl_delay(user_agent) if respect_robots else None

    # 2. sitemaps: those declared in robots + the default candidate.
    declared = list(dict.fromkeys([*robots.sitemaps, f"{norm.origin}/sitemap.xml"]))

    sitemap_urls: set[str] = set()
    sitemap_valid = False
    seen: set[str] = set()
    queue = list(declared)
    depth = 0
    while queue and depth < max_index_depth:
        next_queue: list[str] = []
        for sm_url in queue:
            if sm_url in seen:
                continue
            seen.add(sm_url)
            try:
                sm_resp = await fetch(sm_url)
            except httpx.HTTPError:
                continue
            if sm_resp.status_code != 200 or not sm_resp.content:
                continue
            parsed = parse_sitemap(
                sm_resp.content, content_type=sm_resp.content_type, source_url=sm_url
            )
            if not parsed.valid:
                continue
            sitemap_valid = True
            if parsed.is_index:
                next_queue.extend(parsed.sitemaps)
            else:
                sitemap_urls.update(loc for loc in parsed.urls if same_host(loc, norm.host))
        queue = next_queue
        depth += 1

    # 3. deterministic frontier: home first, then allowed sitemap URLs, sorted.
    ordered = sorted(sitemap_urls)[:max_sitemap_urls]
    home_allowed = robots.can_fetch(norm.url, user_agent) if respect_robots else True
    frontier: list[str] = [norm.url] if home_allowed else []
    for url in ordered:
        if url == norm.url:
            continue
        if respect_robots and not robots.can_fetch(url, user_agent):
            continue
        frontier.append(url)

    return DiscoveryResult(
        home_url=norm.url,
        origin=norm.origin,
        domain=norm.host,
        robots=robots,
        robots_found=robots.found,
        crawl_delay=crawl_delay,
        declared_sitemaps=declared,
        sitemap_urls=ordered,
        sitemap_valid=sitemap_valid,
        home_allowed=home_allowed,
        frontier=frontier,
    )


async def discover(
    raw_url: str,
    *,
    user_agent: str,
    timeout: float = 15.0,
    respect_robots: bool = True,
    fetch: ResourceFetcher | None = None,
    max_sitemap_urls: int = DEFAULT_MAX_SITEMAP_URLS,
    max_index_depth: int = DEFAULT_MAX_INDEX_DEPTH,
) -> DiscoveryResult:
    """Run M1 Discovery on a URL and return the initial crawl frontier.

    If `fetch` is provided (tests), it is used as-is; otherwise a shared httpx
    client is opened for the duration of discovery.
    """
    norm = normalize_url(raw_url)
    if fetch is not None:
        return await _run_discovery(
            norm,
            fetch,
            user_agent=user_agent,
            respect_robots=respect_robots,
            max_sitemap_urls=max_sitemap_urls,
            max_index_depth=max_index_depth,
        )

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": user_agent},
    ) as client:

        async def _fetch(url: str) -> FetchedResource:
            response = await client.get(url)
            return FetchedResource(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content=response.content,
                content_type=response.headers.get("content-type"),
            )

        return await _run_discovery(
            norm,
            _fetch,
            user_agent=user_agent,
            respect_robots=respect_robots,
            max_sitemap_urls=max_sitemap_urls,
            max_index_depth=max_index_depth,
        )
