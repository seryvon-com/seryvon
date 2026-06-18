# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests des règles ASO statiques (M11) sur leurs paliers."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import (
    AsoSignals,
    ExternalSignals,
    PageSignals,
    SignalBundle,
    SiteSignals,
    WebMcpSignals,
)
from seryvon.scoring.rules.aso import (
    AsoAccessibleFormsCriterion,
    AsoActionSchemaCriterion,
    AsoAgentAccessCriterion,
    AsoAiDiscoveryCriterion,
    AsoMcpReadinessCriterion,
    AsoNlwebCriterion,
    AsoOpenApiCriterion,
    AsoPotentialActionsCriterion,
)


def _aso_page(**aso: object) -> PageSignals:
    return PageSignals(url="https://ex.com/", aso=AsoSignals(**aso))  # type: ignore[arg-type]


def _bundle(*pages: PageSignals) -> SignalBundle:
    return SignalBundle(domain="ex.com", pages=list(pages))


# --------------------------------------------------------------------------- #
# aso.mcp_readiness                                                            #
# --------------------------------------------------------------------------- #
def test_mcp_readiness_imperative_or_declarative() -> None:
    imperative = _aso_page(webmcp=WebMcpSignals(has_register_tool=True))
    assert AsoMcpReadinessCriterion().evaluate(_bundle(imperative)).score == 100
    declarative = _aso_page(webmcp=WebMcpSignals(has_tool_attributes=True, tool_count=2))
    assert AsoMcpReadinessCriterion().evaluate(_bundle(declarative)).score == 100


def test_mcp_readiness_partial_and_absent() -> None:
    partial = _aso_page(webmcp=WebMcpSignals(partial_signals=True))
    assert AsoMcpReadinessCriterion().evaluate(_bundle(partial)).score == 50
    assert AsoMcpReadinessCriterion().evaluate(_bundle(_aso_page())).score == 0
    assert AsoMcpReadinessCriterion().evaluate(_bundle()).status is Status.NOT_MEASURED


# --------------------------------------------------------------------------- #
# aso.potential_actions                                                        #
# --------------------------------------------------------------------------- #
def test_potential_actions_executable_vs_search() -> None:
    buy = _aso_page(potential_actions=["BuyAction"])
    assert AsoPotentialActionsCriterion().evaluate(_bundle(buy)).score == 100
    search = _aso_page(potential_actions=["SearchAction"])
    assert AsoPotentialActionsCriterion().evaluate(_bundle(search)).score == 50
    assert AsoPotentialActionsCriterion().evaluate(_bundle(_aso_page())).score == 0


# --------------------------------------------------------------------------- #
# aso.action_schema                                                            #
# --------------------------------------------------------------------------- #
def test_action_schema_paliers() -> None:
    two = _aso_page(action_schema_types=["Product", "HowTo"])
    result = AsoActionSchemaCriterion().evaluate(_bundle(two))
    assert result.score == 100
    assert result.pillars == ["aso", "gso"]
    one = _aso_page(action_schema_types=["Product"])
    assert AsoActionSchemaCriterion().evaluate(_bundle(one)).score == 50
    assert AsoActionSchemaCriterion().evaluate(_bundle(_aso_page())).score == 0


def test_action_schema_unions_across_pages() -> None:
    bundle = _bundle(
        _aso_page(action_schema_types=["Product"]),
        _aso_page(action_schema_types=["Event"]),
    )
    assert AsoActionSchemaCriterion().evaluate(bundle).score == 100  # union = 2 types


# --------------------------------------------------------------------------- #
# aso.accessible_forms / aso.openapi                                           #
# --------------------------------------------------------------------------- #
def test_accessible_forms() -> None:
    assert (
        AsoAccessibleFormsCriterion().evaluate(_bundle(_aso_page(agent_usable_forms=1))).score
        == 100
    )
    assert AsoAccessibleFormsCriterion().evaluate(_bundle(_aso_page())).score == 0


def test_openapi() -> None:
    with_api = _aso_page(openapi_links=["/openapi.json"])
    assert AsoOpenApiCriterion().evaluate(_bundle(with_api)).score == 100
    assert AsoOpenApiCriterion().evaluate(_bundle(_aso_page())).score == 0


# --------------------------------------------------------------------------- #
# aso.agent_access                                                             #
# --------------------------------------------------------------------------- #
def test_agent_access_all_allowed() -> None:
    bundle = SignalBundle(domain="ex.com", site=SiteSignals(agent_bots_checked=9))
    result = AsoAgentAccessCriterion().evaluate(bundle)
    assert result.score == 100
    assert result.pillars == ["aso", "geo"]


def test_agent_access_degressive() -> None:
    bundle = SignalBundle(
        domain="ex.com",
        site=SiteSignals(agent_bots_checked=10, blocked_agent_bots=["GPTBot", "ClaudeBot"]),
    )
    assert AsoAgentAccessCriterion().evaluate(bundle).score == 80.0  # 8/10


def test_agent_access_not_measured_when_unchecked() -> None:
    bundle = SignalBundle(domain="ex.com", site=SiteSignals(agent_bots_checked=0))
    assert AsoAgentAccessCriterion().evaluate(bundle).status is Status.NOT_MEASURED


# --------------------------------------------------------------------------- #
# aso.ai_discovery / aso.nlweb (sondes légères)                               #
# --------------------------------------------------------------------------- #
def test_ai_discovery_ratio() -> None:
    two_valid = SignalBundle(
        domain="ex.com",
        external=ExternalSignals(
            ai_discovery_endpoints={"ai_txt": True, "summary": True, "faq": False, "service": False}
        ),
    )
    assert AsoAiDiscoveryCriterion().evaluate(two_valid).score == 50.0  # 2/4
    full = SignalBundle(
        domain="ex.com",
        external=ExternalSignals(
            ai_discovery_endpoints={"ai_txt": True, "summary": True, "faq": True, "service": True}
        ),
    )
    assert AsoAiDiscoveryCriterion().evaluate(full).score == 100.0


def test_ai_discovery_not_measured_when_not_probed() -> None:
    assert (
        AsoAiDiscoveryCriterion().evaluate(SignalBundle(domain="ex.com")).status
        is Status.NOT_MEASURED
    )


def test_nlweb_levels() -> None:
    def _bundle_nlweb(status: str) -> SignalBundle:
        return SignalBundle(domain="ex.com", external=ExternalSignals(nlweb_status=status))

    assert AsoNlwebCriterion().evaluate(_bundle_nlweb("conformant")).score == 100
    assert AsoNlwebCriterion().evaluate(_bundle_nlweb("present")).score == 50
    assert AsoNlwebCriterion().evaluate(_bundle_nlweb("absent")).score == 0
    assert AsoNlwebCriterion().evaluate(SignalBundle(domain="ex.com")).status is Status.NOT_MEASURED
