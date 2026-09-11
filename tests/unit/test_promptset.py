# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for prompt-set generation (Voie A templates, deterministic)."""

from __future__ import annotations

import unicodedata

from seryvon.citation import extract_theme_profile, generate_prompt_set
from seryvon.citation.promptset import ThemeProfile, _brand, _candidates, _content_type, _is_biased
from seryvon.models.prompts import PromptIntent
from seryvon.models.signals import PageSignals, SignalBundle


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _bundle() -> SignalBundle:
    return SignalBundle(
        domain="acme-robotics.com",
        pages=[
            PageSignals(
                url="https://acme-robotics.com/",
                title="Acme Robotics — Capteurs industriels et automatisation",
                meta_description="Solutions de capteurs pour l'automatisation industrielle.",
                structured_data_types=["Product"],
                open_graph={"og:site_name": "Acme Robotics"},
            ),
            PageSignals(
                url="https://acme-robotics.com/temperature",
                title="Capteurs de température pour la robotique industrielle",
                meta_description="Nos capteurs de température fiables pour la robotique.",
            ),
        ],
    )


def test_theme_profile_extraction() -> None:
    profile = extract_theme_profile(_bundle())
    assert profile.domain == "acme-robotics.com"
    assert profile.brand == "Acme Robotics"
    assert profile.content_type == "ecommerce"  # Product schema
    assert "capteurs" in profile.topics
    # Brand must not leak into the topics/entities.
    assert all("acme" not in _norm(t) for t in profile.topics)


def test_generate_prompt_set_basic() -> None:
    ps = generate_prompt_set(_bundle(), target_size=10)
    assert ps.domain == "acme-robotics.com"
    assert ps.generated_by == "templates"
    assert 0 < len(ps.prompts) <= 10
    # All prompts are French interrogatives from the templates.
    assert all(p.text.endswith("?") for p in ps.prompts)
    assert all(p.source == "template" for p in ps.prompts)


def test_prompts_never_mention_brand_or_domain() -> None:
    ps = generate_prompt_set(_bundle(), target_size=15)
    for prompt in ps.prompts:
        norm = _norm(prompt.text)
        assert "acme robotics" not in norm  # brand
        assert "robotics" not in norm  # domain label fragment
        assert "acme-robotics" not in norm


def test_intent_variety() -> None:
    ps = generate_prompt_set(_bundle(), target_size=15)
    intents = {p.intent for p in ps.prompts}
    # With several topics, recommendation and comparative should both appear.
    assert PromptIntent.RECOMMENDATION in intents
    assert PromptIntent.COMPARATIVE in intents


def test_generation_is_deterministic() -> None:
    first = generate_prompt_set(_bundle(), target_size=12)
    second = generate_prompt_set(_bundle(), target_size=12)
    assert first.model_dump() == second.model_dump()


def test_competitors_recorded_and_sorted() -> None:
    ps = generate_prompt_set(_bundle(), competitors=["rival.com", "", "alpha.io"])
    assert ps.tracked_competitors == ["alpha.io", "rival.com"]


def test_empty_bundle_yields_no_prompts() -> None:
    ps = generate_prompt_set(SignalBundle(domain="ex.com"))
    assert ps.prompts == []
    assert ps.theme_profile.topics == []


def test_brand_fallbacks_and_missing_home() -> None:
    assert _brand(SignalBundle(domain="ex.com")) is None
    assert (
        _brand(
            SignalBundle(
                domain="ex.com",
                pages=[PageSignals(url="https://ex.com/", title="Plain title")],
            )
        )
        == "Plain title"
    )
    assert (
        _brand(
            SignalBundle(
                domain="ex.com",
                pages=[PageSignals(url="https://ex.com/", title="Brand | Topic")],
            )
        )
        == "Brand"
    )


def test_content_type_classification() -> None:
    assert _content_type({"SoftwareApplication"}) == "software"
    assert _content_type({"Article"}) == "editorial"
    assert _content_type({"FAQPage"}) == "knowledge_base"
    assert _content_type(set()) == "general"


def test_brand_missing_title_and_candidate_filters() -> None:
    assert _brand(SignalBundle(domain="ex.com", pages=[PageSignals(url="https://ex.com/")])) is None
    profile = ThemeProfile(domain="acme.com", brand="Acme", topics=["pricing"])
    assert _is_biased("Acme pricing", profile)
    candidates = _candidates(profile.model_copy(update={"topics": ["pricing", "pricing"]}))
    texts = [prompt.text for values in candidates.values() for prompt in values]
    assert len(texts) == len({_norm(text) for text in texts})
