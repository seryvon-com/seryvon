# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Citation-tracking task (IO-bound queue).

LLM calls are network-bound: high concurrency, low CPU. This task runs on the
``io`` queue so it never blocks CPU-bound crawl workers.

Return value on SUCCESS: serialized ``CitationMetrics`` dict.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from seryvon.citation.connector import LlmConnector
from seryvon.citation.engines import AnthropicConnector, GeminiConnector, OpenAiConnector
from seryvon.citation.perplexity import PerplexityConnector
from seryvon.citation.tracking import run_tracking
from seryvon.core.config import Settings
from seryvon.core.settings_resolver import resolve_settings
from seryvon.db.base import session_scope
from seryvon.models.prompts import Prompt, PromptIntent, PromptSet, ThemeProfile
from seryvon.tasks.app import celery_app

log = logging.getLogger(__name__)


def _build_connectors(settings: Settings) -> list[LlmConnector]:
    connectors: list[LlmConnector] = []
    if settings.perplexity_api_key:
        connectors.append(PerplexityConnector(api_key=settings.perplexity_api_key))
    if settings.openai_api_key:
        connectors.append(OpenAiConnector(api_key=settings.openai_api_key))
    if settings.anthropic_api_key:
        connectors.append(AnthropicConnector(api_key=settings.anthropic_api_key))
    if settings.gemini_api_key:
        connectors.append(GeminiConnector(api_key=settings.gemini_api_key))
    return connectors


def _minimal_prompt_set(domain: str, brand: str | None, competitors: list[str]) -> PromptSet:
    b = brand or domain
    prompts = [
        Prompt(text=f"What is {domain}?", intent=PromptIntent.DEFINITIONAL, quality_score=0.8),
        Prompt(text=f"Tell me about {b}", intent=PromptIntent.DEFINITIONAL, quality_score=0.7),
        Prompt(text=f"Should I use {b}?", intent=PromptIntent.RECOMMENDATION, quality_score=0.7),
        Prompt(text=f"How does {b} work?", intent=PromptIntent.EXPLANATORY, quality_score=0.7),
        Prompt(
            text=f"What are the best alternatives to {b}?",
            intent=PromptIntent.COMPARATIVE,
            quality_score=0.6,
        ),
    ]
    return PromptSet(
        domain=domain,
        generated_by="task",
        theme_profile=ThemeProfile(domain=domain, brand=b),
        prompts=prompts,
        tracked_competitors=list(competitors),
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    name="seryvon.tasks.citation.run_citation_task",
    bind=True,
    track_started=True,
    queue="io",
)
def run_citation_task(
    self: Any,
    domain: str,
    brand: str | None,
    competitors: list[str],
) -> dict[str, Any]:
    """Run LLM citation tracking and return the serialized CitationMetrics."""
    log.info("citation_task start domain=%s task_id=%s", domain, self.request.id)

    with session_scope() as session:
        settings = resolve_settings(session)

    connectors = _build_connectors(settings)
    if not connectors:
        raise ValueError("No LLM API keys configured — add them via /keys")

    prompt_set = _minimal_prompt_set(domain, brand, competitors)

    async def _run() -> Any:
        return await run_tracking(
            prompt_set,
            connectors,
            target_domain=domain,
            brand=brand,
            competitors=competitors,
            repetitions=2,
        )

    metrics = asyncio.run(_run())
    if metrics is None:
        raise ValueError("No LLM responses collected")

    log.info("citation_task done domain=%s", domain)
    result: dict[str, Any] = metrics.model_dump(mode="json")
    return result
