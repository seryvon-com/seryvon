# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the citation-run cost estimator (pure)."""

from __future__ import annotations

from seryvon.citation.cost import ModelPricing, estimate_cost


def test_single_engine_estimate() -> None:
    estimate = estimate_cost(["perplexity"], prompt_count=10, repetitions=5)
    # 50 calls × (40e-6 + 400e-6 + 0.005) = 50 × 0.00544 = 0.272 (indicative defaults).
    assert estimate.calls == 50
    assert estimate.per_engine == {"perplexity": 0.272}
    assert estimate.total == 0.272
    assert estimate.indicative is True
    assert estimate.currency == "USD"


def test_multi_engine_sums_per_engine() -> None:
    estimate = estimate_cost(["perplexity", "openai"], prompt_count=2, repetitions=1)
    assert estimate.calls == 4
    assert estimate.per_engine == {"perplexity": 0.0109, "openai": 0.0205}
    assert estimate.total == 0.0314


def test_custom_pricing_is_not_indicative() -> None:
    pricing = {"perplexity": ModelPricing(2.0, 2.0, 0.0)}
    estimate = estimate_cost(["perplexity"], 1, 1, pricing=pricing)
    assert estimate.per_engine == {"perplexity": 0.0009}
    assert estimate.indicative is False


def test_unknown_engine_skipped() -> None:
    estimate = estimate_cost(["bing"], prompt_count=5, repetitions=2)
    assert estimate.per_engine == {}
    assert estimate.total == 0.0


def test_empty_prompt_set_costs_nothing() -> None:
    estimate = estimate_cost(["perplexity"], prompt_count=0, repetitions=5)
    assert estimate.total == 0.0
    assert estimate.per_engine == {"perplexity": 0.0}
