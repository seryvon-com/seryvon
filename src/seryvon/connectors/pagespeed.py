# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""PageSpeed Insights connector (Core Web Vitals + Lighthouse), free BYOK.

Source of the Core Web Vitals: the **CrUX field data** exposed by PSI in
`loadingExperience.metrics` (real LCP/CLS/INP). If a site lacks enough traffic,
that block is absent => `core_web_vitals = None` => `perf.*` criteria
`not_measured` (never estimated, document 01 §6.2). The Lighthouse score comes
from the lab test (`lighthouseResult.categories.performance.score`, 0–1).

Parsing (`parse_pagespeed`) is pure and deterministic; only `fetch_pagespeed`
performs the I/O (injectable httpx client for tests). Decision D4: call on the
home page only, `mobile` strategy by default.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
# CrUX expresses CLS in hundredths (5 => 0.05); we convert back to the standard scale.
_CLS_SCALE = 100.0


@dataclass(slots=True)
class PageSpeedResult:
    """Extracted PSI signals; `None` => metric unavailable (-> not_measured)."""

    core_web_vitals: dict[str, float] | None = None
    lighthouse_performance: float | None = None


def _percentile(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key, {}).get("percentile")
    return float(value) if isinstance(value, int | float) else None


def _parse_field_metrics(loading_experience: dict[str, Any]) -> dict[str, float] | None:
    """Extract LCP (ms), CLS (ratio) and INP (ms) from the CrUX field data."""
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
    """Extract the Lighthouse performance score (0–1)."""
    score = lighthouse_result.get("categories", {}).get("performance", {}).get("score")
    return float(score) if isinstance(score, int | float) else None


def parse_pagespeed(payload: dict[str, Any]) -> PageSpeedResult:
    """Turn a PSI v5 response into a `PageSpeedResult`. Pure and deterministic."""
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
    """Query PSI for `url` and return the signals. Error => empty result.

    Graceful degradation (ENF-03): any network/HTTP/JSON error returns an empty
    `PageSpeedResult`, which maps to `perf.*` criteria being `not_measured`.
    """
    params = {"url": url, "strategy": strategy, "category": "performance", "key": api_key}
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    payload: dict[str, Any] = {}
    t0 = time.monotonic()
    log.info("pagespeed start url=%s strategy=%s", url, strategy)
    try:
        response = await client.get(PSI_ENDPOINT, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(
            "pagespeed error url=%s elapsed_ms=%d error=%s",
            url,
            int((time.monotonic() - t0) * 1000),
            exc,
        )
        return PageSpeedResult()
    finally:
        if own_client:
            await client.aclose()
    log.info("pagespeed done url=%s elapsed_ms=%d", url, int((time.monotonic() - t0) * 1000))
    return parse_pagespeed(payload)
