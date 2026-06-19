# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the PageSpeed Insights connector (pure parsing + fetch via MockTransport)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from seryvon.connectors.pagespeed import PageSpeedResult, fetch_pagespeed, parse_pagespeed
from seryvon.core.config import Settings

SAMPLE_PSI: dict[str, Any] = {
    "loadingExperience": {
        "metrics": {
            "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2400, "category": "FAST"},
            "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 5, "category": "FAST"},
            "INTERACTION_TO_NEXT_PAINT": {"percentile": 180, "category": "FAST"},
        }
    },
    "lighthouseResult": {"categories": {"performance": {"score": 0.92}}},
}


# --------------------------------------------------------------------------- #
# parse_pagespeed (pur)                                                        #
# --------------------------------------------------------------------------- #
def test_parse_full_response() -> None:
    result = parse_pagespeed(SAMPLE_PSI)
    assert result.core_web_vitals == {"lcp": 2400.0, "cls": 0.05, "inp": 180.0}
    assert result.lighthouse_performance == 0.92


def test_parse_without_field_data() -> None:
    payload = {"lighthouseResult": {"categories": {"performance": {"score": 0.5}}}}
    result = parse_pagespeed(payload)
    assert result.core_web_vitals is None  # no CrUX field data
    assert result.lighthouse_performance == 0.5


def test_parse_partial_metrics() -> None:
    payload = {
        "loadingExperience": {"metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 1800}}}
    }
    result = parse_pagespeed(payload)
    assert result.core_web_vitals == {"lcp": 1800.0}
    assert result.lighthouse_performance is None


def test_parse_empty_payload() -> None:
    result = parse_pagespeed({})
    assert result == PageSpeedResult(core_web_vitals=None, lighthouse_performance=None)


# --------------------------------------------------------------------------- #
# fetch_pagespeed (I/O via MockTransport)                                      #
# --------------------------------------------------------------------------- #
async def test_fetch_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SAMPLE_PSI)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_pagespeed("https://ex.com/", api_key="k", client=client)
    await client.aclose()
    assert result.lighthouse_performance == 0.92
    assert result.core_web_vitals == {"lcp": 2400.0, "cls": 0.05, "inp": 180.0}


async def test_fetch_sends_expected_params() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await fetch_pagespeed(
        "https://ex.com/page", api_key="secret", strategy="desktop", client=client
    )
    await client.aclose()
    assert captured["url"] == "https://ex.com/page"
    assert captured["strategy"] == "desktop"
    assert captured["key"] == "secret"


async def test_fetch_http_error_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_pagespeed("https://ex.com/", api_key="k", client=client)
    await client.aclose()
    assert result == PageSpeedResult()


async def test_fetch_invalid_json_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_pagespeed("https://ex.com/", api_key="k", client=client)
    await client.aclose()
    assert result == PageSpeedResult()


# --------------------------------------------------------------------------- #
# BYOK: key read via PSI_API_KEY                                               #
# --------------------------------------------------------------------------- #
def test_settings_reads_psi_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSI_API_KEY", "abc123")
    assert Settings().psi_api_key == "abc123"
