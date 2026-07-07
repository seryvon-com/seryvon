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

from seryvon.models.signals import GscComparison, GscPage, GscQuery, GscResult

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
    except ImportError as exc:
        # google-auth's `requests` transport needs the `requests` package, which
        # google-auth does NOT pull in automatically — surface the real cause.
        log.warning(
            "gsc: auth dependency missing (%s) — run `pip install -e '.[dev]'`"
            " (needs google-auth + requests); rank tracking stays not_measured",
            exc,
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the (possibly missing) ``rows`` list from a GSC response."""
    rows = payload.get("rows", [])
    return rows if isinstance(rows, list) else []


def parse_gsc(payload: dict[str, Any], *, date_range_days: int = 90) -> GscResult:
    """Parse a GSC ``dimensions=[query]`` response into a `GscResult` (pure)."""
    queries: list[GscQuery] = []
    for row in _rows(payload):
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


def parse_gsc_pages(payload: dict[str, Any]) -> list[GscPage]:
    """Parse a GSC ``dimensions=[page]`` response into `GscPage` rows (pure).

    Sorted by clicks descending (most impactful pages first) so the action plan
    surfaces the pages that matter for measuring optimisation impact.
    """
    pages: list[GscPage] = []
    for row in _rows(payload):
        keys: list[str] = row.get("keys", [])
        if not keys:
            continue
        pages.append(
            GscPage(
                page=keys[0],
                position=round(float(row.get("position", 0.0)), 1),
                clicks=int(row.get("clicks", 0)),
                impressions=int(row.get("impressions", 0)),
                ctr=round(float(row.get("ctr", 0.0)), 4),
            )
        )
    pages.sort(key=lambda p: (-p.clicks, p.position))
    return pages


def _period_totals(payload: dict[str, Any]) -> tuple[int, int, float, float | None]:
    """Aggregate a ``dimensions=[query]`` response into period totals (pure).

    Returns ``(clicks, impressions, ctr, avg_position)``; ``avg_position`` is
    ``None`` when the period has no rows.
    """
    rows = _rows(payload)
    clicks = sum(int(r.get("clicks", 0)) for r in rows)
    impressions = sum(int(r.get("impressions", 0)) for r in rows)
    ctr = round(clicks / impressions, 4) if impressions else 0.0
    positions = [float(r.get("position", 0.0)) for r in rows if r.get("keys")]
    avg_position = round(sum(positions) / len(positions), 1) if positions else None
    return clicks, impressions, ctr, avg_position


def build_comparison(
    current: GscResult,
    previous_payload: dict[str, Any],
    *,
    period_days: int,
) -> GscComparison:
    """Compute before/after deltas between the current result and a prior period.

    Deltas are ``current − previous``. `position_delta` negative = improvement.
    """
    p_clicks, p_impr, p_ctr, p_pos = _period_totals(previous_payload)
    position_delta = (
        round(current.avg_position - p_pos, 1)
        if current.avg_position is not None and p_pos is not None
        else None
    )
    return GscComparison(
        previous_clicks=p_clicks,
        previous_impressions=p_impr,
        previous_ctr=p_ctr,
        previous_avg_position=p_pos,
        clicks_delta=current.total_clicks - p_clicks,
        impressions_delta=current.total_impressions - p_impr,
        ctr_delta=round(current.avg_ctr - p_ctr, 4),
        position_delta=position_delta,
        period_days=period_days,
    )


def _query_body(
    *,
    start_date: date,
    end_date: date,
    dimensions: list[str],
    row_limit: int,
    start_row: int,
) -> dict[str, Any]:
    return {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "startRow": start_row,
    }


async def _query(
    client: httpx.AsyncClient,
    url: str,
    *,
    start_date: date,
    end_date: date,
    dimensions: list[str],
    headers: dict[str, str],
    row_limit: int,
    max_rows: int,
) -> dict[str, Any] | None:
    """Run a (paginated) Search Analytics query on a resolved property.

    Follows ``startRow`` pagination until a short page is returned or ``max_rows``
    is reached. Returns a merged ``{"rows": [...]}`` payload, or ``None`` on
    HTTP/parse failure (caller degrades gracefully).
    """
    merged: list[dict[str, Any]] = []
    start_row = 0
    while start_row < max_rows:
        page_limit = min(row_limit, max_rows - start_row)
        body = _query_body(
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions,
            row_limit=page_limit,
            start_row=start_row,
        )
        try:
            resp = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            log.debug("gsc query_error dims=%s error=%s", dimensions, exc)
            return None
        if resp.status_code != 200:
            log.debug("gsc query_status=%d dims=%s", resp.status_code, dimensions)
            return None
        try:
            rows = _rows(resp.json())
        except ValueError as exc:
            log.debug("gsc parse_error dims=%s error=%s", dimensions, exc)
            return None
        merged.extend(rows)
        if len(rows) < page_limit:
            break
        start_row += page_limit
    return {"rows": merged}


async def _resolve_site(
    client: httpx.AsyncClient,
    domain: str,
    *,
    start_date: date,
    end_date: date,
    headers: dict[str, str],
) -> str | None:
    """Probe the candidate site templates and return the first accessible URL."""
    probe_body = _query_body(
        start_date=start_date,
        end_date=end_date,
        dimensions=["query"],
        row_limit=1,
        start_row=0,
    )
    for template in _SITE_TEMPLATES:
        site_url = template.format(domain=domain)
        url = _GSC_ENDPOINT.format(site=httpx.URL(site_url))
        try:
            resp = await client.post(url, json=probe_body, headers=headers)
        except httpx.HTTPError as exc:
            log.debug("gsc resolve_error site=%s error=%s", site_url, exc)
            continue
        if resp.status_code == 200:
            return url
        log.debug("gsc resolve_status=%d site=%s trying_next", resp.status_code, site_url)
    return None


async def fetch_gsc(
    domain: str,
    *,
    service_account_json: str,
    client: httpx.AsyncClient | None = None,
    date_range_days: int = 90,
    row_limit: int = 100,
    max_rows: int = 1000,
    include_pages: bool = True,
    compare: bool = True,
    _access_token: str | None = None,
) -> GscResult:
    """Fetch GSC search analytics for a domain (graceful degradation).

    Beyond the ``dimensions=[query]`` snapshot, optionally fetches a
    ``dimensions=[page]`` breakdown (`include_pages`) to attribute traffic to
    individual pages, and a same-length **previous** period (`compare`) to
    measure the impact of the action plan (before/after deltas). Both are
    additive and never affect scoring.

    Returns an empty `GscResult` on any error (missing key, network issue,
    permission denied). Decision: never raise — dependent criteria become
    `not_measured` (ENF-03).
    """
    empty = GscResult(avg_position=None, date_range_days=date_range_days)

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
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    own_client = client is None
    active_client: httpx.AsyncClient = (
        client if client is not None else httpx.AsyncClient(timeout=30.0)
    )

    try:
        url = await _resolve_site(
            active_client, domain, start_date=start_date, end_date=end_date, headers=headers
        )
        if url is None:
            log.info(
                "gsc no_property domain=%s elapsed_ms=%d",
                domain,
                int((time.monotonic() - t0) * 1000),
            )
            return empty

        query_payload = await _query(
            active_client,
            url,
            start_date=start_date,
            end_date=end_date,
            dimensions=["query"],
            headers=headers,
            row_limit=row_limit,
            max_rows=max_rows,
        )
        if query_payload is None:
            return empty
        result = parse_gsc(query_payload, date_range_days=date_range_days)

        pages: list[GscPage] = []
        if include_pages:
            page_payload = await _query(
                active_client,
                url,
                start_date=start_date,
                end_date=end_date,
                dimensions=["page"],
                headers=headers,
                row_limit=row_limit,
                max_rows=max_rows,
            )
            if page_payload is not None:
                pages = parse_gsc_pages(page_payload)

        comparison: GscComparison | None = None
        if compare and result.avg_position is not None:
            prev_end = start_date
            prev_start = prev_end - timedelta(days=date_range_days)
            prev_payload = await _query(
                active_client,
                url,
                start_date=prev_start,
                end_date=prev_end,
                dimensions=["query"],
                headers=headers,
                row_limit=row_limit,
                max_rows=max_rows,
            )
            if prev_payload is not None:
                comparison = build_comparison(result, prev_payload, period_days=date_range_days)

        log.info(
            "gsc done domain=%s queries=%d pages=%d compared=%s elapsed_ms=%d",
            domain,
            len(result.queries),
            len(pages),
            comparison is not None,
            int((time.monotonic() - t0) * 1000),
        )
        return result.model_copy(update={"pages": pages, "comparison": comparison})
    finally:
        if own_client:
            await active_client.aclose()
