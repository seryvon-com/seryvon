# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the GSC connector (pure parsing + fetch via MockTransport + BYOK)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from seryvon.connectors.gsc import fetch_gsc, parse_gsc
from seryvon.core.config import Settings
from seryvon.models.signals import GscResult

SAMPLE_GSC: dict[str, Any] = {
    "rows": [
        {"keys": ["seryvon audit"], "position": 3.2, "clicks": 120, "impressions": 980, "ctr": 0.1224},
        {"keys": ["web audit tool"], "position": 8.1, "clicks": 45, "impressions": 1200, "ctr": 0.0375},
        {"keys": ["seo checker free"], "position": 14.5, "clicks": 12, "impressions": 670, "ctr": 0.0179},
    ]
}


# --------------------------------------------------------------------------- #
# parse_gsc (pur)                                                              #
# --------------------------------------------------------------------------- #
def test_parse_full_response() -> None:
    result = parse_gsc(SAMPLE_GSC)
    assert len(result.queries) == 3
    # Sorted by position ascending
    assert result.queries[0].query == "seryvon audit"
    assert result.queries[0].position == 3.2
    assert result.queries[0].clicks == 120
    assert result.total_clicks == 177
    assert result.total_impressions == 2850
    assert result.avg_position == pytest.approx(8.6, abs=0.5)


def test_parse_empty_rows() -> None:
    result = parse_gsc({})
    assert result.queries == []
    assert result.avg_position is None
    assert result.total_clicks == 0
    assert result.total_impressions == 0
    assert result.avg_ctr == 0.0


def test_parse_row_without_keys_is_skipped() -> None:
    payload = {"rows": [{"position": 5.0, "clicks": 10, "impressions": 100, "ctr": 0.1}]}
    result = parse_gsc(payload)
    assert result.queries == []


def test_parse_sorts_by_position() -> None:
    payload = {
        "rows": [
            {"keys": ["b"], "position": 15.0, "clicks": 5, "impressions": 50, "ctr": 0.1},
            {"keys": ["a"], "position": 2.0, "clicks": 80, "impressions": 400, "ctr": 0.2},
        ]
    }
    result = parse_gsc(payload)
    assert result.queries[0].query == "a"
    assert result.queries[1].query == "b"


def test_parse_date_range_days_forwarded() -> None:
    result = parse_gsc({}, date_range_days=30)
    assert result.date_range_days == 30


# --------------------------------------------------------------------------- #
# fetch_gsc (I/O via MockTransport + _access_token injection)                  #
# --------------------------------------------------------------------------- #
async def test_fetch_success_sc_domain() -> None:
    """Successful fetch via sc-domain: property (first template)."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "sc-domain:example.com" in str(request.url)
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(200, json=SAMPLE_GSC)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_gsc(
        "example.com",
        service_account_json="{}",
        client=client,
        _access_token="fake-token",
    )
    await client.aclose()
    assert len(result.queries) == 3
    assert result.avg_position is not None


async def test_fetch_falls_back_to_url_prefix() -> None:
    """403 on sc-domain: property => falls back to https://domain/ property."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if "sc-domain" in url:
            return httpx.Response(403, json={"error": "no access"})
        return httpx.Response(200, json=SAMPLE_GSC)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_gsc(
        "example.com",
        service_account_json="{}",
        client=client,
        _access_token="fake-token",
    )
    await client.aclose()
    assert len(calls) == 2
    assert len(result.queries) == 3


async def test_fetch_both_403_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "no access"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_gsc(
        "example.com",
        service_account_json="{}",
        client=client,
        _access_token="fake-token",
    )
    await client.aclose()
    assert result == GscResult()


async def test_fetch_network_error_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("timeout")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_gsc(
        "example.com",
        service_account_json="{}",
        client=client,
        _access_token="fake-token",
    )
    await client.aclose()
    assert result.avg_position is None


async def test_fetch_no_token_returns_empty() -> None:
    """When _get_access_token returns None (bad JSON), graceful empty result."""
    result = await fetch_gsc(
        "example.com",
        service_account_json="not-valid-json",
        _access_token=None,
    )
    assert result.avg_position is None


# --------------------------------------------------------------------------- #
# BYOK: key read via GSC_SERVICE_ACCOUNT                                       #
# --------------------------------------------------------------------------- #
def test_settings_reads_gsc_service_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GSC_SERVICE_ACCOUNT", '{"type": "service_account"}')
    assert Settings().gsc_service_account == '{"type": "service_account"}'
