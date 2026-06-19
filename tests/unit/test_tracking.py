# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the citation-tracking orchestration (fake connector, no network)."""

from __future__ import annotations

import httpx

from seryvon.citation.tracking import run_tracking
from seryvon.models.llm import LlmCitation, LlmResponse
from seryvon.models.prompts import Prompt, PromptIntent, PromptSet, ThemeProfile


def _prompt_set() -> PromptSet:
    return PromptSet(
        domain="example.com",
        theme_profile=ThemeProfile(domain="example.com"),
        prompts=[
            Prompt(text="p1", intent=PromptIntent.RECOMMENDATION),
            Prompt(text="p2", intent=PromptIntent.COMPARATIVE),
        ],
    )


class _FakeConnector:
    """Connector that cites example.com only for the prompt ids in `cites`."""

    provider = "perplexity"

    def __init__(self, cites: set[str]) -> None:
        self._cites = cites

    async def query(
        self,
        prompt: str,
        *,
        prompt_id: str = "",
        repetition: int = 1,
        model: str | None = None,
        web_search: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> LlmResponse:
        url = "https://example.com/" if prompt_id in self._cites else "https://rival.org/"
        return LlmResponse(
            engine=self.provider,
            model="fake",
            prompt_id=prompt_id,
            repetition=repetition,
            response_text="ok",
            citations=[LlmCitation(url=url, position=1)],
            web_search_enabled=True,
        )


class _FailingConnector:
    provider = "perplexity"

    async def query(self, prompt: str, **kwargs: object) -> LlmResponse:
        raise httpx.ConnectError("boom")


async def test_run_tracking_aggregates_metrics() -> None:
    metrics = await run_tracking(
        _prompt_set(),
        [_FakeConnector({"p1"})],
        target_domain="example.com",
        repetitions=2,
    )
    assert metrics is not None
    # 1 engine x 2 prompts x 2 reps = 4 retrieval cells; only p1 (2 cells) cites.
    assert metrics.citation_rate == 0.5
    # p1 cited 2/2 -> the only cited group -> confidence 1.0.
    assert metrics.citation_confidence == 1.0
    assert metrics.engines == ["perplexity"]
    assert metrics.repetitions == 2
    assert metrics.prompt_count == 2


async def test_run_tracking_excludes_failed_cells() -> None:
    metrics = await run_tracking(
        _prompt_set(),
        [_FailingConnector()],
        target_domain="example.com",
        repetitions=1,
        max_attempts=1,  # no retry waits -> fast
    )
    assert metrics is None  # every cell failed -> no response collected


async def test_run_tracking_empty_prompt_set() -> None:
    empty = PromptSet(domain="example.com", theme_profile=ThemeProfile(domain="example.com"))
    metrics = await run_tracking(empty, [_FakeConnector(set())], target_domain="example.com")
    assert metrics is None
