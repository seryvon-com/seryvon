# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""OpenPageRank connector: free domain-authority proxy (0–10), BYOK.

OpenPageRank returns a decimal PageRank (0–10) per domain. It is an authority
**proxy** (to be documented as such), not a backlink index. Without a key
(`OPR_API_KEY`), the `authority.opr` criterion stays `not_measured`.

Pure parsing (`parse_openpagerank`) + injectable fetch I/O (`fetch_openpagerank`),
same pattern as the PageSpeed Insights connector.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

OPR_ENDPOINT = "https://openpagerank.com/api/v1.0/getPageRank"


@dataclass(slots=True)
class OpenPageRankResult:
    """Domain authority (0–10); `None` => unavailable (-> not_measured)."""

    page_rank: float | None = None


def parse_openpagerank(payload: dict[str, Any]) -> OpenPageRankResult:
    """Extract the `page_rank_decimal` of the first entry. Pure and deterministic."""
    response = payload.get("response")
    if isinstance(response, list) and response:
        entry = response[0]
        if isinstance(entry, dict) and entry.get("status_code") == 200:
            value = entry.get("page_rank_decimal")
            if isinstance(value, int | float):
                return OpenPageRankResult(page_rank=float(value))
    return OpenPageRankResult()


async def fetch_openpagerank(
    domain: str,
    *,
    api_key: str,
    timeout: float = 15.0,
    client: httpx.AsyncClient | None = None,
) -> OpenPageRankResult:
    """Query OpenPageRank for `domain`. Error => empty result (ENF-03)."""
    headers = {"API-OPR": api_key}
    params = {"domains[]": domain}
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    payload: dict[str, Any] = {}
    t0 = time.monotonic()
    log.info("openpagerank start domain=%s", domain)
    try:
        response = await client.get(OPR_ENDPOINT, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(
            "openpagerank error domain=%s elapsed_ms=%d error=%s",
            domain,
            int((time.monotonic() - t0) * 1000),
            exc,
        )
        return OpenPageRankResult()
    finally:
        if own_client:
            await client.aclose()
    log.info(
        "openpagerank done domain=%s elapsed_ms=%d", domain, int((time.monotonic() - t0) * 1000)
    )
    return parse_openpagerank(payload)
