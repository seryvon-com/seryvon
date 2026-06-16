# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Orchestrateur d'audit.

Chaîne verticale complète (vertical slice, document 06) : M1 Discovery ->
M2 Crawl multi-pages -> extraction de signaux -> scoring 5 piliers -> rapport
JSON. L'exécution via Celery arrive plus tard ; cet orchestrateur asynchrone
reste la référence de test.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from seryvon import PILLARS, __version__
from seryvon.core.config import AuditConfig, get_settings
from seryvon.crawler import crawl_site, discover
from seryvon.models.report import AuditReport
from seryvon.models.signals import SIGNAL_SCHEMA_VERSION, SignalBundle
from seryvon.scoring import run_criteria, score_global, score_pillar


def _config_digest(config: AuditConfig) -> str:
    """Empreinte stable de la config (reproductibilité — document 05, §8)."""
    payload = json.dumps(config.model_dump(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


async def run_audit(url: str, config: AuditConfig | None = None) -> AuditReport:
    """Exécute un audit sur l'URL fournie et renvoie le rapport.

    Étapes : discovery (robots/sitemaps/frontière) -> crawl multi-pages ->
    extraction signaux -> exécution des règles -> agrégation par pilier ->
    score global -> assemblage du rapport. Un site injoignable produit un
    rapport (pages vides), jamais une exception (ENF-03).
    """
    settings = get_settings()
    config = config or AuditConfig.default()
    started = datetime.now(UTC)
    user_agent = config.crawl.user_agent or settings.user_agent

    discovery = await discover(
        url,
        user_agent=user_agent,
        timeout=settings.request_timeout,
        respect_robots=config.crawl.respect_robots,
    )
    pages = await crawl_site(
        discovery,
        user_agent=user_agent,
        max_pages=config.crawl.max_pages,
        max_depth=config.crawl.max_depth,
        respect_robots=config.crawl.respect_robots,
        timeout=settings.request_timeout,
    )
    bundle = SignalBundle(
        domain=discovery.domain,
        signal_schema_version=SIGNAL_SCHEMA_VERSION,
        pages=pages,
    )

    results = run_criteria(bundle, config)
    pillar_scores = {p: score_pillar(p, results) for p in PILLARS}
    overall = score_global(pillar_scores, config)

    return AuditReport(
        domain=bundle.domain,
        tool_version=__version__,
        schema_version=SIGNAL_SCHEMA_VERSION,
        started_at=started,
        finished_at=datetime.now(UTC),
        score_global=overall,
        pillars=pillar_scores,
        criteria=results,
        config_digest=_config_digest(config),
    )
