# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Règles d'autorité de domaine (sous-domaine SEO « backlinks & autorité »).

- `authority.opr` : proxy d'autorité OpenPageRank (0–10 -> ×10). `not_measured`
  sans clé OPR.
- `authority.backlinks` : domaines référents, échelle log normalisée. Aucune
  source gratuite n'est câblée en v0.1 (Common Crawl en backlog) -> la règle lit
  `external.referring_domains`, qui reste `None` => `not_measured` (décision D3,
  jamais d'estimation). La règle est néanmoins prête pour un futur connecteur.
"""

from __future__ import annotations

import math
from typing import ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle

# Échelle log : ~10 000 domaines référents -> score 100 (log10(10001) ≈ 4).
_BACKLINKS_LOG_FACTOR = 25.0


@register
class AuthorityOprCriterion(Criterion):
    """Autorité de domaine via OpenPageRank (`authority.opr`) : PageRank ×10."""

    key = "authority.opr"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(self, signals: SignalBundle) -> CriterionResult:
        opr = signals.external.open_page_rank
        if opr is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "OpenPageRank non configuré (clé OPR absente)."
            )
        score = round(min(100.0, max(0.0, opr * 10)), 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"open_page_rank": opr},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "PageRank (0–10) ×10", "proxy": True},
            explanation=f"Autorité de domaine (proxy OpenPageRank) : {opr}/10.",
            evidence={"source": "OpenPageRank (proxy d'autorité)"},
            weight=self.weight,
        )


@register
class AuthorityBacklinksCriterion(Criterion):
    """Domaines référents (`authority.backlinks`), échelle log normalisée.

    `not_measured` en v0.1 : aucune source de backlinks gratuite n'est câblée
    (décision D3). La règle est prête pour un connecteur ultérieur (Common Crawl).
    """

    key = "authority.backlinks"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(self, signals: SignalBundle) -> CriterionResult:
        referring = signals.external.referring_domains
        if referring is None:
            return CriterionResult.not_measured(
                self.key,
                self.pillars,
                self.weight,
                "Aucune source de domaines référents configurée (Common Crawl à venir).",
            )
        score = round(min(100.0, math.log10(referring + 1) * _BACKLINKS_LOG_FACTOR), 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"referring_domains": referring},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "log10(domaines+1) normalisé"},
            explanation=f"{referring} domaine(s) référent(s) (échelle log).",
            evidence={"source": "source de backlinks tierce"},
            weight=self.weight,
        )
