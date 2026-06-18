# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Sondes de découverte agentique (pilier ASO) — fetchs légers, gratuits.

AI Discovery (transposé d'`audit_ai_discovery.py`, GEO Optimizer MIT — voir
NOTICE) : 4 endpoints validés (HTTP 200 + JSON conforme aux longueurs minimales
du document 11 §4.3). NLWeb : sonde heuristique de la convention `/ask`
(le standard n'a pas de chemin de découverte universel — à raffiner).

Validators purs et déterministes ; seuls les `probe_*` font de l'I/O (client
httpx injectable pour les tests). Toute erreur => endpoint invalide / NLWeb absent
(dégradation gracieuse, ENF-03).
"""

from __future__ import annotations

from typing import Any

import httpx

AI_DISCOVERY_ENDPOINTS = 4  # ai.txt + summary + faq + service
_NLWEB_PATH = "/ask"


# --------------------------------------------------------------------------- #
# Validators purs (document 11 §4.3)                                           #
# --------------------------------------------------------------------------- #
def _str_len(value: Any) -> int:
    return len(str(value).strip()) if isinstance(value, str) else 0


def valid_summary(data: Any) -> bool:
    """`/ai/summary.json` : name ≥ 3 car., description ≥ 20 car."""
    return (
        isinstance(data, dict)
        and _str_len(data.get("name")) >= 3
        and _str_len(data.get("description")) >= 20
    )


def valid_service(data: Any) -> bool:
    """`/ai/service.json` : name ≥ 3 car. + capabilities non vide."""
    if not isinstance(data, dict):
        return False
    caps = data.get("capabilities")
    return _str_len(data.get("name")) >= 3 and isinstance(caps, list) and len(caps) > 0


def valid_faq(data: Any) -> bool:
    """`/ai/faq.json` : liste non vide ; chaque item question ≥ 10, answer ≥ 20."""
    items = data
    if isinstance(data, dict):
        items = data.get("faq") or data.get("questions")
    if not isinstance(items, list) or not items:
        return False
    for item in items:
        if not isinstance(item, dict):
            return False
        question = item.get("question") or item.get("q")
        answer = item.get("answer") or item.get("a")
        if _str_len(question) < 10 or _str_len(answer) < 20:
            return False
    return True


# --------------------------------------------------------------------------- #
# I/O (client injectable)                                                      #
# --------------------------------------------------------------------------- #
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    try:
        return await client.get(url)
    except httpx.HTTPError:
        return None


def _json_200(response: httpx.Response | None) -> Any | None:
    if response is None or response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


async def probe_ai_discovery(
    origin: str,
    *,
    timeout: float = 15.0,
    client: httpx.AsyncClient | None = None,
) -> dict[str, bool]:
    """Sonde les 4 endpoints de découverte IA. Renvoie {clé: valide}."""
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        ai_txt = await _get(client, f"{origin}/.well-known/ai.txt")
        return {
            "ai_txt": bool(ai_txt and ai_txt.status_code == 200 and ai_txt.content.strip()),
            "summary": valid_summary(_json_200(await _get(client, f"{origin}/ai/summary.json"))),
            "faq": valid_faq(_json_200(await _get(client, f"{origin}/ai/faq.json"))),
            "service": valid_service(_json_200(await _get(client, f"{origin}/ai/service.json"))),
        }
    finally:
        if own_client:
            await client.aclose()


async def probe_nlweb(
    origin: str,
    *,
    timeout: float = 15.0,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Sonde l'endpoint NLWeb (`/ask`). Renvoie 'conformant' / 'present' / 'absent'."""
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        response = await _get(client, f"{origin}{_NLWEB_PATH}")
    finally:
        if own_client:
            await client.aclose()
    if response is None or response.status_code != 200:
        return "absent"
    data = _json_200(response)
    if isinstance(data, dict) and ("@context" in data or "results" in data):
        return "conformant"
    return "present"
