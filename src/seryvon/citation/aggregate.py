# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""LLM citation aggregator — pure, deterministic core (document 07 §8-9).

Turns a list of `LlmResponse` (collected by the connectors, non-deterministic)
into a frozen `CitationMetrics`. No I/O: the same responses in => the same
metrics out (collection/scoring boundary, document 03 §9).

Formulas (document 07 §9; intent is authoritative, the implementation makes it explicit):
- `citation_rate`   : share of *retrieval* responses (web search active) citing
  the target domain — URL citation only exists in retrieval mode.
- `mention_rate`    : share of responses (all modes) mentioning the brand.
- `citation_confidence` : for each (prompt, engine) cited at least once, the
  fraction of repetitions citing; averaged over those groups (5/5 = strong, 1/5 = weak).
- `share_of_voice`  : domain citations / (domain + competitors), retrieval mode.
- `knowledge_presence` : brand mention in bare mode (awareness), informational.

Dependency-free domain normalization (eTLD+1 via a table of known compound
suffixes); a full PSL (`tldextract` offline) may refine it in a later slice.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from seryvon.models.llm import LlmCitation, LlmResponse
from seryvon.models.signals import CitationMetrics, EngineCitationMetrics

# Common compound public suffixes (eTLD+1 = 3 labels instead of 2).
_COMPOUND_SUFFIXES = frozenset(
    {
        "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk", "ltd.uk", "plc.uk",
        "com.au", "net.au", "org.au", "edu.au", "gov.au", "id.au",
        "co.nz", "net.nz", "org.nz", "govt.nz",
        "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp",
        "com.br", "net.br", "org.br", "gov.br",
        "co.in", "net.in", "org.in", "gen.in", "firm.in",
        "com.cn", "net.cn", "org.cn", "gov.cn",
        "co.za", "org.za", "gov.za",
        "com.mx", "com.ar", "com.tr", "com.sg", "com.hk", "com.tw",
        "co.kr", "or.kr",
    }
)  # fmt: skip


def registrable_domain(value: str | None) -> str | None:
    """Reduce a URL or host to its registrable domain (eTLD+1), lowercased."""
    if not value:
        return None
    raw = value.strip().lower()
    if not raw:
        return None
    if "//" not in raw:
        raw = "//" + raw  # `urlsplit` only isolates the netloc with an authority separator.
    host = urlsplit(raw).netloc
    host = host.rsplit("@", 1)[-1].split(":", 1)[0].strip(".")
    if not host:
        return None
    host = host.removeprefix("www.")
    labels = host.split(".")
    if len(labels) <= 2:
        return host or None
    if ".".join(labels[-2:]) in _COMPOUND_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def domain_matches(citation_domain: str | None, target: str) -> bool:
    """True if both domains share the same registrable domain (www/subdomains ignored)."""
    left = registrable_domain(citation_domain)
    right = registrable_domain(target)
    return left is not None and left == right


def _normalize(text: str) -> str:
    """Casefold + strip accents (robust case/accent-insensitive matching)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def brand_mentioned(text: str, brand: str) -> bool:
    """True if `brand` appears in `text` (case/accent-insensitive, word boundaries)."""
    if not text or not brand:
        return False
    needle = _normalize(brand).strip()
    if not needle:
        return False
    haystack = _normalize(text)
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _citation_domain(citation: LlmCitation) -> str | None:
    return registrable_domain(citation.domain) or registrable_domain(citation.url)


def _cites(response: LlmResponse, target: str | None) -> bool:
    return target is not None and any(_citation_domain(c) == target for c in response.citations)


def _best_position(response: LlmResponse, target: str | None) -> int | None:
    if target is None:
        return None
    ranks = [
        c.position
        for c in response.citations
        if c.position is not None and _citation_domain(c) == target
    ]
    return min(ranks) if ranks else None


def _ratio(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


@dataclass(frozen=True)
class _Metrics:
    citation_rate: float
    mention_rate: float
    citation_confidence: float
    share_of_voice: float | None
    knowledge_presence: float | None
    average_position: float | None


def _compute(
    responses: list[LlmResponse],
    target: str | None,
    brand: str | None,
    competitors: frozenset[str],
) -> _Metrics:
    retrieval = [r for r in responses if r.web_search_enabled]
    knowledge = [r for r in responses if not r.web_search_enabled]
    cited_flags = [_cites(r, target) for r in retrieval]

    citation_rate = _ratio(sum(cited_flags), len(retrieval))
    mention_rate = _ratio(
        sum(1 for r in responses if brand and brand_mentioned(r.response_text, brand)),
        len(responses),
    )
    knowledge_presence = (
        _ratio(
            sum(1 for r in knowledge if brand and brand_mentioned(r.response_text, brand)),
            len(knowledge),
        )
        if knowledge
        else None
    )

    # For each (prompt, engine) retrieval group cited at least once, fraction of
    # repetitions citing; averaged over those groups (5/5 strong, 1/5 weak).
    groups: defaultdict[tuple[str, str], list[bool]] = defaultdict(list)
    for response, cited in zip(retrieval, cited_flags, strict=True):
        groups[(response.prompt_id, response.engine)].append(cited)
    cited_fracs = [sum(g) / len(g) for g in groups.values() if any(g)]
    citation_confidence = round(sum(cited_fracs) / len(cited_fracs), 4) if cited_fracs else 0.0

    target_hits = 0
    competitor_hits = 0
    for response in retrieval:
        for citation in response.citations:
            cdom = _citation_domain(citation)
            if cdom is None:
                continue
            if target is not None and cdom == target:
                target_hits += 1
            elif cdom in competitors:
                competitor_hits += 1
    sov_denom = target_hits + competitor_hits
    share_of_voice = round(target_hits / sov_denom, 4) if sov_denom else None

    positions = [pos for r in retrieval if (pos := _best_position(r, target)) is not None]
    average_position = round(sum(positions) / len(positions), 2) if positions else None

    return _Metrics(
        citation_rate=citation_rate,
        mention_rate=mention_rate,
        citation_confidence=citation_confidence,
        share_of_voice=share_of_voice,
        knowledge_presence=knowledge_presence,
        average_position=average_position,
    )


def aggregate_citations(
    responses: list[LlmResponse],
    *,
    target_domain: str,
    brand: str | None = None,
    competitors: Sequence[str] = (),
    prompt_set_version: int | None = None,
) -> CitationMetrics | None:
    """Aggregate the `LlmResponse` list into `CitationMetrics`; `None` if the list is empty."""
    if not responses:
        return None

    target = registrable_domain(target_domain)
    brand_name = brand or (target.split(".")[0] if target else None)
    competitor_domains = frozenset(
        dom for c in competitors if (dom := registrable_domain(c)) is not None
    )

    overall = _compute(responses, target, brand_name, competitor_domains)

    engines = sorted({r.engine for r in responses})
    per_engine: dict[str, EngineCitationMetrics] = {}
    for engine in engines:
        metrics = _compute(
            [r for r in responses if r.engine == engine], target, brand_name, competitor_domains
        )
        per_engine[engine] = EngineCitationMetrics(
            citation_rate=metrics.citation_rate,
            mention_rate=metrics.mention_rate,
            citation_confidence=metrics.citation_confidence,
            average_position=metrics.average_position,
        )

    group_sizes: defaultdict[tuple[str, str], int] = defaultdict(int)
    for response in responses:
        group_sizes[(response.prompt_id, response.engine)] += 1

    return CitationMetrics(
        citation_rate=overall.citation_rate,
        mention_rate=overall.mention_rate,
        citation_confidence=overall.citation_confidence,
        share_of_voice=overall.share_of_voice,
        knowledge_presence=overall.knowledge_presence,
        average_position=overall.average_position,
        per_engine=per_engine,
        engines=engines,
        prompt_count=len({r.prompt_id for r in responses}),
        repetitions=max(group_sizes.values(), default=0),
        prompt_set_version=prompt_set_version,
    )
