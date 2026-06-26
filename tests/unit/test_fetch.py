# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the bare-bones fetch helpers (fetch_page / fetch_resource).

`safe_get` is monkey-patched here — it has its own dedicated test module. The
goal of these tests is the wrapping logic (FetchResult / FetchedResource
shapes, redirect count propagation, content-type plumbing), not SSRF.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from seryvon.crawler import fetch as fetch_mod
from seryvon.crawler.fetch import FetchedResource, FetchResult, fetch_page, fetch_resource
from seryvon.crawler.safety import UnsafeUrlError


def _fake_safe_get(response: httpx.Response, redirects: int = 0) -> Any:
    """Return a coroutine matching safe_get's signature for monkeypatching."""

    async def _impl(_client: httpx.AsyncClient, _url: str, **_kwargs: Any) -> Any:
        return response, redirects

    return _impl


async def test_fetch_page_returns_result_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(
        200,
        text="<html><title>ok</title></html>",
        request=httpx.Request("GET", "https://ex.com/final"),
    )
    monkeypatch.setattr(fetch_mod, "safe_get", _fake_safe_get(response, redirects=2))

    result = await fetch_page("https://ex.com/", user_agent="Seryvon/test", timeout=5.0)
    assert isinstance(result, FetchResult)
    assert result.url == "https://ex.com/"
    assert result.final_url == "https://ex.com/final"
    assert result.status_code == 200
    assert "<title>ok</title>" in result.html
    assert result.redirects == 2


async def test_fetch_page_preserves_4xx_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """4xx/5xx are returned as-is (indexability rules need to see them)."""
    response = httpx.Response(
        404, text="not found", request=httpx.Request("GET", "https://ex.com/missing")
    )
    monkeypatch.setattr(fetch_mod, "safe_get", _fake_safe_get(response))
    result = await fetch_page("https://ex.com/missing", user_agent="Seryvon/test")
    assert result.status_code == 404


async def test_fetch_page_propagates_unsafe_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """An SSRF-unsafe target bubbles up as httpx.HTTPError (UnsafeUrlError)."""

    async def _raise(_client: httpx.AsyncClient, _url: str, **_kwargs: Any) -> Any:
        raise UnsafeUrlError("blocked")

    monkeypatch.setattr(fetch_mod, "safe_get", _raise)
    with pytest.raises(httpx.HTTPError):
        await fetch_page("http://169.254.169.254/", user_agent="Seryvon/test")


async def test_fetch_resource_returns_bytes_and_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        content=b"\x1f\x8b\x08\x00gzipped-sitemap-bytes",
        headers={"content-type": "application/gzip"},
        request=httpx.Request("GET", "https://ex.com/sitemap.xml.gz"),
    )
    monkeypatch.setattr(fetch_mod, "safe_get", _fake_safe_get(response))

    result = await fetch_resource(
        "https://ex.com/sitemap.xml.gz", user_agent="Seryvon/test", timeout=5.0
    )
    assert isinstance(result, FetchedResource)
    assert result.content.startswith(b"\x1f\x8b\x08")  # body kept as bytes (not decoded)
    assert result.content_type == "application/gzip"
    assert result.status_code == 200


async def test_fetch_resource_missing_content_type_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200, content=b"User-agent: *", request=httpx.Request("GET", "https://ex.com/robots.txt")
    )
    monkeypatch.setattr(fetch_mod, "safe_get", _fake_safe_get(response))
    result = await fetch_resource("https://ex.com/robots.txt", user_agent="Seryvon/test")
    assert result.content_type is None


async def test_fetch_resource_preserves_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing robots.txt (404) is returned as-is — caller interprets it (RFC 9309)."""
    response = httpx.Response(
        404, content=b"", request=httpx.Request("GET", "https://ex.com/robots.txt")
    )
    monkeypatch.setattr(fetch_mod, "safe_get", _fake_safe_get(response))
    result = await fetch_resource("https://ex.com/robots.txt", user_agent="Seryvon/test")
    assert result.status_code == 404
    assert result.content == b""
