# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Connecteur OpenPageRank : proxy gratuit d'autorité de domaine (0–10), BYOK.

OpenPageRank renvoie un PageRank décimal (0–10) par domaine. C'est un **proxy**
d'autorité (à documenter comme tel), pas un index de backlinks. Sans clé
(`OPR_API_KEY`), le critère `authority.opr` reste `not_measured`.

Parsing pur (`parse_openpagerank`) + fetch I/O injectable (`fetch_openpagerank`),
même patron que le connecteur PageSpeed Insights.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

OPR_ENDPOINT = "https://openpagerank.com/api/v1.0/getPageRank"


@dataclass(slots=True)
class OpenPageRankResult:
    """Autorité de domaine (0–10) ; `None` => indisponible (-> not_measured)."""

    page_rank: float | None = None


def parse_openpagerank(payload: dict[str, Any]) -> OpenPageRankResult:
    """Extrait le `page_rank_decimal` de la première entrée. Pur et déterministe."""
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
    """Interroge OpenPageRank pour `domain`. Erreur => résultat vide (ENF-03)."""
    headers = {"API-OPR": api_key}
    params = {"domains[]": domain}
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    payload: dict[str, Any] = {}
    try:
        response = await client.get(OPR_ENDPOINT, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return OpenPageRankResult()
    finally:
        if own_client:
            await client.aclose()
    return parse_openpagerank(payload)
