# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the Perplexity connector (parsing + fetch via MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from seryvon.citation import LlmConnector, PerplexityConnector
from seryvon.core.config import Settings

SONAR_RESPONSE: dict[str, Any] = {
    "id": "abc",
    "model": "sonar",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Seryvon is a deterministic audit tool."},
            "finish_reason": "stop",
        }
    ],
    "citations": ["https://seryvon.com/", "https://example.org/article"],
    "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46},
}


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_connector_satisfies_protocol() -> None:
    assert isinstance(PerplexityConnector("key"), LlmConnector)
    assert PerplexityConnector("key").provider == "perplexity"


async def test_query_parses_content_and_citations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SONAR_RESPONSE)

    client = _client(handler)
    response = await PerplexityConnector("key").query(
        "Which deterministic audit tools exist?", prompt_id="p1", repetition=2, client=client
    )
    await client.aclose()

    assert response.engine == "perplexity"
    assert response.model == "sonar"
    assert response.prompt_id == "p1"
    assert response.repetition == 2
    assert response.web_search_enabled is True
    assert "Seryvon" in response.response_text
    assert [c.url for c in response.citations] == [
        "https://seryvon.com/",
        "https://example.org/article",
    ]
    assert [c.position for c in response.citations] == [1, 2]
    assert response.usage["total_tokens"] == 46


async def test_query_prefers_search_results_with_titles() -> None:
    payload = {
        **SONAR_RESPONSE,
        "search_results": [
            {"title": "Seryvon", "url": "https://seryvon.com/", "date": "2026-06-01"},
            {"title": "Article", "url": "https://example.org/article"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = _client(handler)
    response = await PerplexityConnector("key").query("prompt?", client=client)
    await client.aclose()

    assert response.citations[0].title == "Seryvon"
    assert response.citations[0].url == "https://seryvon.com/"
    assert response.citations[0].position == 1


async def test_query_sends_authenticated_request() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=SONAR_RESPONSE)

    client = _client(handler)
    await PerplexityConnector("secret", model="sonar-pro").query("Hello?", client=client)
    await client.aclose()

    assert captured["auth"] == "Bearer secret"
    assert captured["body"]["model"] == "sonar-pro"
    assert captured["body"]["messages"] == [{"role": "user", "content": "Hello?"}]


async def test_query_captures_rate_limit_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=SONAR_RESPONSE,
            headers={"x-ratelimit-remaining-requests": "49", "retry-after": "1", "x-other": "z"},
        )

    client = _client(handler)
    response = await PerplexityConnector("key").query("prompt?", client=client)
    await client.aclose()

    assert response.rate_limit_snapshot["x-ratelimit-remaining-requests"] == "49"
    assert response.rate_limit_snapshot["retry-after"] == "1"
    assert "x-other" not in response.rate_limit_snapshot


async def test_query_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server"})

    client = _client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await PerplexityConnector("key").query("prompt?", client=client)
    await client.aclose()


def test_settings_reads_perplexity_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-123")
    assert Settings().perplexity_api_key == "pk-123"
