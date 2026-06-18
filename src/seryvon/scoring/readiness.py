# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Agentic-readiness aggregator (ASO pillar, document 11 §4.8).

Pure, deterministic synthesis of the ASO signals into a graded level:
- `advanced`: WebMCP present AND >=2 action signals (potentialAction/forms/openapi);
- `ready`   : WebMCP present OR >=2 action signals;
- `basic`   : >=1 action signal;
- `none`    : none.

Feeds the report's `aso_readiness` summary table (document 05 §2.8).
"""

from __future__ import annotations

from seryvon.models.enums import ReadinessLevel
from seryvon.models.report import AsoReadiness
from seryvon.models.signals import SignalBundle

_AGENT_READY = (ReadinessLevel.READY, ReadinessLevel.ADVANCED)


def compute_aso_readiness(bundle: SignalBundle) -> AsoReadiness:
    """Derive the aggregated agentic readiness of a `SignalBundle`."""
    pages = bundle.pages
    has_webmcp = any(
        p.aso.webmcp.has_register_tool or p.aso.webmcp.has_tool_attributes for p in pages
    )
    has_potential = any(p.aso.potential_actions for p in pages)
    has_forms = any(p.aso.agent_usable_forms > 0 for p in pages)
    has_openapi = any(p.aso.openapi_links for p in pages)
    action_signals = sum((has_potential, has_forms, has_openapi))
    has_action_schema = has_potential or any(p.aso.action_schema_types for p in pages)

    if has_webmcp and action_signals >= 2:
        level = ReadinessLevel.ADVANCED
    elif has_webmcp or action_signals >= 2:
        level = ReadinessLevel.READY
    elif action_signals >= 1:
        level = ReadinessLevel.BASIC
    else:
        level = ReadinessLevel.NONE

    endpoints = bundle.external.ai_discovery_endpoints or {}
    brand = bundle.external.brand_coherence
    brand_score = round(sum(brand.values()) / len(brand) * 100, 2) if brand else None
    return AsoReadiness(
        readiness_level=level,
        agent_ready=level in _AGENT_READY,
        has_webmcp=has_webmcp,
        has_action_schema=has_action_schema,
        ai_discovery_endpoints=sum(1 for ok in endpoints.values() if ok),
        has_nlweb=bundle.external.nlweb_status == "conformant",
        brand_coherence_score=brand_score,
        blocked_agent_bots=list(bundle.site.blocked_agent_bots),
    )
