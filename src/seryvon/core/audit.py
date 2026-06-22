# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Audit orchestrator.

Full vertical chain (vertical slice, document 06): M1 Discovery -> M2 multi-page
crawl -> signal extraction -> 5-pillar scoring -> JSON report. Execution via
Celery comes later; this asynchronous orchestrator remains the test reference.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from seryvon import PILLARS, __version__
from seryvon.connectors import (
    brand_coherence,
    fetch_gsc,
    fetch_openpagerank,
    fetch_pagespeed,
    fetch_wikidata,
    probe_ai_discovery,
    probe_nlweb,
)
from seryvon.core.config import AuditConfig, Settings, get_settings
from seryvon.crawler import crawl_site, discover
from seryvon.crawler.discovery import AGENT_BOTS, blocked_agent_bots
from seryvon.i18n import set_locale
from seryvon.models.artifact import ArtifactRef, ArtifactType
from seryvon.models.report import AuditReport, MeasurementProfile
from seryvon.models.signals import (
    SIGNAL_SCHEMA_VERSION,
    ExternalSignals,
    PageSignals,
    SignalBundle,
    SiteSignals,
)
from seryvon.scoring import (
    build_issues,
    compute_aso_readiness,
    run_criteria,
    score_coverage,
    score_global,
    score_pillar,
)
from seryvon.storage import ArtifactStore


def _config_digest(config: AuditConfig) -> str:
    """Stable fingerprint of the config (reproducibility — document 05, §8)."""
    payload = json.dumps(config.model_dump(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _rule_catalog_digest() -> str:
    """Fingerprint of the registered rule set (key + class name for each rule)."""
    from seryvon.models.criterion import RULES

    catalog = sorted(f"{k}:{type(v).__name__}" for k, v in RULES.items())
    payload = json.dumps(catalog).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _build_measurement_profile(
    config: AuditConfig,
    active_connectors: list[str],
) -> MeasurementProfile:
    """Build and hash the canonical measurement profile (SIC doc 04 §6)."""
    from seryvon import __version__
    from seryvon.models.signals import SIGNAL_SCHEMA_VERSION

    fields: dict[str, object] = {
        "seryvon_version": __version__,
        "signal_schema_version": SIGNAL_SCHEMA_VERSION,
        "rule_catalog_digest": _rule_catalog_digest(),
        "pillar_weights": config.pillar_weights,
        "thresholds": config.thresholds,
        "criteria_overrides": config.criteria_overrides,
        "active_connectors": sorted(active_connectors),
    }
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return MeasurementProfile(**fields, digest=digest)


async def _collect_external(
    domain: str, pages: list[PageSignals], settings: Settings
) -> ExternalSignals:
    """Collect the external signals (PSI, OpenPageRank, GSC). BYOK: no key, no call.

    Decision D4: PageSpeed Insights on the home page only. Without a key, the
    dependent criteria stay `not_measured` (graceful degradation, ENF-03).
    """
    external = ExternalSignals()
    if settings.psi_api_key and pages:
        psi = await fetch_pagespeed(
            pages[0].url,
            api_key=settings.psi_api_key,
            strategy=settings.pagespeed_strategy,
            timeout=settings.request_timeout,
        )
        external.core_web_vitals = psi.core_web_vitals
        external.lighthouse_performance = psi.lighthouse_performance
    if settings.opr_api_key and domain:
        opr = await fetch_openpagerank(
            domain, api_key=settings.opr_api_key, timeout=settings.request_timeout
        )
        external.open_page_rank = opr.page_rank
    if settings.gsc_service_account and domain:
        external.gsc_data = await fetch_gsc(
            domain, service_account_json=settings.gsc_service_account
        )
    return external


_TITLE_SEPARATORS = ("|", "—", "–", "·", ":", "-")


def _brand_name(home: PageSignals) -> str | None:
    """Brand name for the Wikidata search (decision D11)."""
    site_name = home.open_graph.get("og:site_name")
    if site_name and site_name.strip():
        return site_name.strip()
    if home.title:
        for sep in _TITLE_SEPARATORS:
            if sep in home.title:
                first = home.title.split(sep)[0].strip()
                if first:
                    return first
        return home.title.strip()
    host = (urlsplit(home.url).hostname or "").removeprefix("www.")
    return host.split(".")[0] or None


async def _collect_brand(
    home: PageSignals | None, settings: Settings
) -> tuple[bool | None, dict[str, float] | None]:
    """Collect Wikidata: (kg_presence, brand_coherence). None if disabled/undetermined."""
    if not settings.wikidata_enabled or home is None:
        return None, None
    name = _brand_name(home)
    if not name:
        return None, None
    result = await fetch_wikidata(name, timeout=settings.request_timeout)
    if not result.found:
        return False, None
    description = home.meta_description or home.open_graph.get("og:description")
    return True, brand_coherence(name, description, result)


async def run_audit(
    url: str,
    config: AuditConfig | None = None,
    *,
    artifact_store: ArtifactStore | None = None,
    settings: Settings | None = None,
) -> AuditReport:
    """Run an audit on the given URL and return the report.

    Steps: discovery (robots/sitemaps/frontier) -> multi-page crawl -> signal
    extraction -> rule execution -> per-pillar aggregation -> global score ->
    report assembly. An unreachable site produces a report (empty pages), never an
    exception (ENF-03).

    When `artifact_store` is provided (opt-in, Observe layer C-P2), the raw HTML
    of each crawled page is stored and referenced in `report.artifacts`. This is a
    collection-side side effect: it never feeds scoring (determinism preserved).
    """
    settings = settings or get_settings()
    config = config or AuditConfig.default()
    # Locale for produced text (recommendations, explanations…); presentation only.
    set_locale(config.locale)
    started = datetime.now(UTC)
    user_agent = config.crawl.user_agent or settings.user_agent

    discovery = await discover(
        url,
        user_agent=user_agent,
        timeout=settings.request_timeout,
        respect_robots=config.crawl.respect_robots,
    )

    artifacts: list[ArtifactRef] = []
    html_sink = None
    if artifact_store is not None:
        run_id = uuid.uuid4().hex
        project_id = discovery.domain

        def html_sink(final_url: str, html: str) -> None:
            ref = artifact_store.put(
                html.encode("utf-8"),
                project_id=project_id,
                run_id=run_id,
                artifact_type=ArtifactType.HTML,
                compress=True,
            )
            artifacts.append(ref)

    pages = await crawl_site(
        discovery,
        user_agent=user_agent,
        max_pages=config.crawl.max_pages,
        max_depth=config.crawl.max_depth,
        respect_robots=config.crawl.respect_robots,
        timeout=settings.request_timeout,
        html_sink=html_sink,
    )
    active_connectors: list[str] = ["crawler"]
    external = await _collect_external(discovery.domain, pages, settings)
    if external.core_web_vitals is not None or external.lighthouse_performance is not None:
        active_connectors.append("pagespeed")
    if external.open_page_rank is not None:
        active_connectors.append("openpagerank")
    if external.gsc_data is not None and external.gsc_data.avg_position is not None:
        active_connectors.append("gsc")
    # Agentic discovery probes (free, keyless) — ASO pillar.
    external.ai_discovery_endpoints = await probe_ai_discovery(
        discovery.origin, timeout=settings.request_timeout
    )
    if external.ai_discovery_endpoints:
        active_connectors.append("ai_discovery")
    external.nlweb_status = await probe_nlweb(discovery.origin, timeout=settings.request_timeout)
    if external.nlweb_status:
        active_connectors.append("nlweb")
    external.kg_presence, external.brand_coherence = await _collect_brand(
        pages[0] if pages else None, settings
    )
    if external.kg_presence is not None:
        active_connectors.append("wikidata")
    bundle = SignalBundle(
        domain=discovery.domain,
        signal_schema_version=SIGNAL_SCHEMA_VERSION,
        audited_at=started,
        pages=pages,
        site=SiteSignals(
            robots_found=discovery.robots_found,
            crawl_delay=discovery.crawl_delay,
            sitemap_valid=discovery.sitemap_valid,
            sitemap_url_count=len(discovery.sitemap_urls),
            blocked_agent_bots=blocked_agent_bots(discovery.robots, discovery.home_url),
            agent_bots_checked=len(AGENT_BOTS),
        ),
        external=external,
    )

    results = run_criteria(bundle, config)
    pillar_scores = {p: score_pillar(p, results) for p in PILLARS}
    overall = score_global(pillar_scores, config)

    config_digest = _config_digest(config)
    measurement_profile = _build_measurement_profile(config, active_connectors)
    return AuditReport(
        domain=bundle.domain,
        tool_version=__version__,
        schema_version=SIGNAL_SCHEMA_VERSION,
        started_at=started,
        finished_at=datetime.now(UTC),
        score_global=overall,
        coverage=score_coverage(results),
        pillars=pillar_scores,
        criteria=results,
        issues=build_issues(results),
        aso_readiness=compute_aso_readiness(bundle),
        config_digest=config_digest,
        measurement_profile=measurement_profile,
        artifacts=artifacts,
    )
