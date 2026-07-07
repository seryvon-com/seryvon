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


def _is_decorative_svg(svg: object) -> bool:
    """True if an <svg> is marked decorative/hidden and exempt from `img.svg_alt`.

    Covers `aria-hidden="true"`, `role="presentation"/"none"`, and inline
    `display:none` icon-sprite sheets (defining <symbol>s, never rendered directly).
    """
    attrs = svg.attributes  # type: ignore[attr-defined]
    if (attrs.get("aria-hidden") or "").strip().lower() == "true":
        return True
    if (attrs.get("role") or "").strip().lower() in ("presentation", "none"):
        return True
    style = (attrs.get("style") or "").replace(" ", "").lower()
    return "display:none" in style


#: Elements whose own accessible name is what a screen reader announces for
#: an icon nested inside them (WCAG accessible-name computation).
_INTERACTIVE_TAGS = ("a", "button")
#: How many ancestor levels to search for the nearest interactive control
#: before giving up. Icon libraries often nest the <svg> a couple of wrapper
#: elements deep inside the real `<a>`/`<button>` (e.g. an `<span class="icon-wrap">`),
#: and that control can itself sit inside a larger card-level link.
_LABEL_CONTEXT_MAX_DEPTH = 5


def _is_named(node: object, *, deep: bool) -> bool:
    """True if a node has a non-empty `aria-label`/`aria-labelledby` or text.

    `deep=True` reads the full accessible-name computation for an interactive
    control (all descendant text counts, per WCAG). `deep=False` reads only
    the node's own direct text nodes — used when there is no interactive
    ancestor to anchor on, so we must not pull in a nested descendant's text
    (e.g. a sibling <svg>'s own <title>, or an unrelated nested element).
    """
    attrs = node.attributes  # type: ignore[attr-defined]
    if (attrs.get("aria-label") or "").strip():
        return True
    if (attrs.get("aria-labelledby") or "").strip():
        return True
    return bool(node.text(deep=deep, strip=True))  # type: ignore[attr-defined]


def _has_labeled_context(svg: object) -> bool:
    """True if the icon's accessible-name-defining ancestor already has a name.

    Walks up looking for the *nearest* interactive ancestor (`<a>`/`<button>`/
    `role=button`) within `_LABEL_CONTEXT_MAX_DEPTH` levels, skipping plain
    wrapper elements (div/span) along the way without reading their text —
    reading an arbitrary wrapper's aggregated text would leak unrelated
    sibling content (e.g. a card's category badge or a neighboring row) and
    wrongly exempt an unlabeled icon-only control nested inside the same card.
    Once an interactive ancestor is found, the check stops there and judges
    only that element's own full accessible name — a nested icon-only button
    inside a bigger labeled card link is a distinct control and does NOT
    inherit the card's name. If no interactive ancestor exists at all, falls
    back to the immediate parent's own *direct* text only (handles
    non-interactive captions, e.g. `<time>Updated Mar 10<svg/></time>`) —
    deliberately not `deep`, so a sibling <svg>'s own <title> text (or any
    other nested descendant) cannot leak in and falsely label this icon.
    """
    node = svg.parent  # type: ignore[attr-defined]
    depth = 0
    while node is not None and depth < _LABEL_CONTEXT_MAX_DEPTH:
        tag = node.tag
        role = (node.attributes.get("role") or "").strip().lower()
        if tag in _INTERACTIVE_TAGS or role in ("button", "link"):
            return _is_named(node, deep=True)
        node = node.parent
        depth += 1
    parent = svg.parent  # type: ignore[attr-defined]
    return parent is not None and _is_named(parent, deep=False)


def _svg_accessible_name(svg: object) -> str:
    """Non-empty text of the svg's <title> child, if any (empty string otherwise).

    A `<title>` node can exist but be left empty by a charting library's default
    markup (e.g. Recharts) — that provides no real accessible name, so presence
    alone is not enough; the text itself must be checked.
    """
    title = svg.css_first("title")  # type: ignore[attr-defined]
    return title.text(strip=True) if title is not None else ""


def _svg_accessibility(tree: HTMLParser) -> tuple[int, int]:
    """Count content <svg> elements and how many have an accessible name.

    Excluded upfront (not counted at all): decorative/hidden svgs
    (`_is_decorative_svg`) and icons with a labeled ancestor context
    (`_has_labeled_context`) — neither needs its own name.
    An accessible name is a non-empty `aria-label`/`aria-labelledby`, or a
    <title> child with non-empty text (an empty <title> stub does not count).
    """
    total = 0
    accessible = 0
    for svg in tree.css("svg"):
        if _is_decorative_svg(svg) or _has_labeled_context(svg):
            continue
        total += 1
        attrs = svg.attributes
        has_name = (
            bool((attrs.get("aria-label") or "").strip())
            or bool((attrs.get("aria-labelledby") or "").strip())
            or bool(_svg_accessible_name(svg))
        )
        if has_name:
            accessible += 1
    return total, accessible


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
    "bsky.app": "bluesky",
    "threads.net": "threads",
    "crunchbase.com": "crunchbase",
    "medium.com": "medium",
    "dev.to": "devto",
    "patreon.com": "patreon",
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


def _agent_usable_forms(tree: HTMLParser) -> tuple[int, dict[str, int]]:
    """Count agent-usable forms and return disqualification breakdown.

    Returns (qualifying_count, detail) where detail = {found, no_action,
    no_fields, no_label} — used to build actionable raw_value.
    """
    qualifying = 0
    no_action = 0
    no_fields = 0
    no_label = 0

    for form in tree.css("form"):
        if not (form.attributes.get("action") or form.attributes.get("method")):
            no_action += 1
            continue
        fields = form.css("input, select, textarea")
        if not fields:
            no_fields += 1
            continue
        labelled = bool(form.css("label")) or any(
            (field.attributes.get("aria-label") or field.attributes.get("placeholder"))
            for field in fields
        )
        if labelled:
            qualifying += 1
        else:
            no_label += 1

    found = qualifying + no_action + no_fields + no_label
    return qualifying, {
        "found": found,
        "no_action": no_action,
        "no_fields": no_fields,
        "no_label": no_label,
    }


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
    forms_count, forms_detail = _agent_usable_forms(tree)
    return AsoSignals(
        webmcp=_webmcp_signals(tree, html),
        potential_actions=jsonld.potential_actions,
        action_schema_types=jsonld.action_schema_types,
        agent_usable_forms=forms_count,
        agent_usable_forms_detail=forms_detail,
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
    svg_total, svg_accessible = _svg_accessibility(tree)

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
        svg_total=svg_total,
        svg_accessible=svg_accessible,
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
