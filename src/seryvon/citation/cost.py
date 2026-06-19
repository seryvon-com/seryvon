# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Cost estimator for a citation run — pure (module M4, document 07 §10).

Estimates the spend of a tracking run BEFORE sending anything (`--dry-run`),
since the budget consumed is the user's. The default price table is **indicative**
(rough 2026 placeholders, USD) and meant to be overridden — pass a custom mapping
to `estimate_cost`. No I/O: a function of (engines, prompt count, repetitions, prices).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ModelPricing:
    """Per-engine pricing: USD per 1M input/output tokens + a per-request fee."""

    input_per_1m: float
    output_per_1m: float
    per_request: float = 0.0  # web-search / per-call fee


# INDICATIVE 2026 placeholders (USD) — NOT authoritative. Override before relying
# on the figures (pass `pricing=` / load from config).
DEFAULT_PRICING: dict[str, ModelPricing] = {
    "perplexity": ModelPricing(1.0, 1.0, 0.005),
    "openai": ModelPricing(0.15, 0.60, 0.01),
    "anthropic": ModelPricing(0.80, 4.0, 0.01),
    "gemini": ModelPricing(0.075, 0.30, 0.0),
}

# Rough per-call token assumptions (a short prompt, a medium grounded answer).
DEFAULT_TOKENS_IN = 40
DEFAULT_TOKENS_OUT = 400


class CostEstimate(BaseModel):
    """Estimated cost of a run (indicative when the default price table is used)."""

    currency: str = "USD"
    total: float = 0.0
    calls: int = 0
    per_engine: dict[str, float] = Field(default_factory=dict)
    indicative: bool = True


def estimate_cost(
    engines: Sequence[str],
    prompt_count: int,
    repetitions: int,
    *,
    pricing: Mapping[str, ModelPricing] | None = None,
    tokens_in: int = DEFAULT_TOKENS_IN,
    tokens_out: int = DEFAULT_TOKENS_OUT,
) -> CostEstimate:
    """Estimate the cost of querying `engines` for `prompt_count × repetitions` calls each."""
    table = DEFAULT_PRICING if pricing is None else pricing
    calls_per_engine = prompt_count * repetitions
    per_engine: dict[str, float] = {}
    total = 0.0
    for engine in engines:
        price = table.get(engine)
        if price is None:
            continue
        unit = (
            tokens_in / 1_000_000 * price.input_per_1m
            + tokens_out / 1_000_000 * price.output_per_1m
            + price.per_request
        )
        cost = calls_per_engine * unit
        per_engine[engine] = round(cost, 4)
        total += cost
    return CostEstimate(
        total=round(total, 4),
        calls=calls_per_engine * len(engines),
        per_engine=per_engine,
        indicative=pricing is None,
    )
