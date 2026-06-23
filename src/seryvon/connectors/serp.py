# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""SERP / AI Overview connector (M9, document 09).

Queries a SERP API (default: SerpAPI BYOK) for each probe query and extracts
AI Overview presence: was the target domain cited in the AI-generated answer box?

Provider abstraction:
- ``serpapi`` (default): https://serpapi.com/search.json

Parsing and aggregation are pure functions (no I/O, deterministic, fully testable
via fixture injection). Only ``fetch_serp_aio`` performs network I/O.

Decision: three probe queries per audit (branded + definitional + evaluative).
Minimum viable; a richer prompt set (reuse of M4 PromptSet) is in the backlog.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from seryvon.models.signals import AioMetrics, AioResult, AioSource

log = logging.getLogger(__name__)

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

_DEFAULT_GL = "us"  # country for Google SERP
_DEFAULT_HL = "en"  # language


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _domain_from_url(url: str) -> str:
    """Extract registrable host (without www.) from a URL."""
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.")


def _brand_from_domain(domain: str) -> str:
    """Derive a human-readable brand name from a domain (best-effort).

    ``world-models.io`` → ``world-models``; ``example.com`` → ``example``.
    """
    host = domain.removeprefix("www.")
    return host.rsplit(".", 1)[0]


def build_queries(domain: str, brand: str | None = None) -> list[str]:
    """Three probe queries: branded, definitional, evaluative."""
    b = brand or _brand_from_domain(domain)
    return [b, f"what is {b}", f"{b} review"]


def parse_serp_aio(
    payload: dict[str, Any],
    target_domain: str,
    query: str,
) -> AioResult:
    """Extract AI Overview presence for ``target_domain`` from a SerpAPI payload.

    Pure — no I/O; fully testable with a fixture dict.
    """
    aio_block = payload.get("ai_overview")
    if not aio_block or not isinstance(aio_block, dict):
        return AioResult(query=query, aio_triggered=False, target_cited=False)

    # SerpAPI uses "references" or "sources" depending on the result type.
    raw_refs: list[Any] = aio_block.get("references") or aio_block.get("sources") or []

    sources: list[AioSource] = []
    for i, ref in enumerate(raw_refs, 1):
        if not isinstance(ref, dict):
            continue
        link: str = ref.get("link") or ref.get("url") or ""
        if not link:
            continue
        ref_domain = _domain_from_url(link)
        sources.append(
            AioSource(
                url=link,
                domain=ref_domain,
                title=ref.get("title"),
                position=i,
            )
        )

    cited_source = next(
        (s for s in sources if s.domain == target_domain or target_domain in s.domain), None
    )
    return AioResult(
        query=query,
        aio_triggered=True,
        target_cited=cited_source is not None,
        target_position=cited_source.position if cited_source else None,
        sources=sources,
    )


def aggregate_aio(results: list[AioResult], provider: str = "serpapi") -> AioMetrics:
    """Aggregate per-query ``AioResult`` objects into ``AioMetrics``. Pure."""
    n = len(results)
    if n == 0:
        return AioMetrics(provider=provider)

    triggered = [r for r in results if r.aio_triggered]
    cited = [r for r in results if r.target_cited]
    positions = [r.target_position for r in cited if r.target_position is not None]

    return AioMetrics(
        presence_rate=len(cited) / n,
        trigger_rate=len(triggered) / n,
        avg_position=sum(positions) / len(positions) if positions else None,
        results=results,
        query_count=n,
        provider=provider,
    )


# ---------------------------------------------------------------------------
# I/O layer
# ---------------------------------------------------------------------------


async def _fetch_one(
    query: str,
    *,
    api_key: str,
    target_domain: str,
    gl: str,
    hl: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> AioResult:
    """Fetch a single SERP query from SerpAPI and parse the AIO block."""
    params: dict[str, str | int] = {
        "api_key": api_key,
        "engine": "google",
        "q": query,
        "gl": gl,
        "hl": hl,
        "num": 10,
    }
    t0 = time.monotonic()
    log.debug("serp fetch query=%r domain=%s", query, target_domain)
    try:
        resp = await client.get(SERPAPI_ENDPOINT, params=params, timeout=timeout)
        resp.raise_for_status()
        payload: dict[str, Any] = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(
            "serp error query=%r elapsed_ms=%d error=%s",
            query,
            int((time.monotonic() - t0) * 1000),
            exc,
        )
        return AioResult(query=query, aio_triggered=False, target_cited=False)
    elapsed = int((time.monotonic() - t0) * 1000)
    result = parse_serp_aio(payload, target_domain, query)
    log.debug(
        "serp done query=%r aio=%s cited=%s elapsed_ms=%d",
        query,
        result.aio_triggered,
        result.target_cited,
        elapsed,
    )
    return result


async def fetch_serp_aio(
    domain: str,
    *,
    api_key: str,
    provider: str = "serpapi",
    brand: str | None = None,
    queries: list[str] | None = None,
    gl: str = _DEFAULT_GL,
    hl: str = _DEFAULT_HL,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> AioMetrics | None:
    """Fetch SERP / AI Overview metrics for ``domain``.

    Returns ``None`` on a complete failure (all queries errored). Individual
    query failures degrade gracefully (counted as no AIO).
    """
    probe_queries = queries or build_queries(domain, brand)
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "Seryvon/0.1 (+https://seryvon.com/bot) python-httpx"},
        )

    t0 = time.monotonic()
    log.info(
        "serp_aio start domain=%s queries=%d provider=%s", domain, len(probe_queries), provider
    )
    try:
        tasks = [
            _fetch_one(
                q,
                api_key=api_key,
                target_domain=domain,
                gl=gl,
                hl=hl,
                timeout=timeout,
                client=client,
            )
            for q in probe_queries
        ]
        results: list[AioResult] = await asyncio.gather(*tasks)
    except Exception as exc:
        log.warning("serp_aio fatal domain=%s error=%s", domain, exc)
        return None
    finally:
        if own_client:
            await client.aclose()

    metrics = aggregate_aio(list(results), provider=provider)
    log.info(
        "serp_aio done domain=%s presence=%.2f trigger=%.2f elapsed_ms=%d",
        domain,
        metrics.presence_rate,
        metrics.trigger_rate,
        int((time.monotonic() - t0) * 1000),
    )
    return metrics
