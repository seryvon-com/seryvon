# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the LLM citation aggregator (parser + metrics + determinism)."""

from __future__ import annotations

from seryvon.citation import (
    aggregate_citations,
    brand_mentioned,
    domain_matches,
    registrable_domain,
)
from seryvon.models.llm import LlmCitation, LlmResponse


def test_registrable_domain_variants() -> None:
    assert registrable_domain("https://www.example.com/page?q=1") == "example.com"
    assert registrable_domain("blog.example.com") == "example.com"
    assert registrable_domain("EXAMPLE.COM") == "example.com"
    assert registrable_domain("https://shop.example.co.uk/") == "example.co.uk"
    assert registrable_domain("example.com") == "example.com"
    assert registrable_domain("") is None
    assert registrable_domain("   ") is None
    assert registrable_domain("//") is None  # empty host after parsing
    assert registrable_domain(None) is None


def test_domain_matches() -> None:
    assert domain_matches("https://www.example.com/x", "example.com")
    assert domain_matches("blog.example.com", "https://example.com")
    assert not domain_matches("rival.com", "example.com")
    assert not domain_matches(None, "example.com")


def test_brand_mentioned_case_and_accents() -> None:
    assert brand_mentioned("On adore Séryvon ici", "seryvon")
    assert brand_mentioned("see Example.com today", "Example")
    assert not brand_mentioned("a rival product", "Example")
    assert not brand_mentioned("examples are useful", "Example")  # borne de mot
    assert not brand_mentioned("", "Example")
    assert not brand_mentioned("du texte", "   ")  # brand empty after normalization


def _cit(ref: str, position: int | None = None) -> LlmCitation:
    """Citation by URL if `ref` looks like a URL, otherwise by domain."""
    if "/" in ref or ref.startswith("http"):
        return LlmCitation(url=ref, position=position)
    return LlmCitation(domain=ref, position=position)


def _resp(
    engine: str,
    prompt: str,
    rep: int,
    *,
    web: bool,
    text: str = "",
    citations: list[LlmCitation] | None = None,
) -> LlmResponse:
    return LlmResponse(
        engine=engine,
        model=f"{engine}-model",
        prompt_id=prompt,
        repetition=rep,
        response_text=text,
        web_search_enabled=web,
        citations=citations or [],
    )


def _scenario() -> list[LlmResponse]:
    return [
        _resp(
            "perplexity", "p1", 1, web=True, text="Example is great",
            citations=[_cit("https://www.example.com/page", 1), _cit("rival.com", 2)],
        ),
        _resp("perplexity", "p1", 2, web=True, text="Rival wins", citations=[_cit("rival.com", 1)]),
        _resp(
            "perplexity", "p2", 1, web=True, text="see Example.com",
            citations=[_cit("example.com", 1)],
        ),
        _resp(
            "perplexity", "p2", 2, web=True, text="Example again",
            citations=[_cit("example.com", 2)],
        ),
        _resp("openai", "p1", 1, web=False, text="Example is a known site"),
    ]  # fmt: skip


def test_aggregate_empty_returns_none() -> None:
    assert aggregate_citations([], target_domain="example.com") is None


def test_aggregate_overall_metrics() -> None:
    metrics = aggregate_citations(
        _scenario(), target_domain="example.com", brand="Example", competitors=["rival.com"]
    )
    assert metrics is not None
    assert metrics.citation_rate == 0.75  # 3/4 retrieval responses cite example.com
    assert metrics.mention_rate == 0.8  # 4/5 responses mention the brand
    assert metrics.knowledge_presence == 1.0  # 1/1 bare-mode response mentions the brand
    assert metrics.citation_confidence == 0.75  # mean (0.5, 1.0) of the cited groups
    assert metrics.share_of_voice == 0.6  # 3 citations cible / 5 (cible + concurrent)
    assert metrics.average_position == 1.33  # positions 1, 1, 2
    assert metrics.engines == ["openai", "perplexity"]
    assert metrics.prompt_count == 2
    assert metrics.repetitions == 2


def test_aggregate_per_engine_breakdown() -> None:
    metrics = aggregate_citations(_scenario(), target_domain="example.com", brand="Example")
    assert metrics is not None
    perplexity = metrics.per_engine["perplexity"]
    assert perplexity.citation_rate == 0.75
    assert perplexity.average_position == 1.33
    openai = metrics.per_engine["openai"]
    assert openai.citation_rate == 0.0  # no retrieval response
    assert openai.mention_rate == 1.0


def test_aggregate_is_deterministic() -> None:
    first = aggregate_citations(_scenario(), target_domain="example.com", brand="Example")
    second = aggregate_citations(_scenario(), target_domain="example.com", brand="Example")
    assert first is not None and second is not None
    assert first.model_dump() == second.model_dump()


def test_aggregate_target_never_cited() -> None:
    responses = [_resp("perplexity", "p1", 1, web=True, citations=[_cit("rival.com", 1)])]
    metrics = aggregate_citations(responses, target_domain="example.com")
    assert metrics is not None
    assert metrics.citation_rate == 0.0
    assert metrics.citation_confidence == 0.0
    assert metrics.average_position is None
    assert metrics.share_of_voice is None  # no competitor declared


def test_aggregate_invalid_target_and_empty_citation() -> None:
    # Empty target => target None; a citation without url/domain is ignored.
    responses = [
        _resp("perplexity", "p1", 1, web=True, citations=[LlmCitation(), _cit("rival.com", 1)])
    ]
    metrics = aggregate_citations(responses, target_domain="", competitors=["rival.com"])
    assert metrics is not None
    assert metrics.citation_rate == 0.0
    assert metrics.average_position is None
    assert metrics.share_of_voice == 0.0  # 0 citation cible / 1 (concurrent seul)
