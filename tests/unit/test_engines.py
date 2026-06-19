# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the OpenAI/Anthropic/Gemini connectors (parsing via MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from seryvon.citation import (
    AnthropicConnector,
    GeminiConnector,
    LlmConnector,
    OpenAiConnector,
)

OPENAI: dict[str, Any] = {
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Seryvon is cited.",
                "annotations": [
                    {
                        "type": "url_citation",
                        "url_citation": {"url": "https://seryvon.com/", "title": "Seryvon"},
                    }
                ],
            },
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
}

ANTHROPIC: dict[str, Any] = {
    "model": "claude-haiku-4-5",
    "content": [
        {"type": "text", "text": "Seryvon is cited."},
        {
            "type": "web_search_tool_result",
            "content": [
                {"type": "web_search_result", "url": "https://seryvon.com/", "title": "Seryvon"}
            ],
        },
    ],
    "usage": {"input_tokens": 10, "output_tokens": 20},
}

GEMINI: dict[str, Any] = {
    "modelVersion": "gemini-2.5-flash",
    "candidates": [
        {
            "content": {"parts": [{"text": "Seryvon is cited."}]},
            "groundingMetadata": {
                "groundingChunks": [{"web": {"uri": "https://seryvon.com/", "title": "Seryvon"}}]
            },
        }
    ],
    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
}


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_connectors_satisfy_protocol() -> None:
    assert isinstance(OpenAiConnector("k"), LlmConnector)
    assert isinstance(AnthropicConnector("k"), LlmConnector)
    assert isinstance(GeminiConnector("k"), LlmConnector)
    assert (OpenAiConnector("k").provider, AnthropicConnector("k").provider) == (
        "openai",
        "anthropic",
    )


async def test_openai_parses_content_and_citations() -> None:
    client = _client(lambda request: httpx.Response(200, json=OPENAI))
    response = await OpenAiConnector("k").query("prompt?", prompt_id="p1", client=client)
    await client.aclose()
    assert response.engine == "openai"
    assert response.response_text == "Seryvon is cited."
    assert [c.url for c in response.citations] == ["https://seryvon.com/"]
    assert response.citations[0].title == "Seryvon"
    assert response.web_search_enabled is True
    assert response.usage["completion_tokens"] == 20


async def test_openai_knowledge_mode_sends_no_tool() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "gpt-4o-mini", "choices": []})

    client = _client(handler)
    response = await OpenAiConnector("k").query("prompt?", web_search=False, client=client)
    await client.aclose()
    assert "tools" not in captured["body"]
    assert response.web_search_enabled is False
    assert response.citations == []


async def test_anthropic_parses_text_and_search_results() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=ANTHROPIC)

    client = _client(handler)
    response = await AnthropicConnector("secret").query("prompt?", client=client)
    await client.aclose()
    assert captured["headers"]["x-api-key"] == "secret"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert response.response_text == "Seryvon is cited."
    assert [c.url for c in response.citations] == ["https://seryvon.com/"]


async def test_gemini_parses_grounding_chunks() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json=GEMINI)

    client = _client(handler)
    response = await GeminiConnector("k", model="gemini-2.5-flash").query("prompt?", client=client)
    await client.aclose()
    assert "models/gemini-2.5-flash:generateContent" in captured["url"]
    assert captured["key"] == "k"
    assert response.response_text == "Seryvon is cited."
    assert [c.url for c in response.citations] == ["https://seryvon.com/"]
    assert response.model == "gemini-2.5-flash"


async def test_engines_raise_on_http_error() -> None:
    client = _client(lambda request: httpx.Response(503, json={}))
    for connector in (OpenAiConnector("k"), AnthropicConnector("k"), GeminiConnector("k")):
        with pytest.raises(httpx.HTTPStatusError):
            await connector.query("prompt?", client=client)
    await client.aclose()
