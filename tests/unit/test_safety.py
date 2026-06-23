# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""SSRF guard tests (SIC doc 10 §2). DNS is injected — fully offline."""

from __future__ import annotations

import httpx
import pytest

from seryvon.crawler.safety import (
    UnsafeUrlError,
    safe_get,
    validate_url,
)


def _resolver(mapping: dict[str, list[str]]):
    """Build a deterministic resolver from host -> IPs (raises like getaddrinfo)."""

    def resolve(host: str) -> list[str]:
        if host not in mapping:
            raise OSError(f"name not resolved: {host}")
        return mapping[host]

    return resolve


PUBLIC = _resolver({"example.com": ["93.184.216.34"]})


# --------------------------------------------------------------------------- #
# validate_url — scheme / userinfo / host                                     #
# --------------------------------------------------------------------------- #
def test_public_host_passes() -> None:
    validate_url("https://example.com/path", resolver=PUBLIC)  # no raise


@pytest.mark.parametrize("scheme", ["file", "ftp", "gopher", "data"])
def test_disallowed_scheme_rejected(scheme: str) -> None:
    with pytest.raises(UnsafeUrlError, match="scheme"):
        validate_url(f"{scheme}://example.com/x", resolver=PUBLIC)


def test_userinfo_rejected() -> None:
    with pytest.raises(UnsafeUrlError, match="userinfo"):
        validate_url("https://user:pass@example.com/", resolver=PUBLIC)


def test_missing_host_rejected() -> None:
    with pytest.raises(UnsafeUrlError, match="no host"):
        validate_url("https:///path", resolver=PUBLIC)


# --------------------------------------------------------------------------- #
# validate_url — IP literals and resolved IPs                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP/Azure metadata
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://[::ffff:169.254.169.254]/",  # IPv4-mapped IPv6
        "http://0.0.0.0/",
    ],
)
def test_private_ip_literals_rejected(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_url(url, resolver=PUBLIC)


def test_metadata_hostname_rejected() -> None:
    with pytest.raises(UnsafeUrlError, match="metadata"):
        validate_url("http://metadata.google.internal/", resolver=PUBLIC)


def test_host_resolving_to_private_ip_rejected() -> None:
    # DNS rebinding shape: a public-looking name resolves to a private address.
    rebind = _resolver({"evil.example": ["127.0.0.1"]})
    with pytest.raises(UnsafeUrlError, match="non-public"):
        validate_url("http://evil.example/", resolver=rebind)


def test_unresolvable_host_rejected() -> None:
    with pytest.raises(UnsafeUrlError, match="resolve"):
        validate_url("http://nope.invalid/", resolver=PUBLIC)


def test_one_private_answer_among_public_rejected() -> None:
    mixed = _resolver({"mixed.example": ["93.184.216.34", "10.1.2.3"]})
    with pytest.raises(UnsafeUrlError):
        validate_url("http://mixed.example/", resolver=mixed)


# --------------------------------------------------------------------------- #
# safe_get — redirect handling (offline via MockTransport)                    #
# --------------------------------------------------------------------------- #
def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


@pytest.mark.asyncio
async def test_safe_get_returns_final_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    async with _client(handler) as client:
        resp, redirects = await safe_get(client, "https://example.com/", resolver=PUBLIC)
    assert resp.status_code == 200
    assert redirects == 0


@pytest.mark.asyncio
async def test_safe_get_follows_and_counts_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "https://example.com/final"})
        return httpx.Response(200, text="landed")

    async with _client(handler) as client:
        resp, redirects = await safe_get(client, "https://example.com/", resolver=PUBLIC)
    assert resp.status_code == 200
    assert redirects == 1


@pytest.mark.asyncio
async def test_safe_get_rejects_redirect_to_private_ip() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # First hop is public; it redirects to a loopback target.
        return httpx.Response(302, headers={"location": "http://127.0.0.1:6379/"})

    async with _client(handler) as client:
        with pytest.raises(UnsafeUrlError):
            await safe_get(client, "https://example.com/", resolver=PUBLIC)


@pytest.mark.asyncio
async def test_safe_get_caps_redirect_chain() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Endless self-redirect on a public host.
        return httpx.Response(302, headers={"location": "https://example.com/loop"})

    async with _client(handler) as client:
        with pytest.raises(UnsafeUrlError, match="too many redirects"):
            await safe_get(client, "https://example.com/", resolver=PUBLIC, max_redirects=3)
