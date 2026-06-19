# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""OpenAI / Anthropic / Gemini connectors (module M4, document 07 §7.2-7.4).

Each implements the `LlmConnector` protocol over raw httpx (injectable client,
raises on HTTP error). `web_search=True` activates the engine's web-search /
grounding tool (retrieval mode); without it the model answers from memory
(knowledge mode) and returns no URL citation.

The request/response shapes follow each provider's documented API and are
validated offline via `httpx.MockTransport`; real-key validation is a follow-up.
"""

from __future__ import annotations

from typing import Any

import httpx

from seryvon.citation.connector import rate_limit_snapshot, request_json
from seryvon.models.llm import LlmCitation, LlmResponse

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _citations(items: list[tuple[Any, Any]]) -> list[LlmCitation]:
    """Build citations from (url, title) pairs, keeping order and skipping empties."""
    out: list[LlmCitation] = []
    for rank, (url, title) in enumerate(items, start=1):
        if isinstance(url, str) and url.strip():
            out.append(LlmCitation(url=url, title=_opt_str(title), position=rank))
    return out


class OpenAiConnector:
    """OpenAI chat-completions connector (document 07 §7.2)."""

    provider = "openai"

    def __init__(self, api_key: str, *, model: str = "gpt-4o-mini", timeout: float = 30.0) -> None:
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
        chosen = model or self._model
        body: dict[str, Any] = {"model": chosen, "messages": [{"role": "user", "content": prompt}]}
        if web_search:
            body["tools"] = [{"type": "web_search"}]
        payload, headers = await request_json(
            OPENAI_ENDPOINT,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json_body=body,
            client=client,
            timeout=self._timeout,
        )
        message: dict[str, Any] = {}
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
        annotations = message.get("annotations") if isinstance(message, dict) else None
        pairs: list[tuple[Any, Any]] = []
        if isinstance(annotations, list):
            for item in annotations:
                cit = item.get("url_citation") if isinstance(item, dict) else None
                if isinstance(cit, dict):
                    pairs.append((cit.get("url"), cit.get("title")))
        usage = payload.get("usage")
        return LlmResponse(
            engine=self.provider,
            model=str(payload.get("model") or chosen),
            prompt_id=prompt_id,
            repetition=repetition,
            response_text=str(message.get("content") or "") if isinstance(message, dict) else "",
            citations=_citations(pairs),
            web_search_enabled=web_search,
            usage=usage if isinstance(usage, dict) else {},
            rate_limit_snapshot=rate_limit_snapshot(headers),
        )


class AnthropicConnector:
    """Anthropic Messages connector (document 07 §7.3)."""

    provider = "anthropic"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-haiku-4-5",
        max_tokens: int = 1024,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
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
        chosen = model or self._model
        body: dict[str, Any] = {
            "model": chosen,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if web_search:
            body["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
        payload, headers = await request_json(
            ANTHROPIC_ENDPOINT,
            headers={"x-api-key": self._api_key, "anthropic-version": ANTHROPIC_VERSION},
            json_body=body,
            client=client,
            timeout=self._timeout,
        )
        blocks = payload.get("content")
        text_parts: list[str] = []
        pairs: list[tuple[Any, Any]] = []
        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(str(block.get("text") or ""))
                elif block.get("type") == "web_search_tool_result":
                    for result in block.get("content") or []:
                        if isinstance(result, dict) and result.get("type") == "web_search_result":
                            pairs.append((result.get("url"), result.get("title")))
        usage = payload.get("usage")
        return LlmResponse(
            engine=self.provider,
            model=str(payload.get("model") or chosen),
            prompt_id=prompt_id,
            repetition=repetition,
            response_text="".join(text_parts),
            citations=_citations(pairs),
            web_search_enabled=web_search,
            usage=usage if isinstance(usage, dict) else {},
            rate_limit_snapshot=rate_limit_snapshot(headers),
        )


class GeminiConnector:
    """Gemini generateContent connector with Google Search grounding (document 07 §7.4)."""

    provider = "gemini"

    def __init__(
        self, api_key: str, *, model: str = "gemini-2.5-flash", timeout: float = 30.0
    ) -> None:
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
        chosen = model or self._model
        body: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
        if web_search:
            body["tools"] = [{"google_search": {}}]
        payload, headers = await request_json(
            GEMINI_ENDPOINT_TEMPLATE.format(model=chosen),
            headers={"x-goog-api-key": self._api_key},
            json_body=body,
            client=client,
            timeout=self._timeout,
        )
        candidate: dict[str, Any] = {}
        candidates = payload.get("candidates")
        if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
            candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
        pairs: list[tuple[Any, Any]] = []
        chunks = (candidate.get("groundingMetadata") or {}).get("groundingChunks") or []
        for chunk in chunks:
            web = chunk.get("web") if isinstance(chunk, dict) else None
            if isinstance(web, dict):
                pairs.append((web.get("uri"), web.get("title")))
        usage = payload.get("usageMetadata")
        return LlmResponse(
            engine=self.provider,
            model=str(payload.get("modelVersion") or chosen),
            prompt_id=prompt_id,
            repetition=repetition,
            response_text=text,
            citations=_citations(pairs),
            web_search_enabled=web_search,
            usage=usage if isinstance(usage, dict) else {},
            rate_limit_snapshot=rate_limit_snapshot(headers),
        )
