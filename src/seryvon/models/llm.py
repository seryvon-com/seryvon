# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""I/O contract for the LLM citation connectors (module M4, document 07 §7).

`LlmResponse` is the raw data produced by a connector (network, non-deterministic)
for a (prompt, engine, repetition) triple. The aggregator
(`seryvon.citation.aggregate`) derives a frozen, deterministic `CitationMetrics`
from it; that — and only that — is what the scoring rules read.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LlmCitation(BaseModel):
    """A source cited by an engine (document 07 §7)."""

    url: str | None = None
    domain: str | None = None
    title: str | None = None
    position: int | None = None  # rank in the citation list


class LlmResponse(BaseModel):
    """An LLM engine response for a (prompt, engine, repetition).

    `web_search_enabled` distinguishes *retrieval* mode (web search active ->
    actual citation) from *knowledge* mode (bare model -> awareness from memory),
    document 07 §2.
    """

    engine: str
    model: str  # variant actually executed (returned by the API)
    prompt_id: str
    repetition: int
    response_text: str = ""
    citations: list[LlmCitation] = Field(default_factory=list)
    web_search_enabled: bool = False
    usage: dict[str, Any] = Field(default_factory=dict)  # tokens in/out, estimated cost
    rate_limit_snapshot: dict[str, Any] = Field(default_factory=dict)
