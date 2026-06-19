# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""LLM connector contract (module M4, document 07 §7).

Each engine connector performs the network call (impure, non-deterministic) and
returns a normalized `LlmResponse`. The pure aggregator (`citation.aggregate`)
then derives the deterministic `CitationMetrics`. Connectors are tested without a
network via `httpx.MockTransport` (injectable client).

`query` raises on a network/HTTP failure so the orchestrator can exclude the
failed (prompt, engine, repetition) cell rather than count it as "not cited".
Capability probing and model listing (document 07 §5) are deferred to a later
slice; the orchestrator determines engine availability from the configured BYOK keys.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

from seryvon.models.llm import LlmResponse


@runtime_checkable
class LlmConnector(Protocol):
    """Common interface implemented by each engine connector."""

    provider: str

    async def query(
        self,
        prompt: str,
        *,
        prompt_id: str = "",
        repetition: int = 1,
        model: str | None = None,
        web_search: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> LlmResponse:
        """Send `prompt` to the engine and return a normalized `LlmResponse`.

        `model=None` uses the connector's default. `client` is injectable for tests
        (otherwise a short-lived client is opened). Raises `httpx.HTTPError` on failure.
        """
        ...
