# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""HTTP page fetching (httpx async).

Phase 0: a single GET on the home page. Concurrency (semaphore), crawl-delay
compliance and Playwright rendering arrive in Phase 1 (M1/M2).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class FetchResult:
    """Raw response of a page fetch."""

    url: str
    final_url: str
    status_code: int
    html: str
    redirects: int


@dataclass(slots=True)
class FetchedResource:
    """Raw response of a non-HTML resource (robots.txt, sitemap, possibly gzip).

    Unlike `FetchResult`, the body is kept as `bytes`: sitemaps can be compressed
    (`.xml.gz`) and must be decompressed before parsing.
    """

    url: str
    final_url: str
    status_code: int
    content: bytes
    content_type: str | None = None


async def fetch_page(
    url: str,
    *,
    user_agent: str,
    timeout: float = 15.0,
) -> FetchResult:
    """Fetch a page following redirects.

    Raises `httpx.HTTPError` on a network failure; the HTTP status (including
    4xx/5xx) is, however, returned as-is so the indexability criteria can score it.
    """
    headers = {"User-Agent": user_agent}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as client:
        response = await client.get(url)
        return FetchResult(
            url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            html=response.text,
            redirects=len(response.history),
        )


async def fetch_resource(
    url: str,
    *,
    user_agent: str,
    timeout: float = 15.0,
) -> FetchedResource:
    """Fetch a raw resource (bytes) — robots.txt, sitemap, etc.

    The body is not decoded to text: sitemaps may be gzipped. The HTTP status
    (including 4xx) is returned as-is; a missing robots.txt (404) is interpreted
    by the caller as "everything allowed" (RFC 9309).
    """
    headers = {"User-Agent": user_agent}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as client:
        response = await client.get(url)
        return FetchedResource(
            url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            content=response.content,
            content_type=response.headers.get("content-type"),
        )
