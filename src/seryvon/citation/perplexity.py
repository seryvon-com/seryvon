# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Perplexity connector — reference engine for retrieval citation (document 07 §7.1).

Perplexity Sonar performs native web search: citations are returned as response
metadata, so this connector measures the *retrieval citation* directly
(`web_search_enabled` is always True). It uses the OpenAI-compatible
chat-completions endpoint via raw httpx (no extra dependency); the client is
injectable for network-free tests.

Parsing is tolerant of both response shapes: `search_results` (rich: title + url)
is preferred, falling back to `citations` (a list of URL strings).
"""

from __future__ import annotations

from typing import Any

import httpx

from seryvon.models.llm import LlmCitation, LlmResponse

PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar"


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _parse_citations(payload: dict[str, Any]) -> list[LlmCitation]:
    """Extract citations, preferring `search_results` (title+url) over `citations`."""
    results = payload.get("search_results")
    if isinstance(results, list):
        rich = [
            LlmCitation(url=str(item["url"]), title=_opt_str(item.get("title")), position=rank)
            for rank, item in enumerate(results, start=1)
            if isinstance(item, dict) and item.get("url")
        ]
        if rich:
            return rich
    urls = payload.get("citations")
    if isinstance(urls, list):
        return [
            LlmCitation(url=url, position=rank)
            for rank, url in enumerate(urls, start=1)
            if isinstance(url, str) and url.strip()
        ]
    return []


def _parse(
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    engine: str,
    model: str,
    prompt_id: str,
    repetition: int,
) -> LlmResponse:
    """Map a Perplexity chat-completions response to a normalized `LlmResponse`."""
    content = ""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            content = str(message.get("content") or "")
    usage = payload.get("usage")
    rate_limit = {
        key: value
        for key, value in headers.items()
        if "ratelimit" in key.lower() or key.lower() == "retry-after"
    }
    return LlmResponse(
        engine=engine,
        model=str(payload.get("model") or model),
        prompt_id=prompt_id,
        repetition=repetition,
        response_text=content,
        citations=_parse_citations(payload),
        web_search_enabled=True,  # Sonar always searches the web (retrieval mode)
        usage=usage if isinstance(usage, dict) else {},
        rate_limit_snapshot=rate_limit,
    )


class PerplexityConnector:
    """LLM connector for Perplexity Sonar (implements the `LlmConnector` protocol)."""

    provider = "perplexity"

    def __init__(self, api_key: str, *, model: str = DEFAULT_MODEL, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

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
        """Query Perplexity for `prompt`. Raises `httpx.HTTPError` on failure (ENF-03)."""
        chosen = model or self._model
        payload: dict[str, Any] = {}
        headers: dict[str, str] = {}
        own_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                PERPLEXITY_ENDPOINT,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": chosen, "messages": [{"role": "user", "content": prompt}]},
            )
            response.raise_for_status()
            payload = response.json()
            headers = dict(response.headers)
        finally:
            if own_client:
                await client.aclose()
        return _parse(
            payload,
            headers,
            engine=self.provider,
            model=chosen,
            prompt_id=prompt_id,
            repetition=repetition,
        )
