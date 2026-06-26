# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the DataForSEO connector (parsers + dual-endpoint fetch via MockTransport)."""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest

from seryvon.connectors.dataforseo import (
    DataForSeoResult,
    _dataforseo_credentials,
    _parse_domain_analytics,
    _parse_labs,
    fetch_dataforseo,
    parse_dataforseo,
)


# --------------------------------------------------------------------------- #
# open_page_rank_equivalent — the score derivation                            #
# --------------------------------------------------------------------------- #
def test_opr_equivalent_from_domain_rank() -> None:
    # rank 455 → 4.55 ; rank 1200 clamped to 10.0
    assert DataForSeoResult(domain_rank=455).open_page_rank_equivalent == 4.55
    assert DataForSeoResult(domain_rank=1200).open_page_rank_equivalent == 10.0
    assert DataForSeoResult(domain_rank=0).open_page_rank_equivalent == 0.0


def test_opr_equivalent_from_etv_fallback() -> None:
    # log10(1001)*2.5 ≈ 7.50 (two-decimal round)
    assert DataForSeoResult(organic_etv=1000.0).open_page_rank_equivalent == 7.5
    # etv=0 → log10(1)*2.5 = 0
    assert DataForSeoResult(organic_etv=0.0).open_page_rank_equivalent == 0.0


def test_opr_equivalent_prefers_domain_rank_over_etv() -> None:
    """When both signals are present, domain_rank wins (backlink-based is stronger)."""
    result = DataForSeoResult(domain_rank=300, organic_etv=1000.0)
    assert result.open_page_rank_equivalent == 3.0


def test_opr_equivalent_none_when_both_missing() -> None:
    assert DataForSeoResult().open_page_rank_equivalent is None


# --------------------------------------------------------------------------- #
# Pure parsers                                                                #
# --------------------------------------------------------------------------- #
def test_parse_domain_analytics_success() -> None:
    payload = {"tasks": [{"result": [{"domain_rank": 455, "target": "ex.com"}]}]}
    assert _parse_domain_analytics(payload) == 455


def test_parse_domain_analytics_null_rank() -> None:
    payload = {"tasks": [{"result": [{"domain_rank": None}]}]}
    assert _parse_domain_analytics(payload) is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tasks": []},
        {"tasks": [{"result": []}]},
        {"tasks": [{}]},
        {"wrong": "shape"},
    ],
)
def test_parse_domain_analytics_malformed(payload: dict[str, Any]) -> None:
    assert _parse_domain_analytics(payload) is None


def test_parse_dataforseo_public_alias() -> None:
    payload = {"tasks": [{"result": [{"domain_rank": 200}]}]}
    result = parse_dataforseo(payload)
    assert result.domain_rank == 200
    assert result.organic_etv is None  # public alias only fills domain_rank


def test_parse_labs_success() -> None:
    payload = {
        "tasks": [{"result": [{"items": [{"metrics": {"organic": {"etv": 42.5, "count": 17}}}]}]}]
    }
    assert _parse_labs(payload) == (42.5, 17)


def test_parse_labs_missing_metrics_defaults_to_zero() -> None:
    payload = {"tasks": [{"result": [{"items": [{"metrics": {"organic": {}}}]}]}]}
    assert _parse_labs(payload) == (0.0, 0)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tasks": [{"result": [{"items": []}]}]},
        {"wrong": "shape"},
    ],
)
def test_parse_labs_malformed(payload: dict[str, Any]) -> None:
    assert _parse_labs(payload) == (0.0, 0)


# --------------------------------------------------------------------------- #
# _dataforseo_credentials — accept raw or pre-encoded                         #
# --------------------------------------------------------------------------- #
def test_credentials_from_raw_login_password() -> None:
    creds = _dataforseo_credentials("user@example.com:password")
    assert creds == base64.b64encode(b"user@example.com:password").decode()


def test_credentials_from_preencoded_token() -> None:
    encoded = base64.b64encode(b"user:password").decode()
    assert _dataforseo_credentials(encoded) == encoded


def test_credentials_rejects_garbage() -> None:
    # Pure base64 but the decoded form has no colon → not credentials.
    no_colon_encoded = base64.b64encode(b"justatoken").decode()
    assert _dataforseo_credentials(no_colon_encoded) is None
    # Total garbage.
    assert _dataforseo_credentials("not base64 either") is None


# --------------------------------------------------------------------------- #
# fetch_dataforseo (MockTransport, offline)                                   #
# --------------------------------------------------------------------------- #
def _make_handler(
    *,
    domain_payload: dict[str, Any] | int,
    labs_payload: dict[str, Any] | int,
) -> Any:
    """Return a MockTransport handler routing each endpoint to its own payload/status."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "domain_analytics" in path:
            if isinstance(domain_payload, int):
                return httpx.Response(domain_payload)
            return httpx.Response(200, json=domain_payload)
        if "dataforseo_labs" in path:
            if isinstance(labs_payload, int):
                return httpx.Response(labs_payload)
            return httpx.Response(200, json=labs_payload)
        return httpx.Response(404)

    return handler


async def test_fetch_dataforseo_invalid_key_skips_network() -> None:
    """An unparseable key returns an empty result without any HTTP call."""
    transport = httpx.MockTransport(lambda r: pytest.fail("network must not be touched"))
    client = httpx.AsyncClient(transport=transport)
    result = await fetch_dataforseo("ex.com", api_key="no-colon", client=client)
    await client.aclose()
    assert result == DataForSeoResult()


async def test_fetch_dataforseo_both_endpoints_succeed() -> None:
    handler = _make_handler(
        domain_payload={"tasks": [{"result": [{"domain_rank": 455}]}]},
        labs_payload={
            "tasks": [
                {"result": [{"items": [{"metrics": {"organic": {"etv": 10.0, "count": 5}}}]}]}
            ]
        },
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_dataforseo("ex.com", api_key="user:pass", client=client)
    await client.aclose()
    assert result.domain_rank == 455
    assert result.organic_etv == 10.0
    assert result.organic_keywords == 5
    # domain_rank wins for the OPR-equivalent.
    assert result.open_page_rank_equivalent == 4.55


async def test_fetch_dataforseo_falls_back_to_etv_when_domain_rank_absent() -> None:
    handler = _make_handler(
        domain_payload={"tasks": [{"result": [{"domain_rank": None}]}]},
        labs_payload={
            "tasks": [
                {"result": [{"items": [{"metrics": {"organic": {"etv": 1000.0, "count": 12}}}]}]}
            ]
        },
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_dataforseo("smallsite.com", api_key="user:pass", client=client)
    await client.aclose()
    assert result.domain_rank is None
    assert result.organic_etv == 1000.0
    assert result.open_page_rank_equivalent == 7.5  # ETV fallback kicks in


async def test_fetch_dataforseo_handles_401_on_both_endpoints() -> None:
    handler = _make_handler(domain_payload=401, labs_payload=401)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_dataforseo("ex.com", api_key="user:pass", client=client)
    await client.aclose()
    # Graceful degradation: empty result, no exception escapes.
    assert result.domain_rank is None
    assert result.organic_etv is None
    assert result.open_page_rank_equivalent is None


async def test_fetch_dataforseo_one_endpoint_fails_other_succeeds() -> None:
    """If domain_analytics 500s, the Labs fallback still fills ETV."""
    handler = _make_handler(
        domain_payload=500,
        labs_payload={
            "tasks": [
                {"result": [{"items": [{"metrics": {"organic": {"etv": 100.0, "count": 4}}}]}]}
            ]
        },
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_dataforseo("ex.com", api_key="user:pass", client=client)
    await client.aclose()
    assert result.domain_rank is None
    assert result.organic_etv == 100.0
    assert result.open_page_rank_equivalent is not None
