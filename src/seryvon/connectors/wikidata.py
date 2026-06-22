# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Wikidata connector (free, keyless) — KG presence + brand coherence.

Queries `wbsearchentities` to find a brand's entity (`aeo.kg_presence`), then
compares the site name + description against Wikidata (`aso.brand_coherence`).
Decision D12: in Phase 2 only 2 surfaces (site, Wikidata); the ">=3 surfaces"
target (LinkedIn/Crunchbase) is in the backlog. The comparison is a token-overlap
heuristic (deliberately simple).

Parsing/comparison are pure and deterministic; only `fetch_wikidata` performs I/O.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

WIKIDATA_ENDPOINT = "https://www.wikidata.org/w/api.php"
_NAME_OVERLAP_MIN = 0.5  # token overlap of the shorter name
_DESC_JACCARD_MIN = 0.1  # minimum similarity of the descriptions


@dataclass(slots=True)
class WikidataResult:
    """Most relevant Wikidata entity for a search (or none)."""

    found: bool = False
    entity_id: str | None = None
    label: str | None = None
    description: str | None = None


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def parse_wikidata(payload: dict[str, Any]) -> WikidataResult:
    """Extract the first entity from a `wbsearchentities` response. Pure."""
    results = payload.get("search")
    if isinstance(results, list) and results:
        top = results[0]
        if isinstance(top, dict) and top.get("id"):
            return WikidataResult(
                found=True,
                entity_id=str(top["id"]),
                label=_opt_str(top.get("label")),
                description=_opt_str(top.get("description")),
            )
    return WikidataResult()


def _tokens(text: str | None) -> set[str]:
    return set(re.findall(r"\w+", text.lower())) if text else set()


def brand_coherence(
    site_name: str | None, site_description: str | None, result: WikidataResult
) -> dict[str, float]:
    """Name/description coherence between the site and the Wikidata entity (2 surfaces, D12).

    Returns {"name": 0/1, "description": 0/1} (1 = coherent). Token-overlap
    heuristic.
    """
    name_a, name_b = _tokens(site_name), _tokens(result.label)
    shorter = min(len(name_a), len(name_b)) or 1
    name_ok = len(name_a & name_b) / shorter >= _NAME_OVERLAP_MIN

    desc_a, desc_b = _tokens(site_description), _tokens(result.description)
    union = len(desc_a | desc_b) or 1
    desc_ok = len(desc_a & desc_b) / union >= _DESC_JACCARD_MIN

    return {"name": 1.0 if name_ok else 0.0, "description": 1.0 if desc_ok else 0.0}


async def fetch_wikidata(
    name: str,
    *,
    language: str = "en",
    timeout: float = 15.0,
    client: httpx.AsyncClient | None = None,
) -> WikidataResult:
    """Search the Wikidata entity for a brand. Error => no entity (ENF-03)."""
    params: dict[str, str | int] = {
        "action": "wbsearchentities",
        "search": name,
        "language": language,
        "uselang": language,
        "format": "json",
        "type": "item",
        "limit": 5,
    }
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    payload: dict[str, Any] = {}
    t0 = time.monotonic()
    log.info("wikidata start name=%r", name)
    try:
        response = await client.get(WIKIDATA_ENDPOINT, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(
            "wikidata error name=%r elapsed_ms=%d error=%s",
            name,
            int((time.monotonic() - t0) * 1000),
            exc,
        )
        return WikidataResult()
    finally:
        if own_client:
            await client.aclose()
    log.info("wikidata done name=%r elapsed_ms=%d", name, int((time.monotonic() - t0) * 1000))
    return parse_wikidata(payload)
