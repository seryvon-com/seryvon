# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Agrégateur de citation LLM — cœur pur et déterministe (document 07 §8-9).

Transforme une liste de `LlmResponse` (collectées par les connecteurs, non
déterministes) en un `CitationMetrics` figé. Aucune I/O : mêmes réponses en
entrée => mêmes métriques en sortie (frontière collecte/scoring, document 03 §9).

Formules (document 07 §9 ; l'intention prime, l'implémentation l'explicite) :
- `citation_rate`   : part des réponses *retrieval* (recherche web active) citant
  le domaine cible — la citation d'URL n'existe qu'en mode retrieval.
- `mention_rate`    : part des réponses (tous modes) mentionnant la marque.
- `citation_confidence` : pour chaque (prompt, moteur) cité au moins une fois,
  fraction de répétitions citant ; moyenne sur ces groupes (5/5 = fort, 1/5 = faible).
- `share_of_voice`  : citations du domaine / (domaine + concurrents), mode retrieval.
- `knowledge_presence` : mention de la marque en mode nu (notoriété), informatif.

Normalisation de domaine sans dépendance (eTLD+1 via une table de suffixes
composés connus) ; une PSL complète (`tldextract` hors-ligne) pourra l'affiner
dans une slice ultérieure.
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

# Suffixes publics composés courants (eTLD+1 = 3 labels au lieu de 2).
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
    """Réduit une URL ou un hôte à son domaine enregistrable (eTLD+1), en minuscules."""
    if not value:
        return None
    raw = value.strip().lower()
    if not raw:
        return None
    if "//" not in raw:
        raw = "//" + raw  # `urlsplit` n'isole le netloc qu'avec un séparateur d'autorité.
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
    """Vrai si deux domaines partagent le même domaine enregistrable (www/sous-domaines ignorés)."""
    left = registrable_domain(citation_domain)
    right = registrable_domain(target)
    return left is not None and left == right


def _normalize(text: str) -> str:
    """Casefold + suppression des accents (matching robuste casse/accents)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def brand_mentioned(text: str, brand: str) -> bool:
    """Vrai si `brand` apparaît dans `text` (insensible à la casse/aux accents, bornes de mot)."""
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
    """Agrège les `LlmResponse` en `CitationMetrics` ; `None` si la liste est vide."""
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
