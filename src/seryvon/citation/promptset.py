# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Prompt-set generation — Voie A templates, pure and deterministic (document 08).

Derives a theme profile from the crawl signals (titles, meta descriptions, Open
Graph, structured-data types — the textual signals available today), instantiates
intent templates, filters out brand/domain-biased candidates (document 08 §4.2),
scores and balances them by intent (§6). No I/O, no LLM: same `SignalBundle` =>
same prompt set. LLM-assisted generation (Voie B) and user validation come later.

Prompt text is French (product content: the measurement instrument). Theme
extraction is bounded by the available signals; richer entity/heading extraction
would require a future M3 signals extension.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence

from seryvon.citation.aggregate import brand_mentioned, registrable_domain
from seryvon.models.prompts import Prompt, PromptIntent, PromptSet, ThemeProfile
from seryvon.models.signals import SignalBundle

_I = PromptIntent

# Single-slot intent templates (French — product). Comparative is handled apart.
_TEMPLATES: dict[PromptIntent, str] = {
    _I.DEFINITIONAL: "Qu'est-ce que {x} ?",
    _I.RECOMMENDATION: "Quels sont les meilleurs {x} ?",
    _I.EXPLANATORY: "Comment fonctionne {x} ?",
    _I.LISTING: "Quels acteurs proposent {x} ?",
    _I.USE_CASE: "Dans quels cas utiliser {x} ?",
    _I.NEWS: "Quelles sont les nouveautés en {x} ?",
}

# Target intent mix over the final set (document 08 §6). Sums to 1.0.
_DISTRIBUTION: dict[PromptIntent, float] = {
    _I.RECOMMENDATION: 0.25,
    _I.COMPARATIVE: 0.25,
    _I.LISTING: 0.15,
    _I.DEFINITIONAL: 0.12,
    _I.USE_CASE: 0.10,
    _I.EXPLANATORY: 0.08,
    _I.NEWS: 0.05,
}

# Base quality per intent: "best/compare/list" questions cite more (§5 heuristic).
_INTENT_BASE: dict[PromptIntent, float] = {
    _I.RECOMMENDATION: 0.85,
    _I.COMPARATIVE: 0.85,
    _I.LISTING: 0.80,
    _I.NEWS: 0.60,
    _I.USE_CASE: 0.60,
    _I.DEFINITIONAL: 0.55,
    _I.EXPLANATORY: 0.50,
}

_MAX_TOPICS = 12
_MAX_ENTITIES = 8
_STOPWORDS = frozenset(
    {
        "avec", "sans", "dans", "pour", "elle", "vous", "nous", "leur", "leurs", "cette",
        "votre", "notre", "plus", "tout", "tous", "toute", "sont", "etre", "avoir", "fait",
        "chez", "comme", "deux", "celui", "celle", "entre", "the", "and", "for", "with",
        "that", "this", "from", "your", "you", "our", "are", "was", "will", "can", "des",
        "les", "une", "aux", "sur",
    }
)  # fmt: skip

_TOKEN_RE = re.compile(r"[a-zà-ÿ0-9]+")
_ENTITY_RE = re.compile(r"[A-ZÀ-Ý][A-Za-zà-ÿ0-9-]+(?:\s+[A-ZÀ-Ý][A-Za-zà-ÿ0-9-]+)*")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _brand(bundle: SignalBundle) -> str | None:
    """Brand name from the home page (og:site_name, else first title segment)."""
    home = bundle.home
    if home is None:
        return None
    site_name = home.open_graph.get("og:site_name")
    if site_name and site_name.strip():
        return site_name.strip()
    if home.title:
        for sep in ("|", "—", "–", "·", ":", "-"):
            if sep in home.title:
                first = home.title.split(sep)[0].strip()
                if first:
                    return first
        return home.title.strip()
    return None


def _brand_tokens(brand: str | None, domain: str) -> set[str]:
    """Normalized individual words of the brand + domain label (anti-bias filter)."""
    label = (registrable_domain(domain) or "").split(".")[0]
    words: set[str] = set()
    for source in (brand or "", label):
        for word in re.split(r"[\s\-_]+", source):
            normalized = _normalize(word)
            if normalized:
                words.add(normalized)
    return words


def _content_type(structured_types: set[str]) -> str:
    if structured_types & {"Product", "Offer", "AggregateOffer"}:
        return "ecommerce"
    if structured_types & {"SoftwareApplication", "WebApplication"}:
        return "software"
    if structured_types & {"Article", "BlogPosting", "NewsArticle"}:
        return "editorial"
    if structured_types & {"FAQPage", "DefinedTerm", "HowTo"}:
        return "knowledge_base"
    return "general"


def _texts(bundle: SignalBundle) -> list[str]:
    """Collect the textual signals usable for theme extraction."""
    collected: list[str] = []
    for page in bundle.pages:
        for value in (
            page.title,
            page.meta_description,
            page.open_graph.get("og:title"),
            page.open_graph.get("og:description"),
        ):
            if value and value.strip():
                collected.append(value.strip())
    return collected


def extract_theme_profile(bundle: SignalBundle) -> ThemeProfile:
    """Derive a deterministic theme profile from the crawl's textual signals."""
    texts = _texts(bundle)
    brand = _brand(bundle)
    excluded = _brand_tokens(brand, bundle.domain)

    token_counts: Counter[str] = Counter()
    for text in texts:
        for token in _TOKEN_RE.findall(text.lower()):
            if len(token) >= 4 and token not in _STOPWORDS and _normalize(token) not in excluded:
                token_counts[token] += 1
    topics = [term for term, _ in sorted(token_counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    entity_counts: Counter[str] = Counter()
    for text in texts:
        for match in _ENTITY_RE.findall(text):
            candidate = match.strip()
            words = {_normalize(w) for w in candidate.split()}
            if len(candidate) >= 3 and not (words & excluded):
                entity_counts[candidate] += 1
    entities = [name for name, _ in sorted(entity_counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    structured = {t for page in bundle.pages for t in page.structured_data_types}
    return ThemeProfile(
        domain=bundle.domain,
        topics=topics[:_MAX_TOPICS],
        entities=entities[:_MAX_ENTITIES],
        content_type=_content_type(structured),
        brand=brand,
    )


def _is_biased(text: str, profile: ThemeProfile) -> bool:
    """Reject candidates naming the audited brand or domain (document 08 §4.2)."""
    if profile.brand and brand_mentioned(text, profile.brand):
        return True
    label = (registrable_domain(profile.domain) or "").split(".")[0]
    return bool(label) and brand_mentioned(text, label)


def _quality(intent: PromptIntent, slot: str) -> float:
    base = _INTENT_BASE[intent]
    bonus = 0.1 if " " in slot.strip() else 0.0  # multi-word slot = more specific
    return round(min(1.0, base + bonus), 4)


def _candidates(profile: ThemeProfile) -> dict[PromptIntent, list[Prompt]]:
    """Build deduplicated, anti-biased, scored candidates grouped by intent."""
    by_intent: dict[PromptIntent, list[Prompt]] = {intent: [] for intent in _DISTRIBUTION}
    seen: set[str] = set()

    def _add(intent: PromptIntent, text: str, slot: str) -> None:
        key = _normalize(text)
        if key in seen or _is_biased(text, profile):
            return
        seen.add(key)
        by_intent[intent].append(
            Prompt(
                text=text, intent=intent, source="template", quality_score=_quality(intent, slot)
            )
        )

    for intent, template in _TEMPLATES.items():
        for topic in profile.topics:
            _add(intent, template.format(x=topic), topic)

    # Comparative needs two distinct subjects (entities if >=2, else topics).
    subjects = profile.entities if len(profile.entities) >= 2 else profile.topics
    for i in range(len(subjects)):
        for j in range(i + 1, len(subjects)):
            _add(
                _I.COMPARATIVE, f"{subjects[i]} ou {subjects[j]} ?", f"{subjects[i]} {subjects[j]}"
            )

    for intent in by_intent:
        by_intent[intent].sort(key=lambda p: (-p.quality_score, p.text))
    return by_intent


def _balanced_select(by_intent: dict[PromptIntent, list[Prompt]], target: int) -> list[Prompt]:
    """Sample each intent cluster to the target mix, topping up with the best leftovers."""
    selected: list[Prompt] = []
    leftovers: list[Prompt] = []
    for intent, quota in _DISTRIBUTION.items():
        pool = by_intent.get(intent, [])
        take = round(quota * target)
        selected.extend(pool[:take])
        leftovers.extend(pool[take:])

    leftovers.sort(key=lambda p: (-p.quality_score, p.text))
    if len(selected) < target:
        selected.extend(leftovers[: target - len(selected)])
    else:
        selected.sort(key=lambda p: (-p.quality_score, p.text))
        selected = selected[:target]

    order = list(_DISTRIBUTION)
    selected.sort(key=lambda p: (order.index(p.intent), -p.quality_score, p.text))
    return selected


def generate_prompt_set(
    bundle: SignalBundle,
    *,
    target_size: int = 15,
    version: int = 1,
    competitors: Sequence[str] = (),
) -> PromptSet:
    """Generate a deterministic, intent-balanced prompt set from a `SignalBundle`."""
    profile = extract_theme_profile(bundle)
    prompts = _balanced_select(_candidates(profile), target_size)
    return PromptSet(
        version=version,
        domain=profile.domain,
        generated_by="templates",
        theme_profile=profile,
        prompts=prompts,
        tracked_competitors=sorted({c for c in competitors if c}),
    )
