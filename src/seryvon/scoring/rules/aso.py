# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""ASO pillar rules (Agentic Search Optimization) — static, document 04 §6.

The differentiator: a site's ability to be discovered, parsed and chosen by
autonomous agents. The readiness logic is adapted from `audit_webmcp.py`
(GEO Optimizer, MIT — Juan Camilo Auriti; see NOTICE). All signals are extracted
by M3.2 (the `AsoSignals` block) or derived from robots.txt (M1) — zero fetch.

Slice 4: mcp_readiness, potential_actions, action_schema, accessible_forms,
openapi, agent_access. The fetch-based criteria (ai_discovery, nlweb) and
brand_coherence (Wikidata) come in later slices; `aso.agent_selection_rate` is v2.
"""

from __future__ import annotations

from typing import ClassVar

from seryvon.i18n import t
from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import PageSignals, SignalBundle

_AI_DISCOVERY_ENDPOINTS = 4  # ai.txt + /ai/summary|faq|service.json (document 11 §4.3)
# JSON-LD actions truly "executable" by an agent (vs a plain SearchAction).
_EXECUTABLE_ACTIONS = {
    "BuyAction",
    "OrderAction",
    "ReserveAction",
    "SubscribeAction",
    "RegisterAction",
}
_HTML_SOURCE = {"source": "HTML/DOM parsing"}


def _union(pages: list[PageSignals], attr: str) -> list[str]:
    """Sorted, deduplicated union of a list field of each page's `AsoSignals`."""
    values: set[str] = set()
    for page in pages:
        values.update(getattr(page.aso, attr))
    return sorted(values)


@register
class AsoMcpReadinessCriterion(Criterion):
    """WebMCP readiness (`aso.mcp_readiness`): imperative API or declarative attributes."""

    key = "aso.mcp_readiness"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.8
    evidence_tier: ClassVar[str] = "experimental"

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
                t("expl.webmcp_full")
                if score == 100
                else t("expl.webmcp_partial")
                if score == 50
                else t("expl.webmcp_none")
            ),
            evidence=_HTML_SOURCE,
            weight=self.weight,
        )


@register
class AsoPotentialActionsCriterion(Criterion):
    """Executable actions (`aso.potential_actions`): JSON-LD potentialAction."""

    key = "aso.potential_actions"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.6
    evidence_tier: ClassVar[str] = "experimental"

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
                t("expl.actions_executable", actions=actions)
                if executable
                else t("expl.actions_nontransactional", actions=actions)
                if actions
                else t("expl.actions_none")
            ),
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class AsoActionSchemaCriterion(Criterion):
    """Rich action schemas (`aso.action_schema`): Product/Service/Event/HowTo."""

    key = "aso.action_schema"
    pillars: ClassVar[list[str]] = ["aso", "gso"]
    weight = 1.5
    evidence_tier: ClassVar[str] = "experimental"

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
            explanation=t("expl.action_schema", types=types if types else t("word.none")),
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class AsoAccessibleFormsCriterion(Criterion):
    """Agent-usable forms (`aso.accessible_forms`): labelled inputs + action."""

    key = "aso.accessible_forms"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        total = sum(p.aso.agent_usable_forms for p in signals.pages)
        score = 100.0 if total >= 1 else 0.0

        total_found = sum(
            d.get("found", 0) for p in signals.pages if (d := p.aso.agent_usable_forms_detail)
        )
        disqualified = {
            "no_action": sum(
                p.aso.agent_usable_forms_detail.get("no_action", 0) for p in signals.pages
            ),
            "no_fields": sum(
                p.aso.agent_usable_forms_detail.get("no_fields", 0) for p in signals.pages
            ),
            "no_label": sum(
                p.aso.agent_usable_forms_detail.get("no_label", 0) for p in signals.pages
            ),
        }
        pages_with_forms = [
            p.url
            for p in signals.pages
            if p.aso.agent_usable_forms_detail.get("found", 0) > 0
        ]

        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "agent_usable_forms": total,
                "total_found": total_found,
                "disqualified": disqualified,
                "pages_with_forms": pages_with_forms[:10],
            },
            score=score,
            status=status_from_score(score),
            threshold={"min": 1},
            explanation=t("expl.accessible_forms", total=total),
            evidence=_HTML_SOURCE,
            weight=self.weight,
        )


@register
class AsoOpenApiCriterion(Criterion):
    """Exposed documented API (`aso.openapi`): openapi/swagger/api-docs links."""

    key = "aso.openapi"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 0.8
    evidence_tier: ClassVar[str] = "experimental"

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if not signals.pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
            explanation=t("expl.openapi_present", links=links)
            if links
            else t("expl.openapi_absent"),
            evidence=_HTML_SOURCE,
            weight=self.weight,
        )


@register
class AsoAiDiscoveryCriterion(Criterion):
    """AI discovery endpoints (`aso.ai_discovery`): (valid / 4) × 100."""

    key = "aso.ai_discovery"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.4
    evidence_tier: ClassVar[str] = "experimental"

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        endpoints = signals.external.ai_discovery_endpoints
        if endpoints is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.ai_discovery_not_probed")
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
            explanation=t("expl.ai_discovery", valid=valid, total=_AI_DISCOVERY_ENDPOINTS),
            evidence={"source": "ai.txt + /ai/*.json"},
            weight=self.weight,
        )


@register
class AsoNlwebCriterion(Criterion):
    """NLWeb readiness (`aso.nlweb`): conformant (100) / present (50) / absent (0)."""

    key = "aso.nlweb"
    pillars: ClassVar[list[str]] = ["aso"]
    weight = 1.0
    evidence_tier: ClassVar[str] = "experimental"

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        status = signals.external.nlweb_status
        if status is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.nlweb_not_probed")
            )
        score = {"conformant": 100.0, "present": 50.0, "absent": 0.0}.get(status, 0.0)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"nlweb": status},
            score=score,
            status=status_from_score(score),
            threshold={"levels": "conformant/present/absent"},
            explanation=t("expl.nlweb", status=status),
            evidence={"source": "sonde /ask"},
            weight=self.weight,
        )


@register
class AsoBrandCoherenceCriterion(Criterion):
    """Cross-surface coherence (`aso.brand_coherence`): site vs Wikidata (aeo tag)."""

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
                t("reason.brand_not_measured"),
            )
        score = round(sum(brand.values()) / len(brand) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"brand_coherence": brand},
            score=score,
            status=status_from_score(score),
            threshold={"target": "nom + description cohérents (site/Wikidata)"},
            explanation=t("expl.brand_coherence", score=score),
            evidence={"source": "Wikidata"},
            weight=self.weight,
        )


@register
class AsoAgentAccessCriterion(Criterion):
    """Agent crawler access (`aso.agent_access`): robots.txt does not block the bots."""

    key = "aso.agent_access"
    pillars: ClassVar[list[str]] = ["aso", "geo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        checked = signals.site.agent_bots_checked
        if checked == 0:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.agent_access_not_evaluated")
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
                t("expl.agent_blocked", count=len(blocked), bots=blocked)
                if blocked
                else t("expl.agent_all_allowed")
            ),
            evidence={"source": "robots.txt (M1)"},
            weight=self.weight,
        )
