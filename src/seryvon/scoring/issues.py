# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Plan d'action priorisé (document 04 §7-8).

Transforme les `CriterionResult` en `warning`/`critical` en `Issue` priorisés :
`priorité = (impact × sévérité) / effort`, classés en P1–P4. Pur et déterministe
(tri stable par priorité décroissante puis clé).

Sévérité : warning=1, critical=2. Impact : poids × nb de piliers, normalisé 1–3.
Effort : table par type de correction (§8), défaut 2. Les critères `not_measured`
et `ok` ne génèrent pas d'issue.
"""

from __future__ import annotations

from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import Severity, Status
from seryvon.models.report import Issue

_DEFAULT_EFFORT = 2

# Effort de correction par critère (1 rapide … 3 lourd), document 04 §8.
_EFFORT: dict[str, int] = {
    # Méta / structure / schema : ajout simple.
    "meta.title": 1,
    "meta.description": 1,
    "meta.canonical": 1,
    "meta.robots": 1,
    "meta.title_unique": 1,
    "og.complete": 1,
    "twitter.cards": 1,
    "struct.h1": 1,
    "struct.hierarchy": 1,
    "struct.schema": 1,
    "links.internal": 1,
    "img.alt": 1,
    "crawl.sitemap": 1,
    "crawl.redirects": 1,
    "i18n.hreflang": 1,
    "gso.faqpage": 1,
    "gso.howto": 1,
    "gso.breadcrumb": 1,
    "gso.itemlist": 1,
    "gso.qa_format": 1,
    "aeo.author_credentials": 1,
    "aeo.about_page": 1,
    "aeo.defined_terms": 1,
    "aeo.dates_structured": 1,
    "aso.potential_actions": 1,
    "aso.action_schema": 1,
    "aso.ai_discovery": 1,
    "aso.agent_access": 1,
    "aso.openapi": 1,
    # Contenu / maillage / cohérence : effort moyen.
    "content.depth": 2,
    "content.text_ratio": 2,
    "links.orphans": 2,
    "crawl.indexable": 2,
    "crawl.https": 2,
    "aeo.comparison_tables": 2,
    "aeo.answer_directness": 2,
    "aeo.kg_presence": 2,
    "aso.brand_coherence": 2,
    "aso.accessible_forms": 2,
    # Chantiers lourds : perf, autorité, rendu, endpoints agentiques.
    "perf.lcp": 3,
    "perf.cls": 3,
    "perf.inp": 3,
    "perf.lighthouse": 3,
    "gso.cwv_eligible": 3,
    "authority.opr": 3,
    "authority.backlinks": 3,
    "geo.ssr": 3,
    "aso.mcp_readiness": 3,
    "aso.nlweb": 3,
}

# Recommandation concise par critère ; fallback générique sinon.
_RECOMMENDATIONS: dict[str, str] = {
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

_SEVERITY = {Status.WARNING: Severity.WARNING, Status.CRITICAL: Severity.CRITICAL}
_SEVERITY_VALUE = {Status.WARNING: 1, Status.CRITICAL: 2}


def _impact(result: CriterionResult) -> int:
    """Impact 1–3 = poids × nb de piliers touchés, normalisé."""
    raw = result.weight * len(result.pillars)
    if raw < 1.5:
        return 1
    if raw < 3.0:
        return 2
    return 3


def _bucket(priority: float) -> str:
    if priority >= 4.0:
        return "P1"
    if priority >= 2.0:
        return "P2"
    if priority >= 1.0:
        return "P3"
    return "P4"


def _affected_pages(result: CriterionResult) -> list[str]:
    for key in ("non_conformes", "orphelines"):
        value = result.evidence.get(key)
        if isinstance(value, list) and value:
            return [str(v) for v in value]
    return []


def build_issues(results: list[CriterionResult]) -> list[Issue]:
    """Construit le plan d'action priorisé à partir des résultats de critères."""
    issues: list[Issue] = []
    for result in results:
        if result.status not in (Status.WARNING, Status.CRITICAL):
            continue
        impact = _impact(result)
        effort = _EFFORT.get(result.key, _DEFAULT_EFFORT)
        priority = round(impact * _SEVERITY_VALUE[result.status] / effort, 2)
        issues.append(
            Issue(
                criterion_key=result.key,
                severity=_SEVERITY[result.status],
                impact=impact,
                effort=effort,
                priority_score=priority,
                priority_bucket=_bucket(priority),
                recommendation=_RECOMMENDATIONS.get(
                    result.key, f"Corriger le critère {result.key}."
                ),
                affected_pages=_affected_pages(result),
            )
        )
    issues.sort(key=lambda i: (-i.priority_score, i.criterion_key))
    return issues
