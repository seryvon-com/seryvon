# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the GSC connector (pure parsing + fetch via MockTransport + BYOK)."""

from __future__ import annotations

import builtins
import json
from datetime import date
from typing import Any

import httpx
import pytest

from seryvon.connectors.gsc import (
    _get_access_token,
    _query,
    build_comparison,
    fetch_gsc,
    parse_gsc,
    parse_gsc_pages,
)
from seryvon.core.config import Settings
from seryvon.models.signals import GscResult

SAMPLE_GSC_PAGES: dict[str, Any] = {
    "rows": [
        {
            "keys": ["https://example.com/blog/a"],
            "position": 4.0,
            "clicks": 90,
            "impressions": 700,
            "ctr": 0.1286,
        },
        {
            "keys": ["https://example.com/"],
            "position": 6.0,
            "clicks": 200,
            "impressions": 2000,
            "ctr": 0.10,
        },
    ]
}

SAMPLE_GSC: dict[str, Any] = {
    "rows": [
        {
            "keys": ["seryvon audit"],
            "position": 3.2,
            "clicks": 120,
            "impressions": 980,
            "ctr": 0.1224,
        },
        {
            "keys": ["web audit tool"],
            "position": 8.1,
            "clicks": 45,
            "impressions": 1200,
            "ctr": 0.0375,
        },
        {
            "keys": ["seo checker free"],
            "position": 14.5,
            "clicks": 12,
            "impressions": 670,
            "ctr": 0.0179,
        },
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


def test_parse_pages_sorted_by_clicks_desc() -> None:
    pages = parse_gsc_pages(SAMPLE_GSC_PAGES)
    assert len(pages) == 2
    assert pages[0].page == "https://example.com/"  # 200 clicks
    assert pages[1].page == "https://example.com/blog/a"  # 90 clicks


def test_parse_pages_skips_rows_without_keys() -> None:
    assert parse_gsc_pages({"rows": [{"clicks": 5}]}) == []


def test_build_comparison_computes_deltas() -> None:
    current = parse_gsc(SAMPLE_GSC)  # clicks=177, impr=2850
    previous = {
        "rows": [
            {
                "keys": ["seryvon audit"],
                "position": 5.0,
                "clicks": 100,
                "impressions": 2000,
                "ctr": 0.05,
            }
        ]
    }
    cmp = build_comparison(current, previous, period_days=90)
    assert cmp.previous_clicks == 100
    assert cmp.clicks_delta == 77  # 177 - 100
    assert cmp.impressions_delta == 850  # 2850 - 2000
    assert cmp.period_days == 90
    # current avg_position (~8.6) worse than previous (5.0) => positive delta.
    assert cmp.position_delta is not None and cmp.position_delta > 0


def test_build_comparison_none_position_when_previous_empty() -> None:
    current = parse_gsc(SAMPLE_GSC)
    cmp = build_comparison(current, {}, period_days=90)
    assert cmp.previous_avg_position is None
    assert cmp.position_delta is None


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
        include_pages=False,
        compare=False,
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
        include_pages=False,
        compare=False,
        _access_token="fake-token",
    )
    await client.aclose()
    # Resolution probes sc-domain (403) then url-prefix (200), then the query runs.
    assert any("sc-domain" in c for c in calls)
    assert any("sc-domain" not in c for c in calls)
    assert len(result.queries) == 3


async def test_fetch_with_pages_and_comparison() -> None:
    """Page breakdown + previous-period comparison are populated when requested."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        if '"page"' in body:
            return httpx.Response(200, json=SAMPLE_GSC_PAGES)
        return httpx.Response(200, json=SAMPLE_GSC)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_gsc(
        "example.com",
        service_account_json="{}",
        client=client,
        include_pages=True,
        compare=True,
        _access_token="fake-token",
    )
    await client.aclose()
    assert len(result.pages) == 2
    # Sorted by clicks descending.
    assert result.pages[0].page == "https://example.com/"
    assert result.comparison is not None
    # Current == previous (same fixture) => zero deltas.
    assert result.comparison.clicks_delta == 0
    assert result.comparison.position_delta == 0.0


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


async def test_fetch_gsc_constructs_and_closes_owned_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OwnedClient:
        def __init__(self, **kwargs: object) -> None:
            self.closed = False

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(403, request=httpx.Request("POST", url))

        async def aclose(self) -> None:
            self.closed = True

    holder: dict[str, OwnedClient] = {}

    def factory(**kwargs: object) -> OwnedClient:
        client = OwnedClient(**kwargs)
        holder["client"] = client
        return client

    monkeypatch.setattr("seryvon.connectors.gsc.httpx.AsyncClient", factory)
    assert (
        await fetch_gsc("example.com", service_account_json="{}", _access_token="token")
        == GscResult()
    )
    assert holder["client"].closed is True


@pytest.mark.asyncio
async def test_query_paginates_until_short_page() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start = int(json.loads(request.content)["startRow"])
        calls.append(start)
        rows = [{"keys": [str(start + i)]} for i in range(2 if start == 0 else 1)]
        return httpx.Response(200, json={"rows": rows})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await _query(
        client,
        "https://gsc.test/query",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        dimensions=["query"],
        headers={},
        row_limit=2,
        max_rows=4,
    )
    await client.aclose()
    assert result is not None and len(result["rows"]) == 3
    assert calls == [0, 2]


@pytest.mark.asyncio
async def test_query_returns_none_on_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await _query(
        client,
        "https://gsc.test/query",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        dimensions=["query"],
        headers={},
        row_limit=10,
        max_rows=10,
    )
    await client.aclose()
    assert result is None


@pytest.mark.asyncio
async def test_query_returns_none_on_status_or_json_error() -> None:
    for response in (
        httpx.Response(503),
        httpx.Response(200, content=b"invalid-json"),
    ):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request, r=response: r))
        result = await _query(
            client,
            "https://gsc.test/query",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            dimensions=["query"],
            headers={},
            row_limit=10,
            max_rows=10,
        )
        await client.aclose()
        assert result is None


@pytest.mark.asyncio
async def test_fetch_returns_empty_when_resolved_property_query_fails() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200 if calls == 1 else 503, json={"rows": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_gsc(
        "example.com",
        service_account_json="{}",
        client=client,
        include_pages=False,
        compare=False,
        _access_token="token",
    )
    await client.aclose()
    assert result == GscResult()


# --------------------------------------------------------------------------- #
# BYOK: key read via GSC_SERVICE_ACCOUNT                                       #
# --------------------------------------------------------------------------- #
def test_settings_reads_gsc_service_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GSC_SERVICE_ACCOUNT", '{"type": "service_account"}')
    assert Settings().gsc_service_account == '{"type": "service_account"}'


def test_get_access_token_handles_missing_google_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def missing_google_auth(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("google.auth") or name.startswith("google.oauth2"):
            raise ImportError("google-auth unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_google_auth)
    assert _get_access_token("{}") is None


def test_get_access_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.auth.transport import requests as auth_requests
    from google.oauth2 import service_account

    class Credentials:
        token: str | None = None

        def refresh(self, request: object) -> None:
            self.token = "token-from-google"

    def from_info(info: dict[str, Any], *, scopes: list[str]) -> Credentials:
        assert info == {}
        assert scopes
        return Credentials()

    monkeypatch.setattr(
        service_account.Credentials, "from_service_account_info", staticmethod(from_info)
    )
    monkeypatch.setattr(auth_requests, "Request", lambda: object())
    assert _get_access_token("{}") == "token-from-google"
