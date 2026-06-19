# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Citation-tracking orchestration (module M4, document 07 §13).

Sequential dispatch with exponential-backoff retry (tenacity) over each
(prompt, engine, repetition) cell. Impure: the connectors perform the network
I/O. A cell that still fails after exhausting its retries is excluded (rather
than counted as "not cited"). The collected `LlmResponse` objects are folded into
a deterministic `CitationMetrics` by the pure aggregator. The advanced
rate-limited dispatcher (document 07 §6) arrives with the multi-engine slice.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from seryvon.citation.aggregate import aggregate_citations
from seryvon.citation.connector import LlmConnector
from seryvon.models.llm import LlmResponse
from seryvon.models.prompts import PromptSet
from seryvon.models.signals import CitationMetrics

DEFAULT_REPETITIONS = 5
DEFAULT_MAX_ATTEMPTS = 4


async def _query_with_retry(
    connector: LlmConnector,
    text: str,
    *,
    prompt_id: str,
    repetition: int,
    max_attempts: int,
    client: httpx.AsyncClient | None,
) -> LlmResponse:
    """Call `connector.query` with exponential backoff + jitter on HTTP errors."""
    retrying = AsyncRetrying(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_random_exponential(multiplier=1, max=20),
        stop=stop_after_attempt(max_attempts),
        reraise=True,
    )
    result: LlmResponse = await retrying(
        connector.query,
        text,
        prompt_id=prompt_id,
        repetition=repetition,
        client=client,
    )
    return result


async def run_tracking(
    prompt_set: PromptSet,
    connectors: Sequence[LlmConnector],
    *,
    target_domain: str,
    brand: str | None = None,
    competitors: Sequence[str] = (),
    repetitions: int = DEFAULT_REPETITIONS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    client: httpx.AsyncClient | None = None,
) -> CitationMetrics | None:
    """Run the prompt set across connectors × repetitions and aggregate the metrics.

    `None` if no response was collected (every cell failed or no prompt/engine).
    Failed cells are skipped after their retries are exhausted (ENF-03).
    """
    responses: list[LlmResponse] = []
    for connector in connectors:
        for prompt in prompt_set.prompts:
            for repetition in range(1, repetitions + 1):
                try:
                    responses.append(
                        await _query_with_retry(
                            connector,
                            prompt.text,
                            prompt_id=prompt.text,
                            repetition=repetition,
                            max_attempts=max_attempts,
                            client=client,
                        )
                    )
                except httpx.HTTPError:
                    continue  # cell excluded after exhausting retries
    return aggregate_citations(
        responses,
        target_domain=target_domain,
        brand=brand,
        competitors=competitors,
        prompt_set_version=prompt_set.version,
    )
