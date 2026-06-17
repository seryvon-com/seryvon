# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Extraction déterministe de signaux internes depuis le HTML d'une page.

M3.1 : title, meta (description/robots/canonical), Open Graph, Twitter, hreflang,
headings, contenu, JSON-LD types, liens (cibles internes), images.
M3.2 (Phase 2) : analyse JSON-LD enrichie (potentialAction, schemas d'action,
auteurs/credentials, dates), comptages on-page (tables, listes de définition,
titres-questions, paragraphe d'accroche) et signaux ASO statiques (WebMCP,
formulaires agent-usables, OpenAPI). L'extraction est PURE (HTML -> PageSignals,
sans I/O), donc testable sur fixtures et reproductible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit

from selectolax.parser import HTMLParser

from seryvon.models.signals import AsoSignals, PageSignals, WebMcpSignals

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


# Types de schema « actionnables » qu'un agent consomme pour agir (pilier ASO).
_ACTION_SCHEMA_TYPES = {"Product", "Service", "Event", "HowTo"}
# Clés signalant des credentials d'auteur (pilier AEO).
_AUTHOR_CREDENTIAL_KEYS = ("jobTitle", "knowsAbout", "sameAs", "affiliation", "award", "alumniOf")
# Indices d'URL d'API documentée (pilier ASO).
_OPENAPI_HINTS = ("openapi", "swagger", "api-docs")


@dataclass(slots=True)
class _JsonLdAnalysis:
    """Synthèse déterministe des blocs JSON-LD d'une page."""

    types: list[str]
    potential_actions: list[str]
    action_schema_types: list[str]
    has_author: bool
    author_has_credentials: bool
    has_structured_dates: bool


def _type_names(node: dict[str, object]) -> list[str]:
    """Valeurs `@type` d'un nœud (str ou liste de str)."""
    raw = node.get("@type")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, str)]
    return []


def _collect_types(node: object) -> list[str]:
    """Collecte récursivement les `@type` sous un nœud JSON-LD."""
    found: list[str] = []
    if isinstance(node, dict):
        found.extend(_type_names(node))
        for value in node.values():
            found.extend(_collect_types(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_types(item))
    return found


def _analyze_jsonld(tree: HTMLParser) -> _JsonLdAnalysis:
    """Parcourt les blocs JSON-LD (support `@graph`) une fois et en tire les signaux.

    Pure et déterministe : sorties triées. Couvre les types, les `potentialAction`,
    les schemas d'action riches, la présence d'auteur/credentials et de dates.
    """
    types: set[str] = set()
    potential_actions: set[str] = set()
    has_author = False
    author_has_credentials = False
    has_dates = False

    def walk(node: object) -> None:
        nonlocal has_author, author_has_credentials, has_dates
        if isinstance(node, dict):
            names = _type_names(node)
            types.update(names)
            if "Person" in names:
                has_author = True
                if any(key in node for key in _AUTHOR_CREDENTIAL_KEYS):
                    author_has_credentials = True
            if "author" in node:
                has_author = True
            if "datePublished" in node or "dateModified" in node:
                has_dates = True
            action = node.get("potentialAction")
            if action is not None:
                potential_actions.update(_collect_types(action))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        walk(data)

    return _JsonLdAnalysis(
        types=sorted(types),
        potential_actions=sorted(potential_actions),
        action_schema_types=sorted(types & _ACTION_SCHEMA_TYPES),
        has_author=has_author,
        author_has_credentials=author_has_credentials,
        has_structured_dates=has_dates,
    )


def _webmcp_signals(tree: HTMLParser, html: str) -> WebMcpSignals:
    """Détecte WebMCP statiquement (D9) : API impérative dans les scripts, attributs déclaratifs."""
    low = html.lower()
    has_register = "registertool" in low or "navigator.modelcontext" in low
    tool_count = len(tree.css("[toolname]"))
    has_attrs = tool_count > 0
    partial = ("modelcontext" in low) and not (has_register or has_attrs)
    return WebMcpSignals(
        has_register_tool=has_register,
        has_tool_attributes=has_attrs,
        tool_count=tool_count,
        partial_signals=partial,
    )


def _agent_usable_forms(tree: HTMLParser) -> int:
    """Compte les formulaires exploitables par un agent (action/méthode + inputs labellisés)."""
    count = 0
    for form in tree.css("form"):
        if not (form.attributes.get("action") or form.attributes.get("method")):
            continue
        fields = form.css("input, select, textarea")
        if not fields:
            continue
        labelled = bool(form.css("label")) or any(
            (field.attributes.get("aria-label") or field.attributes.get("placeholder"))
            for field in fields
        )
        if labelled:
            count += 1
    return count


def _openapi_links(tree: HTMLParser) -> list[str]:
    """Liens vers une API documentée (`<a>`/`<link>` pointant openapi/swagger/api-docs)."""
    links: set[str] = set()
    for node in tree.css("a[href], link[href]"):
        href = (node.attributes.get("href") or "").strip()
        if href and any(hint in href.lower() for hint in _OPENAPI_HINTS):
            links.add(href)
    return sorted(links)


def _aso_signals(tree: HTMLParser, html: str, jsonld: _JsonLdAnalysis) -> AsoSignals:
    """Assemble les signaux ASO statiques (M11, transposé de audit_webmcp.py — MIT)."""
    return AsoSignals(
        webmcp=_webmcp_signals(tree, html),
        potential_actions=jsonld.potential_actions,
        action_schema_types=jsonld.action_schema_types,
        agent_usable_forms=_agent_usable_forms(tree),
        openapi_links=_openapi_links(tree),
    )


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

    jsonld = _analyze_jsonld(tree)
    question_headings = sum(1 for h in tree.css("h2, h3, h4") if h.text(strip=True).endswith("?"))
    main = tree.css_first("main") or body
    lead = main.css_first("p") if main else None
    lead_paragraph_words = len(lead.text(strip=True).split()) if lead else 0

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
        structured_data_types=jsonld.types,
        internal_links=len(internal_targets),
        external_links=external_links,
        internal_link_targets=internal_targets,
        images_total=len(images),
        images_with_alt=images_with_alt,
        tables_count=len(tree.css("table")),
        definition_lists_count=len(tree.css("dl")),
        question_headings=question_headings,
        lead_paragraph_words=lead_paragraph_words,
        has_author=jsonld.has_author,
        author_has_credentials=jsonld.author_has_credentials,
        has_structured_dates=jsonld.has_structured_dates,
        aso=_aso_signals(tree, html, jsonld),
    )
