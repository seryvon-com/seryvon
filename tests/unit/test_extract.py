# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for internal signal extraction."""

from __future__ import annotations

from seryvon.crawler.extract import extract_page_signals


def test_extract_basic_fields(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html, status_code=200)
    assert signals.title is not None
    assert "Seryvon" in signals.title
    assert signals.meta_description is not None
    assert signals.canonical == "https://example.com/"
    assert signals.status_code == 200


def test_extract_headings(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html)
    assert signals.h1_count == 1
    assert signals.headings["h1"] == 1
    assert signals.headings["h2"] == 1


def test_extract_structured_data_types(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html)
    assert "Organization" in signals.structured_data_types


def test_extract_links_and_images(sample_html: str) -> None:
    signals = extract_page_signals("https://example.com/", sample_html)
    assert signals.internal_links == 1
    assert signals.external_links == 1
    assert signals.images_total == 2
    assert signals.images_with_alt == 1


def test_extract_is_deterministic(sample_html: str) -> None:
    """Same HTML -> same signals (reproducibility property)."""
    a = extract_page_signals("https://example.com/", sample_html)
    b = extract_page_signals("https://example.com/", sample_html)
    assert a.model_dump() == b.model_dump()


def test_extract_handles_empty_html() -> None:
    signals = extract_page_signals("https://example.com/", "")
    assert signals.title is None
    assert signals.word_count == 0
    assert signals.structured_data_types == []


def test_extract_ignores_malformed_jsonld() -> None:
    html = '<html><head><script type="application/ld+json">{not valid json}</script></head></html>'
    signals = extract_page_signals("https://example.com/", html)
    assert signals.structured_data_types == []


def test_extract_open_graph() -> None:
    html = (
        "<html><head>"
        '<meta property="og:title" content="Titre OG">'
        '<meta property="og:description" content="Desc OG">'
        '<meta property="og:image" content="https://example.com/img.png">'
        '<meta property="og:url" content="https://example.com/">'
        '<meta property="og:type" content="website">'
        "</head></html>"
    )
    signals = extract_page_signals("https://example.com/", html)
    assert signals.open_graph == {
        "og:title": "Titre OG",
        "og:description": "Desc OG",
        "og:image": "https://example.com/img.png",
        "og:url": "https://example.com/",
        "og:type": "website",
    }


def test_extract_twitter_card() -> None:
    html = (
        "<html><head>"
        '<meta name="twitter:card" content="summary_large_image">'
        '<meta name="twitter:title" content="Titre Twitter">'
        "</head></html>"
    )
    signals = extract_page_signals("https://example.com/", html)
    assert signals.twitter_card == {
        "twitter:card": "summary_large_image",
        "twitter:title": "Titre Twitter",
    }


def test_extract_hreflang() -> None:
    html = (
        "<html><head>"
        '<link rel="alternate" hreflang="fr" href="https://example.com/fr">'
        '<link rel="alternate" hreflang="en" href="https://example.com/en">'
        '<link rel="alternate" hreflang="x-default" href="https://example.com/">'
        "</head></html>"
    )
    signals = extract_page_signals("https://example.com/", html)
    assert signals.hreflang == {
        "fr": "https://example.com/fr",
        "en": "https://example.com/en",
        "x-default": "https://example.com/",
    }


def test_extract_internal_link_targets_resolved_and_classified() -> None:
    html = (
        '<a href="/a">a</a>'
        '<a href="b">b</a>'
        '<a href="/a">a-dup</a>'  # duplicate -> deduplicated
        '<a href="https://other.com/x">ext</a>'
    )
    signals = extract_page_signals("https://example.com/dir/", html)
    assert signals.internal_link_targets == [
        "https://example.com/a",
        "https://example.com/dir/b",
    ]
    assert signals.internal_links == 2
    assert signals.external_links == 1


def test_extract_records_redirects() -> None:
    signals = extract_page_signals("https://example.com/", "<html></html>", redirects=2)
    assert signals.redirects == 2


# --------------------------------------------------------------------------- #
# M3.2 — signaux GSO/AEO on-page + ASO statique                               #
# --------------------------------------------------------------------------- #
_RICH_HTML = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"FAQPage"},
  {"@type":"HowTo","step":[{"@type":"HowToStep"}]},
  {"@type":"Article","datePublished":"2026-01-01",
   "author":{"@type":"Person","name":"Jane","jobTitle":"Engineer",
             "sameAs":["https://www.wikidata.org/wiki/Q1"]}},
  {"@type":"WebSite","potentialAction":{"@type":"SearchAction"}},
  {"@type":"Product","offers":{"@type":"Offer","price":"9.99"}}
]}
</script>
</head>
<body>
<main>
<h1>Titre</h1>
<p>Un paragraphe de réponse directe avec assez de mots pour être significatif ici aujourd'hui.</p>
<h2>Comment faire ?</h2>
<h2>Section normale</h2>
<table><tr><td>a</td></tr></table>
<dl><dt>Terme</dt><dd>Définition</dd></dl>
<form action="/search" method="get"><input name="q" aria-label="Recherche"></form>
<a href="/openapi.json">API</a>
<button toolname="search">x</button>
<script>navigator.modelContext.registerTool({})</script>
</main>
</body></html>"""


def test_extract_jsonld_rich_signals() -> None:
    s = extract_page_signals("https://example.com/", _RICH_HTML)
    assert {"FAQPage", "HowTo", "Article", "WebSite", "Product", "Offer", "Person"} <= set(
        s.structured_data_types
    )
    assert s.has_author is True
    assert s.author_has_credentials is True
    assert s.has_structured_dates is True


def test_extract_content_counts() -> None:
    s = extract_page_signals("https://example.com/", _RICH_HTML)
    assert s.tables_count == 1
    assert s.definition_lists_count == 1
    assert s.question_headings == 1  # "Comment faire ?"
    assert s.lead_paragraph_words == 14


def test_extract_aso_static_signals() -> None:
    aso = extract_page_signals("https://example.com/", _RICH_HTML).aso
    assert aso.webmcp.has_register_tool is True
    assert aso.webmcp.has_tool_attributes is True
    assert aso.webmcp.tool_count == 1
    assert aso.potential_actions == ["SearchAction"]
    assert aso.action_schema_types == ["HowTo", "Product"]
    assert aso.agent_usable_forms == 1
    assert aso.openapi_links == ["/openapi.json"]


def test_extract_aso_absent_by_default(sample_html: str) -> None:
    aso = extract_page_signals("https://example.com/", sample_html).aso
    assert aso.webmcp.has_register_tool is False
    assert aso.potential_actions == []
    assert aso.action_schema_types == []
    assert aso.agent_usable_forms == 0
    assert aso.openapi_links == []


# --------------------------------------------------------------------------- #
# M3.3 — GEO on-page core signals                                             #
# --------------------------------------------------------------------------- #
_GEO_HTML = """<html><head>
<script type="application/ld+json">
{"@type":"Article","datePublished":"2026-05-01","dateModified":"2026-06-10",
 "author":{"@type":"Person","name":"Marie Curie"},
 "sameAs":["https://twitter.com/acme","https://www.linkedin.com/company/acme"]}
</script>
</head>
<body>
<nav>Accueil Produits Contact Blog</nav>
<main>
<h1>Guide Complet</h1>
<p>Paris et Berlin sont des Villes Européennes importantes pour Acme Corporation.</p>
<a href="https://doi.org/10.1000/xyz">Source</a>
<a href="https://github.com/acme">GitHub</a>
</main>
<footer>Mentions Copyright Acme</footer>
</body></html>"""


def test_extract_content_date_is_latest() -> None:
    s = extract_page_signals("https://example.com/", _GEO_HTML)
    assert s.content_date == "2026-06-10"  # max(datePublished, dateModified)


def test_extract_external_link_domains() -> None:
    s = extract_page_signals("https://example.com/", _GEO_HTML)
    assert s.external_link_domains == ["doi.org", "github.com"]


def test_extract_social_platforms() -> None:
    # github (lien) + twitter/linkedin (sameAs JSON-LD).
    s = extract_page_signals("https://example.com/", _GEO_HTML)
    assert s.social_platforms == ["github", "linkedin", "twitter"]


def test_extract_entity_count_heuristic() -> None:
    s = extract_page_signals("https://example.com/", _GEO_HTML)
    assert s.entity_count >= 5  # heuristic: distinct capitalized tokens


def test_extract_main_text_ratio_excludes_boilerplate() -> None:
    s = extract_page_signals("https://example.com/", _GEO_HTML)
    assert s.main_text_ratio is not None
    assert 0.0 < s.main_text_ratio < 1.0  # nav + footer hors contenu principal


def test_extract_main_text_ratio_without_main_landmark() -> None:
    html = "<html><body><nav>Menu Accueil Contact</nav><p>" + ("mot " * 20) + "</p></body></html>"
    s = extract_page_signals("https://example.com/", html)
    assert s.main_text_ratio is not None
    assert s.main_text_ratio < 1.0  # <nav> boilerplate removed from the content
