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
    """Extracted PSI signals; `None` => metric unavailable (-> not_measured).

    `error_reason` carries a human-readable diagnostic when the call failed or
    returned no usable data (presentation only — never read by scoring).
    """

    core_web_vitals: dict[str, float] | None = None
    lighthouse_performance: float | None = None
    error_reason: str | None = None


def _classify_http_error(exc: httpx.HTTPStatusError) -> str:
    """Turn a PSI HTTP error into a precise, actionable reason."""
    body_excerpt = ""
    try:
        payload = exc.response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message", "")
        details = error.get("details", [])
        reasons = {d.get("reason") for d in details if isinstance(d, dict) and d.get("reason")}
        quota_zero = any(
            isinstance(d, dict) and str(d.get("metadata", {}).get("quota_limit_value")) == "0"
            for d in details
        )
        if "RATE_LIMIT_EXCEEDED" in reasons or quota_zero:
            if quota_zero:
                return (
                    "PageSpeed Insights API quota is 0 — enable the API in Google "
                    "Cloud Console (APIs & Services → Library → PageSpeed Insights API) "
                    "and check that the daily quota is not set to 0."
                )
            return "PageSpeed Insights API rate limit exceeded — retry later or raise the quota."
        body_excerpt = f" — {message}" if message else ""
    except (ValueError, KeyError, AttributeError):
        body_excerpt = ""
    status = exc.response.status_code
    if status in (401, 403):
        return f"PageSpeed Insights rejected the API key (HTTP {status}){body_excerpt}."
    return f"PageSpeed Insights request failed (HTTP {status}){body_excerpt}."


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
    except httpx.HTTPStatusError as exc:
        reason = _classify_http_error(exc)
        log.warning(
            "pagespeed http error url=%s elapsed_ms=%d status=%d reason=%s body=%s",
            url,
            int((time.monotonic() - t0) * 1000),
            exc.response.status_code,
            reason,
            exc.response.text[:500],
        )
        return PageSpeedResult(error_reason=reason)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(
            "pagespeed error url=%s elapsed_ms=%d error=%s",
            url,
            int((time.monotonic() - t0) * 1000),
            exc,
        )
        return PageSpeedResult(error_reason=f"PageSpeed Insights unreachable: {exc}")
    finally:
        if own_client:
            await client.aclose()
    log.info("pagespeed done url=%s elapsed_ms=%d", url, int((time.monotonic() - t0) * 1000))
    result = parse_pagespeed(payload)
    # A 200 with no Lighthouse score usually means the lab run was throttled or
    # the page failed to load — surface the runtime error if PSI provided one.
    if result.lighthouse_performance is None:
        runtime = payload.get("lighthouseResult", {}).get("runtimeError", {})
        message = runtime.get("message") if isinstance(runtime, dict) else None
        result.error_reason = (
            f"PageSpeed returned no Lighthouse score: {message}"
            if message
            else "PageSpeed returned no Lighthouse score (lab run unavailable or quota throttled)."
        )
    return result
