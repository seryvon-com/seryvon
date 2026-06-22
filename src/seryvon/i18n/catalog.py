# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Message catalog: English (base) + French. Keys are dotted (e.g. `rec.meta.title`).

Add a key to BOTH locales. Templates use `str.format` named fields. Keep
produced text concise (it surfaces in reports, the dashboard and the CLI).
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Recommendations — one concise fix per criterion (document 04 §7-8).          #
# --------------------------------------------------------------------------- #
_REC_EN: dict[str, str] = {
    "meta.title": "Add a unique 30–60 character <title> on every page.",
    "meta.description": "Write a 120–158 character meta description.",
    "meta.canonical": "Declare an absolute canonical URL.",
    "meta.robots": "Remove noindex directives from pages meant to be indexed.",
    "meta.title_unique": "Deduplicate identical title tags.",
    "og.complete": "Complete the Open Graph tags (title, description, image, url, type).",
    "twitter.cards": "Add Twitter Cards (card, title, description, image).",
    "struct.h1": "Use a single H1 per page.",
    "struct.hierarchy": "Fix the heading hierarchy (one H1, no skipped level).",
    "struct.schema": "Add relevant JSON-LD structured data.",
    "content.depth": "Enrich the content (aim for ≥ 800 useful words).",
    "content.text_ratio": "Increase the text-to-code ratio (lighten the markup).",
    "links.internal": "Add 3 to 100 relevant internal links per page.",
    "links.orphans": "Link orphan pages from the navigation.",
    "img.alt": "Set the alt attribute on every image.",
    "crawl.indexable": "Fix non-indexable pages (HTTP status, noindex).",
    "crawl.sitemap": "Publish a valid sitemap.xml.",
    "crawl.https": "Serve every page over HTTPS.",
    "crawl.redirects": "Reduce redirect chains to one hop at most.",
    "i18n.hreflang": "Declare consistent hreflang with x-default.",
    "perf.lcp": "Optimize LCP (≤ 2500 ms).",
    "perf.cls": "Reduce CLS (≤ 0.1).",
    "perf.inp": "Improve INP (≤ 200 ms).",
    "perf.lighthouse": "Optimize performance (Lighthouse score).",
    "authority.opr": "Acquire quality backlinks and mentions.",
    "authority.backlinks": "Grow a profile of referring domains.",
    "gso.faqpage": "Add FAQPage schema on question pages.",
    "gso.howto": "Add HowTo schema on tutorials.",
    "gso.breadcrumb": "Add a BreadcrumbList to the template.",
    "gso.itemlist": "Structure lists with ItemList or tables.",
    "gso.qa_format": "Phrase extractable question-answer sections.",
    "gso.cwv_eligible": "Bring all 3 Core Web Vitals within thresholds.",
    "aeo.author_credentials": "Declare authors with credentials (Person).",
    "aeo.about_page": "Publish a detailed About page.",
    "aeo.defined_terms": "Add definitions (DefinedTerm or a glossary).",
    "aeo.dates_structured": "Expose datePublished/dateModified in JSON-LD.",
    "aeo.comparison_tables": "Add comparison tables.",
    "aeo.answer_directness": "Place a direct answer at the top of the page.",
    "aeo.kg_presence": "Create or strengthen the entity in Wikidata/Wikipedia.",
    "geo.ssr": "Serve content with server-side rendering (SSR).",
    "geo.noise_ratio": "Increase the share of useful content vs nav/boilerplate.",
    "geo.entity_density": "Densify the content with relevant named entities.",
    "geo.primary_sources": "Cite primary external sources (outbound links).",
    "geo.authors": "Declare a structured author (author/Person in JSON-LD).",
    "geo.cross_platform": "Reference the brand on ≥4 platforms (sameAs).",
    "geo.freshness": "Update the content and expose dateModified.",
    "geo.citation_rate": "Earn generative citations (citable reference content).",
    "geo.mention_rate": "Strengthen brand awareness (mentions, editorial presence).",
    "geo.citation_confidence": "Stabilize citation (consistent canonical content, authority).",
    "aeo.llm_citation": "Optimize for answer engines (direct answers, reliable sources).",
    "aso.mcp_readiness": "Expose a WebMCP server (registerTool / toolname).",
    "aso.potential_actions": "Add executable potentialAction (Buy/Order…).",
    "aso.action_schema": "Enrich action schemas (Product/Offer, Service, Event).",
    "aso.ai_discovery": "Publish /.well-known/ai.txt and /ai/*.json.",
    "aso.nlweb": "Expose a compliant NLWeb endpoint.",
    "aso.accessible_forms": "Label forms (label/for, aria-label).",
    "aso.openapi": "Expose a documented API (OpenAPI/Swagger).",
    "aso.brand_coherence": "Align name and description between the site and Wikidata.",
    "aso.agent_access": "Allow agent bots in robots.txt.",
}

_REC_FR: dict[str, str] = {
    "meta.title": "Ajouter un <title> unique de 30–60 caractères sur chaque page.",
    "meta.description": "Rédiger une meta description de 120–158 caractères.",
    "meta.canonical": "Déclarer une URL canonique absolue.",
    "meta.robots": "Retirer les directives noindex des pages à indexer.",
    "meta.title_unique": "Dédupliquer les balises title identiques.",
    "og.complete": "Compléter les balises Open Graph (title, description, image, url, type).",
    "twitter.cards": "Ajouter les Twitter Cards (card, title, description, image).",
    "struct.h1": "N'utiliser qu'un seul H1 par page.",
    "struct.hierarchy": "Corriger la hiérarchie Hn (un H1, aucun niveau sauté).",
    "struct.schema": "Ajouter des données structurées JSON-LD pertinentes.",
    "content.depth": "Enrichir le contenu (viser ≥ 800 mots utiles).",
    "content.text_ratio": "Augmenter le ratio texte/code (alléger le markup).",
    "links.internal": "Ajouter 3 à 100 liens internes pertinents par page.",
    "links.orphans": "Relier les pages orphelines depuis la navigation.",
    "img.alt": "Renseigner l'attribut alt de toutes les images.",
    "crawl.indexable": "Corriger les pages non indexables (statut HTTP, noindex).",
    "crawl.sitemap": "Publier un sitemap.xml valide.",
    "crawl.https": "Servir toutes les pages en HTTPS.",
    "crawl.redirects": "Réduire les chaînes de redirection à un saut maximum.",
    "i18n.hreflang": "Déclarer des hreflang cohérents avec x-default.",
    "perf.lcp": "Optimiser le LCP (≤ 2500 ms).",
    "perf.cls": "Réduire le CLS (≤ 0.1).",
    "perf.inp": "Améliorer l'INP (≤ 200 ms).",
    "perf.lighthouse": "Optimiser la performance (score Lighthouse).",
    "authority.opr": "Acquérir des backlinks et mentions de qualité.",
    "authority.backlinks": "Développer un profil de domaines référents.",
    "gso.faqpage": "Ajouter un schema FAQPage sur les pages de questions.",
    "gso.howto": "Ajouter un schema HowTo sur les tutoriels.",
    "gso.breadcrumb": "Ajouter un BreadcrumbList sur le template.",
    "gso.itemlist": "Structurer les listes via ItemList ou des tableaux.",
    "gso.qa_format": "Formuler des sections question-réponse extractibles.",
    "gso.cwv_eligible": "Faire passer les 3 Core Web Vitals dans les seuils.",
    "aeo.author_credentials": "Déclarer des auteurs avec credentials (Person).",
    "aeo.about_page": "Publier une page À propos détaillée.",
    "aeo.defined_terms": "Ajouter des définitions (DefinedTerm ou glossaire).",
    "aeo.dates_structured": "Exposer datePublished/dateModified en JSON-LD.",
    "aeo.comparison_tables": "Ajouter des tableaux comparatifs.",
    "aeo.answer_directness": "Placer une réponse directe en tête de page.",
    "aeo.kg_presence": "Créer/renforcer l'entité dans Wikidata/Wikipedia.",
    "geo.ssr": "Servir le contenu en rendu serveur (SSR).",
    "geo.noise_ratio": "Augmenter la part de contenu utile vs nav/boilerplate.",
    "geo.entity_density": "Densifier le contenu en entités nommées pertinentes.",
    "geo.primary_sources": "Citer des sources externes primaires (liens sortants).",
    "geo.authors": "Déclarer un auteur structuré (author/Person en JSON-LD).",
    "geo.cross_platform": "Référencer la marque sur ≥4 plateformes (sameAs).",
    "geo.freshness": "Mettre à jour le contenu et exposer dateModified.",
    "geo.citation_rate": "Gagner des citations génératives (contenu de référence citable).",
    "geo.mention_rate": "Renforcer la notoriété de marque (mentions, présence éditoriale).",
    "geo.citation_confidence": "Stabiliser la citation (contenu canonique constant, autorité).",
    "aeo.llm_citation": "Optimiser pour les answer engines (réponses directes, sources fiables).",
    "aso.mcp_readiness": "Exposer un serveur WebMCP (registerTool / toolname).",
    "aso.potential_actions": "Ajouter des potentialAction exécutables (Buy/Order…).",
    "aso.action_schema": "Enrichir les schemas d'action (Product/Offer, Service, Event).",
    "aso.ai_discovery": "Publier /.well-known/ai.txt et /ai/*.json.",
    "aso.nlweb": "Exposer un endpoint NLWeb conforme.",
    "aso.accessible_forms": "Labelliser les formulaires (label/for, aria-label).",
    "aso.openapi": "Exposer une API documentée (OpenAPI/Swagger).",
    "aso.brand_coherence": "Aligner nom et description entre site et Wikidata.",
    "aso.agent_access": "Autoriser les bots d'agents dans robots.txt.",
}

_EN: dict[str, str] = {
    **{f"rec.{k}": v for k, v in _REC_EN.items()},
    "rec.generic": "Fix the {key} criterion.",
}

_FR: dict[str, str] = {
    **{f"rec.{k}": v for k, v in _REC_FR.items()},
    "rec.generic": "Corriger le critère {key}.",
}

CATALOG: dict[str, dict[str, str]] = {"en": _EN, "fr": _FR}
