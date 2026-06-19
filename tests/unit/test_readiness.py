# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the agentic-readiness aggregator (none/basic/ready/advanced)."""

from __future__ import annotations

from seryvon.models.enums import ReadinessLevel
from seryvon.models.signals import (
    AsoSignals,
    ExternalSignals,
    PageSignals,
    SignalBundle,
    SiteSignals,
    WebMcpSignals,
)
from seryvon.scoring.readiness import compute_aso_readiness


def _bundle(aso: AsoSignals | None = None, **kwargs: object) -> SignalBundle:
    page = PageSignals(url="https://ex.com/", aso=aso or AsoSignals())
    return SignalBundle(domain="ex.com", pages=[page], **kwargs)  # type: ignore[arg-type]


def test_readiness_none() -> None:
    result = compute_aso_readiness(_bundle())
    assert result.readiness_level is ReadinessLevel.NONE
    assert result.agent_ready is False
    assert result.has_webmcp is False


def test_readiness_basic_one_action_signal() -> None:
    aso = AsoSignals(openapi_links=["/openapi.json"])
    result = compute_aso_readiness(_bundle(aso))
    assert result.readiness_level is ReadinessLevel.BASIC
    assert result.agent_ready is False


def test_readiness_ready_via_webmcp() -> None:
    aso = AsoSignals(webmcp=WebMcpSignals(has_register_tool=True))
    result = compute_aso_readiness(_bundle(aso))
    assert result.readiness_level is ReadinessLevel.READY
    assert result.agent_ready is True
    assert result.has_webmcp is True


def test_readiness_ready_via_two_action_signals() -> None:
    aso = AsoSignals(potential_actions=["BuyAction"], agent_usable_forms=1)
    result = compute_aso_readiness(_bundle(aso))
    assert result.readiness_level is ReadinessLevel.READY


def test_readiness_advanced() -> None:
    aso = AsoSignals(
        webmcp=WebMcpSignals(has_tool_attributes=True, tool_count=1),
        potential_actions=["BuyAction"],
        openapi_links=["/openapi.json"],
    )
    result = compute_aso_readiness(_bundle(aso))
    assert result.readiness_level is ReadinessLevel.ADVANCED
    assert result.agent_ready is True
    assert result.has_action_schema is True


def test_readiness_synthesis_fields() -> None:
    bundle = _bundle(
        AsoSignals(),
        site=SiteSignals(blocked_agent_bots=["GPTBot"], agent_bots_checked=9),
        external=ExternalSignals(
            ai_discovery_endpoints={
                "ai_txt": True,
                "summary": True,
                "faq": False,
                "service": False,
            },
            nlweb_status="conformant",
        ),
    )
    result = compute_aso_readiness(bundle)
    assert result.ai_discovery_endpoints == 2
    assert result.has_nlweb is True
    assert result.blocked_agent_bots == ["GPTBot"]
