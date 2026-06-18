# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Connecteur Wikidata (gratuit, sans clé) — présence KG + brand coherence.

Interroge `wbsearchentities` pour trouver l'entité d'une marque (`aeo.kg_presence`)
puis compare nom + description site vs Wikidata (`aso.brand_coherence`). Décision
D12 : en Phase 2 seules 2 surfaces (site, Wikidata) ; la cible « ≥3 surfaces »
(LinkedIn/Crunchbase) est en backlog. La comparaison est une heuristique de
recouvrement de tokens (volontairement simple).

Parsing/comparaison purs et déterministes ; seul `fetch_wikidata` fait l'I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

WIKIDATA_ENDPOINT = "https://www.wikidata.org/w/api.php"
_NAME_OVERLAP_MIN = 0.5  # recouvrement de tokens du nom le plus court
_DESC_JACCARD_MIN = 0.1  # similarité minimale des descriptions


@dataclass(slots=True)
class WikidataResult:
    """Entité Wikidata la plus pertinente pour une recherche (ou aucune)."""

    found: bool = False
    entity_id: str | None = None
    label: str | None = None
    description: str | None = None


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def parse_wikidata(payload: dict[str, Any]) -> WikidataResult:
    """Extrait la première entité d'une réponse `wbsearchentities`. Pur."""
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
    """Cohérence nom/description entre le site et l'entité Wikidata (2 surfaces, D12).

    Renvoie {"name": 0/1, "description": 0/1} (1 = cohérent). Heuristique de
    recouvrement de tokens.
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
    """Recherche l'entité Wikidata d'une marque. Erreur => aucune entité (ENF-03)."""
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
    try:
        response = await client.get(WIKIDATA_ENDPOINT, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return WikidataResult()
    finally:
        if own_client:
            await client.aclose()
    return parse_wikidata(payload)
