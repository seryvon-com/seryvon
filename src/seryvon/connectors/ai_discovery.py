# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Agentic discovery probes (ASO pillar) — lightweight, free fetches.

AI Discovery (adapted from `audit_ai_discovery.py`, GEO Optimizer MIT — see
NOTICE): 4 validated endpoints (HTTP 200 + JSON meeting the minimum lengths of
document 11 §4.3). NLWeb: heuristic probe of the `/ask` convention (the standard
has no universal discovery path — to be refined).

Pure, deterministic validators; only the `probe_*` functions perform I/O
(injectable httpx client for tests). Any error => invalid endpoint / NLWeb absent
(graceful degradation, ENF-03).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from seryvon.crawler.safety import Resolver, _default_resolver, safe_get

log = logging.getLogger(__name__)

AI_DISCOVERY_ENDPOINTS = 4  # ai.txt + summary + faq + service
_NLWEB_PATH = "/ask"


# --------------------------------------------------------------------------- #
# Pure validators (document 11 §4.3)                                           #
# --------------------------------------------------------------------------- #
def _str_len(value: Any) -> int:
    return len(str(value).strip()) if isinstance(value, str) else 0


def valid_summary(data: Any) -> bool:
    """`/ai/summary.json`: name >= 3 chars, description >= 20 chars."""
    return (
        isinstance(data, dict)
        and _str_len(data.get("name")) >= 3
        and _str_len(data.get("description")) >= 20
    )


def valid_service(data: Any) -> bool:
    """`/ai/service.json`: name >= 3 chars + non-empty capabilities."""
    if not isinstance(data, dict):
        return False
    caps = data.get("capabilities")
    return _str_len(data.get("name")) >= 3 and isinstance(caps, list) and len(caps) > 0


def valid_faq(data: Any) -> bool:
    """`/ai/faq.json`: non-empty list; each item question >= 10, answer >= 20."""
    items = data
    if isinstance(data, dict):
        items = data.get("faq") or data.get("questions")
    if not isinstance(items, list) or not items:
        return False
    for item in items:
        if not isinstance(item, dict):
            return False
        question = item.get("question") or item.get("q")
        answer = item.get("answer") or item.get("a")
        if _str_len(question) < 10 or _str_len(answer) < 20:
            return False
    return True


# --------------------------------------------------------------------------- #
# I/O (injectable client)                                                      #
# --------------------------------------------------------------------------- #
async def _get(
    client: httpx.AsyncClient, url: str, *, resolver: Resolver = _default_resolver
) -> httpx.Response | None:
    # Probes hit the *audited* (untrusted) origin: route every hop through the
    # SSRF guard (safe_get re-validates each redirect target before connecting).
    # The client MUST be created with follow_redirects=False (see callers).
    try:
        response, _ = await safe_get(client, url, resolver=resolver)
        return response
    except httpx.HTTPError:
        return None


def _json_200(response: httpx.Response | None) -> Any | None:
    if response is None or response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


async def probe_ai_discovery(
    origin: str,
    *,
    timeout: float = 15.0,
    client: httpx.AsyncClient | None = None,
    resolver: Resolver = _default_resolver,
) -> dict[str, bool]:
    """Probe the 4 AI discovery endpoints. Returns {key: valid}."""
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    t0 = time.monotonic()
    log.info("ai_discovery start origin=%s", origin)
    try:
        ai_txt = await _get(client, f"{origin}/.well-known/ai.txt", resolver=resolver)
        result = {
            "ai_txt": bool(ai_txt and ai_txt.status_code == 200 and ai_txt.content.strip()),
            "summary": valid_summary(
                _json_200(await _get(client, f"{origin}/ai/summary.json", resolver=resolver))
            ),
            "faq": valid_faq(
                _json_200(await _get(client, f"{origin}/ai/faq.json", resolver=resolver))
            ),
            "service": valid_service(
                _json_200(await _get(client, f"{origin}/ai/service.json", resolver=resolver))
            ),
        }
        log.info(
            "ai_discovery done origin=%s found=%s elapsed_ms=%d",
            origin,
            [k for k, v in result.items() if v],
            int((time.monotonic() - t0) * 1000),
        )
        return result
    finally:
        if own_client:
            await client.aclose()


async def probe_nlweb(
    origin: str,
    *,
    timeout: float = 15.0,
    client: httpx.AsyncClient | None = None,
    resolver: Resolver = _default_resolver,
) -> str:
    """Probe the NLWeb endpoint (`/ask`). Returns 'conformant' / 'present' / 'absent'."""
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    t0 = time.monotonic()
    log.info("nlweb start origin=%s", origin)
    try:
        response = await _get(client, f"{origin}{_NLWEB_PATH}", resolver=resolver)
    finally:
        if own_client:
            await client.aclose()
    if response is None or response.status_code != 200:
        log.info(
            "nlweb absent origin=%s elapsed_ms=%d", origin, int((time.monotonic() - t0) * 1000)
        )
        return "absent"
    data = _json_200(response)
    if isinstance(data, dict) and ("@context" in data or "results" in data):
        status = "conformant"
    else:
        status = "present"
    log.info(
        "nlweb done origin=%s status=%s elapsed_ms=%d",
        origin,
        status,
        int((time.monotonic() - t0) * 1000),
    )
    return status
