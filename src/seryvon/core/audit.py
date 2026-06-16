# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Orchestrateur d'audit.

Phase 0 : chaîne verticale minimale mais complète (vertical slice, document 06) :
discovery réduite à la home -> crawl -> extraction de signaux -> scoring 5 piliers
-> rapport JSON. Les modules M1/M2 complets et l'exécution via Celery arrivent
en Phase 1 ; cet orchestrateur synchrone reste la référence de test.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlparse

from seryvon import PILLARS, __version__
from seryvon.core.config import AuditConfig, get_settings
from seryvon.crawler import extract_page_signals, fetch_page
from seryvon.models.report import AuditReport
from seryvon.models.signals import SIGNAL_SCHEMA_VERSION, SignalBundle
from seryvon.scoring import run_criteria, score_global, score_pillar


def _config_digest(config: AuditConfig) -> str:
    """Empreinte stable de la config (reproductibilité — document 05, §8)."""
    payload = json.dumps(config.model_dump(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _domain_of(url: str) -> str:
    """Extrait le domaine (host) d'une URL."""
    return urlparse(url).netloc or url


async def run_audit(url: str, config: AuditConfig | None = None) -> AuditReport:
    """Exécute un audit Phase 0 sur l'URL fournie et renvoie le rapport.

    Étapes : fetch home -> extraction signaux -> exécution des règles ->
    agrégation par pilier -> score global -> assemblage du rapport.
    """
    settings = get_settings()
    config = config or AuditConfig.default()
    started = datetime.now(UTC)

    fetched = await fetch_page(
        url,
        user_agent=config.crawl.user_agent or settings.user_agent,
        timeout=settings.request_timeout,
    )
    page_signals = extract_page_signals(
        fetched.final_url,
        fetched.html,
        status_code=fetched.status_code,
    )
    bundle = SignalBundle(
        domain=_domain_of(fetched.final_url),
        signal_schema_version=SIGNAL_SCHEMA_VERSION,
        pages=[page_signals],
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
