# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Contrat d'E/S des connecteurs de citation LLM (module M4, document 07 §7).

`LlmResponse` est la donnée brute produite par un connecteur (réseau, non
déterministe) pour un triplet (prompt, moteur, répétition). L'agrégateur
(`seryvon.citation.aggregate`) en dérive un `CitationMetrics` figé et
déterministe ; c'est ce dernier — et lui seul — que lisent les règles de scoring.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LlmCitation(BaseModel):
    """Une source citée par un moteur (document 07 §7)."""

    url: str | None = None
    domain: str | None = None
    title: str | None = None
    position: int | None = None  # rang dans la liste de citations


class LlmResponse(BaseModel):
    """Réponse d'un moteur LLM pour un (prompt, moteur, répétition).

    `web_search_enabled` distingue le mode *retrieval* (recherche web active →
    citation réelle) du mode *knowledge* (modèle nu → notoriété de mémoire),
    document 07 §2.
    """

    engine: str
    model: str  # variante réellement exécutée (renvoyée par l'API)
    prompt_id: str
    repetition: int
    response_text: str = ""
    citations: list[LlmCitation] = Field(default_factory=list)
    web_search_enabled: bool = False
    usage: dict[str, Any] = Field(default_factory=dict)  # tokens in/out, coût estimé
    rate_limit_snapshot: dict[str, Any] = Field(default_factory=dict)
