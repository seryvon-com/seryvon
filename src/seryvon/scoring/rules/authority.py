# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Domain-authority rules (SEO "backlinks & authority" sub-area).

- `authority.opr`: OpenPageRank authority proxy (0–10 -> ×10). `not_measured`
  without an OPR key.
- `authority.backlinks`: referring domains, normalized log scale. No free source
  is wired in v0.1 (Common Crawl in the backlog) -> the rule reads
  `external.referring_domains`, which stays `None` => `not_measured` (decision D3,
  never estimated). The rule is nonetheless ready for a future connector.
"""

from __future__ import annotations

import math
from typing import ClassVar

from seryvon.i18n import t
from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle

# Log scale: ~10,000 referring domains -> score 100 (log10(10001) ≈ 4).
_BACKLINKS_LOG_FACTOR = 25.0


@register
class AuthorityOprCriterion(Criterion):
    """Domain authority via DataForSEO backlink rank (`authority.opr`).

    Uses `domain_rank` (0–1000+) from the Domain Analytics Technologies endpoint
    (no Backlinks API subscription required, $0.01/req). Normalised to 0–10 by
    ÷100. Equivalent to OPR semantics for scoring purposes.
    """

    key = "authority.opr"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        opr = signals.external.open_page_rank
        if opr is None:
            reason = (
                t("reason.opr_no_data")
                if signals.external.dataforseo_active
                else t("reason.opr_not_configured")
            )
            return CriterionResult.not_measured(self.key, self.pillars, self.weight, reason)
        score = round(min(100.0, max(0.0, opr * 10)), 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"open_page_rank": opr},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "PageRank (0–10) ×10", "proxy": True},
            explanation=t("expl.authority_opr", opr=opr),
            evidence={"source": "OpenPageRank (proxy d'autorité)"},
            weight=self.weight,
        )


@register
class AuthorityBacklinksCriterion(Criterion):
    """Referring domains (`authority.backlinks`), normalized log scale.

    DataForSEO Labs (standard plan) does not provide referring-domain counts.
    The DataForSEO Backlinks API that does requires a separate $100 minimum
    deposit — it is not called here. This criterion stays `not_measured` until
    a free or standard-plan backlinks source is wired in.
    """

    key = "authority.backlinks"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        referring = signals.external.referring_domains
        if referring is None:
            reason = (
                t("reason.no_backlink_data")
                if signals.external.dataforseo_active
                else t("reason.no_backlink_source")
            )
            return CriterionResult.not_measured(self.key, self.pillars, self.weight, reason)
        score = round(min(100.0, math.log10(referring + 1) * _BACKLINKS_LOG_FACTOR), 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"referring_domains": referring},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "log10(domaines+1) normalisé"},
            explanation=t("expl.backlinks", count=referring),
            evidence={"source": "source de backlinks tierce"},
            weight=self.weight,
        )
