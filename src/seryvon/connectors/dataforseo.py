# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""DataForSEO connector — domain authority (dual-endpoint strategy).

Adapted from OpenSEO (Ben Senescu, MIT) — dataforseo/core and rank-tracking
modules. See NOTICE for the full attribution.

Two endpoints are called in order of preference. Both cost $0.01/req and
require only standard credits (no $100 Backlinks API deposit needed).

1. Domain Analytics Technologies — /v3/domain_analytics/technologies/domain_technologies/live
   Returns `domain_rank` (0–1000+), a backlink-based authority score from
   DataForSEO's own link graph. Only available for established/crawled domains;
   returns null for small or new domains not yet in their index.

2. DataForSEO Labs domain_rank_overview — /v3/dataforseo_labs/google/domain_rank_overview/live
   Returns organic traffic metrics (ETV, keyword count) based on Google SERP
   data. Available for any domain with Google rankings, including small sites.
   Used as fallback when domain_analytics returns no domain_rank.

Score derivation:
  - If domain_rank is available:  open_page_rank_equivalent = min(10, rank / 100)
    (dataforseo.com ≈ 455 → 4.55/10)
  - ETV fallback:                 open_page_rank_equivalent = min(10, log10(etv+1) × 2.5)
    (etv=29 → ≈ 3.7/10 — small but ranked site)

`referring_domains` is NOT available via either endpoint — `authority.backlinks`
stays `not_measured` until a Backlinks API subscription ($100 min) is active.

Graceful degradation (ENF-03): any error returns `DataForSeoResult()` (all None).
"""

from __future__ import annotations

import base64
import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

_ENDPOINT_DOMAIN_ANALYTICS = (
    "https://api.dataforseo.com/v3/domain_analytics/technologies/domain_technologies/live"
)
_ENDPOINT_LABS = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live"

# ETV fallback scale: log10(etv+1) × 2.5 → 0–10.
# etv=1000 → ≈7.5 ; etv=29 → ≈3.7 ; etv=0 → 0.0
_ETV_SCALE = 2.5


@dataclass(slots=True)
class DataForSeoResult:
    """Combined result from Domain Analytics + Labs endpoints.

    Priority: domain_rank (backlink-based, Domain Analytics) > organic_etv (Labs).
    `open_page_rank_equivalent` returns the best available 0–10 authority proxy.
    """

    # From Domain Analytics Technologies (backlink-based, 0–1000+).
    domain_rank: int | None = None
    # From DataForSEO Labs (ETV-based fallback for small domains).
    organic_etv: float | None = None
    organic_keywords: int | None = None
    # NOT available via these endpoints — needs Backlinks API ($100 min deposit).
    referring_domains: int | None = None

    @property
    def open_page_rank_equivalent(self) -> float | None:
        """Best available authority proxy on a 0–10 scale.

        Uses domain_rank (Domain Analytics) if present, else ETV (Labs fallback).
        Returns None only when both sources are unavailable.
        """
        if self.domain_rank is not None:
            return round(min(10.0, self.domain_rank / 100), 2)
        if self.organic_etv is not None:
            return round(min(10.0, math.log10(self.organic_etv + 1) * _ETV_SCALE), 2)
        return None


def parse_dataforseo(payload: dict[str, Any]) -> DataForSeoResult:
    """Parse a DataForSEO Domain Analytics Technologies response (public alias)."""
    return DataForSeoResult(domain_rank=_parse_domain_analytics(payload))


def _parse_domain_analytics(payload: dict[str, Any]) -> int | None:
    """Extract domain_rank from a Domain Analytics Technologies response."""
    try:
        result = payload["tasks"][0]["result"][0]
        rank = result.get("domain_rank")
        return int(rank) if rank is not None else None
    except (KeyError, IndexError, TypeError):
        return None


def _parse_labs(payload: dict[str, Any]) -> tuple[float, int]:
    """Extract (organic_etv, organic_keywords) from a Labs domain_rank_overview response."""
    try:
        item = payload["tasks"][0]["result"][0]["items"][0]
        organic = item["metrics"]["organic"]
        return float(organic.get("etv") or 0.0), int(organic.get("count") or 0)
    except (KeyError, IndexError, TypeError):
        return 0.0, 0


def _dataforseo_credentials(api_key: str) -> str | None:
    """Return the base64 Basic-Auth credential string from a DataForSEO key.

    Accepts two formats:
    - ``login:password`` (raw) — encoded here.
    - Already-encoded base64 token (as shown in the DataForSEO dashboard).

    Returns ``None`` if the key is unparseable.
    """
    if ":" in api_key:
        return base64.b64encode(api_key.encode()).decode()
    try:
        decoded = base64.b64decode(api_key, validate=True).decode("utf-8")
        if ":" not in decoded:
            return None
        return api_key  # already encoded — use as-is
    except Exception:
        return None


async def fetch_dataforseo(
    domain: str,
    *,
    api_key: str,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> DataForSeoResult:
    """Query DataForSEO for domain authority using a dual-endpoint strategy.

    1. Domain Analytics Technologies → domain_rank (backlink-based, established domains).
    2. DataForSEO Labs domain_rank_overview → ETV fallback (any Google-indexed domain).

    Both calls are made if the first returns no domain_rank, ensuring coverage
    for small/new domains not yet in DataForSEO's link graph index.

    `api_key` accepts ``login:password`` (raw) or a pre-encoded base64 token.
    Any network/HTTP/parse error is caught; the other endpoint is still tried.
    """
    credentials = _dataforseo_credentials(api_key)
    if credentials is None:
        log.warning("dataforseo api_key must be 'login:password' or a base64 token — skipping")
        return DataForSeoResult()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }
    body = [{"target": domain}]

    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)

    result = DataForSeoResult()
    t0 = time.monotonic()

    try:
        # --- Step 1: Domain Analytics Technologies (backlink-based domain_rank) ---
        log.info("dataforseo domain_analytics start domain=%s", domain)
        try:
            resp = await client.post(_ENDPOINT_DOMAIN_ANALYTICS, json=body, headers=headers)
            resp.raise_for_status()
            result.domain_rank = _parse_domain_analytics(resp.json())
            log.info(
                "dataforseo domain_analytics done domain=%s domain_rank=%s",
                domain,
                result.domain_rank,
            )
        except Exception as exc:
            log.warning("dataforseo domain_analytics error domain=%s: %s", domain, exc)

        # --- Step 2: Labs domain_rank_overview (ETV fallback for small domains) ---
        # Always called: provides organic traffic data useful regardless of step 1.
        log.info("dataforseo labs start domain=%s", domain)
        try:
            resp = await client.post(_ENDPOINT_LABS, json=body, headers=headers)
            resp.raise_for_status()
            result.organic_etv, result.organic_keywords = _parse_labs(resp.json())
            log.info(
                "dataforseo labs done domain=%s etv=%s keywords=%s",
                domain,
                result.organic_etv,
                result.organic_keywords,
            )
        except Exception as exc:
            log.warning("dataforseo labs error domain=%s: %s", domain, exc)

        log.info(
            "dataforseo combined domain=%s opr_equiv=%s elapsed_ms=%d",
            domain,
            result.open_page_rank_equivalent,
            int((time.monotonic() - t0) * 1000),
        )
        return result

    finally:
        if own_client:
            await client.aclose()
