# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Module M4 — LLM citation tracking (document 07).

`aggregate`: pure, deterministic core (parsing/normalization + aggregation of
`LlmResponse` objects into `CitationMetrics`). `connector`/`perplexity`: network
connectors (impure, injectable client) that feed the aggregator. OpenAI, Anthropic
and Gemini connectors come in a later slice.
"""

from seryvon.citation.aggregate import (
    aggregate_citations,
    brand_mentioned,
    domain_matches,
    registrable_domain,
)
from seryvon.citation.connector import LlmConnector
from seryvon.citation.cost import CostEstimate, estimate_cost
from seryvon.citation.perplexity import PerplexityConnector
from seryvon.citation.promptset import extract_theme_profile, generate_prompt_set
from seryvon.citation.tracking import run_tracking

__all__ = [
    "CostEstimate",
    "LlmConnector",
    "PerplexityConnector",
    "aggregate_citations",
    "brand_mentioned",
    "domain_matches",
    "estimate_cost",
    "extract_theme_profile",
    "generate_prompt_set",
    "registrable_domain",
    "run_tracking",
]
