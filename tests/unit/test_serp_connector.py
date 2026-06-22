# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Tests for the SERP / AI Overview connector (M9)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from seryvon.connectors.serp import (
    AioMetrics,
    AioResult,
    aggregate_aio,
    build_queries,
    fetch_serp_aio,
    parse_serp_aio,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TARGET = "example.com"

_PAYLOAD_WITH_AIO: dict[str, Any] = {
    "search_metadata": {"status": "Success"},
    "ai_overview": {
        "text_blocks": [{"type": "paragraph", "snippet": "Example is a domain used for testing."}],
        "references": [
            {"title": "Example Domain", "link": "https://www.example.com/"},
            {"title": "IANA", "link": "https://www.iana.org/domains/example"},
        ],
    },
    "organic_results": [
        {"position": 1, "title": "Example Domain", "link": "https://www.example.com/"}
    ],
}

_PAYLOAD_AIO_TRIGGERED_NOT_CITED: dict[str, Any] = {
    "ai_overview": {
        "references": [
            {"title": "Other Site", "link": "https://other.com/page"},
            {"title": "Another", "link": "https://another.org/page"},
        ],
    },
}

_PAYLOAD_NO_AIO: dict[str, Any] = {
    "organic_results": [
        {"position": 1, "title": "Example", "link": "https://www.example.com/"}
    ],
}


# ---------------------------------------------------------------------------
# parse_serp_aio — pure unit tests
# ---------------------------------------------------------------------------


def test_parse_aio_target_cited() -> None:
    result = parse_serp_aio(_PAYLOAD_WITH_AIO, TARGET, "example")
    assert result.aio_triggered is True
    assert result.target_cited is True
    assert result.target_position == 1
    assert len(result.sources) == 2


def test_parse_aio_triggered_not_cited() -> None:
    result = parse_serp_aio(_PAYLOAD_AIO_TRIGGERED_NOT_CITED, TARGET, "example what is")
    assert result.aio_triggered is True
    assert result.target_cited is False
    assert result.target_position is None


def test_parse_no_aio() -> None:
    result = parse_serp_aio(_PAYLOAD_NO_AIO, TARGET, "example review")
    assert result.aio_triggered is False
    assert result.target_cited is False
    assert result.sources == []


def test_parse_empty_payload() -> None:
    result = parse_serp_aio({}, TARGET, "q")
    assert result.aio_triggered is False
    assert result.target_cited is False


def test_parse_aio_with_sources_key() -> None:
    """SerpAPI sometimes uses 'sources' instead of 'references'."""
    payload = {
        "ai_overview": {
            "sources": [{"link": "https://example.com/about", "title": "About"}],
        }
    }
    result = parse_serp_aio(payload, TARGET, "q")
    assert result.aio_triggered is True
    assert result.target_cited is True
    assert result.target_position == 1


# ---------------------------------------------------------------------------
# aggregate_aio — pure unit tests
# ---------------------------------------------------------------------------


def test_aggregate_empty() -> None:
    metrics = aggregate_aio([])
    assert metrics.presence_rate == 0.0
    assert metrics.trigger_rate == 0.0
    assert metrics.avg_position is None
    assert metrics.query_count == 0


def test_aggregate_all_cited() -> None:
    results = [
        AioResult(query="q1", aio_triggered=True, target_cited=True, target_position=2),
        AioResult(query="q2", aio_triggered=True, target_cited=True, target_position=1),
    ]
    m = aggregate_aio(results)
    assert m.presence_rate == 1.0
    assert m.trigger_rate == 1.0
    assert m.avg_position == pytest.approx(1.5)
    assert m.query_count == 2


def test_aggregate_partial() -> None:
    results = [
        AioResult(query="q1", aio_triggered=True, target_cited=True, target_position=1),
        AioResult(query="q2", aio_triggered=True, target_cited=False),
        AioResult(query="q3", aio_triggered=False, target_cited=False),
    ]
    m = aggregate_aio(results)
    assert m.presence_rate == pytest.approx(1 / 3)
    assert m.trigger_rate == pytest.approx(2 / 3)
    assert m.avg_position == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# build_queries
# ---------------------------------------------------------------------------


def test_build_queries_from_domain() -> None:
    qs = build_queries("world-models.io")
    assert qs[0] == "world-models"
    assert "what is world-models" in qs
    assert len(qs) == 3


def test_build_queries_with_brand_override() -> None:
    qs = build_queries("example.com", brand="Acme Corp")
    assert qs[0] == "Acme Corp"
    assert all("Acme Corp" in q for q in qs)


# ---------------------------------------------------------------------------
# fetch_serp_aio — network-free via MockTransport
# ---------------------------------------------------------------------------


def _make_transport(responses: list[dict[str, Any]]) -> httpx.MockTransport:
    """Return a MockTransport that serves each payload in sequence."""
    payloads = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        data = next(payloads, {})
        return httpx.Response(200, content=json.dumps(data).encode())

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_serp_aio_cited() -> None:
    payloads = [_PAYLOAD_WITH_AIO, _PAYLOAD_AIO_TRIGGERED_NOT_CITED, _PAYLOAD_NO_AIO]
    client = httpx.AsyncClient(transport=_make_transport(payloads))
    metrics = await fetch_serp_aio(
        TARGET, api_key="test_key", queries=["example", "what is example", "example review"],
        client=client
    )
    assert metrics is not None
    assert metrics.query_count == 3
    assert metrics.presence_rate == pytest.approx(1 / 3)
    assert metrics.trigger_rate == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_fetch_serp_aio_no_aio() -> None:
    payloads = [_PAYLOAD_NO_AIO, _PAYLOAD_NO_AIO, _PAYLOAD_NO_AIO]
    client = httpx.AsyncClient(transport=_make_transport(payloads))
    metrics = await fetch_serp_aio(
        TARGET, api_key="test_key", queries=["q1", "q2", "q3"], client=client
    )
    assert metrics is not None
    assert metrics.presence_rate == 0.0
    assert metrics.trigger_rate == 0.0
    assert metrics.avg_position is None


@pytest.mark.asyncio
async def test_fetch_serp_aio_http_error_degrades_gracefully() -> None:
    """A 4xx on one query does not crash; that query counts as no AIO."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, content=json.dumps(_PAYLOAD_WITH_AIO).encode())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    metrics = await fetch_serp_aio(
        TARGET, api_key="key", queries=["q1", "q2"], client=client
    )
    assert metrics is not None
    assert metrics.query_count == 2
    # First query failed → no AIO; second cited → 1/2
    assert metrics.presence_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Scoring criterion — integration via SignalBundle
# ---------------------------------------------------------------------------


def test_gso_ai_overview_not_measured_when_no_metrics() -> None:
    from seryvon.models.signals import ExternalSignals, SignalBundle

    bundle = SignalBundle(domain="example.com", external=ExternalSignals())
    from seryvon.scoring.rules.gso import GsoAiOverviewCriterion

    result = GsoAiOverviewCriterion().evaluate(bundle)
    assert result.status == "not_measured"


def test_gso_ai_overview_scored_from_aio_metrics() -> None:
    from seryvon.models.signals import AioMetrics, ExternalSignals, SignalBundle

    aio = AioMetrics(presence_rate=0.67, trigger_rate=1.0, avg_position=2.0, query_count=3)
    bundle = SignalBundle(domain="example.com", external=ExternalSignals(aio_metrics=aio))
    from seryvon.scoring.rules.gso import GsoAiOverviewCriterion

    result = GsoAiOverviewCriterion().evaluate(bundle)
    assert result.status != "not_measured"
    assert result.score == pytest.approx(67.0)
    assert result.raw_value["presence_rate"] == pytest.approx(0.67)  # type: ignore[index]
    assert result.raw_value["trigger_rate"] == pytest.approx(1.0)  # type: ignore[index]
