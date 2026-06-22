# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""GEO pillar rules (Generative Engine Optimization), document 04 §3.

GEO on-page core (Phase 2.6): `geo.ssr` (render_mode heuristic, D10),
`noise_ratio`, `entity_density`, `primary_sources`, `authors`, `cross_platform`,
`freshness`. Freshness reads `SignalBundle.audited_at` (frozen reference, DG2 ->
determinism). LLM citation (Phase 3, M4): `geo.citation_rate`, `mention_rate`,
`citation_confidence` read `external.citation_metrics` (`not_measured` without a BYOK key).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar

from seryvon.i18n import t
from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle

# GEO on-page core thresholds (document 04 §3).
_NOISE_RATIO_TARGET = 0.20
_ENTITY_DENSITY_MIN = 0.02
_ENTITY_DENSITY_MAX = 0.20
_CROSS_PLATFORM_TARGET = 4
_FRESH_DAYS = 90
_STALE_DAYS = 365


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


@register
class GeoSsrCriterion(Criterion):
    """Server-side vs client-side rendering (`geo.ssr`): share of server-rendered pages."""

    key = "geo.ssr"
    pillars: ClassVar[list[str]] = ["geo", "aeo", "aso"]
    weight = 1.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        modes = [p.render_mode for p in signals.pages if p.render_mode]
        if not modes:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.render_mode_unavailable")
            )
        ssr = sum(1 for mode in modes if mode == "ssr")
        score = round(ssr / len(modes) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(modes), "ssr": ssr},
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% SSR"},
            explanation=t("expl.ssr", ssr=ssr, total=len(modes)),
            evidence={"source": "heuristique SSR/CSR (M2)"},
            weight=self.weight,
        )


@register
class GeoNoiseRatioCriterion(Criterion):
    """Content/noise ratio (`geo.noise_ratio`): >= 0.20 = optimal."""

    key = "geo.noise_ratio"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        ratios = [p.main_text_ratio for p in signals.pages if p.main_text_ratio is not None]
        if not ratios:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.noise_ratio_unavailable")
            )
        scores = [
            100.0 if r >= _NOISE_RATIO_TARGET else round(r / _NOISE_RATIO_TARGET * 100, 2)
            for r in ratios
        ]
        score = _mean(scores)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(ratios), "mean_ratio": round(_mean(ratios) / 100, 4)},
            score=score,
            status=status_from_score(score),
            threshold={"min_ratio": _NOISE_RATIO_TARGET},
            explanation=t("expl.noise_ratio", pages=len(ratios)),
            evidence={"source": "HTML (contenu principal)"},
            weight=self.weight,
        )


@register
class GeoEntityDensityCriterion(Criterion):
    """Entity density (`geo.entity_density`): normalized over a target range (heuristic)."""

    key = "geo.entity_density"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 1.0

    def _score_page(self, entity_count: int, word_count: int) -> float:
        density = entity_count / word_count
        if density < _ENTITY_DENSITY_MIN:
            return round(density / _ENTITY_DENSITY_MIN * 100, 2)
        if density <= _ENTITY_DENSITY_MAX:
            return 100.0
        return 60.0  # too dense (likely noise/lists)

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = [p for p in signals.pages if p.word_count > 0]
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_text_content")
            )
        score = _mean([self._score_page(p.entity_count, p.word_count) for p in pages])
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages)},
            score=score,
            status=status_from_score(score),
            threshold={"min": _ENTITY_DENSITY_MIN, "max": _ENTITY_DENSITY_MAX},
            explanation=t("expl.entity_density", pages=len(pages)),
            evidence={"source": "heuristique entités (M3.3)"},
            weight=self.weight,
        )


@register
class GeoPrimarySourcesCriterion(Criterion):
    """Primary sources (`geo.primary_sources`): >=1 outbound link per page (aeo tag)."""

    key = "geo.primary_sources"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        with_sources = sum(1 for p in pages if p.external_link_domains)
        score = round(with_sources / len(pages) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages), "with_sources": with_sources},
            score=score,
            status=status_from_score(score),
            threshold={"min": "≥1 source sortante par page"},
            explanation=t("expl.primary_sources", with_sources=with_sources, total=len(pages)),
            evidence={"source": "liens sortants"},
            weight=self.weight,
        )


@register
class GeoAuthorsCriterion(Criterion):
    """Identifiable authors (`geo.authors`): presence of a structured author (aeo tag)."""

    key = "geo.authors"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        present = any(p.has_author for p in pages)
        score = 100.0 if present else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"has_author": present},
            score=score,
            status=status_from_score(score),
            threshold={"structured": "author/Person en JSON-LD"},
            explanation=t("expl.geo_authors_present") if present else t("expl.geo_authors_absent"),
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class GeoCrossPlatformCriterion(Criterion):
    """Cross-platform presence (`geo.cross_platform`): >=4 platforms = 100 (aso tag)."""

    key = "geo.cross_platform"
    pillars: ClassVar[list[str]] = ["geo", "aso"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        platforms = sorted({platform for p in pages for platform in p.social_platforms})
        score = round(min(100.0, len(platforms) / _CROSS_PLATFORM_TARGET * 100), 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"platforms": platforms},
            score=score,
            status=status_from_score(score),
            threshold={"target": _CROSS_PLATFORM_TARGET},
            explanation=t(
                "expl.cross_platform",
                count=len(platforms),
                platforms=platforms if platforms else t("word.none"),
            ),
            evidence={"source": "sameAs + liens sociaux"},
            weight=self.weight,
        )


@register
class GeoFreshnessCriterion(Criterion):
    """Freshness (`geo.freshness`): content < 90 days = optimal (aeo tag).

    Age computed against `SignalBundle.audited_at` (frozen reference, DG2 determinism).
    """

    key = "geo.freshness"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if signals.audited_at is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_audit_reference")
            )
        dates = [d for p in signals.pages if p.content_date and (d := _parse_date(p.content_date))]
        if not dates:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_content_dates")
            )
        age = (signals.audited_at.date() - max(dates)).days
        score = 100.0 if age < _FRESH_DAYS else 50.0 if age < _STALE_DAYS else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"age_days": age, "latest": max(dates).isoformat()},
            score=score,
            status=status_from_score(score),
            threshold={"fresh_days": _FRESH_DAYS},
            explanation=t("expl.freshness", age=age),
            evidence={"source": "dates JSON-LD vs date d'audit"},
            weight=self.weight,
        )


# LLM citation criteria (M4, Phase 3): read the aggregated, deterministic metrics
# from `external.citation_metrics`. Without a BYOK key => `not_measured`.


@register
class GeoCitationRateCriterion(Criterion):
    """LLM citation rate (`geo.citation_rate`): % of retrieval responses citing the domain."""

    key = "geo.citation_rate"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 2.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = round(cm.citation_rate * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"citation_rate": cm.citation_rate, "engines": cm.engines},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "% réponses retrieval citant le domaine"},
            explanation=t(
                "expl.citation_rate",
                score=score,
                prompts=cm.prompt_count,
                reps=cm.repetitions,
                engines=len(cm.engines),
            ),
            evidence={"source": "M4 citation tracking", "average_position": cm.average_position},
            weight=self.weight,
        )


@register
class GeoMentionRateCriterion(Criterion):
    """LLM mention rate (`geo.mention_rate`): % of responses mentioning the brand."""

    key = "geo.mention_rate"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = round(cm.mention_rate * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "mention_rate": cm.mention_rate,
                "knowledge_presence": cm.knowledge_presence,
            },
            score=score,
            status=status_from_score(score),
            threshold={"formula": "% réponses mentionnant la marque"},
            explanation=t("expl.mention_rate", score=score),
            evidence={"source": "M4 citation tracking"},
            weight=self.weight,
        )


@register
class GeoCitationConfidenceCriterion(Criterion):
    """Citation stability (`geo.citation_confidence`): consistency over K repetitions."""

    key = "geo.citation_confidence"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = round(cm.citation_confidence * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "citation_confidence": cm.citation_confidence,
                "repetitions": cm.repetitions,
            },
            score=score,
            status=status_from_score(score),
            threshold={"formula": "constance de citation sur K répétitions"},
            explanation=t("expl.citation_confidence", score=score, reps=cm.repetitions),
            evidence={"source": "M4 citation tracking"},
            weight=self.weight,
        )
