# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Règles du pilier ASO (Agentic Search Optimization) — statique, document 04 §6.

Le différenciateur : aptitude d'un site à être découvert, parsé et choisi par des
agents autonomes. Logique de readiness transposée de `audit_webmcp.py`
(GEO Optimizer, MIT — Juan Camilo Auriti ; voir NOTICE). Tous les signaux sont
extraits par M3.2 (bloc `AsoSignals`) ou dérivés de robots.txt (M1) — zéro fetch.

Slice 4 : mcp_readiness, potential_actions, action_schema, accessible_forms,
openapi, agent_access. Les critères à fetch (ai_discovery, nlweb) et brand_coherence
(Wikidata) arrivent aux slices suivantes ; `aso.agent_selection_rate` est v2.
"""

from __future__ import annotations

from typing import ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import PageSignals, SignalBundle

_AI_DISCOVERY_ENDPOINTS = 4  # ai.txt + /ai/summary|faq|service.json (document 11 §4.3)
# Actions JSON-LD réellement « exécutables » par un agent (vs simple SearchAction).
_EXECUTABLE_ACTIONS = {
    "BuyAction",
    "OrderAction",
    "ReserveAction",
    "SubscribeAction",
    "RegisterAction",
}
_HTML_SOURCE = {"source": "HTML/DOM parsing"}


def _union(pages: list[PageSignals], attr: str) -> list[str]:
    """Union triée et dédupliquée d'un champ liste de l'`AsoSignals` de chaque page."""
    values: set[str] = set()
    for page in pages:
        values.update(getattr(page.aso, attr))
    return sorted(values)


@register
class AsoMcpReadinessCriterion(Criterion):
    """Readiness WebMCP (`aso.mcp_readiness`) : API impérative ou attributs déclaratifs."""

    key = "aso.mcp_readiness"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        imperative = any(p.aso.webmcp.has_register_tool for p in signals.pages)
        declarative = any(p.aso.webmcp.has_tool_attributes for p in signals.pages)
        partial = any(p.aso.webmcp.partial_signals for p in signals.pages)
        score = 100.0 if (imperative or declarative) else 50.0 if partial else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"imperative": imperative, "declarative": declarative},
            score=score,
            status=status_from_score(score),
            threshold={"ready": "registerTool() OU toolname"},
            explanation=(
                "WebMCP détecté (agents peuvent appeler des outils)."
                if score == 100
                else "Signaux WebMCP partiels."
                if score == 50
                else "Aucun signal WebMCP."
            ),
            evidence=_HTML_SOURCE,
            weight=self.weight,
        )


@register
class AsoPotentialActionsCriterion(Criterion):
    """Actions exécutables (`aso.potential_actions`) : potentialAction JSON-LD."""

    key = "aso.potential_actions"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.6

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        actions = _union(signals.pages, "potential_actions")
        executable = any(action in _EXECUTABLE_ACTIONS for action in actions)
        score = 100.0 if executable else 50.0 if actions else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"actions": actions},
            score=score,
            status=status_from_score(score),
            threshold={"executable": "BuyAction/OrderAction/ReserveAction…"},
            explanation=(
                f"Action exécutable présente : {actions}."
                if executable
                else f"SearchAction/action non transactionnelle : {actions}."
                if actions
                else "Aucun potentialAction."
            ),
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class AsoActionSchemaCriterion(Criterion):
    """Schemas d'action riches (`aso.action_schema`) : Product/Service/Event/HowTo."""

    key = "aso.action_schema"
    pillars: ClassVar[list[str]] = ["aso", "gso"]
    weight = 1.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        types = _union(signals.pages, "action_schema_types")
        score = 100.0 if len(types) >= 2 else 50.0 if len(types) == 1 else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"action_schema_types": types},
            score=score,
            status=status_from_score(score),
            threshold={"rich": "≥2 types d'action"},
            explanation=f"Types d'action riches détectés : {types or 'aucun'}.",
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class AsoAccessibleFormsCriterion(Criterion):
    """Formulaires agent-usables (`aso.accessible_forms`) : inputs labellisés + action."""

    key = "aso.accessible_forms"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        total = sum(p.aso.agent_usable_forms for p in signals.pages)
        score = 100.0 if total >= 1 else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"agent_usable_forms": total},
            score=score,
            status=status_from_score(score),
            threshold={"min": 1},
            explanation=f"{total} formulaire(s) exploitable(s) par un agent.",
            evidence=_HTML_SOURCE,
            weight=self.weight,
        )


@register
class AsoOpenApiCriterion(Criterion):
    """API documentée exposée (`aso.openapi`) : liens openapi/swagger/api-docs."""

    key = "aso.openapi"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        links = _union(signals.pages, "openapi_links")
        score = 100.0 if links else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"openapi_links": links},
            score=score,
            status=status_from_score(score),
            threshold={"present": "lien openapi/swagger/api-docs"},
            explanation=f"API documentée exposée : {links}." if links else "Aucune API documentée.",
            evidence=_HTML_SOURCE,
            weight=self.weight,
        )


@register
class AsoAiDiscoveryCriterion(Criterion):
    """Endpoints de découverte IA (`aso.ai_discovery`) : (valides / 4) × 100."""

    key = "aso.ai_discovery"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.4

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        endpoints = signals.external.ai_discovery_endpoints
        if endpoints is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Endpoints de découverte IA non sondés."
            )
        valid = sum(1 for ok in endpoints.values() if ok)
        score = round(valid / _AI_DISCOVERY_ENDPOINTS * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"endpoints": endpoints, "valid": valid},
            score=score,
            status=status_from_score(score),
            threshold={"endpoints": _AI_DISCOVERY_ENDPOINTS},
            explanation=f"{valid}/{_AI_DISCOVERY_ENDPOINTS} endpoint(s) de découverte IA valides.",
            evidence={"source": "ai.txt + /ai/*.json"},
            weight=self.weight,
        )


@register
class AsoNlwebCriterion(Criterion):
    """NLWeb readiness (`aso.nlweb`) : conforme (100) / présent (50) / absent (0)."""

    key = "aso.nlweb"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        status = signals.external.nlweb_status
        if status is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Endpoint NLWeb non sondé."
            )
        score = {"conformant": 100.0, "present": 50.0, "absent": 0.0}.get(status, 0.0)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"nlweb": status},
            score=score,
            status=status_from_score(score),
            threshold={"levels": "conformant/present/absent"},
            explanation=f"Endpoint NLWeb : {status}.",
            evidence={"source": "sonde /ask"},
            weight=self.weight,
        )


@register
class AsoBrandCoherenceCriterion(Criterion):
    """Cohérence cross-surface (`aso.brand_coherence`) : site vs Wikidata (tag aeo)."""

    key = "aso.brand_coherence"
    pillars: ClassVar[list[str]] = ["aso", "aeo"]
    weight = 1.3

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        brand = signals.external.brand_coherence
        if not brand:
            return CriterionResult.not_measured(
                self.key,
                self.pillars,
                self.weight,
                "Cohérence de marque non mesurée (entité Wikidata absente ou désactivée).",
            )
        score = round(sum(brand.values()) / len(brand) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"brand_coherence": brand},
            score=score,
            status=status_from_score(score),
            threshold={"target": "nom + description cohérents (site/Wikidata)"},
            explanation=f"Cohérence de marque : {score}% (site vs Wikidata).",
            evidence={"source": "Wikidata"},
            weight=self.weight,
        )


@register
class AsoAgentAccessCriterion(Criterion):
    """Accès des crawlers d'agents (`aso.agent_access`) : robots.txt n'interdit pas les bots."""

    key = "aso.agent_access"
    pillars: ClassVar[list[str]] = ["aso", "geo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        checked = signals.site.agent_bots_checked
        if checked == 0:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Accès des bots d'agents non évalué."
            )
        blocked = signals.site.blocked_agent_bots
        score = round((checked - len(blocked)) / checked * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"checked": checked, "blocked": blocked},
            score=score,
            status=status_from_score(score),
            threshold={"target": "tous les bots d'agents autorisés"},
            explanation=(
                f"{len(blocked)} bot(s) d'agent bloqué(s) : {blocked}."
                if blocked
                else "Tous les bots d'agents connus sont autorisés."
            ),
            evidence={"source": "robots.txt (M1)"},
            weight=self.weight,
        )
