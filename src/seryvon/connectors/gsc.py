# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Google Search Console connector (M10 Rank Tracking), free BYOK.

Adapted from OpenSEO (Ben Senescu, MIT) — gsc/searchAnalytics and
gsc/selfHostedOAuth modules. See NOTICE for the full attribution.

Authentication uses a **service account JSON** (BYOK via `GSC_SERVICE_ACCOUNT`
env variable). The user grants read-only Search Console access to the service
account email in their GSC property settings.

Parsing (`parse_gsc`) is pure and deterministic; only `fetch_gsc` performs I/O
(injectable httpx client for tests). The `_access_token` parameter lets tests
bypass the Google auth flow entirely.

Position values are always `average_position` (GSC doc constraint: never
instantaneous position). Results are sorted by ascending position (best first).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date, timedelta
from typing import Any

import httpx

from seryvon.models.signals import GscQuery, GscResult

log = logging.getLogger(__name__)

_GSC_ENDPOINT = (
    "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
)
_GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"

# "sc-domain:" properties expose domain-level aggregates; URL-prefix properties
# use the exact URL. We try both and prefer the domain property.
_SITE_TEMPLATES = ("sc-domain:{domain}", "https://{domain}/")


def _get_access_token(service_account_json: str) -> str | None:
    """Exchange a service account JSON for a short-lived access token (sync).

    Returns ``None`` on any failure (graceful degradation, ENF-03), but logs the
    cause so a misconfigured GSC connector is diagnosable instead of silently
    yielding `not_measured`. A missing `google-auth` dependency (declared in
    pyproject) is surfaced distinctly from an auth/network failure.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        log.warning(
            "gsc: google-auth is not installed — run `pip install -e '.[dev]'`"
            " or `pip install google-auth`; rank tracking stays not_measured"
        )
        return None
    try:
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            info, scopes=[_GSC_SCOPE]
        )
        creds.refresh(Request())
        return str(creds.token)
    except Exception as exc:
        log.warning("gsc: failed to obtain access token — %s", exc)
        return None


def parse_gsc(payload: dict[str, Any], *, date_range_days: int = 90) -> GscResult:
    """Parse a GSC Search Analytics response into a `GscResult` (pure)."""
    rows: list[dict[str, Any]] = payload.get("rows", [])
    queries: list[GscQuery] = []
    for row in rows:
        keys: list[str] = row.get("keys", [])
        if not keys:
            continue
        queries.append(
            GscQuery(
                query=keys[0],
                position=round(float(row.get("position", 0.0)), 1),
                clicks=int(row.get("clicks", 0)),
                impressions=int(row.get("impressions", 0)),
                ctr=round(float(row.get("ctr", 0.0)), 4),
            )
        )
    queries.sort(key=lambda q: q.position)
    total_clicks = sum(q.clicks for q in queries)
    total_impressions = sum(q.impressions for q in queries)
    avg_ctr = round(total_clicks / total_impressions, 4) if total_impressions else 0.0
    avg_position = round(sum(q.position for q in queries) / len(queries), 1) if queries else None
    return GscResult(
        queries=queries,
        total_clicks=total_clicks,
        total_impressions=total_impressions,
        avg_ctr=avg_ctr,
        avg_position=avg_position,
        date_range_days=date_range_days,
    )


async def fetch_gsc(
    domain: str,
    *,
    service_account_json: str,
    client: httpx.AsyncClient | None = None,
    date_range_days: int = 90,
    row_limit: int = 25,
    _access_token: str | None = None,
) -> GscResult:
    """Fetch GSC search analytics for a domain (graceful degradation).

    Returns an empty `GscResult` on any error (missing key, network issue,
    permission denied). Decision: never raise — dependent criteria become
    `not_measured` (ENF-03).
    """
    empty = GscResult(
        queries=[],
        total_clicks=0,
        total_impressions=0,
        avg_ctr=0.0,
        avg_position=None,
        date_range_days=date_range_days,
    )

    t0 = time.monotonic()
    log.info("gsc start domain=%s", domain)
    token = _access_token
    if token is None:
        token = await asyncio.to_thread(_get_access_token, service_account_json)
    if not token:
        log.warning(
            "gsc auth_failed domain=%s elapsed_ms=%d", domain, int((time.monotonic() - t0) * 1000)
        )
        return empty

    end_date = date.today()
    start_date = end_date - timedelta(days=date_range_days)
    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["query"],
        "rowLimit": row_limit,
        "startRow": 0,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    own_client = client is None
    active_client: httpx.AsyncClient = (
        client if client is not None else httpx.AsyncClient(timeout=30.0)
    )

    try:
        for template in _SITE_TEMPLATES:
            site_url = template.format(domain=domain)
            url = _GSC_ENDPOINT.format(site=httpx.URL(site_url))
            try:
                resp = await active_client.post(url, json=body, headers=headers)
                if resp.status_code == 200:
                    log.info(
                        "gsc done domain=%s elapsed_ms=%d",
                        domain,
                        int((time.monotonic() - t0) * 1000),
                    )
                    return parse_gsc(resp.json(), date_range_days=date_range_days)
                if resp.status_code == 403:
                    log.debug("gsc 403 site=%s trying_next", site_url)
                    continue
            except (httpx.HTTPError, ValueError) as exc:
                log.debug("gsc fetch_error site=%s error=%s", site_url, exc)
                continue
        log.info(
            "gsc no_property domain=%s elapsed_ms=%d", domain, int((time.monotonic() - t0) * 1000)
        )
        return empty
    finally:
        if own_client:
            await active_client.aclose()
