# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Deterministic extraction of internal signals from a page's HTML.

M3.1: title, meta (description/robots/canonical), Open Graph, Twitter, hreflang,
headings, content, JSON-LD types, links (internal targets), images.
M3.2 (Phase 2): enriched JSON-LD analysis (potentialAction, action schemas,
authors/credentials, dates), on-page counts (tables, definition lists,
question headings, lead paragraph) and static ASO signals (WebMCP,
agent-usable forms, OpenAPI).
M3.3 (GEO core): main-content/noise ratio, estimated entities (heuristic),
outbound domains, content date, cross-surface platforms. Extraction is PURE
(HTML -> PageSignals, no I/O), so it is testable on fixtures and reproducible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit

from selectolax.parser import HTMLParser

from seryvon.models.signals import AsoSignals, PageSignals, WebMcpSignals

# href schemes ignored when expanding the crawl frontier.
_NON_HTTP_SCHEMES = ("#", "mailto:", "tel:", "javascript:", "data:")


def _host(url: str) -> str:
    """Lowercased host of a URL (empty string if not parseable)."""
    return (urlsplit(url).hostname or "").lower()


def _links_from_tree(tree: HTMLParser, base_url: str) -> list[str]:
    """Absolute HTTP(S) links of a tree, fragment removed, deduplicated and sorted."""
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
    """Absolute HTTP(S) links of a page, fragment removed, deduplicated and sorted.

    Used by the crawler (M2) to expand the frontier. Same-host filtering and
    robots.txt compliance are applied by the caller, not here (pure, deterministic
    function: same HTML => same links in the same order).
    """
    return _links_from_tree(HTMLParser(html), base_url)


def _text_ratio(html: str, text: str) -> float | None:
    """Visible-text / raw-HTML size ratio. None if HTML is empty."""
    html_len = len(html)
    if html_len == 0:
        return None
    return round(len(text) / html_len, 4)


# "Actionable" schema types an agent consumes to act (ASO pillar).
_ACTION_SCHEMA_TYPES = {"Product", "Service", "Event", "HowTo"}
# Keys signalling author credentials (AEO pillar).
_AUTHOR_CREDENTIAL_KEYS = ("jobTitle", "knowsAbout", "sameAs", "affiliation", "award", "alumniOf")
# URL hints of a documented API (ASO pillar).
_OPENAPI_HINTS = ("openapi", "swagger", "api-docs")
# Estimated entity (GEO heuristic, DG1): alphabetic capitalized token, length >= 3.
_ENTITY_RE = re.compile(r"\b[A-ZÀ-Ý][\wÀ-ÿ]{2,}\b")
# Recognized cross-surface platforms (GEO/ASO pillar): host fragment -> name.
_PLATFORM_HOSTS = {
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "github.com": "github",
    "tiktok.com": "tiktok",
    "pinterest.com": "pinterest",
    "mastodon": "mastodon",
    "reddit.com": "reddit",
}


@dataclass(slots=True)
class _JsonLdAnalysis:
    """Deterministic summary of a page's JSON-LD blocks."""

    types: list[str]
    potential_actions: list[str]
    action_schema_types: list[str]
    has_author: bool
    author_has_credentials: bool
    has_structured_dates: bool
    content_date: str | None
    same_as: list[str]


def _type_names(node: dict[str, object]) -> list[str]:
    """`@type` values of a node (str or list of str)."""
    raw = node.get("@type")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, str)]
    return []


def _collect_types(node: object) -> list[str]:
    """Recursively collect the `@type` values under a JSON-LD node."""
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
    """Walk the JSON-LD blocks (with `@graph` support) once and derive the signals.

    Pure and deterministic: sorted outputs. Covers types, `potentialAction`,
    rich action schemas, the presence of author/credentials and of dates.
    """
    types: set[str] = set()
    potential_actions: set[str] = set()
    same_as: set[str] = set()
    dates: list[str] = []
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
            for date_key in ("datePublished", "dateModified"):
                value = node.get(date_key)
                if isinstance(value, str):
                    has_dates = True
                    dates.append(value)
            same = node.get("sameAs")
            if isinstance(same, str):
                same_as.add(same)
            elif isinstance(same, list):
                same_as.update(x for x in same if isinstance(x, str))
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
        content_date=max(dates) if dates else None,
        same_as=sorted(same_as),
    )


def _webmcp_signals(tree: HTMLParser, html: str) -> WebMcpSignals:
    """Detect WebMCP statically (D9): imperative API in scripts, declarative attributes."""
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
    """Count agent-usable forms (action/method + labelled inputs)."""
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
    """Links to a documented API (`<a>`/`<link>` pointing to openapi/swagger/api-docs)."""
    links: set[str] = set()
    for node in tree.css("a[href], link[href]"):
        href = (node.attributes.get("href") or "").strip()
        if href and any(hint in href.lower() for hint in _OPENAPI_HINTS):
            links.add(href)
    return sorted(links)


def _aso_signals(tree: HTMLParser, html: str, jsonld: _JsonLdAnalysis) -> AsoSignals:
    """Assemble the static ASO signals (M11, adapted from audit_webmcp.py — MIT)."""
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
    """Turn a page's HTML into `PageSignals` (complete internal signals)."""
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

    # M3.3 signals (GEO core).
    main_node = tree.css_first("main") or tree.css_first("article")
    if main_node is not None:
        main_words = len(main_node.text(separator=" ", strip=True).split())
    else:
        boilerplate = sum(
            len(node.text(separator=" ", strip=True).split())
            for selector in ("nav", "header", "footer", "aside")
            for node in tree.css(selector)
        )
        main_words = max(0, word_count - boilerplate)
    main_text_ratio = round(main_words / word_count, 4) if word_count else None
    entity_count = len(set(_ENTITY_RE.findall(visible_text)))
    external_link_domains = sorted(
        {_host(link) for link in all_links if _host(link) and _host(link) != page_host}
    )
    candidate_hosts = [*external_link_domains, *(_host(u) for u in jsonld.same_as)]
    social_platforms = sorted(
        {
            name
            for host in candidate_hosts
            for fragment, name in _PLATFORM_HOSTS.items()
            if fragment in host
        }
    )

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
        main_text_ratio=main_text_ratio,
        entity_count=entity_count,
        external_link_domains=external_link_domains,
        content_date=jsonld.content_date,
        social_platforms=social_platforms,
        aso=_aso_signals(tree, html, jsonld),
    )
