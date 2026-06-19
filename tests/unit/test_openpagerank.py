# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the OpenPageRank connector (pure parsing + fetch via MockTransport)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from seryvon.connectors.openpagerank import (
    OpenPageRankResult,
    fetch_openpagerank,
    parse_openpagerank,
)
from seryvon.core.config import Settings

SAMPLE_OPR: dict[str, Any] = {
    "status_code": 200,
    "response": [
        {
            "status_code": 200,
            "error": "",
            "page_rank_integer": 4,
            "page_rank_decimal": 4.27,
            "rank": "123456",
            "domain": "ex.com",
        }
    ],
}


# --------------------------------------------------------------------------- #
# parse_openpagerank (pur)                                                     #
# --------------------------------------------------------------------------- #
def test_parse_valid() -> None:
    assert parse_openpagerank(SAMPLE_OPR).page_rank == 4.27


def test_parse_domain_not_found() -> None:
    payload = {"response": [{"status_code": 404, "error": "Domain not found"}]}
    assert parse_openpagerank(payload).page_rank is None


def test_parse_empty() -> None:
    assert parse_openpagerank({}).page_rank is None
    assert parse_openpagerank({"response": []}).page_rank is None


# --------------------------------------------------------------------------- #
# fetch_openpagerank (I/O via MockTransport)                                   #
# --------------------------------------------------------------------------- #
async def test_fetch_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SAMPLE_OPR)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_openpagerank("ex.com", api_key="k", client=client)
    await client.aclose()
    assert result.page_rank == 4.27


async def test_fetch_sends_key_header_and_domain() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["api_opr"] = request.headers["API-OPR"]
        captured["domain"] = request.url.params["domains[]"]
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await fetch_openpagerank("ex.com", api_key="secret", client=client)
    await client.aclose()
    assert captured == {"api_opr": "secret", "domain": "ex.com"}


async def test_fetch_http_error_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_openpagerank("ex.com", api_key="k", client=client)
    await client.aclose()
    assert result == OpenPageRankResult()


def test_settings_reads_opr_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPR_API_KEY", "opr-key")
    assert Settings().opr_api_key == "opr-key"
