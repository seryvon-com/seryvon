# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""M1 Discovery : normalisation du domaine, robots.txt, sitemaps, frontière de crawl.

Module de la couche *collecte* : il fait des I/O (fetch robots.txt + sitemaps),
strictement séparé du scoring. La logique de parsing (`normalize_url`,
`parse_sitemap`, `RobotsTxt`) est pure et testable sans réseau ; seule
`discover()` orchestre les fetchs, via un `fetch` injectable (déterminisme des
tests, document 03 §9).

Conformité robots.txt (ENF-04, critère d'acceptation §8) déléguée à `protego`
(RFC 9309 : wildcards `*`/`$`, longest-match, crawl-delay, Sitemap). Un robots.txt
absent => tout autorisé.
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

# Limite de taille d'un sitemap (spec sitemaps.org : 50 Mio non compressés).
_MAX_SITEMAP_BYTES = 52_428_800
_GZIP_MAGIC = b"\x1f\x8b"
_DEFAULT_PORTS = {"http": "80", "https": "443"}

DEFAULT_MAX_SITEMAP_URLS = 5000
DEFAULT_MAX_INDEX_DEPTH = 3

# User-agents de bots d'agents IA connus (critère aso.agent_access).
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

#: Récupère une ressource brute par URL (injectable pour les tests).
ResourceFetcher = Callable[[str], Awaitable[FetchedResource]]


@dataclass(frozen=True, slots=True)
class NormalizedUrl:
    """URL canonique : hôte en minuscules, port par défaut retiré, fragment supprimé."""

    url: str  # URL complète canonique (seed/home)
    origin: str  # scheme://host[:port]
    scheme: str
    host: str  # hôte en minuscules, sans point final


def normalize_url(raw: str) -> NormalizedUrl:
    """Normalise une URL ou un domaine nu en forme canonique déterministe.

    - Schéma absent => `https`.
    - Hôte et schéma en minuscules ; point final de l'hôte retiré.
    - Port par défaut (80/443) retiré ; chemin vide => `/` ; fragment supprimé.
    """
    candidate = raw.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError(f"URL sans hôte exploitable : {raw!r}")

    netloc = host
    port = parts.port
    if port is not None and _DEFAULT_PORTS.get(scheme) != str(port):
        netloc = f"{host}:{port}"

    origin = f"{scheme}://{netloc}"
    path = parts.path or "/"
    url = urlunsplit((scheme, netloc, path, parts.query, ""))
    return NormalizedUrl(url=url, origin=origin, scheme=scheme, host=host)


class RobotsTxt:
    """robots.txt parsé (protego), avec sémantique RFC 9309.

    Un robots.txt absent ou illisible => tout autorisé (`found=False`).
    """

    def __init__(self, *, parser: Protego | None, found: bool) -> None:
        self._parser = parser
        self.found = found

    @classmethod
    def parse(cls, text: str) -> RobotsTxt:
        """Construit depuis le texte d'un robots.txt récupéré."""
        return cls(parser=Protego.parse(text), found=True)

    @classmethod
    def allow_all(cls) -> RobotsTxt:
        """robots.txt absent : aucune restriction (RFC 9309)."""
        return cls(parser=None, found=False)

    def can_fetch(self, url: str, user_agent: str) -> bool:
        """Indique si `user_agent` peut récupérer `url`."""
        if self._parser is None:
            return True
        return bool(self._parser.can_fetch(url, user_agent))

    def crawl_delay(self, user_agent: str) -> float | None:
        """Délai de politesse déclaré pour `user_agent`, ou None."""
        if self._parser is None:
            return None
        delay = self._parser.crawl_delay(user_agent)
        return float(delay) if delay is not None else None

    @property
    def sitemaps(self) -> list[str]:
        """Sitemaps déclarés via les lignes `Sitemap:`."""
        if self._parser is None:
            return []
        return list(self._parser.sitemaps)


@dataclass(slots=True)
class SitemapParseResult:
    """Résultat du parsing d'un sitemap : URLs (urlset) ou sous-sitemaps (index)."""

    urls: list[str]
    sitemaps: list[str]
    is_index: bool
    valid: bool


def _localname(tag: str) -> str:
    """Nom local d'une balise XML, namespace retiré, en minuscules."""
    return tag.rsplit("}", 1)[-1].lower()


def _collect_locs(root: ET.Element, child_tag: str) -> list[str]:
    """Collecte les `<loc>` des enfants `child_tag` (`url` ou `sitemap`)."""
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
    """Décompresse du gzip avec une borne stricte (protection anti gzip-bomb)."""
    decompressor = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    out = decompressor.decompress(data, max_size + 1)
    if len(out) > max_size or decompressor.unconsumed_tail:
        raise OSError("sitemap décompressé trop volumineux")
    out += decompressor.flush()
    if len(out) > max_size:
        raise OSError("sitemap décompressé trop volumineux")
    return out


def _maybe_gunzip(
    content: bytes, *, content_type: str | None, source_url: str | None
) -> bytes | None:
    """Décompresse si le contenu est gzippé (magic bytes / content-type / extension)."""
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
    """Parse un sitemap (urlset ou sitemapindex), gzip géré. Pur et déterministe.

    Sécurité : tout DTD/entité est refusé avant parsing (parade XXE / billion laughs) —
    un sitemap conforme n'en contient jamais. La taille est bornée.
    """
    invalid = SitemapParseResult(urls=[], sitemaps=[], is_index=False, valid=False)

    raw = _maybe_gunzip(content, content_type=content_type, source_url=source_url)
    if raw is None or len(raw) > _MAX_SITEMAP_BYTES:
        return invalid

    prologue = raw[:4096].lower()
    if b"<!doctype" in prologue or b"<!entity" in prologue:
        return invalid

    try:
        # DTD/entités déjà refusés ci-dessus : pas d'expansion d'entité possible.
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
    """Vrai si `url` est sur le même hôte (comparaison insensible à la casse)."""
    try:
        parsed_host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return parsed_host == host


def blocked_agent_bots(robots: RobotsTxt, url: str) -> list[str]:
    """Bots d'agents IA (`AGENT_BOTS`) interdits d'accès à `url` par robots.txt."""
    return sorted(bot for bot in AGENT_BOTS if not robots.can_fetch(url, bot))


@dataclass(slots=True)
class DiscoveryResult:
    """Sortie de M1 : tout ce dont le crawler (M2) a besoin pour démarrer.

    `robots` est conservé pour que le crawler vérifie `can_fetch` sur les URLs
    découvertes en cours de route sans re-récupérer robots.txt.
    """

    home_url: str
    origin: str
    domain: str
    robots: RobotsTxt
    robots_found: bool
    crawl_delay: float | None
    declared_sitemaps: list[str]  # déclarés (robots) + candidat /sitemap.xml
    sitemap_urls: list[str]  # URLs same-host extraites des sitemaps, triées
    sitemap_valid: bool  # au moins un sitemap parsé avec succès
    home_allowed: bool
    frontier: list[str]  # seeds de crawl déterministes : home puis sitemap_urls autorisées


async def _run_discovery(
    norm: NormalizedUrl,
    fetch: ResourceFetcher,
    *,
    user_agent: str,
    respect_robots: bool,
    max_sitemap_urls: int,
    max_index_depth: int,
) -> DiscoveryResult:
    """Orchestration de la découverte à partir d'un fetcher (réel ou injecté)."""
    # 1. robots.txt
    robots = RobotsTxt.allow_all()
    try:
        resp = await fetch(f"{norm.origin}/robots.txt")
    except httpx.HTTPError:
        resp = None
    if resp is not None and resp.status_code == 200 and resp.content:
        robots = RobotsTxt.parse(resp.content.decode("utf-8", errors="replace"))

    crawl_delay = robots.crawl_delay(user_agent) if respect_robots else None

    # 2. sitemaps : ceux déclarés dans robots + le candidat par défaut.
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

    # 3. frontière déterministe : home en tête, puis URLs sitemap autorisées, triées.
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
    """Exécute M1 Discovery sur une URL et renvoie la frontière de crawl initiale.

    Si `fetch` est fourni (tests), il est utilisé tel quel ; sinon un client httpx
    partagé est ouvert le temps de la découverte.
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
