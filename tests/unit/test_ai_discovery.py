# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the ASO probes: AI discovery (4 endpoints) + NLWeb."""

from __future__ import annotations

import httpx

from seryvon.connectors.ai_discovery import (
    probe_ai_discovery,
    probe_nlweb,
    valid_faq,
    valid_service,
    valid_summary,
)


# --------------------------------------------------------------------------- #
# Validators purs                                                             #
# --------------------------------------------------------------------------- #
def test_valid_summary() -> None:
    assert valid_summary({"name": "Acme", "description": "x" * 25}) is True
    assert valid_summary({"name": "Ac", "description": "x" * 25}) is False  # name trop court
    assert valid_summary({"name": "Acme", "description": "court"}) is False
    assert valid_summary("nope") is False


def test_valid_service() -> None:
    assert valid_service({"name": "Acme", "capabilities": ["search"]}) is True
    assert valid_service({"name": "Acme", "capabilities": []}) is False
    assert valid_service({"name": "Acme"}) is False


def test_valid_faq() -> None:
    good = [{"question": "Quelle est la question ?", "answer": "Une réponse assez longue ici."}]
    assert valid_faq(good) is True
    assert valid_faq({"faq": good}) is True  # wrapped form
    assert valid_faq([{"question": "court", "answer": "court"}]) is False
    assert valid_faq([]) is False


# --------------------------------------------------------------------------- #
# probe_ai_discovery (MockTransport)                                          #
# --------------------------------------------------------------------------- #
def _full_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/.well-known/ai.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    if path == "/ai/summary.json":
        return httpx.Response(200, json={"name": "Acme", "description": "x" * 25})
    if path == "/ai/faq.json":
        return httpx.Response(
            200, json=[{"question": "Une vraie question ?", "answer": "Une réponse assez longue."}]
        )
    if path == "/ai/service.json":
        return httpx.Response(200, json={"name": "Acme", "capabilities": ["search"]})
    return httpx.Response(404)


async def test_probe_ai_discovery_all_valid() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(_full_handler))
    result = await probe_ai_discovery("https://ex.com", client=client)
    await client.aclose()
    assert result == {"ai_txt": True, "summary": True, "faq": True, "service": True}


async def test_probe_ai_discovery_all_absent() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    result = await probe_ai_discovery("https://ex.com", client=client)
    await client.aclose()
    assert result == {"ai_txt": False, "summary": False, "faq": False, "service": False}


# --------------------------------------------------------------------------- #
# probe_nlweb (MockTransport)                                                 #
# --------------------------------------------------------------------------- #
async def test_probe_nlweb_conformant() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"@context": "https://schema.org", "results": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await probe_nlweb("https://ex.com", client=client) == "conformant"
    await client.aclose()


async def test_probe_nlweb_present_non_conformant() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok"))
    )
    assert await probe_nlweb("https://ex.com", client=client) == "present"
    await client.aclose()


async def test_probe_nlweb_absent() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    assert await probe_nlweb("https://ex.com", client=client) == "absent"
    await client.aclose()
