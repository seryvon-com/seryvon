# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Récupération HTTP des pages (httpx async).

Phase 0 : un seul GET sur la home. La concurrence (sémaphore), le respect du
crawl-delay et le rendu Playwright arrivent en Phase 1 (M1/M2).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class FetchResult:
    """Réponse brute d'une récupération de page."""

    url: str
    final_url: str
    status_code: int
    html: str
    redirects: int


async def fetch_page(
    url: str,
    *,
    user_agent: str,
    timeout: float = 15.0,
) -> FetchResult:
    """Récupère une page en suivant les redirections.

    Lève `httpx.HTTPError` en cas d'échec réseau ; le statut HTTP (y compris 4xx/5xx)
    est en revanche retourné tel quel pour être scoré par les critères d'indexabilité.
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
