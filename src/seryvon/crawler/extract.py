# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Extraction déterministe de signaux internes depuis le HTML d'une page.

Signaux M3.1 complets : title, meta (description/robots/canonical), Open Graph,
Twitter Cards, hreflang, headings, contenu, JSON-LD types, liens (cibles internes
absolues pour le graphe de maillage), images. L'extraction est PURE
(HTML -> PageSignals, sans I/O), donc testable sur fixtures et reproductible.
"""

from __future__ import annotations

import json
from urllib.parse import urldefrag, urljoin, urlsplit

from selectolax.parser import HTMLParser

from seryvon.models.signals import PageSignals

# Schémas de href ignorés lors de l'expansion de la frontière de crawl.
_NON_HTTP_SCHEMES = ("#", "mailto:", "tel:", "javascript:", "data:")


def _host(url: str) -> str:
    """Hôte d'une URL en minuscules (chaîne vide si non analysable)."""
    return (urlsplit(url).hostname or "").lower()


def _links_from_tree(tree: HTMLParser, base_url: str) -> list[str]:
    """Liens HTTP(S) absolus d'un arbre, fragment retiré, dédupliqués et triés."""
    links: set[str] = set()
    for node in tree.css("a[href]"):
        href = (node.attributes.get("href") or "").strip()
        if not href or href.startswith(_NON_HTTP_SCHEMES):
            continue
        absolute = urldefrag(urljoin(base_url, href)).url
        if absolute.startswith(("http://", "https://")):
            links.add(absolute)
    return sorted(links)


def extract_links(html: str, base_url: str) -> list[str]:
    """Liens HTTP(S) absolus d'une page, fragment retiré, dédupliqués et triés.

    Utilisé par le crawler (M2) pour étendre la frontière. Le filtrage same-host
    et le respect de robots.txt sont appliqués par l'appelant, pas ici (fonction
    pure, déterministe : même HTML => mêmes liens dans le même ordre).
    """
    return _links_from_tree(HTMLParser(html), base_url)


def _text_ratio(html: str, text: str) -> float | None:
    """Ratio texte visible / taille HTML brute. None si HTML vide."""
    html_len = len(html)
    if html_len == 0:
        return None
    return round(len(text) / html_len, 4)


def _structured_data_types(tree: HTMLParser) -> list[str]:
    """Extrait les `@type` des blocs JSON-LD (récursif minimal, support `@graph`)."""
    types: list[str] = []
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        types.extend(_collect_types(data))
    # Déterminisme : tri + déduplication stable.
    return sorted(set(types))


def _collect_types(node: object) -> list[str]:
    """Collecte récursivement les valeurs de `@type` dans un objet JSON-LD."""
    found: list[str] = []
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            found.append(t)
        elif isinstance(t, list):
            found.extend(x for x in t if isinstance(x, str))
        for value in node.values():
            found.extend(_collect_types(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_types(item))
    return found


def extract_page_signals(
    url: str,
    html: str,
    *,
    status_code: int | None = None,
    redirects: int = 0,
) -> PageSignals:
    """Transforme le HTML d'une page en `PageSignals` (signaux internes complets)."""
    tree = HTMLParser(html)

    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else None

    description = None
    meta_robots = None
    open_graph: dict[str, str] = {}
    twitter_card: dict[str, str] = {}
    for meta in tree.css("meta"):
        attrs = meta.attributes
        name = (attrs.get("name") or "").lower()
        prop = (attrs.get("property") or "").lower()
        content = attrs.get("content")
        if name == "description":
            description = content
        elif name == "robots":
            meta_robots = content
        key = prop or name
        if key.startswith("og:"):
            open_graph[key] = content or ""
        elif key.startswith("twitter:"):
            twitter_card[key] = content or ""

    canonical = None
    for link in tree.css('link[rel="canonical"]'):
        canonical = link.attributes.get("href")
        break

    hreflang: dict[str, str] = {}
    for link in tree.css('link[rel="alternate"]'):
        lang = (link.attributes.get("hreflang") or "").strip()
        if lang:
            hreflang[lang] = (link.attributes.get("href") or "").strip()

    headings: dict[str, int] = {}
    for level in range(1, 7):
        tag = f"h{level}"
        count = len(tree.css(tag))
        if count:
            headings[tag] = count

    body = tree.body
    visible_text = body.text(separator=" ", strip=True) if body else ""
    word_count = len(visible_text.split())

    images = tree.css("img")
    images_with_alt = sum(1 for img in images if (img.attributes.get("alt") or "").strip())

    page_host = _host(url)
    all_links = _links_from_tree(tree, url)
    internal_targets = [link for link in all_links if _host(link) == page_host]
    external_links = len(all_links) - len(internal_targets)

    return PageSignals(
        url=url,
        status_code=status_code,
        redirects=redirects,
        title=title,
        meta_description=description,
        canonical=canonical,
        meta_robots=meta_robots,
        open_graph=open_graph,
        twitter_card=twitter_card,
        hreflang=hreflang,
        h1_count=headings.get("h1", 0),
        headings=headings,
        word_count=word_count,
        text_ratio=_text_ratio(html, visible_text),
        structured_data_types=_structured_data_types(tree),
        internal_links=len(internal_targets),
        external_links=external_links,
        internal_link_targets=internal_targets,
        images_total=len(images),
        images_with_alt=images_with_alt,
    )
