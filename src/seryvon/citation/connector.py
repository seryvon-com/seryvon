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

from typing import Any, Protocol, runtime_checkable

import httpx

from seryvon.models.llm import LlmResponse


async def request_json(
    url: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any],
    client: httpx.AsyncClient | None,
    timeout: float,
) -> tuple[dict[str, Any], dict[str, str]]:
    """POST `json_body`, raise on HTTP error, return (payload, response headers).

    Shared transport helper for the engine connectors: opens a short-lived client
    when none is injected, otherwise reuses the caller's (and never closes it).
    """
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    try:
        response = await client.post(url, headers=headers, json=json_body)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return payload, dict(response.headers)
    finally:
        if own_client:
            await client.aclose()


def rate_limit_snapshot(headers: dict[str, str]) -> dict[str, str]:
    """Keep the rate-limit / retry-after response headers (for the dispatcher)."""
    return {
        key: value
        for key, value in headers.items()
        if "ratelimit" in key.lower() or key.lower() == "retry-after"
    }


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
