# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Extraction déterministe de signaux internes depuis le HTML d'une page.

Phase 0 : signaux de base (title, meta, headings, contenu, JSON-LD types,
liens, images). L'extraction est PURE (HTML -> PageSignals, sans I/O), donc
testable sur fixtures et reproductible.
"""

from __future__ import annotations

import json

from selectolax.parser import HTMLParser

from seryvon.models.signals import PageSignals


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
) -> PageSignals:
    """Transforme le HTML d'une page en `PageSignals` (signaux internes de base)."""
    tree = HTMLParser(html)

    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else None

    description = None
    canonical = None
    meta_robots = None
    for meta in tree.css("meta"):
        name = (meta.attributes.get("name") or "").lower()
        if name == "description":
            description = meta.attributes.get("content")
        elif name == "robots":
            meta_robots = meta.attributes.get("content")
    for link in tree.css('link[rel="canonical"]'):
        canonical = link.attributes.get("href")
        break

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

    internal_links = 0
    external_links = 0
    for a in tree.css("a[href]"):
        href = a.attributes.get("href") or ""
        if href.startswith(("http://", "https://")):
            external_links += 1
        elif href.startswith(("/", "#", ".")) or not href.startswith("mailto:"):
            internal_links += 1

    return PageSignals(
        url=url,
        status_code=status_code,
        title=title,
        meta_description=description,
        canonical=canonical,
        meta_robots=meta_robots,
        h1_count=headings.get("h1", 0),
        headings=headings,
        word_count=word_count,
        text_ratio=_text_ratio(html, visible_text),
        structured_data_types=_structured_data_types(tree),
        internal_links=internal_links,
        external_links=external_links,
        images_total=len(images),
        images_with_alt=images_with_alt,
    )
