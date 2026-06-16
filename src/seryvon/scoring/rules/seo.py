# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Règles de scoring du pilier SEO.

Phase 0 : un seul critère (`meta.title`) pour valider le pattern de bout en bout
(crawl -> signal -> règle -> score -> rapport). Le catalogue complet (document 04, §2)
est implémenté en Phase 1.
"""

from __future__ import annotations

from typing import ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle

# Plage recommandée pour la longueur du title (document 04, §2).
TITLE_MIN_LEN = 30
TITLE_MAX_LEN = 60


@register
class MetaTitleCriterion(Criterion):
    """Présence et longueur de la balise <title> (document 04 : `meta.title`)."""

    key = "meta.title"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.5

    def evaluate(self, signals: SignalBundle) -> CriterionResult:
        page = signals.home
        title = page.title if page else None

        if not title:
            score = 0.0
            explanation = "Balise <title> absente."
            length = 0
        else:
            length = len(title)
            if TITLE_MIN_LEN <= length <= TITLE_MAX_LEN:
                score = 100.0
                explanation = f"Title présent et de longueur optimale ({length} car.)."
            elif length < TITLE_MIN_LEN:
                score = 60.0
                explanation = (
                    f"Title court ({length} car., recommandé {TITLE_MIN_LEN}–{TITLE_MAX_LEN})."
                )
            else:
                score = 70.0
                explanation = (
                    f"Title long ({length} car., recommandé {TITLE_MIN_LEN}–{TITLE_MAX_LEN})."
                )

        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"title": title, "length": length},
            score=score,
            status=status_from_score(score),
            threshold={"min": TITLE_MIN_LEN, "max": TITLE_MAX_LEN},
            explanation=explanation,
            evidence={"source": "HTML <head> parsing"},
            weight=self.weight,
        )
