# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Prioritized action plan (document 04 §7-8).

Turns the `warning`/`critical` `CriterionResult` objects into prioritized
`Issue` objects: `priority = (impact × severity) / effort`, bucketed into P1–P4.
Pure and deterministic (stable sort by descending priority then key).

Severity: warning=1, critical=2. Impact: derived from the criterion weight (1–3);
the number of pillars touched is informational only, not a multiplier (review §13).
Effort: a table per fix type (§8), default 2. `not_measured`, `not_applicable`,
`ok` and `experimental` criteria do not generate an issue.
"""

from __future__ import annotations

from seryvon.i18n import has_message, t
from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import Severity, Status
from seryvon.models.report import Issue

_DEFAULT_EFFORT = 2

# Fix effort per criterion (1 quick … 3 heavy), document 04 §8.
_EFFORT: dict[str, int] = {
    # Meta / structure / schema: simple addition.
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
    # Content / internal linking / coherence: medium effort.
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
    # GEO on-page core.
    "geo.primary_sources": 1,
    "geo.authors": 1,
    "geo.freshness": 1,
    "geo.noise_ratio": 2,
    "geo.entity_density": 2,
    "geo.cross_platform": 2,
    # Heavy work: perf, authority, rendering, agentic endpoints.
    "perf.lcp": 3,
    "perf.cls": 3,
    "perf.inp": 3,
    "perf.lighthouse": 3,
    "gso.cwv_eligible": 3,
    "authority.opr": 3,
    "authority.backlinks": 3,
    "geo.ssr": 3,
    "geo.citation_rate": 3,
    "geo.mention_rate": 3,
    "geo.citation_confidence": 3,
    "aeo.llm_citation": 3,
    "aso.mcp_readiness": 3,
    "aso.nlweb": 3,
}

_SEVERITY = {Status.WARNING: Severity.WARNING, Status.CRITICAL: Severity.CRITICAL}
_SEVERITY_VALUE = {Status.WARNING: 1, Status.CRITICAL: 2}


def _impact(result: CriterionResult) -> int:
    """Impact 1–3 derived from the criterion weight alone.

    The number of pillars touched is no longer a multiplier (review §13): a shared
    signal must not become a priority just because it is tagged in several pillars.
    """
    if result.weight < 1.0:
        return 1
    if result.weight < 1.8:
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


def _recommendation(key: str) -> str:
    """Localized recommendation for a criterion, with a generic fallback."""
    message_key = f"rec.{key}"
    return t(message_key) if has_message(message_key) else t("rec.generic", key=key)


def build_issues(results: list[CriterionResult]) -> list[Issue]:
    """Build the prioritized action plan from the criterion results.

    Recommendation text is localized via the active locale (set from the audit
    config); see `seryvon.i18n`.
    """
    issues: list[Issue] = []
    for result in results:
        if result.status not in (Status.WARNING, Status.CRITICAL):
            continue
        # Experimental signals are advisory: never flag their absence as an issue (review §9).
        if result.evidence_tier == "experimental":
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
                recommendation=_recommendation(result.key),
                affected_pages=_affected_pages(result),
                affected_pillars=len(result.pillars),
            )
        )
    issues.sort(key=lambda i: (-i.priority_score, i.criterion_key))
    return issues
