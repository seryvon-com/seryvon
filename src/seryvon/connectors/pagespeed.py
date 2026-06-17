# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Connecteur PageSpeed Insights (Core Web Vitals + Lighthouse), BYOK gratuit.

Source des Core Web Vitals : les **données terrain CrUX** exposées par PSI dans
`loadingExperience.metrics` (LCP/CLS/INP réels). Si un site n'a pas assez de
trafic, ce bloc est absent => `core_web_vitals = None` => critères `perf.*`
`not_measured` (jamais d'estimation, document 01 §6.2). Le score Lighthouse
provient du test labo (`lighthouseResult.categories.performance.score`, 0–1).

Le parsing (`parse_pagespeed`) est pur et déterministe ; seul `fetch_pagespeed`
fait l'I/O (client httpx injectable pour les tests). Décision D4 : appel sur la
home seule, stratégie `mobile` par défaut.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
# CrUX exprime le CLS en centièmes (5 => 0.05) ; on revient à l'échelle standard.
_CLS_SCALE = 100.0


@dataclass(slots=True)
class PageSpeedResult:
    """Signaux PSI extraits ; `None` => métrique indisponible (-> not_measured)."""

    core_web_vitals: dict[str, float] | None = None
    lighthouse_performance: float | None = None


def _percentile(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key, {}).get("percentile")
    return float(value) if isinstance(value, int | float) else None


def _parse_field_metrics(loading_experience: dict[str, Any]) -> dict[str, float] | None:
    """Extrait LCP (ms), CLS (ratio) et INP (ms) des données terrain CrUX."""
    metrics = loading_experience.get("metrics", {})
    cwv: dict[str, float] = {}
    lcp = _percentile(metrics, "LARGEST_CONTENTFUL_PAINT_MS")
    if lcp is not None:
        cwv["lcp"] = lcp
    cls = _percentile(metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE")
    if cls is not None:
        cwv["cls"] = round(cls / _CLS_SCALE, 4)
    inp = _percentile(metrics, "INTERACTION_TO_NEXT_PAINT")
    if inp is not None:
        cwv["inp"] = inp
    return cwv or None


def _parse_lighthouse(lighthouse_result: dict[str, Any]) -> float | None:
    """Extrait le score de performance Lighthouse (0–1)."""
    score = lighthouse_result.get("categories", {}).get("performance", {}).get("score")
    return float(score) if isinstance(score, int | float) else None


def parse_pagespeed(payload: dict[str, Any]) -> PageSpeedResult:
    """Transforme une réponse PSI v5 en `PageSpeedResult`. Pur et déterministe."""
    return PageSpeedResult(
        core_web_vitals=_parse_field_metrics(payload.get("loadingExperience", {})),
        lighthouse_performance=_parse_lighthouse(payload.get("lighthouseResult", {})),
    )


async def fetch_pagespeed(
    url: str,
    *,
    api_key: str,
    strategy: str = "mobile",
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> PageSpeedResult:
    """Interroge PSI pour `url` et renvoie les signaux. Erreur => résultat vide.

    Dégradation gracieuse (ENF-03) : toute erreur réseau/HTTP/JSON renvoie un
    `PageSpeedResult` vide, qui se traduit en critères `perf.*` `not_measured`.
    """
    params = {"url": url, "strategy": strategy, "category": "performance", "key": api_key}
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    payload: dict[str, Any] = {}
    try:
        response = await client.get(PSI_ENDPOINT, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return PageSpeedResult()
    finally:
        if own_client:
            await client.aclose()
    return parse_pagespeed(payload)
